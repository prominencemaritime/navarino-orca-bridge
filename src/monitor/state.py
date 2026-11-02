# src/monitor/state.py
"""
Persisted monitor state.

Records which vessels are in a declared outage (so a recovery email is only sent
after a real outage) and when the last outage / parse-issue emails went out (so
they repeat every MONITOR_ALERT_REPEAT_HOURS rather than every run).

Vessels are keyed by IMO, so a ref_code rename in vessels.yaml (e.g. agistrifx ->
agistri) keeps its state.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


def _to_iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value is not None else None


def _from_iso(value: Optional[str]) -> Optional[datetime]:
    return datetime.fromisoformat(value) if value else None


@dataclass
class VesselState:
    ref_code: str
    in_outage: bool = False
    outage_declared_at: Optional[datetime] = None
    last_seen_before_outage: Optional[datetime] = None

    def clear_outage(self) -> None:
        self.in_outage = False
        self.outage_declared_at = None
        self.last_seen_before_outage = None


@dataclass
class MonitorState:
    vessels: Dict[str, VesselState] = field(default_factory=dict)   # IMO -> state
    last_outage_alert_at: Optional[datetime] = None
    last_parse_alert_at: Optional[datetime] = None

    def vessel(self, imo: str, ref_code: str) -> VesselState:
        """Return the state for an IMO, creating it if needed and following renames."""
        state = self.vessels.get(imo)
        if state is None:
            state = self.vessels[imo] = VesselState(ref_code=ref_code)
        elif state.ref_code != ref_code:
            logger.info(f"Vessel IMO {imo} renamed: {state.ref_code} -> {ref_code}")
            state.ref_code = ref_code
        return state


class StateStore:
    """Load and atomically save MonitorState as JSON."""

    def __init__(self, path: Path):
        self.path = Path(path)

    def load(self) -> MonitorState:
        if not self.path.exists():
            logger.info(f"No state file at {self.path}; starting fresh")
            return MonitorState()

        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            vessels = {
                str(imo): VesselState(
                    ref_code=str(data.get("ref_code", "")),
                    in_outage=bool(data.get("in_outage", False)),
                    outage_declared_at=_from_iso(data.get("outage_declared_at")),
                    last_seen_before_outage=_from_iso(data.get("last_seen_before_outage")),
                )
                for imo, data in raw.get("vessels", {}).items()
            }
            return MonitorState(
                vessels=vessels,
                last_outage_alert_at=_from_iso(raw.get("last_outage_alert_at")),
                last_parse_alert_at=_from_iso(raw.get("last_parse_alert_at")),
            )
        except (OSError, ValueError, TypeError, AttributeError) as exc:
            backup = self.path.with_name(self.path.name + ".corrupt")
            logger.error(
                f"Unreadable state file {self.path} ({exc}); moving it to {backup.name} "
                "and starting fresh"
            )
            try:
                self.path.replace(backup)
            except OSError as move_exc:
                logger.error(f"Could not move corrupt state file: {move_exc}")
            return MonitorState()

    def save(self, state: MonitorState) -> None:
        data = {
            "vessels": {
                imo: {
                    "ref_code": v.ref_code,
                    "in_outage": v.in_outage,
                    "outage_declared_at": _to_iso(v.outage_declared_at),
                    "last_seen_before_outage": _to_iso(v.last_seen_before_outage),
                }
                for imo, v in sorted(state.vessels.items())
            },
            "last_outage_alert_at": _to_iso(state.last_outage_alert_at),
            "last_parse_alert_at": _to_iso(state.last_parse_alert_at),
        }

        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(
            dir=self.path.parent, prefix=f".{self.path.name}.", suffix=".tmp"
        )
        try:
            os.fchmod(fd, 0o644)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
                fh.write("\n")
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(temp_path, self.path)
        except BaseException:
            Path(temp_path).unlink(missing_ok=True)
            raise
