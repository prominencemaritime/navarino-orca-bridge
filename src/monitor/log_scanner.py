# src/monitor/log_scanner.py
"""
Scan bridge logs for confirmed ORCA POSTs and derive each vessel's status.

A POST only counts once ORCA has accepted it: its "POST payload:" line must be
followed by ORCA's success line ("Data saved successfully to ORCA") before any
WARNING/ERROR line or the next payload. The bridge syncs vessels one at a time
(max_instances=1), so the next success line belongs to the latest payload.

Statuses (judged against the outage threshold):
    OK       latest update is within the threshold
    STALE    latest update is older than the threshold
    MISSING  no confirmed update anywhere in logs covering at least the threshold
    PENDING  no confirmed update yet, but the logs are younger than the threshold
             (e.g. a vessel just added, or logs just rotated) - not alerted on
"""
from __future__ import annotations

import gzip
import json
import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Tuple

PAYLOAD_MARKER = "POST payload:"
CONFIRM_MARKER = "Data saved successfully to ORCA"

LINE_TIMESTAMP = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})")
PROBLEM_LEVEL = re.compile(r"\|\s*(?:WARNING|ERROR|CRITICAL)\s*\|")

# Bridge logs are written in UTC (see config/logging_config.py).
LOG_TIMEZONE = timezone.utc

# Lines stamped further ahead than this are reported as a clock/timezone problem.
FUTURE_TOLERANCE = timedelta(minutes=5)

STATUS_OK = "OK"
STATUS_STALE = "STALE"
STATUS_MISSING = "MISSING"
STATUS_PENDING = "PENDING"
FAILING_STATUSES = (STATUS_STALE, STATUS_MISSING)

# 'position': judge by the newest position timestamp inside the payload
# 'post':     judge by when the bridge POSTed it (log line timestamp)
BASES = ("position", "post")


@dataclass(frozen=True)
class VesselStatus:
    ref_code: str
    imo: str
    status: str
    last_post_at: Optional[datetime]
    last_position_at: Optional[datetime]
    reference_at: Optional[datetime]   # the timestamp the status was judged on
    age_hours: Optional[float]

    @property
    def is_failing(self) -> bool:
        return self.status in FAILING_STATUSES


@dataclass(frozen=True)
class ScanIssue:
    source: str
    line_number: Optional[int]
    logged_at: Optional[datetime]
    message: str

    def describe(self) -> str:
        where = self.source if self.line_number is None else f"{self.source}:{self.line_number}"
        return f"{where}: {self.message}"


@dataclass
class ScanResult:
    checked_at: datetime
    threshold_hours: float
    basis: str
    files: List[Path]
    coverage_start: Optional[datetime]
    vessels: List[VesselStatus]
    issues: List[ScanIssue] = field(default_factory=list)

    @property
    def failing(self) -> List[VesselStatus]:
        return [v for v in self.vessels if v.is_failing]


def _parse_line_timestamp(line: str) -> Optional[datetime]:
    match = LINE_TIMESTAMP.match(line)
    if match is None:
        return None
    return datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S").replace(tzinfo=LOG_TIMEZONE)


def _parse_position_timestamp(value: object) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("payload value has no timestamp")
    parsed = datetime.fromisoformat(value.strip())
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _parse_payload(text: str) -> List[Tuple[str, datetime]]:
    """
    Return (imo, newest position timestamp) for every entry in a POST payload.

    Raises:
        ValueError / TypeError: the payload is not in the expected ORCA shape
    """
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("payload is not a JSON object")

    entries = payload.get("data")
    if not isinstance(entries, list):
        raise ValueError("payload 'data' is not a list")

    parsed = []
    for entry in entries:
        if not isinstance(entry, dict) or "imo" not in entry:
            raise ValueError("payload entry is missing its IMO")

        imo = str(entry["imo"]).strip()
        values = entry.get("values")
        if not isinstance(values, list) or not values:
            raise ValueError(f"IMO {imo}: payload entry has no values")

        newest = max(
            _parse_position_timestamp(v.get("timestamp") if isinstance(v, dict) else None)
            for v in values
        )
        parsed.append((imo, newest))

    return parsed


