# Navarino ORCA Bridge

A Python service that synchronises vessel positions from Infinity Web Services to the ORCA Vessel Tracking Service API, runs on a schedule in Docker, records every sync attempt in the datalab, and emails an alert when a vessel stops reporting.

## Overview

The project runs two Docker services:

1. **`navarino-orca-bridge`**: every `SYNC_INTERVAL_MINUTES` it
   1. fetches each vessel's live position and interface status from Infinity Web Services (SOAP/XML),
   2. parses the XML and transforms it into the ORCA format,
   3. POSTs the position to the ORCA API,
   4. optionally writes one row per attempt to the datalab table `external.vessel_position_sync_log`.
2. **`vessel-monitor`**: on its own schedule it reads `logs/bridge.log` and emails:
   - an **outage alert** when a vessel has had no ORCA-confirmed location for longer than a threshold (default 24 hours), repeated every 24 hours while the outage lasts;
   - a **recovery email** (`AlertDev | <vessel> API Online`) when that vessel reports again;
   - optionally, a technical email when bridge log lines cannot be parsed.

Short interruptions that recover within the threshold never trigger an email.

## Features

- **Multi-vessel support**: vessels and their Infinity credentials are defined in `vessels.yaml`
- **Live position sync** every 5 minutes (configurable), plus manual historical sync
- **Datalab sync log** (optional): one row per sync attempt in PostgreSQL, using IAM authentication
- **Vessel outage alerts** by email, with recovery notifications and configurable thresholds
- **Dry run modes** for both the bridge (no ORCA POST) and the monitor (no email, or redirect to a test address)
- **Test/Live ORCA environments**
- **Docker healthchecks** for both services
- **Retry with backoff** on network/server errors (3 attempts, exponential backoff)
- **UTC logging** with file and line numbers, to console and file

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│ navarino-orca-bridge                                                 │
│                                                                      │
│  [Infinity API] ──→ [Parser] ──→ [Formatter] ──→ [ORCA API]          │
│   SOAP/XML           XML          ORCA JSON       REST POST          │
│                                        │                             │
│                                        ├──→ logs/bridge.log          │
│                                        └──→ datalab sync log (opt.)  │
└──────────────────────────────────────────────────────────────────────┘
                         │ logs/ (read-only mount)
                         ▼
