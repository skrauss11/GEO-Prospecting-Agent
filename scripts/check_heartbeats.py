#!/usr/bin/env python3
"""
check_heartbeats.py — watchdog for cron jobs wrapped with @cron_job.

Reads data/cron_heartbeat.json and posts a Discord alert if any job hasn't
succeeded within 1.25× its expected interval. Run on its own Hermes cron
(suggested: every 6 hours).

Run: python3 scripts/check_heartbeats.py
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.cron_wrapper import _HEARTBEAT_FILE, _post_alert  # type: ignore

STALENESS_MULTIPLIER = 1.25


def _parse_iso(s: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(s)
    except (TypeError, ValueError):
        return None


def main() -> int:
    if not _HEARTBEAT_FILE.exists():
        print("[check_heartbeats] no heartbeat file yet — nothing to check")
        return 0

    state = json.loads(_HEARTBEAT_FILE.read_text())
    now = datetime.now(timezone.utc)
    stale: List[str] = []

    for name, hb in state.items():
        interval_h = float(hb.get("expected_interval_hours", 24))
        threshold_h = interval_h * STALENESS_MULTIPLIER

        last_success = _parse_iso(hb.get("last_success", ""))
        if last_success is None:
            stale.append(f"• `{name}` — has never recorded a successful run")
            continue

        age_h = (now - last_success).total_seconds() / 3600
        if age_h > threshold_h:
            last_status = hb.get("last_status", "?")
            last_err = hb.get("last_error") or "—"
            stale.append(
                f"• `{name}` — last success {age_h:.1f}h ago "
                f"(threshold {threshold_h:.1f}h) · status={last_status} · err={last_err}"
            )

    if not stale:
        print(f"[check_heartbeats] all {len(state)} jobs healthy")
        return 0

    print(f"[check_heartbeats] {len(stale)} stale job(s):")
    for line in stale:
        print(f"  {line}")

    _post_alert(
        title=f"Watchdog: {len(stale)} stale cron job(s)",
        body="\n".join(stale),
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
