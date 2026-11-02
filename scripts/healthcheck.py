#!/usr/bin/env python3
"""
Docker healthcheck for the Navarino ORCA bridge.

Healthy while logs/health_status.txt shows a completed sync cycle within the
last HEALTHCHECK_MAX_AGE_MINUTES (default 60), whether that cycle ended OK or
ERROR. Vessels that stop reporting are alerted by the vessel-monitor service.

Exit codes: 0 healthy, 1 unhealthy.
"""
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


def main():
    """
    Main healthcheck logic.

    Validates the health_status.txt file by checking:
    1. File exists
    2. File contains valid structured data
    3. Status is OK or ERROR is recent
    4. Timestamp is recent enough based on schedule

    Exit codes:
        0: Healthy
        1: Unhealthy
    """
    BASE_DIR = Path(__file__).resolve().parent.parent
    health_file = BASE_DIR / "logs" / "health_status.txt"

    # Validate file structure first
    try:
        validate_health_file_structure(health_file)
    except Exception as e:
        print(f"Health file validation failed: {e}", file=sys.stderr)
        sys.exit(1)

    # Read and parse health status
    try:
        health_data = parse_health_file(health_file)
    except Exception as e:
        print(f"Cannot parse health status: {e}", file=sys.stderr)
        sys.exit(1)

    # Get the timezone to use for time calculations
    tz_name = get_effective_timezone()

    # Calculate maximum age based on schedule mode
    max_age_minutes = calculate_max_age()

    # Calculate file age using the parsed timestamp (timezone-aware)
    try:
        now = datetime.now(tz=ZoneInfo(tz_name))
        file_age_seconds = (now - health_data['timestamp']).total_seconds()
        file_age_minutes = file_age_seconds / 60
    except Exception as e:
        print(f"Cannot calculate file age: {e}", file=sys.stderr)
        sys.exit(1)

    # Healthy = the bridge is still completing sync cycles. Per-vessel sync
    # errors (status ERROR) are not a container problem: vessels that stop
    # reporting are alerted by the vessel-monitor service.
    if file_age_minutes > max_age_minutes:
       print(
           f"No completed sync cycle for {file_age_minutes:.1f} minutes "
           f"(max: {max_age_minutes:.1f}). Last status: {health_data['status']} "
           f"{health_data.get('error_msg', '')}".rstrip(),
           file=sys.stderr,
       )
       sys.exit(1)

    print(
       f"Healthy (last sync cycle {file_age_minutes:.1f} min ago, "
       f"status {health_data['status']}, max {max_age_minutes:.0f} min)"
    )
    sys.exit(0)


def parse_health_file(health_file: Path) -> dict:
    """
    Parse the structured health status file.

    Expected format:
        Line 1: STATUS YYYY-MM-DDTHH:MM:SS.ffffff+HH:MM
        Line 2: ALERT_TYPE: ClassName
        Line 3: TIMEZONE: timezone_name
        Line 4: ERROR_MSG: message (optional, only if ERROR)

    Args:
        health_file: Path to health_status.txt

    Returns:
        Dictionary with parsed health data:
            - status: "OK" or "ERROR"
            - timestamp: timezone-aware datetime object
            - alert_type: Alert class name
            - timezone: Timezone name from file
            - error_msg: Error message (only if status is ERROR)

    Raises:
        ValueError: If file format is invalid
        Exception: If file cannot be read or parsed
    """
    content = health_file.read_text().strip()
    lines = content.split('\n')

    if len(lines) < 3:
        raise ValueError(f"Health file has insufficient lines: {len(lines)} (expected at least 3)")

    # Parse line 1: STATUS TIMESTAMP
    status_line = lines[0].strip()
    parts = status_line.split(' ', 1)

    if len(parts) != 2:
        raise ValueError(f"Invalid status line format: '{status_line}'")

    status = parts[0]
    timestamp_str = parts[1]

    if status not in ["OK", "ERROR"]:
        raise ValueError(f"Invalid status: '{status}' (expected OK or ERROR)")

    # Parse timestamp (ISO format with timezone)
    try:
        timestamp = datetime.fromisoformat(timestamp_str)
    except ValueError as e:
        raise ValueError(f"Invalid timestamp format: '{timestamp_str}': {e}")

    # Ensure timestamp is timezone-aware
    if timestamp.tzinfo is None:
        raise ValueError(f"Timestamp is not timezone-aware: '{timestamp_str}'")

    # Parse line 2: ALERT_TYPE
    if not lines[1].startswith("ALERT_TYPE: "):
        raise ValueError(f"Invalid ALERT_TYPE line: '{lines[1]}'")
    alert_type = lines[1].replace("ALERT_TYPE: ", "").strip()

    # Parse line 3: TIMEZONE
    if not lines[2].startswith("TIMEZONE: "):
        raise ValueError(f"Invalid TIMEZONE line: '{lines[2]}'")
    timezone = lines[2].replace("TIMEZONE: ", "").strip()

    result = {
        'status': status,
        'timestamp': timestamp,
        'alert_type': alert_type,
        'timezone': timezone
    }

    # Parse line 4 (optional): ERROR_MSG
    if len(lines) >= 4 and lines[3].startswith("ERROR_MSG: "):
        error_msg = lines[3].replace("ERROR_MSG: ", "").strip()
        result['error_msg'] = error_msg

    return result


def get_effective_timezone() -> str:
    """
    Determine which timezone to use for time calculations.

    Precedence:
        1. SCHEDULE_TIMES_TIMEZONE (if set)
        2. TIMEZONE (if set)
        3. UTC (default fallback)

    Returns:
        Timezone name (e.g., "Europe/Athens", "UTC")
    """
    schedule_tz = os.getenv('SCHEDULE_TIMES_TIMEZONE', '').strip()
    if schedule_tz:
        return schedule_tz

    general_tz = os.getenv('TIMEZONE', '').strip()
    if general_tz:
        return general_tz

    return 'UTC'


def validate_health_file_structure(health_file: Path) -> None:
    """
    Perform initial validation of health file structure before parsing.

    Raises:
        FileNotFoundError: If file does not exist
        ValueError: If file is empty or has invalid structure
    """
    if not health_file.exists():
        raise FileNotFoundError(f"Health file not found: {health_file}")

    stat = health_file.stat()
    if stat.st_size == 0:
        raise ValueError("Health file is empty")

    if stat.st_size > 10000:  # 10KB limit
        raise ValueError(f"Health file is too large: {stat.st_size} bytes (max 10KB)")


def calculate_max_age() -> float:
   """Minutes without a completed sync cycle before the container is unhealthy."""
   raw = os.getenv('HEALTHCHECK_MAX_AGE_MINUTES', '').strip()
   try:
       return float(raw) if raw else 60.0
   except ValueError:
       print(f"Invalid HEALTHCHECK_MAX_AGE_MINUTES: {raw!r}; using 60", file=sys.stderr)
       return 60.0


if __name__ == "__main__":
    main()