┌──────────────────────────────────────────────────────────────────────┐
│ vessel-monitor                                                       │
│                                                                      │
│  [bridge.log] ──→ [Log scanner] ──→ [Alert state] ──→ [SMTP email]   │
│                    confirmed POSTs   monitor/          outage /      │
│                    per vessel        monitor_state     recovery      │
└──────────────────────────────────────────────────────────────────────┘
```

## Project Structure

```
navarino-orca-bridge/
├── config/
│   ├── settings.py                  # Bridge configuration and validation
│   └── logging_config.py            # Logging setup (UTC timestamps)
├── scripts/
│   ├── scheduler.py                 # Bridge entry point (Docker CMD)
│   ├── sync_vessels.py              # Manual one-off sync
│   ├── healthcheck.py               # Bridge Docker healthcheck
│   ├── monitor_healthcheck.py       # Vessel-monitor Docker healthcheck
│   ├── check_recent_posts.py        # Manual vessel status check from bridge.log
│   ├── infinity_credentials_check.py
│   └── verify_setup.py
├── src/
│   ├── app.py                       # Bridge bootstrap
│   ├── bridge.py                    # Sync orchestration
│   ├── clients/
│   │   ├── infinity.py              # Infinity SOAP client
│   │   └── orca.py                  # ORCA REST client
│   ├── db/
│   │   ├── datalab.py               # Datalab connection (IAM auth, verify-full SSL)
│   │   └── sync_log.py              # Writer for external.vessel_position_sync_log
│   ├── monitor/                     # Vessel monitor (python3 -m src.monitor)
│   │   ├── __main__.py              # Entry point
│   │   ├── config.py                # MONITOR_* settings
│   │   ├── log_scanner.py           # Finds ORCA-confirmed POSTs in bridge.log
│   │   ├── monitor.py               # Alert rules (outage, repeat, recovery, parse issues)
│   │   ├── state.py                 # Persisted alert state
│   │   ├── formatting.py            # Email text and HTML
│   │   ├── email_sender.py          # SMTP sender
│   │   ├── scheduler.py             # Interval or fixed-time scheduling
│   │   └── vessels.py               # Reads ref_code/IMO from vessels.yaml
│   ├── parsers/infinity_parser.py
│   ├── transformers/orca_formatter.py
│   └── utils/retry.py
├── sql/ddl/                         # Datalab table and index DDL
├── media/triton_logo.png            # Logo embedded in alert emails
├── logs/                            # bridge.log, health_status.txt (gitignored)
├── monitor/                         # Monitor state, health and log (gitignored)
├── data/                            # XML/JSON samples (gitignored)
├── vessels.yaml                     # Vessel list and Infinity credentials (gitignored)
├── vessels.yaml.example
├── .env / .env.example
├── Dockerfile
├── docker-compose.yml
├── DEPLOYMENT.md
├── requirements.txt
└── test_*.py                        # Manual test scripts
```

## Prerequisites

- Docker and Docker Compose v2
- Python 3.13 (for local development without Docker)
- Credentials for:
  - Infinity Web Services (per vessel, in `vessels.yaml`)
  - ORCA API (API key, Source ID, Organisation UUID)
  - SMTP account for alert emails
- For the datalab sync log: an EC2 instance role allowed `rds-db:connect` as the database user, and the RDS CA bundle on the host

## Installation

### 1. Clone the repository

```bash
git clone git@github.com:prominencemaritime/navarino-orca-bridge.git
cd navarino-orca-bridge
```

### 2. Configure vessels

```bash
cp vessels.yaml.example vessels.yaml
vim vessels.yaml
```

```yaml
vessels:
  - ref_code: mountfu
    imo: "9509011"
    infinity_base_url: https://node1.infinityfleet.net
    infinity_token: token_for_mountfu
```

### 3. Configure environment variables

```bash
cp .env.example .env
vim .env
```

Both services load `.env` through `env_file` in `docker-compose.yml`. Keep one setting per line, without inline comments. See the Configuration Reference below.

### 4. Start with Docker

```bash
docker compose up -d --build
docker compose ps        # both services should become "healthy" within a few minutes
docker compose logs -f
```

The bridge syncs immediately on startup, then every `SYNC_INTERVAL_MINUTES`. The monitor runs its first check immediately, then on its schedule.

### 5. Local development (without Docker)

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 scripts/scheduler.py          # bridge
python3 -m src.monitor --run-once     # one monitor check
```

## Usage

### Docker

```bash
docker compose up -d --build                    # build and start both services
docker compose logs -f navarino-orca-bridge     # bridge logs
docker compose logs -f vessel-monitor           # monitor logs
docker compose restart navarino-orca-bridge     # restart (triggers an immediate sync)
docker compose up -d --force-recreate <service> # reload .env for a service
docker compose down
```

Code and scripts are built into the image: after `git pull`, use `--build`. Changes to `.env` need `--force-recreate`; `restart` does not reload `.env`.

### Check vessel reporting status by hand

```bash
# On the server
docker compose exec vessel-monitor python3 scripts/check_recent_posts.py

# Locally, against a copy of the server log
scp ubuntu@<server>:/srv/repos/navarino-orca-bridge/logs/bridge.log logs/
python3 scripts/check_recent_posts.py --tz Europe/Athens

# Options
python3 scripts/check_recent_posts.py --hours 12 --basis post --tz Europe/Athens
```

Exit codes: `0` all vessels reporting, `1` at least one vessel STALE or MISSING, `2` incomplete check (log parse/read problems).

### Manual one-off sync

```bash
docker compose run --rm navarino-orca-bridge python scripts/sync_vessels.py
```

