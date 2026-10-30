# src/db/sync_log.py
"""Writer for external.vessel_position_sync_log."""

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import column, table

from src.db.datalab import check_db_connection, get_db_transaction

logger = logging.getLogger(__name__)

# After a failed write, skip datalab writes for this long.
_COOLDOWN_SECONDS = 120

_TABLE = table(
    "vessel_position_sync_log",
    column("vessel_name"), column("imo"), column("provider"),
    column("source_host"), column("interface"), column("position_ts"),
    column("lat"), column("lon"), column("course"), column("speed_og"),
    column("outcome"), column("orca_status"), column("orca_response"),
    column("error"), column("duration_ms"), column("payload"),
    schema="external",
)


def _first_value(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    try:
        return payload["data"][0]["values"][0]
    except (KeyError, IndexError, TypeError):
        return {}


def _parse_ts(ts: Optional[str]) -> Optional[datetime]:
    """Payload timestamps are UTC strings without a zone marker."""
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts).replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


class SyncLogRepository:
    """
    Writes one row per sync attempt. Never raises: a datalab problem must
    not stop a position from reaching ORCA. bridge.log remains the fallback
    record, and a backfill can fill any gaps.
    """

    def __init__(self) -> None:
        self._skip_until = 0.0

    def check(self) -> bool:
        return check_db_connection()

    def log_attempt(
        self, *, vessel: str, imo: str, provider: str, outcome: str,
        source_host: Optional[str] = None, interface: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
        orca_status: Optional[int] = None, orca_response: Optional[str] = None,
        error: Optional[str] = None, duration_ms: Optional[int] = None,
    ) -> None:
        if time.monotonic() < self._skip_until:
            return

        try:
            v = _first_value(payload)
            record = {
                "vessel_name":   vessel,
                "imo":           imo,
                "provider":      provider,
                "source_host":   source_host,
                "interface":     interface,
                "position_ts":   _parse_ts(v.get("timestamp")),
                "lat":           v.get("lat"),
                "lon":           v.get("lon"),
                "course":        v.get("course"),
                "speed_og":      v.get("speed_og"),
                "outcome":       outcome,
                "orca_status":   orca_status,
                "orca_response": orca_response[:500] if orca_response else None,
                "error":         error[:1000] if error else None,
                "duration_ms":   duration_ms,
                "payload":       json.dumps(payload) if payload else None,
            }
            with get_db_transaction() as conn:
                conn.execute(_TABLE.insert().values(**record))
        except Exception as e:
            self._skip_until = time.monotonic() + _COOLDOWN_SECONDS
            logger.warning(
                f"Could not write sync log row, pausing datalab logging for "
                f"{_COOLDOWN_SECONDS}s | vessel={vessel} outcome={outcome} | error={e}"
            )
