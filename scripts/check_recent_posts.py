#!/usr/bin/env python3
"""Check whether each configured vessel has a recent POST payload in bridge logs."""

import argparse
import gzip
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


# Vessel names and IMO numbers from your bridge logs.
VESSELS = {
    "mountfu": "9509011",
    "agistri": "9597018",
    "tatakifx": "9410210",
    "odessaf": "9633458",
}

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOG_DIRECTORY = PROJECT_ROOT / "logs"

# Your supplied bridge logs use UTC.
LOG_TIMEZONE = timezone.utc

TIMESTAMP_PATTERN = re.compile(r"\b(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\b")
PAYLOAD_MARKER = "POST payload:"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--hours",
        type=float,
        default=24,
        help="Lookback window in hours (default: 24).",
    )
    args = parser.parse_args()

    if not 0 < args.hours < float("inf"):
        parser.error("--hours must be a finite positive number")

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=args.hours)
    latest = {imo: None for imo in VESSELS.values()}

    # Excludes copies such as tmp.log and bridge_logs_up_to_2_oct_2026.log.
    log_files = sorted(
        path
        for path in LOG_DIRECTORY.glob("bridge.log*")
        if path.is_file()
    )

    if not log_files:
        print(f"ERROR: No bridge.log* files found in {LOG_DIRECTORY}", file=sys.stderr)
        return 2

    errors = 0

    for path in log_files:
        opener = gzip.open if path.suffix == ".gz" else open

        try:
            with opener(path, "rt", encoding="utf-8", errors="replace") as log:
                for line_number, line in enumerate(log, start=1):
                    if PAYLOAD_MARKER not in line:
                        continue

                    prefix, payload_text = line.split(PAYLOAD_MARKER, 1)

                    try:
                        match = TIMESTAMP_PATTERN.search(prefix)
                        if match is None:
                            raise ValueError("Missing log timestamp")

                        logged_at = datetime.strptime(
                            match.group(1), "%Y-%m-%d %H:%M:%S"
                        ).replace(tzinfo=LOG_TIMEZONE)

                        if logged_at > now:
                            continue

                        payload = json.loads(payload_text.strip())
                        if not isinstance(payload, dict):
                            raise ValueError("Payload must be a JSON object")

                        entries = payload.get("data")
                        if not isinstance(entries, list):
                            raise ValueError("Payload 'data' must be a list")

                        # Validate before recording any matches from this line.
                        if any(
                            not isinstance(entry, dict) or "imo" not in entry
                            for entry in entries
                        ):
                            raise ValueError("Payload entry is missing its IMO")

                        for entry in entries:
                            imo = str(entry["imo"]).strip()
                            if imo in latest:
                                previous = latest[imo]
                                if previous is None or logged_at > previous:
                                    latest[imo] = logged_at

                    except (ValueError, TypeError) as exc:
                        errors += 1
                        print(
                            f"WARNING: {path.name}:{line_number}: {exc}",
                            file=sys.stderr,
                        )

        except (OSError, EOFError) as exc:
            errors += 1
            print(f"ERROR: Cannot read {path}: {exc}", file=sys.stderr)

    print(f"\nWindow: {cutoff:%Y-%m-%d %H:%M:%S} → {now:%Y-%m-%d %H:%M:%S} UTC")
    print(f"Log files checked: {len(log_files)}\n")
    print(f"{'VESSEL':<14} {'IMO':<10} {'STATUS':<10} LATEST POST (UTC)")
    print("-" * 62)

    missing = []

    for vessel, imo in VESSELS.items():
        timestamp = latest[imo]

        if timestamp is None:
            status = "MISSING"
            formatted = "No POST found in available logs"
            missing.append(vessel)
        elif timestamp < cutoff:
            status = "STALE"
            formatted = timestamp.strftime("%Y-%m-%d %H:%M:%S")
            missing.append(vessel)
        else:
            status = "FOUND"
            formatted = timestamp.strftime("%Y-%m-%d %H:%M:%S")

        print(f"{vessel:<14} {imo:<10} {status:<10} {formatted}")

    if errors:
        print(f"\nINCOMPLETE CHECK: {errors} read/parse error(s); see warnings.")
        return 2

    if missing:
        print(f"\nFAIL: No POST payload within the last {args.hours:g} hours for: {', '.join(missing)}")
        return 1

    print("\nPASS: Every configured vessel has a POST payload in this window.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
