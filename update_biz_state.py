#!/usr/bin/env python3
"""
Update business state from actual activities.
Run this after completing key actions (sending snapshots, booking calls, etc.)
or schedule as a daily aggregation cron job.
"""

import json
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from shared.cron_wrapper import cron_job

BIZ_STATE_PATH = Path.home() / "Desktop" / "ScottOS" / "Business State" / "biz_state.json"
CRON_OUTPUTS_DIR = Path.home() / "Desktop" / "ScottOS" / "Cron Outputs"

def load_state():
    with open(BIZ_STATE_PATH) as f:
        return json.load(f)

def save_state(state):
    state["generated_at"] = str(date.today())
    with open(BIZ_STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)

def parse_last_snapshot():
    """Check cron outputs to infer when last snapshot was sent."""
    files = sorted(CRON_OUTPUTS_DIR.glob("geo_content_brief_*.md"))
    if files:
        latest = files[-1]
        mtime = datetime.fromtimestamp(latest.stat().st_mtime).date()
        return mtime.isoformat()
    return None

@cron_job("update_biz_state", expected_interval_hours=72)
def main():
    state = load_state()
    
    # Update last snapshot sent
    last_snapshot = parse_last_snapshot()
    if last_snapshot:
        state["last_snapshot_sent"] = last_snapshot
        last = date.fromisoformat(last_snapshot)
        days_ago = (date.today() - last).days
        if days_ago > 7:
            state["pipeline_health"] = "critical"
        elif days_ago > 3:
            state["pipeline_health"] = "stalled"
        elif days_ago <= 3:
            state["pipeline_health"] = "active"
    
    save_state(state)
    print(f"Business state updated: {BIZ_STATE_PATH}")
    print(json.dumps(state, indent=2))

if __name__ == "__main__":
    main()
