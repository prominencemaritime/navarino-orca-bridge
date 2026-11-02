# src/monitor/vessels.py
"""Load the vessel list (ref_code -> IMO) from vessels.yaml."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict
from urllib.parse import urlparse

import yaml

# Matches InfinityORCABridge.PROVIDER; override per vessel with 'provider:' in vessels.yaml.
DEFAULT_PROVIDER = "navarino_infinity"


@dataclass(frozen=True)
class VesselInfo:
    provider: str
    source_host: str


def load_vessels(path: Path) -> Dict[str, str]:
    """
    Return an ordered mapping of ref_code -> IMO from vessels.yaml.

    Only 'ref_code' and 'imo' are read; Infinity credentials are ignored, so the
    monitor never needs them.

    Raises:
        FileNotFoundError: vessels.yaml is missing
        ValueError: the file is malformed, empty, or has an invalid/duplicate entry
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Vessel file not found: {path}")

    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}

    entries = data.get("vessels") if isinstance(data, dict) else None
    if not isinstance(entries, list) or not entries:
        raise ValueError(f"No vessels defined in {path}")

    vessels: Dict[str, str] = {}
    seen_imos = set()

    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict) or "ref_code" not in entry or "imo" not in entry:
            raise ValueError(f"{path}: vessel #{index} needs both 'ref_code' and 'imo'")

        ref_code = str(entry["ref_code"]).strip()
        imo = str(entry["imo"]).strip()

        if not ref_code:
            raise ValueError(f"{path}: vessel #{index} has an empty ref_code")
        if not (imo.isdigit() and len(imo) == 7):
            raise ValueError(f"{path}: invalid IMO '{imo}' for vessel '{ref_code}'")
        if ref_code in vessels or imo in seen_imos:
            raise ValueError(f"{path}: duplicate vessel '{ref_code}' / IMO {imo}")

        vessels[ref_code] = imo
        seen_imos.add(imo)

    return vessels


def load_vessel_details(path: Path) -> Dict[str, VesselInfo]:
    """
    Return IMO -> provider and source host, for display in alerts.

    source_host is the hostname of infinity_base_url, matching the source_host
    column of the datalab sync log. Missing optional fields give "".
    """
    with Path(path).open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}

    entries = data.get("vessels") if isinstance(data, dict) else None
    details: Dict[str, VesselInfo] = {}
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict) or "imo" not in entry:
            continue
        url = str(entry.get("infinity_base_url") or "")
        details[str(entry["imo"]).strip()] = VesselInfo(
            provider=str(entry.get("provider") or DEFAULT_PROVIDER).strip(),
            source_host=urlparse(url).hostname or "",
        )
    return details
