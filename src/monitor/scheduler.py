# src/monitor/scheduler.py
"""
Scheduler for the vessel monitor (adapted from approved-no-po's AlertScheduler).

Modes:
  * Interval: MONITOR_SCHEDULE_FREQUENCY_HOURS set -> every N hours
  * Time-based: MONITOR_SCHEDULE_TIMES (+ optional MONITOR_SCHEDULE_DAYS) in
    MONITOR_SCHEDULE_TIMES_TIMEZONE

In both modes a check runs once at startup (the state file prevents duplicate
emails), and a heartbeat is written every few minutes for the Docker healthcheck.
"""
from __future__ import annotations

import logging
import signal
from datetime import datetime
from typing import Callable, Optional
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from src.monitor.config import MonitorConfig
from src.monitor.formatting import format_duration

logger = logging.getLogger(__name__)

HEARTBEAT_MINUTES = 5
DAY_NAMES = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


class MonitorScheduler:
    def __init__(self, cfg: MonitorConfig, check: Callable[[], object], heartbeat: Callable[[], None]):
        self.cfg = cfg
        self.check = check
        self.heartbeat = heartbeat
        self.tz = ZoneInfo(cfg.schedule_timezone)
        self._scheduler: Optional[BlockingScheduler] = None

    def start(self) -> None:
        self._scheduler = BlockingScheduler(
            timezone=self.tz,
            job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 3600},
        )
        now = datetime.now(self.tz)

        logger.info("=" * 70)
        if self.cfg.schedule_frequency_hours:
            logger.info("\u25b6 VESSEL MONITOR STARTED (interval mode)")
            logger.info(f"Frequency: every {format_duration(self.cfg.schedule_frequency_hours)}")
            self._scheduler.add_job(
                self.check,
                IntervalTrigger(hours=self.cfg.schedule_frequency_hours, timezone=self.tz),
                id="monitor_check",
                name="Vessel monitor check",
                next_run_time=now,
            )
        else:
            days = self.cfg.schedule_days or list(range(1, 8))
            day_spec = ",".join(DAY_NAMES[d - 1] for d in days)
            logger.info("\u25b6 VESSEL MONITOR STARTED (time-based mode)")
            logger.info(f"Run times: {', '.join(self.cfg.schedule_times)} | days: {day_spec}")
            for time_str in self.cfg.schedule_times:
                hour, minute = (int(part) for part in time_str.split(":"))
                self._scheduler.add_job(
                    self.check,
                    CronTrigger(day_of_week=day_spec, hour=hour, minute=minute, timezone=self.tz),
                    id=f"monitor_check_{hour:02d}{minute:02d}",
                    name=f"Vessel monitor check {hour:02d}:{minute:02d}",
                )
            self._scheduler.add_job(self.check, "date", run_date=now, id="monitor_check_startup")

        self._scheduler.add_job(
            self.heartbeat,
            IntervalTrigger(minutes=HEARTBEAT_MINUTES, timezone=self.tz),
            id="monitor_heartbeat",
            name="Vessel monitor heartbeat",
            next_run_time=now,
        )

        logger.info(f"Schedule timezone: {self.cfg.schedule_timezone}")
        logger.info(
            f"Outage threshold: {format_duration(self.cfg.outage_threshold_hours)} | "
            f"repeat: {format_duration(self.cfg.alert_repeat_hours)} | "
            f"basis: {self.cfg.staleness_basis}"
        )
        mode = "DRY RUN" if self.cfg.dry_run else "LIVE"
        if self.cfg.dry_run and self.cfg.dry_run_email:
            mode += f" (redirected to {', '.join(self.cfg.dry_run_email)})"
        logger.info(f"Mode: {mode} | emails {'enabled' if self.cfg.enable_email_alerts else 'disabled'}")
        logger.info("=" * 70)

        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

        try:
            self._scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            logger.info("Scheduler stopped by user")
        finally:
            logger.info("Vessel monitor shutdown complete")

    def _signal_handler(self, signum, frame) -> None:
        logger.info(f"Received {signal.Signals(signum).name} - shutting down...")
        if self._scheduler is not None and self._scheduler.running:
            self._scheduler.shutdown(wait=True)
