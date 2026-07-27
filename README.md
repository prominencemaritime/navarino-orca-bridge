# Infinity-ORCA Bridge

A Python-based data bridge that synchronises vessel tracking data from Infinity Web Services to the ORCA Vessel Tracking Service API, running as a scheduled Docker service.

## Overview

This bridge automates the process of:
1. Fetching vessel position data from Infinity Web Services (SOAP API)
2. Parsing XML responses into structured data
3. Transforming data into ORCA API format
4. Posting vessel positions to ORCA API on a configurable schedule

The system supports both live position updates and historical position synchronisation for multiple vessels.

## Features

- **Multi-vessel support** - Track multiple vessels simultaneously
- **Live position sync** - Real-time vessel location updates
- **Historical sync** - Batch upload of position history
- **Scheduled execution** - Configurable sync interval via APScheduler
- **Comprehensive logging** - Detailed logs with file and line numbers, written to console and file
- **Dry run mode** - Test without posting to ORCA
- **Test/Live environments** - Separate ORCA endpoints for testing and production
- **Health monitoring** - Writes health status file for Docker healthcheck integration
- **Retry with backoff** - Automatic retry on network/server errors (3 attempts, exponential backoff)
- **Type safety** - Full type hints throughout codebase
- **Error handling** - Robust error handling with detailed logging

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    Infinity-ORCA Bridge                      │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  [Infinity API] ──→ [Parser] ──→ [Formatter] ──→ [ORCA API]  │
│                                                              │
│  SOAP/XML           Python        JSON            REST       │
│  • getLivePosition  • ElementTree • ORCA schema   • POST     │
│  • getHistory       • Type hints  • Validation    • GET      │
│  • getInterface     • Error check • Transform     • Auth     │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

## Project Structure

```
infinity-orca-bridge/
├── config/
│   ├── settings.py              # Configuration management with validation
│   └── logging_config.py        # Logging setup with file output
├── scripts/
│   ├── scheduler.py             # Production scheduler (primary entry point)
│   ├── sync_vessels.py          # Manual one-off sync script
│   ├── healthcheck.py           # Docker healthcheck script
│   ├── infinity_credentials_check.py  # Verify Infinity API credentials
│   └── verify_setup.py          # Verify full environment setup
├── src/
│   ├── __init__.py
│   ├── app.py                   # Application bootstrap (initialises all components)
│   ├── bridge.py                # Main orchestration logic
│   ├── clients/
│   │   ├── __init__.py
│   │   ├── infinity.py          # Infinity Web Services SOAP client
│   │   └── orca.py              # ORCA REST API client
│   ├── parsers/
│   │   ├── __init__.py
│   │   └── infinity_parser.py   # XML parser for Infinity responses
│   ├── transformers/
│   │   ├── __init__.py
│   │   └── orca_formatter.py    # Transform data to ORCA API format
│   └── utils/
│       ├── __init__.py
│       └── retry.py             # Retry decorator with exponential backoff
├── data/                        # XML/JSON output files (gitignored)
├── logs/                        # Log files (gitignored)
├── .env                         # Configuration (gitignored)
├── .env.example                 # Example configuration template
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── DEPLOYMENT.md
├── requirements.txt
├── test_bridge.py               # Test complete bridge pipeline
├── test_infinity.py             # Test Infinity API connection
├── test_orca_client.py          # Test ORCA client (GET + POST + verify)
├── test_parser.py               # Test XML parsing
└── README.md
```

## Prerequisites

- Docker and Docker Compose (recommended for all environments)
- Python 3.11+ (for local development without Docker)
- Access credentials for:
  - Infinity Web Services (base URL + token)
  - ORCA API (base URL + API key + Source ID + Organisation UUID)

## Installation

### 1. Clone the repository

```bash
git clone <repository-url>
cd infinity-orca-bridge
```

### 2. Configure environment variables

```bash
cp .env.example .env
vim .env  # Edit with your actual credentials
```

Required environment variables:

```bash
# Bridge Operation Mode
DRY_RUN=True                    # Always start with True; set False only after verification

# Infinity Web Services
INFINITY_BASE_URL=https://your-infinity-node.infinityfleet.net
INFINITY_TOKEN=your_infinity_token_here

# Vessel Configuration (comma-separated, order must match)
VESSEL_REF_CODE=vessel1,vessel2
VESSEL_IMO=1234567,7654321

# ORCA API
ORCA_TEST=True                                    # True for test, False for live
ORCA_BASE_URL_TEST=https://vts.orca.wtm.blue
ORCA_BASE_URL_LIVE=https://vts.orca.tools
ORCA_X_API_KEY=your_orca_api_key_here
ORCA_X_SOURCE=your_vts_source_id
ORCA_X_ORGANIZATION=your_organization_uuid

# Scheduling
SYNC_INTERVAL_MINUTES=5
TIMEZONE=UTC

# Logging
LOG_LEVEL=INFO
LOG_FILE=bridge.log
REQUEST_TIMEOUT=30
DEBUG=False
```

