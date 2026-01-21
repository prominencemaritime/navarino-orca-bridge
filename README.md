# Infinity-ORCA Bridge

A Python-based data bridge that synchronizes vessel tracking data from Infinity Web Services to the ORCA Vessel Tracking Service API.

## Overview

This bridge automates the process of:
1. Fetching vessel position data from Infinity Web Services (SOAP API)
2. Parsing XML responses into structured data
3. Transforming data into ORCA API format
4. Posting vessel positions to ORCA API

The system supports both live position updates and historical position synchronization for multiple vessels.

## Features

- ✅ **Multi-vessel support** - Track multiple vessels simultaneously
- ✅ **Live position sync** - Real-time vessel location updates
- ✅ **Historical sync** - Batch upload of position history
- ✅ **Internet connection tracking** - Captures active internet interface (e.g., Starlink, VSAT)
- ✅ **Comprehensive logging** - Detailed logs with file and line numbers
- ✅ **Dry run mode** - Test without posting to ORCA
- ✅ **Test/Live environments** - Separate ORCA endpoints for testing and production
- ✅ **Type safety** - Full type hints throughout codebase
- ✅ **Error handling** - Robust error handling with detailed logging

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
│   ├── __init__.py
│   ├── settings.py              # Configuration management with validation
│   └── logging_config.py        # Logging setup with file output
├── src/
│   ├── __init__.py
│   ├── clients/
│   │   ├── __init__.py
│   │   ├── infinity.py          # Infinity Web Services SOAP client
│   │   └── orca.py              # ORCA REST API client
│   ├── parsers/
│   │   ├── __init__.py
│   │   └── infinity_parser.py   # XML parser for Infinity responses
│   ├── transformers/
│   │   ├── __init__.py
│   │   └── orca_formatter.py    # Transform data to ORCA format
│   └── bridge.py                # Main orchestration logic
├── data/                        # XML/JSON output files (gitignored)
├── logs/                        # Log files (gitignored)
├── .env                         # Configuration (gitignored)
├── .env.example                 # Example configuration template
├── .gitignore
├── requirements.txt
├── test_infinity.py             # Test Infinity API connection
├── test_parser.py               # Test XML parsing
├── test_bridge.py               # Test complete bridge (dry run)
└── README.md
```

## Prerequisites

- Python 3.8+
- pip (Python package manager)
- Access credentials for:
  - Infinity Web Services (base URL + token)
  - ORCA API (base URL + API key)

## Installation

### 1. Clone the repository
```bash
git clone <repository-url>
cd infinity-orca-bridge
```

### 2. Create virtual environment (recommended)
```bash
python -m venv venv
source venv/bin/activate  # On macOS/Linux
# or
venv\Scripts\activate     # On Windows
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure environment variables
```bash
cp .env.example .env
vim .env  # Edit with your actual credentials
```

Required environment variables:
```bash
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

# Optional: Email alerts (leave empty to disable)
ENABLE_EMAIL_ALERT=False
SMTP_HOST=smtp.gmail.com
SMTP_PORT=465
SMTP_USER=your-email@gmail.com
SMTP_PASS=your-app-password
TO_RECIPIENTS=recipient@example.com
CC_RECIPIENTS=

# Scheduling
SYNC_INTERVAL_MINUTES=5
TIMEZONE=UTC

# Logging
LOG_LEVEL=INFO
LOG_FILE=bridge.log
REQUEST_TIMEOUT=30
DEBUG=False
```

## Usage

### Test Infinity Connection

Verify credentials and fetch sample data:
```bash
python test_infinity.py
```

This will:
- Test authentication with Infinity API
- Fetch live position, history, and interface data
- Save XML responses to `data/` directory

### Test Parser

Parse XML responses and format for ORCA:
```bash
python test_parser.py
```

This will:
- Parse all XML files in `data/` directory
- Show parsed position data
- Format data for ORCA API
- Save JSON files to `data/` directory

### Test Complete Bridge (Dry Run)

Test the complete pipeline without posting to ORCA:
```bash
python test_bridge.py
```

This will:
- Fetch data from Infinity
- Parse and format for ORCA
- Show what would be posted (dry run mode)
- NOT actually POST to ORCA

### Sync Live Data (Production)

**⚠️ WARNING: This will POST data to ORCA!**
```python
from config.settings import get_config
from src.clients.infinity import InfinityWebServiceClient
from src.clients.orca import ORCAClient
from src.bridge import InfinityORCABridge

cfg = get_config()

# Initialize clients
infinity = InfinityWebServiceClient(
    base_url=cfg.infinity_base_url,
    token=cfg.infinity_token,
    timeout=cfg.request_timeout
)

orca = ORCAClient(
    base_url=cfg.orca_base_url,
    api_key=cfg.orca_x_api_key,
    timeout=cfg.request_timeout
)

# Initialize bridge
bridge = InfinityORCABridge(infinity, orca)

# Sync all vessels (live positions only)
results = bridge.sync_all_vessels(
    vessel_identifiers=cfg.vessel_identifiers,
    sync_history=False,
    dry_run=False  # Set to True for dry run
)

print(results)
```

### Sync Historical Data
```python
# Sync historical positions for all vessels
results = bridge.sync_all_vessels(
    vessel_identifiers=cfg.vessel_identifiers,
    sync_history=True,
    dry_run=False
)
```

## API Reference

### Infinity Web Services Endpoints

The bridge uses the following Infinity endpoints:

