#!/usr/bin/env python3
"""
Docker healthcheck for the vessel-monitor service.

Healthy when the scheduler heartbeat is fresh (the process is alive and its
scheduler loop is running) and the most recent check did not end in ERROR.
Independent of the check schedule, so weekly time-based schedules work too.

Exit codes: 0 healthy, 1 unhealthy.
"""
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAX_HEARTBEAT_AGE = timedelta(minutes=15)


def main() -> int:
    raw_dir = os.getenv("MONITOR_STATE_DIR", "").strip()
    state_dir = Path(raw_dir) if raw_dir else PROJECT_ROOT / "monitor"
    if not state_dir.is_absolute():
        state_dir = PROJECT_ROOT / state_dir

    heartbeat_file = state_dir / "heartbeat"
    health_file = state_dir / "health_status.txt"

    try:
        beat = datetime.fromisoformat(heartbeat_file.read_text(encoding="utf-8").strip())
    except (OSError, ValueError) as exc:
        print(f"Heartbeat unreadable: {exc}", file=sys.stderr)
        return 1

    age = datetime.now(timezone.utc) - beat
    if age > MAX_HEARTBEAT_AGE:
        print(f"Heartbeat is stale: {age.total_seconds() / 60:.1f} minutes old", file=sys.stderr)
        return 1

    if health_file.exists():
        try:
            lines = health_file.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            print(f"Health file unreadable: {exc}", file=sys.stderr)
            return 1
        if lines and lines[0].startswith("ERROR"):
            message = next((l[len("ERROR_MSG: "):] for l in lines if l.startswith("ERROR_MSG: ")), "")
            print(f"Last check failed: {message or 'no message'}", file=sys.stderr)
            return 1

    print(f"Healthy (heartbeat {age.total_seconds() / 60:.1f} minutes ago)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