This script includes safety prompts before posting to a live environment.

### Test scripts

```bash
python test_infinity.py        # Infinity connection (saves XML samples to data/)
python test_parser.py          # XML parsing
python test_bridge.py          # full pipeline (dry run by default)
python test_orca_client.py     # ORCA GET/POST/verify
```

## Vessel Monitor

### How a vessel's status is decided

The monitor reads `logs/bridge.log*` and counts a position only when its `POST payload:` line is followed by ORCA's `Data saved successfully to ORCA` line. Failed or rejected POSTs do not count. The age of each vessel's latest confirmed position is compared with `MONITOR_OUTAGE_THRESHOLD_HOURS`:

| Status | Meaning |
|---|---|
| `OK` | Latest confirmed position is within the threshold |
| `STALE` | Latest confirmed position is older than the threshold |
| `MISSING` | No confirmed position anywhere in logs covering at least the threshold |
| `PENDING` | No confirmed position yet, but the logs are younger than the threshold (not alerted) |

By default age is measured from the position timestamp inside the payload (`MONITOR_STALENESS_BASIS=position`), so a vessel whose Infinity position stops updating is caught even if the bridge keeps posting it. Set `post` to measure from the POST time instead.

### Emails

| Email | When | Subject |
|---|---|---|
| Outage digest | A vessel becomes STALE/MISSING; repeated every `MONITOR_ALERT_REPEAT_HOURS` while any vessel stays in that state | `AlertDev \| "agistri, odessaf" Not Reporting Locations` |
| Recovery | A vessel in a declared outage reports again (one email per vessel) | `AlertDev \| agistri API Online` |
| Parse issues | Bridge log lines within the threshold window cannot be parsed (if enabled) | `AlertDev \| Vessel Monitor: N Log Parse Issues` |

Alert state is stored in `monitor/monitor_state.json`, keyed by IMO, so renaming a vessel's `ref_code` keeps its history. State is only updated after an email is actually sent, so a failed SMTP attempt is retried on the next check.

### Testing alerts

```bash
# Force an outage email to the dry-run address (1-minute threshold, throwaway state)
docker compose run --rm -e MONITOR_DRY_RUN=True \
  -e MONITOR_OUTAGE_THRESHOLD_HOURS=0.0167 -e MONITOR_STATE_DIR=/tmp/t \
  vessel-monitor python3 -m src.monitor --run-once
```

With `MONITOR_DRY_RUN=True` and `MONITOR_DRY_RUN_EMAIL` set, emails go only to that address with a `[DRY-RUN]` subject prefix. With `MONITOR_DRY_RUN_EMAIL` empty, no email is sent at all.

## Datalab Sync Log

When `SYNC_LOG_ENABLED=True`, the bridge writes one row per sync attempt to `external.vessel_position_sync_log` (outcome `posted`, `fetch_failed`, `parse_failed` or `post_failed`, with position, ORCA status and timing). A datalab problem never stops a position from reaching ORCA: write failures are logged and datalab writes pause for 2 minutes.

Setup, done once:

1. Run `sql/ddl/vessel_position_sync_log.sql` and `sql/ddl/vessel_position_sync_log_index.sql` as a database admin.
2. Grant the database user:
   ```sql
   GRANT USAGE  ON SCHEMA external TO data;
   GRANT INSERT ON external.vessel_position_sync_log TO data;
   GRANT USAGE  ON SEQUENCE external.vessel_position_sync_log_id_seq TO data;
   ```
3. Allow the server's IAM role `rds-db:connect` on `arn:aws:rds-db:<region>:<account>:dbuser:<DbiResourceId>/data`.
4. Place the RDS CA bundle at `/etc/ssl/certs/aws-global-bundle.pem` on the host (mounted read-only into the bridge container):
   ```bash
   sudo curl -fsSL -o /etc/ssl/certs/aws-global-bundle.pem \
     https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem
   ```
