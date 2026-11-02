# src/monitor/monitor.py
"""
One monitoring pass: scan the logs, decide which emails are due, send them,
and persist state only for emails that actually went out.

Alert rules:
  * Outage digest (all vessels listed) when at least one vessel is STALE/MISSING,
    i.e. no confirmed location for longer than MONITOR_OUTAGE_THRESHOLD_HOURS.
    Sent immediately when a vessel newly enters that state, then repeated every
    MONITOR_ALERT_REPEAT_HOURS while any vessel remains in it. Short failures that
    recover within the threshold never alert.
  * Recovery email, one per vessel ("AlertDev | <vessel> API Online"), only for a
    vessel whose outage was declared by a successfully sent digest.
  * Parse-issue email (toggle + own recipients) when the scan hit read/parse
    problems on lines inside the threshold window, repeated on the same cadence.
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

from src.monitor.config import MonitorConfig
from src.monitor.email_sender import EmailSender
from src.monitor.formatting import (
    EmailContent,
    build_outage_email,
    build_parse_issue_email,
    build_recovery_email,
    format_duration,
)
from src.monitor.log_scanner import STATUS_OK, ScanResult, scan_logs
from src.monitor.state import MonitorState, StateStore
from src.monitor.vessels import VesselInfo, load_vessel_details, load_vessels

logger = logging.getLogger(__name__)


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.tmp")
    temp.write_text(text, encoding="utf-8")
    temp.replace(path)


class VesselMonitor:
    def __init__(self, cfg: MonitorConfig, sender: EmailSender, store: StateStore):
        self.cfg = cfg
        self.sender = sender
        self.store = store
        self._lock = threading.Lock()
        self._send_failures = 0
        self._details: Dict[str, VesselInfo] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> bool:
        """Run one check. Returns True if it completed without errors."""
        if not self._lock.acquire(blocking=False):
            logger.warning("Previous check still running; skipping this one")
            return True

        now = datetime.now(timezone.utc)
        self._send_failures = 0
        logger.info("=" * 70)
        logger.info("\u25b6 VESSEL MONITOR CHECK STARTED")

        try:
            vessels = load_vessels(self.cfg.vessels_file)
            self._details = load_vessel_details(self.cfg.vessels_file)
            result = scan_logs(
                self.cfg.logs_dir,
                vessels,
                self.cfg.outage_threshold_hours,
                basis=self.cfg.staleness_basis,
                now=now,
                pattern=self.cfg.log_pattern,
            )
            self._log_result(result)

            state = self.store.load()
            self._handle_outages(result, state, now)
            self._handle_recoveries(result, state, now)
            self._handle_parse_issues(result, state, now)
            self._prune(state, set(vessels.values()))
            self.store.save(state)

            if self._send_failures:
                message = f"{self._send_failures} email(s) failed to send"
                logger.error(message)
                self._write_health("ERROR", now, message)
                return False

            self._write_health("OK", now)
            return True

        except Exception as exc:
            logger.exception(f"Vessel monitor check failed: {exc}")
            self._write_health("ERROR", now, str(exc))
            return False

        finally:
            logger.info("\u25fc VESSEL MONITOR CHECK COMPLETE")
            logger.info("=" * 70)
            self._lock.release()

    def write_heartbeat(self) -> None:
        """Called by the scheduler every few minutes; read by the Docker healthcheck."""
        try:
            _atomic_write(self.cfg.heartbeat_file, datetime.now(timezone.utc).isoformat() + "\n")
        except OSError as exc:
            logger.error(f"Could not write heartbeat: {exc}")

    # ------------------------------------------------------------------
    # Alert handlers
    # ------------------------------------------------------------------

    def _handle_outages(self, result: ScanResult, state: MonitorState, now: datetime) -> None:
        failing = result.failing
        if not failing:
            state.last_outage_alert_at = None
            return

        newly_failing = [v for v in failing if not state.vessel(v.imo, v.ref_code).in_outage]
        repeat_every = timedelta(hours=self.cfg.alert_repeat_hours)
        repeat_due = (
            state.last_outage_alert_at is None
            or now - state.last_outage_alert_at >= repeat_every
        )

        if not newly_failing and not repeat_due:
            next_at = state.last_outage_alert_at + repeat_every
            logger.info(
                f"Outage ongoing for {', '.join(v.ref_code for v in failing)}; "
                f"next reminder due {next_at:%Y-%m-%d %H:%M} UTC"
            )
            return

        email = build_outage_email(
            result, self.cfg.alert_repeat_hours, self.cfg.display_timezone, self.cfg.logo_cid,
            details=self._details,
        )
        if not self._deliver(email, self.cfg.alert_recipients, self.cfg.alert_cc_recipients):
            return

        state.last_outage_alert_at = now
        for v in newly_failing:
            vessel_state = state.vessel(v.imo, v.ref_code)
            vessel_state.in_outage = True
            vessel_state.outage_declared_at = now
            vessel_state.last_seen_before_outage = v.reference_at
            logger.warning(f"Outage declared for {v.ref_code} (IMO {v.imo})")

    def _handle_recoveries(self, result: ScanResult, state: MonitorState, now: datetime) -> None:
        for v in result.vessels:
            vessel_state = state.vessels.get(v.imo)
            if v.status != STATUS_OK or vessel_state is None or not vessel_state.in_outage:
                continue

            email = build_recovery_email(
                v,
                vessel_state.outage_declared_at,
                vessel_state.last_seen_before_outage,
                now,
                self.cfg.display_timezone,
                self.cfg.logo_cid,
                info=self._details.get(v.imo),
            )
            if self._deliver(email, self.cfg.alert_recipients, self.cfg.alert_cc_recipients):
                logger.info(f"Recovery sent for {v.ref_code} (IMO {v.imo})")
                vessel_state.clear_outage()

    def _handle_parse_issues(self, result: ScanResult, state: MonitorState, now: datetime) -> None:
        if not result.issues:
            state.last_parse_alert_at = None
            return

        if not self.cfg.enable_parse_error_alerts:
            logger.info("Parse-issue emails disabled (MONITOR_ENABLE_PARSE_ERROR_ALERTS=False)")
            return

        repeat_every = timedelta(hours=self.cfg.alert_repeat_hours)
        if state.last_parse_alert_at is not None and now - state.last_parse_alert_at < repeat_every:
            logger.info("Parse issues persist; reminder not yet due")
            return

        recipients = self.cfg.parse_error_recipients or self.cfg.alert_recipients
        email = build_parse_issue_email(
            result, self.cfg.display_timezone, self.cfg.logo_cid, details=self._details
        )
        if self._deliver(email, recipients, []):
            state.last_parse_alert_at = now

    def _prune(self, state: MonitorState, current_imos: set) -> None:
        for imo in [imo for imo in state.vessels if imo not in current_imos]:
            logger.info(f"Dropping state for IMO {imo} (no longer in vessels.yaml)")
            del state.vessels[imo]

    # ------------------------------------------------------------------
    # Delivery, logging, health
    # ------------------------------------------------------------------

    def _deliver(self, email: EmailContent, to: List[str], cc: List[str]) -> bool:
        """Send an email. Returns True only if it was actually sent."""
        if not self.cfg.enable_email_alerts:
            logger.info(f"[EMAIL DISABLED] Would send '{email.subject}' to {to} (CC {cc})")
            return False

        subject = email.subject
        if self.cfg.dry_run:
            if not self.cfg.dry_run_email:
                logger.info(f"[DRY-RUN] Would send '{subject}' to {to} (CC {cc})")
                return False
            subject = f"[DRY-RUN] {subject} (Original: {', '.join(to) or 'none'})"
            to, cc = self.cfg.dry_run_email, []

        if not to:
            logger.error(f"No recipients configured for '{subject}'")
            self._send_failures += 1
            return False

        try:
            self.sender.send(
                subject=subject,
                plain_text=email.text,
                html_content=email.html,
                recipients=to,
                cc_recipients=cc,
            )
            return True
        except Exception as exc:
            self._send_failures += 1
            logger.error(f"Failed to send '{subject}': {exc}")
            return False

    def _log_result(self, result: ScanResult) -> None:
        logger.info(
            f"Scanned {len(result.files)} log file(s) | threshold "
            f"{format_duration(result.threshold_hours)} | basis={result.basis}"
        )
        for v in result.vessels:
            ref = f"{v.reference_at:%Y-%m-%d %H:%M:%S} UTC" if v.reference_at else "never"
            logger.info(
                f"  {v.ref_code:<12} IMO={v.imo} status={v.status:<8} "
                f"last={ref} age={format_duration(v.age_hours)}"
            )
        for issue in result.issues[:20]:
            logger.warning(f"Log issue: {issue.describe()}")
        if len(result.issues) > 20:
            logger.warning(f"... and {len(result.issues) - 20} more log issue(s)")

    def _write_health(self, status: str, run_time: datetime, error_msg: str = "") -> None:
        lines = [
            f"{status} {run_time.isoformat()}",
            "ALERT_TYPE: VesselMonitor",
            "TIMEZONE: UTC",
        ]
        if error_msg:
            lines.append(f"ERROR_MSG: {' '.join(error_msg.split())}")
        try:
            _atomic_write(self.cfg.health_file, "\n".join(lines) + "\n")
        except OSError as exc:
            logger.error(f"Could not write health status: {exc}")