1. **getLivePosition** - Current vessel position
   - Endpoint: `/pub/ws/positionsws.php`
   - Returns: Latest position with timestamp, lat/lon, course, speed

2. **getHistoryPositions** - Historical positions
   - Endpoint: `/pub/ws/positionsws.php`
   - Returns: Array of recent positions (typically 16-20 entries)

3. **getVesselsCurrentInterface** - Internet connection status
   - Endpoint: `/pub/ws/vesselsws.php`
   - Returns: Current interface profile (e.g., "Starlink", "VSAT")

### ORCA API Endpoints

1. **POST /data** - Save vessel measurements
   - Authentication: `x-api-key` header
   - Body: JSON with vessel IMO and position values
   - Response codes:
     - 200: Data saved successfully
     - 403: Authentication failed
     - 404: Vessel not found (check IMO)
     - 422: Invalid data format

2. **GET /data** - Retrieve vessel data (for debugging)
   - Parameters: `imo`, `dates[from]`, `dates[to]`

## Data Format

### ORCA Input Format
```json
{
  "data": [
    {
      "imo": 9509011,
      "values": [
        {
          "timestamp": "2026-01-21T17:25:53+00:00",
          "lat": 36.1422,
          "lon": -4.3229,
          "course": 269.0,
          "speed_og": 10.96,
          "internet_connection_status": "Starlink"
        }
      ]
    }
  ]
}
```

### Field Definitions

- `timestamp` (required): ISO 8601 format with timezone
- `lat` (required): Latitude, decimal degrees [-90, 90]
- `lon` (required): Longitude, decimal degrees [-180, 180]
- `course` (optional): Vessel heading, degrees [0, 360]
- `speed_og` (optional): Speed over ground, knots [>= 0]
- `internet_connection_status` (optional): Current connection type

## Logging

Logs are written to:
- **Console**: INFO level and above
- **File**: `logs/bridge.log` (all levels based on LOG_LEVEL)

Log format:
```
2026-01-21 19:39:30 | INFO     | filename.py:42 | Message here
```

View logs in real-time:
```bash
tail -f logs/bridge.log
```

## Configuration Management

The bridge uses a centralized configuration system with validation:

- **Settings class**: `config/settings.py`
- **Singleton pattern**: Configuration loaded once
- **Validation**: All settings validated on startup
- **Type safety**: Full type hints with dataclasses

### Adding New Vessels

Edit `.env`:
```bash
VESSEL_REF_CODE=vessel1,vessel2,vessel3
VESSEL_IMO=1234567,7654321,9876543
```

Order must match! Each ref code must have a corresponding IMO.

## Error Handling

The bridge handles errors at multiple levels:

1. **Configuration errors**: Validated at startup, fails fast
2. **Network errors**: Logged with retry suggestions
3. **Parse errors**: Logged, continues with next vessel
4. **ORCA errors**: HTTP status codes mapped to meaningful messages

Check logs for detailed error information.

## Testing

### Run All Tests
```bash
# Test Infinity connection
python test_infinity.py

# Test parser
python test_parser.py

# Test bridge (dry run)
python test_bridge.py
```

### Expected Test Flow

1. **test_infinity.py**: Verifies API credentials, saves XML samples
2. **test_parser.py**: Verifies XML parsing, creates ORCA JSON
3. **test_bridge.py**: Verifies end-to-end flow in dry run mode

## Troubleshooting

### Common Issues

**"Module not found" errors**
```bash
# Ensure you're in project root and venv is activated
source venv/bin/activate
pip install -r requirements.txt
```

**"Configuration validation failed"**
- Check all required variables in `.env`
- Verify VESSEL_REF_CODE and VESSEL_IMO have same number of entries

**"ORCA 403 Unauthorized"**
- Verify ORCA_X_API_KEY is correct
- Check header format (should be `x-api-key`, lowercase)

**"ORCA 404 Vessel not found"**
- Verify IMO number is registered in ORCA
- Check IMO format (should be integer, e.g., 9509011)

**"XML parse error"**
- Check Infinity API is returning valid XML
- Verify vessel ref code exists in Infinity

## Development

### Adding New Features

1. **New Infinity endpoint**:
   - Add method to `src/clients/infinity.py`
   - Add parser method to `src/parsers/infinity_parser.py`

2. **New data transformation**:
   - Add method to `src/transformers/orca_formatter.py`

3. **New sync mode**:
   - Add method to `src/bridge.py`

### Code Style

- Type hints on all functions
- Docstrings for all public methods
- Logging at appropriate levels (DEBUG, INFO, WARNING, ERROR)
- Error handling with try/except blocks

## Deployment

### Production Checklist

- [ ] Set `ORCA_TEST=False` in `.env`
- [ ] Verify ORCA live URL is correct
- [ ] Test with `dry_run=True` first
- [ ] Monitor logs during first live sync
- [ ] Set up automated scheduling (cron/systemd)
- [ ] Configure email alerts for errors

### Future Enhancements

- [ ] Docker containerization
- [ ] Automated scheduling with systemd timer
- [ ] Email notifications on sync errors
- [ ] Prometheus metrics for monitoring
- [ ] Historical data backfill with date range
- [ ] CLI tool for manual operations
- [ ] Web dashboard for monitoring

## License

[Your License Here]

## Support

For issues or questions:
- Check logs in `logs/bridge.log`
- Review test output from test scripts
- Contact: [Your Contact Info]

## Acknowledgments

- Infinity Web Services for vessel tracking data
- ORCA Vessel Tracking Service for data storage API