5. Set the `DB_DATALAB_*` variables and `SYNC_LOG_ENABLED=True`, then `docker compose up -d --force-recreate navarino-orca-bridge`.

Startup logs `Sync log ENABLED | external.vessel_position_sync_log` when the connection works.

## Health Checks

| Container | Unhealthy when | Not unhealthy for |
|---|---|---|
| `navarino-orca-bridge` | No sync cycle has completed for `HEALTHCHECK_MAX_AGE_MINUTES` (default 60), i.e. the bridge is hung or stopped | Individual or repeated vessel sync errors |
| `vessel-monitor` | Its scheduler heartbeat is over 15 minutes old, or its last check failed (e.g. an email could not be sent) | Vessel outages (those produce an email) |

A sync cycle is one run of the bridge's scheduled job: all vessels are processed, then `logs/health_status.txt` is rewritten with `OK` or `ERROR`. Vessels that stop reporting are handled by the vessel monitor, not the healthcheck.

```bash
docker compose exec navarino-orca-bridge python3 scripts/healthcheck.py
docker compose exec vessel-monitor python3 scripts/monitor_healthcheck.py
```

## Logging

- **Bridge**: console and `logs/bridge.log`
- **Monitor**: console and `monitor/monitor.log` (rotated at 10 MB, 5 backups)

All timestamps are UTC:
```
2026-11-02 13:03:07 | INFO     | bridge.py:226  | ✓ Successfully synced vessel mountfu
```

The vessel monitor parses the bridge's `POST payload:` and `Data saved successfully to ORCA` lines in `src/clients/orca.py`. Do not change their text or lower their level below INFO.

## Configuration Reference

### Bridge

| Variable | Default | Description |
|---|---|---|
| `DRY_RUN` | `True` | If True, fetches and formats but does not POST to ORCA |
| `ORCA_TEST` | `True` | Use the test URL if True, live URL if False |
| `ORCA_BASE_URL_TEST` | required | ORCA test environment URL |
| `ORCA_BASE_URL_LIVE` | required | ORCA live environment URL |
| `ORCA_X_API_KEY` | required | ORCA API key |
| `ORCA_X_SOURCE` | required | VTS Source ID |
| `ORCA_X_ORGANIZATION` | required | Organisation UUID |
| `SYNC_INTERVAL_MINUTES` | `5` | Minutes between sync cycles |
| `TIMEZONE` | `UTC` | Bridge scheduler timezone |
| `LOG_LEVEL` | `INFO` | DEBUG, INFO, WARNING, ERROR |
| `LOG_FILE` | `bridge.log` | Log filename within `logs/` |
| `REQUEST_TIMEOUT` | `30` | HTTP request timeout in seconds |
| `DEBUG` | `False` | Debug mode |
| `HEALTHCHECK_MAX_AGE_MINUTES` | `60` | Bridge is unhealthy if no sync cycle completed within this time |

Vessels are configured in `vessels.yaml`, not `.env`.

### Datalab sync log

| Variable | Default | Description |
|---|---|---|
| `SYNC_LOG_ENABLED` | `False` | Write one row per sync attempt to the datalab |
| `DB_DATALAB_HOST` | required if enabled | RDS endpoint |
| `DB_DATALAB_PORT` | required if enabled | Usually `5432` |
| `DB_DATALAB_NAME` | required if enabled | Database name |
| `DB_DATALAB_USER` | required if enabled | IAM-enabled database user |
| `DB_DATALAB_REGION` | required if enabled | AWS region, e.g. `eu-west-1` |
| `DB_DATALAB_SSL_CERT` | required if enabled | Path to the RDS CA bundle inside the container |
| `DB_DATALAB_CONNECT_TIMEOUT` | `5` | Connection timeout in seconds |
| `DB_DATALAB_STATEMENT_TIMEOUT_MS` | `5000` | Statement timeout in milliseconds |

### Vessel monitor

