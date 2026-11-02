#!/usr/bin/env python3
"""
Show each vessel's latest confirmed ORCA POST from the bridge logs.

USAGE (locally): 

        "python scripts/check_recent_posts.py --tz Europe/Athens"
    
USAGE (production): 

        "docker compose exec vessel-monitor python3 scripts/check_recent_posts.py"

Vessels come from vessels.yaml. A POST counts only when ORCA confirmed it.

Exit codes:
    0  every vessel reporting (PENDING vessels do not fail the check)
    1  at least one vessel STALE or MISSING
    2  incomplete check (read/parse issues, or vessels.yaml unreadable)
"""
import argparse
import math
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.monitor.formatting import format_duration, render_status_text  # noqa: E402
from src.monitor.log_scanner import BASES, scan_logs  # noqa: E402
from src.monitor.vessels import load_vessels  # noqa: E402


def positive_hours(text: str) -> float:
    value = float(text)
    if not (value > 0 and math.isfinite(value)):
        raise argparse.ArgumentTypeError("must be a finite positive number")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--hours", type=positive_hours, default=24.0,
                        help="Outage threshold in hours (default: 24)")
    parser.add_argument("--basis", choices=BASES, default="position",
                        help="Judge by payload position time or POST time (default: position)")
    parser.add_argument("--logs-dir", type=Path, default=PROJECT_ROOT / "logs",
                        help="Directory holding bridge.log* (default: ./logs)")
    parser.add_argument("--vessels", type=Path, default=PROJECT_ROOT / "vessels.yaml",
                        help="Vessel file (default: ./vessels.yaml)")
    parser.add_argument("--tz", default="UTC", help="Display timezone (default: UTC)")
    args = parser.parse_args()

    try:
        vessels = load_vessels(args.vessels)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    result = scan_logs(args.logs_dir, vessels, args.hours, basis=args.basis)
    print(render_status_text(result, args.tz))

    for issue in result.issues:
        print(f"WARNING: {issue.describe()}", file=sys.stderr)

    if result.issues:
        print(f"\nINCOMPLETE CHECK: {len(result.issues)} read/parse issue(s); see warnings.")
        return 2

    if result.failing:
        names = ", ".join(v.ref_code for v in result.failing)
        print(f"\nFAIL: No confirmed location within {format_duration(args.hours)} for: {names}")
        return 1

    print(f"\nPASS: Every vessel has a confirmed location within {format_duration(args.hours)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
