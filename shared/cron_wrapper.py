"""
Cron wrapper — failure alerting + heartbeat tracking for Hermes cron jobs.

Wraps a cron entrypoint so that:
  1. Unhandled exceptions get posted to Discord (with traceback) instead of
     dying silently in cron logs.
  2. Each run writes a heartbeat to data/cron_heartbeat.json so a separate
     watchdog can detect "this job hasn't succeeded in N hours".

Usage:
    from shared.cron_wrapper import cron_job

    @cron_job("geo_daily_briefing", expected_interval_hours=24)
    def main():
        ...

    if __name__ == "__main__":
        main()
"""

import json
import socket
import sys
import traceback
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path

import httpx

from shared.config import DISCORD_DM_WEBHOOK_URL

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_HEARTBEAT_FILE = _PROJECT_ROOT / "data" / "cron_heartbeat.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read_heartbeats() -> dict:
    if not _HEARTBEAT_FILE.exists():
        return {}
    try:
        return json.loads(_HEARTBEAT_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _write_heartbeat(job_name: str, payload: dict) -> None:
    _HEARTBEAT_FILE.parent.mkdir(parents=True, exist_ok=True)
    state = _read_heartbeats()
    state[job_name] = {**state.get(job_name, {}), **payload}
    _HEARTBEAT_FILE.write_text(json.dumps(state, indent=2, sort_keys=True))


def _post_alert(title: str, body: str) -> None:
    if not DISCORD_DM_WEBHOOK_URL:
        print(f"[cron_wrapper] no alert webhook configured; alert dropped: {title}", flush=True)
        return
    content = f"🚨 **{title}**\n```\n{body[:1800]}\n```"
    try:
        resp = httpx.post(
            DISCORD_DM_WEBHOOK_URL,
            json={"content": content, "username": "GEO Agent — Alerts"},
            timeout=15,
        )
        if resp.status_code not in (200, 204):
            print(f"[cron_wrapper] alert post failed: {resp.status_code} {resp.text[:200]}", flush=True)
    except Exception as e:
        print(f"[cron_wrapper] alert post error: {e}", flush=True)


def cron_job(name: str, expected_interval_hours: float = 24.0):
    """
    Decorator that adds failure alerting + heartbeat tracking to a cron entrypoint.

    Args:
        name: Stable identifier for the job. Used as the heartbeat key.
        expected_interval_hours: How often this job is expected to run. The
            watchdog uses 1.25× this value as the staleness threshold.
    """

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            started = _now_iso()
            host = socket.gethostname()
            _write_heartbeat(name, {
                "last_attempt": started,
                "last_status": "running",
                "expected_interval_hours": expected_interval_hours,
                "host": host,
            })
            try:
                result = fn(*args, **kwargs)
            except SystemExit:
                raise
            except BaseException as e:
                tb = traceback.format_exc()
                _write_heartbeat(name, {
                    "last_status": "error",
                    "last_error": f"{type(e).__name__}: {e}",
                    "last_error_at": _now_iso(),
                })
                _post_alert(
                    title=f"Cron failure: {name}",
                    body=f"host: {host}\nstarted: {started}\n\n{tb}",
                )
                raise
            _write_heartbeat(name, {
                "last_success": _now_iso(),
                "last_status": "ok",
                "last_error": None,
            })
            return result

        return wrapper

    return decorator
