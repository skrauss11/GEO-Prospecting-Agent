#!/usr/bin/env python3
"""
Schedule the GEO Orchestrator to run daily at 7am ET.

Supports macOS launchd (native) and provides cron instructions as fallback.

Usage:
    python schedule_daily.py --install     # install the daily 7am schedule
    python schedule_daily.py --uninstall   # remove the schedule
    python schedule_daily.py --status      # check if scheduled
    python schedule_daily.py --cron        # print cron command instead
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

PLIST_NAME = "com.madtechgrowth.geo-orchestrator"
PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{PLIST_NAME}.plist"

# Resolve paths relative to this script
SCRIPT_DIR = Path(__file__).parent.resolve()
GEO_SCRIPT = SCRIPT_DIR / "geo_orchestrator.py"
LOG_FILE = SCRIPT_DIR / "geo_orchestrator.log"
ERR_LOG_FILE = SCRIPT_DIR / "geo_orchestrator_error.log"


def find_python() -> str:
    """Find the Python interpreter to use."""
    # Prefer the Python that's running this script
    return sys.executable


def generate_plist() -> str:
    """Generate the launchd plist XML."""
    python = find_python()

    # Build the environment variables section from current env
    env_vars = {}
    for key in ["NOUS_API_KEY", "DISCORD_WEBHOOK_URL", "NOUS_BASE_URL", "AIRTABLE_TOKEN", "AIRTABLE_BASE_ID", "AIRTABLE_TABLE_NAME"]:
        val = os.environ.get(key)
        if val:
            env_vars[key] = val

    env_section = ""
    if env_vars:
        env_entries = "\n".join(
            f"            <key>{k}</key>\n            <string>{v}</string>"
            for k, v in env_vars.items()
        )
        env_section = f"""
        <key>EnvironmentVariables</key>
        <dict>
{env_entries}
        </dict>"""

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{PLIST_NAME}</string>

    <key>ProgramArguments</key>
    <array>
        <string>{python}</string>
        <string>{GEO_SCRIPT}</string>
    </array>

    <key>WorkingDirectory</key>
    <string>{SCRIPT_DIR}</string>

    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>7</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
{env_section}

    <key>StandardOutPath</key>
    <string>{LOG_FILE}</string>

    <key>StandardErrorPath</key>
    <string>{ERR_LOG_FILE}</string>

    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
"""


def install():
    """Install the launchd plist and load it."""
    # Ensure LaunchAgents directory exists
    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Check required env vars
    # Load from .env file as fallback so we can inject them into the plist
    dotenv_path = SCRIPT_DIR / ".env"
    if dotenv_path.exists():
        from dotenv import dotenv_values
        env_from_dotenv = dotenv_values(str(dotenv_path))
        for key, val in env_from_dotenv.items():
            if val and key not in os.environ:
                os.environ[key] = val

    missing = []
    for key in ["NOUS_API_KEY", "DISCORD_WEBHOOK_URL", "AIRTABLE_TOKEN", "AIRTABLE_BASE_ID"]:
        if not os.environ.get(key):
            missing.append(key)

    if missing:
        print(f"⚠️  Warning: These env vars are not currently set: {', '.join(missing)}")
        print("   The scheduled job will need them. Set them in your .env file")
        print("   or shell profile before the job runs.\n")

    # Write plist
    plist_content = generate_plist()
    PLIST_PATH.write_text(plist_content)
    print(f"✅ Plist written to: {PLIST_PATH}")

    # Load it
    subprocess.run(["launchctl", "unload", str(PLIST_PATH)],
                    capture_output=True)  # unload first if exists
    result = subprocess.run(["launchctl", "load", str(PLIST_PATH)],
                            capture_output=True, text=True)
    if result.returncode == 0:
        print("✅ Scheduled! GEO Orchestrator will run daily at 7:00 AM ET.")
        print(f"   Logs: {LOG_FILE}")
        print(f"   Errors: {ERR_LOG_FILE}")
    else:
        print(f"❌ Failed to load: {result.stderr}")


def uninstall():
    """Unload and remove the launchd plist."""
    if PLIST_PATH.exists():
        subprocess.run(["launchctl", "unload", str(PLIST_PATH)],
                        capture_output=True)
        PLIST_PATH.unlink()
        print("✅ Schedule removed.")
    else:
        print("ℹ️  No schedule found — nothing to remove.")


def status():
    """Check if the job is currently loaded."""
    result = subprocess.run(
        ["launchctl", "list"],
        capture_output=True, text=True,
    )
    if PLIST_NAME in result.stdout:
        print(f"✅ GEO Orchestrator is scheduled (job: {PLIST_NAME})")
        # Get more detail
        detail = subprocess.run(
            ["launchctl", "list", PLIST_NAME],
            capture_output=True, text=True,
        )
        if detail.returncode == 0:
            print(detail.stdout)
    else:
        print("❌ GEO Orchestrator is NOT currently scheduled.")
        if PLIST_PATH.exists():
            print(f"   Plist exists at {PLIST_PATH} but is not loaded.")
            print("   Run: python schedule_daily.py --install")


def print_cron():
    """Print the equivalent cron command."""
    python = find_python()
    print("Add this to your crontab (run `crontab -e`):\n")
    print(f"0 7 * * * cd {SCRIPT_DIR} && {python} {GEO_SCRIPT} >> {LOG_FILE} 2>&1")
    print()
    print("Make sure your environment variables are available to cron.")
    print("You can add them at the top of your crontab:")
    print("  NOUS_API_KEY=***")
    print("  DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...")
    print("  NOUS_BASE_URL=https://gateway.nous.uno/v1")
    print("  AIRTABLE_TOKEN=***")
    print("  AIRTABLE_BASE_ID=***")


def main():
    parser = argparse.ArgumentParser(
        description="Schedule the GEO Orchestrator to run daily at 9am"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--install", action="store_true", help="Install the daily schedule")
    group.add_argument("--uninstall", action="store_true", help="Remove the schedule")
    group.add_argument("--status", action="store_true", help="Check schedule status")
    group.add_argument("--cron", action="store_true", help="Print cron command instead")
    args = parser.parse_args()

    if args.install:
        install()
    elif args.uninstall:
        uninstall()
    elif args.status:
        status()
    elif args.cron:
        print_cron()


if __name__ == "__main__":
    main()
