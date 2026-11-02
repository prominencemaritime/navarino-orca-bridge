"""
Vessel position monitor.

Scans the bridge logs for confirmed ORCA POSTs and emails alerts when a vessel
has not reported a location for longer than the configured outage threshold,
plus a recovery email when a vessel in a declared outage reports again.

Run with:  python3 -m src.monitor [--run-once] [--dry-run]
"""