def _open_log(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    return path.open("r", encoding="utf-8", errors="replace")


def _newer(current: Optional[datetime], candidate: datetime) -> datetime:
    return candidate if current is None or candidate > current else current


def scan_logs(
    logs_dir: Path,
    vessels: Mapping[str, str],
    threshold_hours: float,
    basis: str = "position",
    now: Optional[datetime] = None,
    pattern: str = "bridge.log*",
) -> ScanResult:
    """
    Scan the bridge logs and return each vessel's latest confirmed update.

    Args:
        logs_dir:        Directory holding bridge.log (and any rotated copies)
        vessels:         Ordered mapping of ref_code -> IMO
        threshold_hours: Age after which a vessel counts as STALE
        basis:           'position' or 'post' (see BASES)
        now:             Reference time (default: current UTC time)
        pattern:         Glob for log files; excludes copies such as tmp.log

    Returns:
        ScanResult. Parse/read problems are collected in .issues rather than
        raised; only problems on lines logged within the threshold window are
        kept, so an old malformed line does not alert forever.
    """
    if basis not in BASES:
        raise ValueError(f"basis must be one of {BASES}, got {basis!r}")
    if not (0 < threshold_hours and math.isfinite(threshold_hours)):
        raise ValueError("threshold_hours must be a finite positive number")

    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    threshold = timedelta(hours=threshold_hours)
    issue_window_start = now - threshold

    wanted = set(vessels.values())
    last_post: Dict[str, Optional[datetime]] = {imo: None for imo in wanted}
    last_position: Dict[str, Optional[datetime]] = {imo: None for imo in wanted}
    issues: List[ScanIssue] = []
    coverage_start: Optional[datetime] = None

    logs_dir = Path(logs_dir)
    files = sorted(p for p in logs_dir.glob(pattern) if p.is_file())
    if not files:
        issues.append(ScanIssue(str(logs_dir), None, None, f"no files matching '{pattern}'"))

    for path in files:
        pending: Optional[Tuple[datetime, List[Tuple[str, datetime]]]] = None
        need_first_timestamp = True

        try:
            with _open_log(path) as log:
                for line_number, line in enumerate(log, start=1):
                    if need_first_timestamp:
                        first = _parse_line_timestamp(line)
                        if first is not None:
                            need_first_timestamp = False
                            if first <= now + FUTURE_TOLERANCE and (
                                coverage_start is None or first < coverage_start
                            ):
                                coverage_start = first

                    if PAYLOAD_MARKER in line:
                        pending = None
                        logged_at = _parse_line_timestamp(line)
                        in_window = logged_at is None or logged_at >= issue_window_start

                        try:
                            if logged_at is None:
                                raise ValueError("payload line has no log timestamp")
                            if logged_at > now + FUTURE_TOLERANCE:
                                raise ValueError(
                                    f"log timestamp {logged_at:%Y-%m-%d %H:%M:%S} is in the "
                                    "future (clock or timezone mismatch?)"
                                )
                            entries = _parse_payload(line.split(PAYLOAD_MARKER, 1)[1].strip())
                        except (ValueError, TypeError) as exc:
                            if in_window:
                                issues.append(ScanIssue(path.name, line_number, logged_at, str(exc)))
                            continue

                        pending = (logged_at, entries)
                        continue

                    if pending is None:
                        continue

                    if CONFIRM_MARKER in line:
                        posted_at, entries = pending
                        pending = None
                        for imo, position_at in entries:
                            if imo not in wanted:
                                continue
                            # A position cannot postdate the POST that carried it.
                            position_at = min(position_at, posted_at)
                            last_post[imo] = _newer(last_post[imo], posted_at)
                            last_position[imo] = _newer(last_position[imo], position_at)
                    elif PROBLEM_LEVEL.search(line):
                        # ORCA rejected it or the request failed: not a confirmed update.
                        pending = None

        except (OSError, EOFError) as exc:
            issues.append(ScanIssue(path.name, None, None, f"cannot read file: {exc}"))

    statuses: List[VesselStatus] = []
    for ref_code, imo in vessels.items():
        post_at = last_post[imo]
        position_at = last_position[imo]
        reference = position_at if basis == "position" else post_at

        if reference is None:
            enough_history = coverage_start is not None and now - coverage_start >= threshold
            status = STATUS_MISSING if enough_history else STATUS_PENDING
            age_hours = None
        else:
            age = now - reference
            age_hours = max(age.total_seconds(), 0.0) / 3600
            status = STATUS_STALE if age > threshold else STATUS_OK

        statuses.append(
            VesselStatus(
                ref_code=ref_code,
                imo=imo,
                status=status,
                last_post_at=post_at,
                last_position_at=position_at,
                reference_at=reference,
                age_hours=age_hours,
            )
        )

    return ScanResult(
        checked_at=now,
        threshold_hours=threshold_hours,
        basis=basis,
        files=files,
        coverage_start=coverage_start,
        vessels=statuses,
        issues=issues,
    )