### 3. Start with Docker (recommended)

```bash
docker compose up -d
docker compose logs -f
```

The scheduler fires immediately on startup, then every `SYNC_INTERVAL_MINUTES`.

### 4. Local development (without Docker)

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python scripts/scheduler.py
```

## Usage

### Docker (primary workflow)

```bash
# Start the bridge
docker compose up -d

# Watch live logs
docker compose logs -f

# Run a test script inside the running container
docker compose exec navarino-orca-bridge python test_bridge.py

# Run a one-off command without disturbing the scheduler
docker compose run --rm navarino-orca-bridge python test_bridge.py

# Restart (also triggers an immediate sync cycle)
docker compose restart navarino-orca-bridge

# Stop
docker compose down
```

### Manual one-off sync

```bash
# With Docker
docker compose run --rm navarino-orca-bridge python scripts/sync_vessels.py

# Locally
python scripts/sync_vessels.py
```

This script includes safety prompts before posting to a live environment.

### Test scripts

```bash
# Test Infinity API connection (saves XML samples to data/)
python test_infinity.py

# Test XML parsing (reads from data/, outputs ORCA JSON)
python test_parser.py

# Test complete pipeline (dry run by default)
python test_bridge.py

# Test ORCA client: GET auth check, POST, then GET to verify
python test_orca_client.py
```

## API Reference

### Infinity Web Services Endpoints

The bridge uses the following Infinity endpoints:

1. **getLivePosition** - Current vessel position
   - Endpoint: `/pub/ws/positionsws.php`
   - Returns: Latest position with timestamp, lat/lon, course, speed

2. **getHistoryPositions** - Historical positions
   - Endpoint: `/pub/ws/positionsws.php`
   - Returns: Array of recent positions (typically 16 entries)

3. **getVesselsCurrentInterface** - Internet connection status
   - Endpoint: `/pub/ws/vesselsws.php`
   - Returns: Current interface profile (e.g., "Starlink", "VSAT")

### ORCA API Endpoints

Base URL: `https://vts.orca.tools` (live) / `https://vts.orca.wtm.blue` (test)

**Required headers on all requests:**

| Header | Description |
|---|---|
| `X-API-KEY` | API key |
| `X-Source` | VTS Source ID |
| `X-Organization` | Organisation UUID |

**POST /data** - Save vessel positions

| Response | Meaning |
|---|---|
| 200 | Data saved successfully |
| 422 | Invalid data format |

**GET /data** - Retrieve vessel data (for debugging)

Query parameters: `imo` (string), `dates[from]` (yyyy-mm-dd), `dates[to]` (yyyy-mm-dd)

Note: date range cannot exceed one month.

| Response | Meaning |
|---|---|
| 200 | Returns vessel_position and internet_connection_status arrays |
| 404 | Vessel not found |
| 422 | Invalid query parameters |

## Data Format

### ORCA POST Body

```json
{
  "data": [
    {
      "imo": "9509011",
      "values": [
        {
          "timestamp": "2026-01-21 17:25:53",
          "lat": 36.1422,
          "lon": -4.3229,
          "course": 269.0,
          "speed": 10.960
        }
      ]
    }
  ]
}
```

### Field Definitions

| Field | Type | Required | Notes |
|---|---|---|---|
| `imo` | string | yes | 7-digit IMO number as string |
| `timestamp` | string | yes | Format: `yyyy-mm-dd HH:MM:SS` (UTC, timezone ignored) |
| `lat` | float | nullable | Decimal degrees, range [-90, 90] |
| `lon` | float | nullable | Decimal degrees, range [-180, 180] |
| `course` | float | nullable | Degrees, range [0, 360] |
| `speed` | float | nullable | Speed over ground in knots, up to 3 decimal places |

### ORCA GET Response

```json
{
  "vessel_position": [
    {
      "timestamp": "2026-01-26 07:41:17",
      "lat": "-19.4",
      "lon": "56.433333",
      "rotation": "0",
      "estimated": false
    }
  ],
  "internet_connection_status": [
    {
      "timestamp": "2026-01-26 07:41:17",
      "value": "Online"
    }
  ]
}
```

## Logging

Logs are written to:
- **Console**: INFO level and above
- **File**: `logs/bridge.log` (level controlled by `LOG_LEVEL`)

Log format:
```
2026-01-21 19:39:30 | INFO     | filename.py:42   | Message here
```

View logs in real-time:
```bash
# Docker
docker compose logs -f

# Local
tail -f logs/bridge.log
```

## Configuration Reference

