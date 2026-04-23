#!/usr/bin/env python3
"""
Daily Pipeline — Runs both GEO discovery and research briefing sequentially.

This is the single entry point scheduled by launchd/cron at 7:00 AM ET.
"""

import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()


def run_script(name: str) -> bool:
    """Run a Python script and report status."""
    script = SCRIPT_DIR / name
    print(f"\n{'=' * 50}")
    print(f"Running {name}...")
    print('=' * 50)
    result = subprocess.run([sys.executable, str(script)], cwd=SCRIPT_DIR)
    if result.returncode != 0:
        print(f"⚠️  {name} exited with code {result.returncode}")
        return False
    print(f"✅ {name} completed.")
    return True


def main():
    print("🚀 MadTech Growth — Daily Pipeline")
    print(f"Working directory: {SCRIPT_DIR}")

    # 1. Research briefing (lightweight, runs first)
    run_script("research_agent.py")

    # 2. GEO discovery (heavier, runs second)
    run_script("geo_orchestrator.py")

    print("\n🏁 Daily pipeline complete.")


if __name__ == "__main__":
    main()
