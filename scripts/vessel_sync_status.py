#!/usr/bin/env python3
"""
vessel_sync_status.py

Parse bridge.log and report the last successful sync and elapsed time
since last successful sync for each vessel.

Usage (run from the project root):
    python scripts/vessel_sync_status.py
    python scripts/vessel_sync_status.py --log /path/to/bridge.log
    python scripts/vessel_sync_status.py --json
    python scripts/vessel_sync_status.py --errors
    python scripts/vessel_sync_status.py --vessel mountfu
"""

import re
import sys
import json
import argparse
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict

# Log line format (no container prefix in the file on disk):
#   YYYY-MM-DD HH:MM:SS | LEVEL    | source.py:N  | message...
#
# Using search() rather than match() so the pattern is found anywhere in the
# line — keeps this robust if the logging config ever adds a prefix.
LOG_LINE_RE = re.compile(
    r"(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s*\|\s*"
    r"(?P<level>\w+)\s*\|\s*"
    r"(?P<source>\S+)\s*\|\s*"
    r"(?P<message>.+)$"
)

SUCCESS_RE = re.compile(r"Successfully synced vessel (\w+)")
FAILURE_RE = re.compile(r"Failed to sync vessel (\w+)\s*\|\s*error=(.+)")

TIMESTAMP_FMT = "%Y-%m-%d %H:%M:%S"


def parse_log(log_path: Path, vessel_filter: str | None = None) -> dict:
    """
    Scan log_path line-by-line, tracking the most recent successful and
    failed sync event for each vessel.

    Returns a mapping of vessel_name -> state dict.
    """
    state: dict = defaultdict(lambda: {
        "last_success": None,
        "last_failure": None,
        "last_failure_error": None,
    })

    with open(log_path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = LOG_LINE_RE.search(line.rstrip())
            if not m:
                continue

            try:
                ts = datetime.strptime(m.group("timestamp").strip(), TIMESTAMP_FMT)
            except ValueError:
                continue

            message = m.group("message").strip()

            s = SUCCESS_RE.search(message)
            if s:
                vessel = s.group(1)
                if vessel_filter and vessel != vessel_filter:
                    continue
                entry = state[vessel]
                if entry["last_success"] is None or ts > entry["last_success"]:
                    entry["last_success"] = ts
                continue

            f = FAILURE_RE.search(message)
            if f:
                vessel, error = f.group(1), f.group(2).strip()
                if vessel_filter and vessel != vessel_filter:
                    continue
                entry = state[vessel]
                if entry["last_failure"] is None or ts > entry["last_failure"]:
                    entry["last_failure"] = ts
                    entry["last_failure_error"] = error

    return dict(state)


def elapsed(dt: datetime, now: datetime) -> str:
    """Return a human-readable elapsed time string."""
    secs = int((now - dt).total_seconds())
    if secs < 0:
        return "in the future?"
    if secs < 60:
        return f"{secs}s ago"
    if secs < 3600:
        return f"{secs // 60}m {secs % 60}s ago"
    if secs < 86400:
        return f"{secs // 3600}h {(secs % 3600) // 60}m ago"
    days  = secs // 86400
    hours = (secs % 86400) // 3600
    mins  = (secs % 3600) // 60
    return f"{days}d {hours}h {mins}m ago"


def vessel_status(v: dict) -> str:
    """Derive a simple status label from a vessel state dict."""
    if v["last_success"] is None:
        return "NO DATA"
    if v["last_failure"] and v["last_failure"] > v["last_success"]:
        return "FAILING"
    return "OK"


def print_table(state: dict, now: datetime, show_errors: bool) -> None:
    vessels = sorted(state.keys())

    w_vessel = max(len("VESSEL"),  max(len(v) for v in vessels))
    w_ts     = len("YYYY-MM-DD HH:MM:SS")  # fixed-width timestamp column
    w_since  = max(len("TIME SINCE"), 14)
    w_status = max(len("STATUS"),  max(len(vessel_status(state[v])) for v in vessels))

    widths = [w_vessel, w_ts, w_since, w_status]
    sep = "+" + "+".join("-" * (w + 2) for w in widths) + "+"

    def row(*cols: str) -> str:
        return "| " + " | ".join(f"{c:<{w}}" for c, w in zip(cols, widths)) + " |"

    print(sep)
    print(row("VESSEL", "LAST SUCCESS (UTC)", "TIME SINCE", "STATUS"))
    print(sep)

    for vessel in vessels:
        v = state[vessel]
        last_success = v["last_success"]
        status       = vessel_status(v)

        ts_str    = last_success.strftime(TIMESTAMP_FMT) if last_success else "NEVER"
        since_str = elapsed(last_success, now)           if last_success else "N/A"

        print(row(vessel, ts_str, since_str, status))

    print(sep)

    if show_errors:
        failing = {v: state[v] for v in vessels if vessel_status(state[v]) == "FAILING"}
        if failing:
            print("\nError detail for failing vessels:")
            for vessel, v in failing.items():
                ts = v["last_failure"].strftime(TIMESTAMP_FMT)
                print(f"  {vessel}:")
                print(f"    failed at : {ts} ({elapsed(v['last_failure'], now)})")
                print(f"    error     : {v['last_failure_error']}")
        else:
            print("\nNo vessels currently in a failing state.")


def print_json(state: dict, now: datetime) -> None:
    output = {}
    for vessel, v in sorted(state.items()):
        last_success = v["last_success"]
        last_failure = v["last_failure"]
        output[vessel] = {
            "last_success": last_success.strftime(TIMESTAMP_FMT) if last_success else None,
            "seconds_since_success": (
                int((now - last_success).total_seconds()) if last_success else None
            ),
            "last_failure": last_failure.strftime(TIMESTAMP_FMT) if last_failure else None,
            "last_failure_error": v["last_failure_error"],
            "status": vessel_status(v),
        }
    print(json.dumps(output, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Report last successful sync per vessel from bridge.log.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--log",
        default="logs/bridge.log",
        metavar="PATH",
        help="Path to bridge.log (default: logs/bridge.log)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Emit results as JSON instead of a table",
    )
    parser.add_argument(
        "--errors",
        action="store_true",
        help="Print error detail for any currently-failing vessels",
    )
    parser.add_argument(
        "--vessel",
        metavar="NAME",
        default=None,
        help="Filter to a single vessel (e.g. --vessel mountfu)",
    )
    args = parser.parse_args()

    log_path = Path(args.log)
    if not log_path.is_file():
        print(f"error: log file not found: {log_path}", file=sys.stderr)
        sys.exit(1)

    state = parse_log(log_path, vessel_filter=args.vessel)
    if not state:
        print("No vessel sync records found in log.", file=sys.stderr)
        sys.exit(1)

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    if args.as_json:
        print_json(state, now)
    else:
        print(f"\nVessel Sync Status  —  {now.strftime(TIMESTAMP_FMT)} UTC\n")
        print_table(state, now, show_errors=args.errors)
        print()


if __name__ == "__main__":
    main()
