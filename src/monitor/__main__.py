# src/monitor/__main__.py
"""
Vessel monitor entry point.

Usage:
    python3 -m src.monitor               # run on schedule (Docker CMD)
    python3 -m src.monitor --run-once    # one check, then exit
    python3 -m src.monitor --dry-run     # force dry-run (overrides MONITOR_DRY_RUN)
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

from src.monitor.config import MonitorConfig
from src.monitor.email_sender import EmailSender
from src.monitor.monitor import VesselMonitor
from src.monitor.scheduler import MonitorScheduler
from src.monitor.state import StateStore

logger = logging.getLogger("src.monitor")


def setup_logging(log_file: Path, level: str) -> None:
    """Same line format as the bridge, always stamped in UTC."""
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(filename)s:%(lineno)-4d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    formatter.converter = time.gmtime

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)

    log_file.parent.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        log_file, maxBytes=10_485_760, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(getattr(logging, level, logging.INFO))
    root.handlers.clear()
    root.addHandler(console)
    root.addHandler(file_handler)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Vessel position monitor")
    parser.add_argument("--run-once", action="store_true", help="Run one check and exit")
    parser.add_argument("--dry-run", action="store_true", help="Force dry-run mode")
    args = parser.parse_args(argv)

    cfg = MonitorConfig.from_env()
    if args.dry_run:
        cfg.dry_run = True

    setup_logging(cfg.monitor_log_file, cfg.log_level)

    try:
        cfg.validate()
    except ValueError as exc:
        logger.error(str(exc))
        return 1

    sender = EmailSender(
        smtp_host=cfg.smtp_host,
        smtp_port=cfg.smtp_port,
        smtp_user=cfg.smtp_user,
        smtp_pass=cfg.smtp_pass,
        company_logos=cfg.company_logos,
        dry_run=not cfg.will_send_email,   # safety net: send() raises if ever reached
    )
    monitor = VesselMonitor(cfg, sender, StateStore(cfg.state_file))

    if args.run_once:
        return 0 if monitor.run() else 1

    MonitorScheduler(cfg, monitor.run, monitor.write_heartbeat).start()
    return 0


if __name__ == "__main__":
    sys.exit(main())
