# src/monitor/config.py
"""
Configuration for the vessel monitor, loaded from the environment / .env.

Every monitor-specific variable is prefixed MONITOR_ because the monitor shares
.env with the bridge, which already uses SCHEDULE_FREQUENCY_HOURS (0.0833, for its
own healthcheck) and DRY_RUN. SMTP_* are shared as-is.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from decouple import config

from src.monitor.log_scanner import BASES

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOGO_NAME = "triton"


def _csv(name: str) -> List[str]:
    raw = config(name, default="")
    return [s.strip() for s in raw.split(",") if s.strip()]


def _optional_float(name: str) -> Optional[float]:
    raw = config(name, default="").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        raise ValueError(f"{name} must be a number, got {raw!r}") from None


def _float(name: str, default: float) -> float:
    value = _optional_float(name)
    return default if value is None else value


def _int_csv(name: str) -> List[int]:
    try:
        return [int(s) for s in _csv(name)]
    except ValueError:
        raise ValueError(f"{name} must be comma-separated integers") from None


def _path(name: str, default: Path, root: Path) -> Path:
    raw = config(name, default="").strip()
    path = Path(raw) if raw else default
    return path if path.is_absolute() else root / path


@dataclass
class MonitorConfig:
    # Paths
    project_root: Path
    logs_dir: Path
    log_pattern: str
    vessels_file: Path
    state_dir: Path
    media_dir: Path
    logo_file: Optional[Path]

    # Detection
    outage_threshold_hours: float
    alert_repeat_hours: float
    staleness_basis: str

    # Email
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_pass: str
    alert_recipients: List[str]
    alert_cc_recipients: List[str]
    parse_error_recipients: List[str]
    enable_email_alerts: bool
    enable_parse_error_alerts: bool
    dry_run: bool
    dry_run_email: List[str]

    # Scheduling
    schedule_frequency_hours: Optional[float]
    schedule_times: List[str]
    schedule_days: List[int]
    schedule_timezone: str
    display_timezone: str

    # Logging
    log_level: str

    # ------------------------------------------------------------------
    # Derived paths
    # ------------------------------------------------------------------

    @property
    def state_file(self) -> Path:
        return self.state_dir / "monitor_state.json"

    @property
    def health_file(self) -> Path:
        return self.state_dir / "health_status.txt"

    @property
    def heartbeat_file(self) -> Path:
        return self.state_dir / "heartbeat"

    @property
    def monitor_log_file(self) -> Path:
        return self.state_dir / "monitor.log"

    @property
    def company_logos(self) -> Dict[str, Path]:
        """Logo mapping for EmailSender; CID becomes '<name>_logo'."""
        if self.logo_file is not None and self.logo_file.is_file():
            return {LOGO_NAME: self.logo_file}
        return {}

    @property
    def logo_cid(self) -> Optional[str]:
        return f"{LOGO_NAME}_logo" if self.company_logos else None

    @property
    def will_send_email(self) -> bool:
        return self.enable_email_alerts and (not self.dry_run or bool(self.dry_run_email))

    # ------------------------------------------------------------------
    # Loading and validation
    # ------------------------------------------------------------------

    @classmethod
    def from_env(cls, project_root: Optional[Path] = None) -> "MonitorConfig":
        root = project_root or PROJECT_ROOT
        media_dir = root / "media"
        logo_name = config("MONITOR_LOGO", default="triton_logo.png").strip()

        return cls(
            project_root=root,
            logs_dir=_path("MONITOR_LOGS_DIR", root / "logs", root),
            log_pattern=config("MONITOR_LOG_PATTERN", default="bridge.log*").strip(),
            vessels_file=_path("MONITOR_VESSELS_FILE", root / "vessels.yaml", root),
            state_dir=_path("MONITOR_STATE_DIR", root / "monitor", root),
            media_dir=media_dir,
            logo_file=(media_dir / logo_name) if logo_name else None,

            outage_threshold_hours=_float("MONITOR_OUTAGE_THRESHOLD_HOURS", 24.0),
            alert_repeat_hours=_float("MONITOR_ALERT_REPEAT_HOURS", 24.0),
            staleness_basis=config("MONITOR_STALENESS_BASIS", default="position").strip().lower(),

            smtp_host=config("SMTP_HOST", default="").strip(),
            smtp_port=config("SMTP_PORT", default=465, cast=int),
            smtp_user=config("SMTP_USER", default="").strip(),
            smtp_pass=config("SMTP_PASS", default=""),
            alert_recipients=_csv("MONITOR_ALERT_RECIPIENTS"),
            alert_cc_recipients=_csv("MONITOR_ALERT_CC_RECIPIENTS"),
            parse_error_recipients=_csv("MONITOR_PARSE_ERROR_RECIPIENTS"),
            enable_email_alerts=config("MONITOR_ENABLE_EMAIL_ALERTS", default=True, cast=bool),
            enable_parse_error_alerts=config("MONITOR_ENABLE_PARSE_ERROR_ALERTS", default=True, cast=bool),
            dry_run=config("MONITOR_DRY_RUN", default=True, cast=bool),
            dry_run_email=_csv("MONITOR_DRY_RUN_EMAIL"),

            schedule_frequency_hours=_optional_float("MONITOR_SCHEDULE_FREQUENCY_HOURS"),
            schedule_times=_csv("MONITOR_SCHEDULE_TIMES"),
            schedule_days=_int_csv("MONITOR_SCHEDULE_DAYS"),
            schedule_timezone=config("MONITOR_SCHEDULE_TIMES_TIMEZONE", default="Europe/Athens").strip(),
            display_timezone=config("MONITOR_DISPLAY_TIMEZONE", default="UTC").strip(),

            log_level=config("MONITOR_LOG_LEVEL", default="INFO").strip().upper(),
        )

    def validate(self) -> None:
        """Raise ValueError listing every configuration problem found."""
        errors: List[str] = []

        if self.staleness_basis not in BASES:
            errors.append(f"MONITOR_STALENESS_BASIS must be one of {BASES}")

        for name, value in (
            ("MONITOR_OUTAGE_THRESHOLD_HOURS", self.outage_threshold_hours),
            ("MONITOR_ALERT_REPEAT_HOURS", self.alert_repeat_hours),
        ):
            if not (value > 0 and math.isfinite(value)):
                errors.append(f"{name} must be a finite positive number")

        if self.schedule_frequency_hours is not None:
            if not (self.schedule_frequency_hours > 0 and math.isfinite(self.schedule_frequency_hours)):
                errors.append("MONITOR_SCHEDULE_FREQUENCY_HOURS must be a finite positive number")
            if self.schedule_times:
                logger.warning(
                    "Both MONITOR_SCHEDULE_FREQUENCY_HOURS and MONITOR_SCHEDULE_TIMES are set; "
                    "interval mode wins"
                )
        elif not self.schedule_times:
            errors.append("Set MONITOR_SCHEDULE_FREQUENCY_HOURS or MONITOR_SCHEDULE_TIMES")

        for time_str in self.schedule_times:
            try:
                hour, minute = (int(part) for part in time_str.split(":"))
                if not (0 <= hour <= 23 and 0 <= minute <= 59):
                    raise ValueError
            except ValueError:
                errors.append(f"MONITOR_SCHEDULE_TIMES entry {time_str!r} is not HH:MM")

        for day in self.schedule_days:
            if not 1 <= day <= 7:
                errors.append(f"MONITOR_SCHEDULE_DAYS entry {day} must be 1 (Mon) .. 7 (Sun)")

        for name, tz in (
            ("MONITOR_SCHEDULE_TIMES_TIMEZONE", self.schedule_timezone),
            ("MONITOR_DISPLAY_TIMEZONE", self.display_timezone),
        ):
            try:
                ZoneInfo(tz)
            except (ZoneInfoNotFoundError, ValueError):
                errors.append(f"{name} {tz!r} is not a valid IANA timezone")

        if self.will_send_email:
            for name, value in (("SMTP_HOST", self.smtp_host), ("SMTP_USER", self.smtp_user),
                                ("SMTP_PASS", self.smtp_pass)):
                if not value:
                    errors.append(f"{name} is required when emails are enabled")
            if not self.dry_run and not self.alert_recipients:
                errors.append("MONITOR_ALERT_RECIPIENTS is required when emails are enabled")

        if not self.vessels_file.is_file():
            errors.append(f"Vessel file not found: {self.vessels_file}")

        if self.logo_file is not None and not self.logo_file.is_file():
            logger.warning(f"Logo not found at {self.logo_file}; emails will be sent without it")

        if errors:
            raise ValueError("Invalid monitor configuration:\n  - " + "\n  - ".join(errors))