| Variable | Default | Description |
|---|---|---|
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS` | port `465` | Mail server (465 = SSL, otherwise STARTTLS) |
| `MONITOR_ALERT_RECIPIENTS` | required when live | Comma-separated TO addresses |
| `MONITOR_ALERT_CC_RECIPIENTS` | empty | Comma-separated CC addresses |
| `MONITOR_PARSE_ERROR_RECIPIENTS` | alert recipients | Addresses for parse-issue emails |
| `MONITOR_ENABLE_EMAIL_ALERTS` | `True` | Master switch for all monitor emails |
| `MONITOR_ENABLE_PARSE_ERROR_ALERTS` | `True` | Send parse-issue emails |
| `MONITOR_DRY_RUN` | `True` | No real recipients; see `MONITOR_DRY_RUN_EMAIL` |
| `MONITOR_DRY_RUN_EMAIL` | empty | In dry run, redirect emails here (empty = send nothing) |
| `MONITOR_OUTAGE_THRESHOLD_HOURS` | `24` | Hours without a confirmed position before a vessel is in outage |
| `MONITOR_ALERT_REPEAT_HOURS` | `24` | Repeat interval for outage and parse-issue emails |
| `MONITOR_STALENESS_BASIS` | `position` | `position` (payload timestamp) or `post` (POST time) |
| `MONITOR_SCHEDULE_FREQUENCY_HOURS` | empty | Check every N hours (takes precedence over fixed times) |
| `MONITOR_SCHEDULE_TIMES` | empty | Fixed check times, e.g. `08:00,20:00` |
| `MONITOR_SCHEDULE_DAYS` | every day | ISO weekdays for fixed times: 1=Mon … 7=Sun |
| `MONITOR_SCHEDULE_TIMES_TIMEZONE` | `Europe/Athens` | Timezone for fixed check times |
| `MONITOR_DISPLAY_TIMEZONE` | `UTC` | Timezone shown in emails |
| `MONITOR_LOGO` | `triton_logo.png` | Logo file in `media/` |
| `MONITOR_LOG_LEVEL` | `INFO` | Monitor log level |

One of `MONITOR_SCHEDULE_FREQUENCY_HOURS` or `MONITOR_SCHEDULE_TIMES` must be set.

## Adding or Renaming Vessels

1. Edit `vessels.yaml` (`ref_code`, `imo`, `infinity_base_url`, `infinity_token`).
2. Restart the bridge: `docker compose restart navarino-orca-bridge`.

The monitor rereads `vessels.yaml` on every check, so it needs no restart. A newly added vessel shows as `PENDING` until it has reported once.

## Error Handling

1. **Configuration errors**: validated at startup; the service fails fast with a clear message
2. **Network errors**: retried up to 3 times with exponential backoff (1s, 2s, 4s)
3. **Parse errors**: logged; the bridge continues with the next vessel
4. **ORCA 4xx errors**: not retried (auth/validation failures), logged with status code
5. **ORCA 5xx errors**: retried with backoff
6. **Datalab errors**: logged; never block the ORCA POST; writes pause for 2 minutes
7. **Vessels not reporting**: emailed by the vessel monitor after the outage threshold

## Troubleshooting

**Container crashes on startup with `UndefinedValueError`**
- A required variable is missing from `.env`; add it, then `docker compose up -d --force-recreate <service>`

**Infinity `ReadTimeout` errors**
- The vessel has probably lost satellite connectivity; the bridge retries on the next cycle
- If it lasts beyond the outage threshold, the vessel monitor emails

**ORCA `422 Unprocessable`**
- Check the payload format (Data Format below); common causes are `imo` sent as an integer, a bad timestamp or out-of-range lat/lon

**ORCA auth failure**
- Check `ORCA_X_API_KEY`, `ORCA_X_SOURCE` and `ORCA_X_ORGANIZATION`

**`Sync log enabled but datalab is unreachable at startup`**
- `root certificate file ... does not exist`: the CA bundle is missing on the host or not mounted
- `PAM authentication failed for user "data"`: the server's IAM role lacks `rds-db:connect` for that database user
- `permission denied` / `relation does not exist`: grants or table missing (see Datalab Sync Log)

**Vessel monitor: `Invalid monitor configuration`**
- The message lists each invalid `MONITOR_*` setting; fix them and recreate the container

**No outage email although a vessel is down**
- Check `docker compose logs vessel-monitor` for the vessel's status and age
- Emails are only sent once the age exceeds `MONITOR_OUTAGE_THRESHOLD_HOURS`
- Confirm `MONITOR_DRY_RUN=False` and that the server can reach the SMTP host (`nc -vz -w 5 <SMTP_HOST> 465`)

**`no permission to read ... monitor/monitor_state.json` during build**
- `.dockerignore` must exclude `/monitor`, `/logs` and `/state`

## Data Format

### ORCA POST Body

```json
{
  "data": [
    {
      "imo": "9509011",
      "values": [
        {
          "timestamp": "2026-10-30 08:08:46",
          "lat": 11.7858,
          "lon": 113.2714,
          "course": 44.0,
          "speed_og": 11.3
        }
      ]
    }
  ]
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `imo` | string | yes | 7-digit IMO number as a string |
| `timestamp` | string | yes | `yyyy-mm-dd HH:MM:SS`, UTC |
| `lat` | float | nullable | Decimal degrees, [-90, 90] |
| `lon` | float | nullable | Decimal degrees, [-180, 180] |
| `course` | float | nullable | Degrees, [0, 360] |
| `speed_og` | float | nullable | Speed over ground in knots |

### ORCA API

Base URL: `https://vts.orca.tools` (live) / `https://vts.orca.wtm.blue` (test). Required headers: `X-API-KEY`, `X-Source`, `X-Organization`.

- **POST /data**: save positions (`200` saved, `422` invalid data)
- **GET /data**: query parameters `imo`, `dates[from]`, `dates[to]` (yyyy-mm-dd, range at most one month); `200` returns `vessel_position` and `internet_connection_status`, `404` vessel not found

### Infinity Web Services

- **getLivePosition** (`/pub/ws/positionsws.php`): latest position
- **getHistoryPositions** (`/pub/ws/positionsws.php`): recent positions (typically 16)
- **getVesselsCurrentInterface** (`/pub/ws/vesselsws.php`): current connection profile (e.g. Starlink, VSAT)

## Development

### Adding a New Infinity Endpoint

1. Add a method to `src/clients/infinity.py`
2. Add a parser method to `src/parsers/infinity_parser.py`
3. Call it from `src/bridge.py`

### Adding a New Data Field to ORCA Output

1. Confirm the field is accepted by the ORCA API
2. Parse it in `src/parsers/infinity_parser.py`
3. Include it in `src/transformers/orca_formatter.py`

### Code Style

- Type hints and docstrings on public functions
- Logging at appropriate levels
- Errors caught and logged; optional integrations (datalab, email) never block the ORCA sync

## Deployment

See `DEPLOYMENT.md`. Typical update on the server:

```bash
cd /srv/repos/navarino-orca-bridge
git status                     # must be clean
git pull
docker compose up -d --build
docker compose ps
```

### Production Checklist

- [x] `DRY_RUN=False`, `ORCA_TEST=False`
- [x] Docker containerisation and healthchecks
- [x] Datalab sync log
- [x] Vessel outage and recovery email alerts
- [ ] Log rotation for `bridge.log` (the monitor already reads rotated `bridge.log.1` and `.gz` files)

### Future Enhancements

- [ ] Log rotation for `bridge.log`
- [ ] Datalab rows for historical syncs
- [ ] Prometheus metrics
- [ ] Historical backfill with a configurable date range

## Support

- `docker compose logs navarino-orca-bridge` / `docker compose logs vessel-monitor`
- `python3 scripts/check_recent_posts.py` for current vessel status
- `logs/health_status.txt` for the last sync cycle result
- `python scripts/verify_setup.py` to check environment configuration

Last update: 2026-11-02