| Variable | Default | Description |
|---|---|---|
| `DRY_RUN` | `True` | If True, fetches and formats but does not POST to ORCA |
| `INFINITY_BASE_URL` | required | Infinity Web Services base URL |
| `INFINITY_TOKEN` | required | Infinity authentication token |
| `VESSEL_REF_CODE` | required | Comma-separated vessel ref codes |
| `VESSEL_IMO` | required | Comma-separated IMO numbers (must match order of ref codes) |
| `ORCA_TEST` | `True` | Use test URL if True, live URL if False |
| `ORCA_BASE_URL_TEST` | required | ORCA test environment URL |
| `ORCA_BASE_URL_LIVE` | required | ORCA live environment URL |
| `ORCA_X_API_KEY` | required | ORCA API key |
| `ORCA_X_SOURCE` | required | VTS Source ID |
| `ORCA_X_ORGANIZATION` | required | Organisation UUID |
| `SYNC_INTERVAL_MINUTES` | `5` | How often the scheduler runs a sync cycle |
| `TIMEZONE` | `UTC` | Scheduler timezone |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `LOG_FILE` | `bridge.log` | Log filename within the logs/ directory |
| `REQUEST_TIMEOUT` | `30` | HTTP request timeout in seconds |
| `DEBUG` | `False` | Enable debug mode |

### Adding New Vessels

Edit `.env`:

```bash
VESSEL_REF_CODE=vessel1,vessel2,vessel3
VESSEL_IMO=1234567,7654321,9876543
```

Order must match. Each ref code must have a corresponding IMO. Restart the container after changes.

## Error Handling

Errors are handled at multiple levels:

1. **Configuration errors**: Validated at startup, fails fast with a clear message
2. **Network errors**: Retried up to 3 times with exponential backoff (1s, 2s, 4s)
3. **Parse errors**: Logged, continues with next vessel
4. **ORCA 4xx errors**: Not retried (auth/validation failures); logged with status code
5. **ORCA 5xx errors**: Retried with backoff
6. **Health status**: Written to `logs/health_status.txt` after each sync cycle (`OK` or `ERROR`)

## Troubleshooting

**Container crashes on startup with `UndefinedValueError`**
- A required variable is missing from `.env`
- Check the error message for the variable name and add it to `.env`
- Ensure `docker-compose.yml` passes the variable to the container

**Infinity `ReadTimeout` errors**
- The Infinity server accepted the connection but did not respond within `REQUEST_TIMEOUT` seconds
- Usually indicates the vessel has lost satellite connectivity (Starlink/VSAT)
- The bridge will retry automatically on the next scheduled cycle
- Verify vessel status in the Infinity web portal

**ORCA `422 Unprocessable`**
- Validate the POST payload format against the Data Format section above
- Common causes: `imo` sent as integer instead of string, invalid timestamp format, out-of-range lat/lon
- Run `test_bridge.py` with `DRY_RUN=True` to inspect the formatted payload before posting

**ORCA auth failure**
- Verify `ORCA_X_API_KEY`, `ORCA_X_SOURCE`, and `ORCA_X_ORGANIZATION` are all set correctly
- Headers must be `X-API-KEY`, `X-Source`, `X-Organization` (case as shown)

**`VESSEL_REF_CODE` and `VESSEL_IMO` mismatch**
- Both variables must have the same number of comma-separated entries
- The bridge fails fast at startup with a clear error if they do not match

**Logs show `Operation: DRY RUN` but you expected live posting**
- Set `DRY_RUN=False` in `.env` and restart the container

## Development

### Adding New Vessels

Edit `.env` and restart the container. No code changes required.

### Adding a New Infinity Endpoint

1. Add a method to `src/clients/infinity.py`
2. Add a parser method to `src/parsers/infinity_parser.py`
3. Call it from `src/bridge.py` in the appropriate sync method

### Adding a New Data Field to ORCA Output

1. Confirm the field is accepted by the ORCA API
2. Parse it in `src/parsers/infinity_parser.py` and add it to the position dict
3. Include it in the value dict in `src/transformers/orca_formatter.py`

### Code Style

- Type hints on all functions
- Docstrings on all public methods
- Logging at appropriate levels (DEBUG, INFO, WARNING, ERROR)
- All exceptions caught with try/except and logged

## Deployment

### Production Checklist

- [ ] Set `DRY_RUN=False` in `.env`
- [ ] Set `ORCA_TEST=False` in `.env`
- [ ] Verify all three ORCA credentials are set (`X_API_KEY`, `X_SOURCE`, `X_ORGANIZATION`)
- [ ] Confirm IMO numbers are registered in ORCA
- [ ] Run one cycle with `DRY_RUN=True` and inspect the payload in logs
- [ ] Monitor logs during first live sync cycle
- [x] Docker containerisation complete
- [x] Health monitoring configured (via `logs/health_status.txt`)

### Future Enhancements

- [ ] Email notifications on sync errors
- [ ] Prometheus metrics for monitoring
- [ ] Historical data backfill with configurable date range
- [ ] CLI tool for manual operations
- [ ] Web dashboard for monitoring

## License

[Your License Here]

## Support

For issues:
- Check `logs/bridge.log` or `docker compose logs`
- Check `logs/health_status.txt` for last sync status
- Run `python scripts/verify_setup.py` to check environment configuration
- Contact: [Your Contact Info]

## Acknowledgments

- Infinity Web Services for vessel tracking data
- ORCA Vessel Tracking Service for data storage API
