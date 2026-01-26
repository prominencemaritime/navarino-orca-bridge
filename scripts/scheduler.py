#!/usr/bin/env python3
"""
Production scheduler for Navarino ORCA Bridge.
Initialises once, runs continuously, handles shutdown gracefully.
"""

import sys
import signal
import logging
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

from src.app import initialise_app, AppContext

logger = logging.getLogger(__name__)

# Global scheduler instance for signal handling only
_scheduler: Optional[BlockingScheduler] = None


def create_sync_job(ctx: AppContext):
    """
    Factory that creates a sync job with context injected.

    This is called *once* at startup to create the job function.
    The job function then has access to ctx via closure.

    Args:
        ctx: Application context with config and clients

    Returns:
        Job function suitable for APScheduler
    """
    def sync_job():
        """
        Scheduled job that syncs all vessels.

        Reuns every SYNC_INTERVAL_MINUTES.
        Has access to ctx from closude - no need to reload config.
        """
        try:
            logger.info("=" * 70)
            logger.info("▶ SCHEDULED SYNC STARTED")
            logger.info(f"Time: {datetime.now(tz=ZoneInfo(ctx.config.timezone)).isoformat()}")
            logger.info(f"Vessels: {list(ctx.config.vessel_identifiers.keys())}")
            logger.info(f"Mode: {'DRY_RUN' if ctx.config.dry_run else 'LIVE'}")
            logger.info("=" * 70)

            # Sync all vessels - bridge writes health status
            results = ctx.bridge.sync_all_vessels(
                vessel_identifiers=ctx.config.vessel_identifiers,
                sync_history=False,
                dry_run=ctx.config.dry_run
            )
            
            # Log Summary
            success_count = sum(1 for r in results if r['status'] in ['success', 'dry_run'])
            error_count = sum(1 for r in results if r['status'] == 'error')

            if error_count > 0:
                logger.warning(f"⚠️  Sync completed with {error_count} error{'' if error_count==1 else 's'}")
            else:
                logger.info(f"✓ Sync completed - {success_count} vessel{'' if success_count==1 else 's'}")

            logger.info("=" * 70)

        except Exception as e:
            logger.exception(f"Critical error in sync_job: {e}")

            # Write ERROR health status (no config reload)
            try:
                health_file = ctx.config.logs_dir / "health_status.txt"
                health_file.parent.mkdir(parents=True, exist_ok=True)
                now = datetime.now(tz=ZoneInfo(ctx.config.timezone))

                # Simple, direct write - no complex recovery
                with open(health_file, 'w') as f:
                    f.write(f"ERROR {now.isoformat()}\n")
                    f.write(f"ALERT_TYPE: VesselSync\n")
                    f.write(f"TIMEZONE: {ctx.config.timezone}\n")
                    f.write(f"ERROR_MSG: Scheduler exception: {str(e)}\n")

            except Exception as write_error:
                logger.error(f"Could not write health status: {write_error}")
                
    return sync_job


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    global _scheduler

    signal_name = signal.Signals(signum).name
    logger.info(f"Received {signal_name} signal - shutting down..")

    if _scheduler and _scheduler.running:
        logger.info("Stopping scheduler..")
        _scheduler.shutdown(wait=True)
        logger.info("Scheduler stopped")


def main():
    """Main scheduler loop"""
    global _scheduler

    # Step 1: Initialise application (*once* at startup)
    logger.info("=" * 70)
    logger.info("▶ NAVARINO ORCA BRIDGE STARTING")
    logger.info("=" * 70)

    try:
        ctx = initialise_app()
    except Exception as e:
        logger.exception(f"Failed at initialise application: {e}")
        sys.exit(1)

    # Step 2: Display configuration
    logger.info(f"Sync interval: {ctx.config.sync_interval_minutes} minutes")
    logger.info(f"Timezone: {ctx.config.timezone}")
    logger.info(f"Vessels: {list(ctx.config.vessel_identifiers.keys())}")
    logger.info(f"Mode: {'DRY RUN' if ctx.config.dry_run else 'LIVE'}")
    logger.info(f"ORCA: {'TEST' if ctx.config.orca_test else 'LIVE'} environment")
    logger.info("=" * 70)

    # Step 3: Register signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # Step 4: Create scheduler
    _scheduler = BlockingScheduler(timezone=ctx.config.timezone)

    # Step 5: Create job function with context injected
    sync_job_func = create_sync_job(ctx)

    # Step 6: Schedule job with proper timezone-aware start time
    _scheduler.add_job(
        sync_job_func,
        trigger=IntervalTrigger(minutes=ctx.config.sync_interval_minutes),
        id='vessel_sync',
        name='Vessel Position Sync',
        max_instances=1,
        coalesce=True,
        next_run_time=datetime.now(ZoneInfo(ctx.config.timezone))
    )

    # Step 7: Start scheduler (blocking)
    try:
        _scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped by user")
    finally:
        logger.info("Scheduler shutdown complete")


if __name__ == "__main__":
    main()
