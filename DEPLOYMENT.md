# Navarino ORCA Bridge - Deployment Guide

## Ubuntu Server Deployment

### Prerequisites
- Docker and Docker Compose installed
- SSH access to server
- Health Monitor running at `/srv/repos/_docker_monitoring/`

### Deployment Steps

1. **Clone repository:**
```bash
   cd /srv/repos/
   git clone <repo-url> navarino-orca-bridge
   cd navarino-orca-bridge
```

2. **Create .env file:**
```bash
   cp .env.example .env
   vim .env
   # Update all required variables
```

3. **Create directories:**
```bash
   mkdir -p logs state
```

4. **Build and start:**
```bash
   docker compose build
   docker compose up -d
```

5. **Verify:**
```bash
   docker ps  # Should show "healthy" after 2-3 min
   docker logs navarino-orca-bridge -f
   docker exec navarino-orca-bridge cat /app/logs/health_status.txt
```

### Configuration

Start with these settings:
- `DRY_RUN=True` (test mode)
- `ORCA_TEST=True` (test environment)
- After verification, switch to:
  - `DRY_RUN=False` (live mode)
  - `ORCA_TEST=False` (production - optional)

### Health Monitor Integration

The container will be automatically detected by the Health Monitor.

- Healthcheck interval: 2 minutes
- Max age: 15 minutes (SYNC_INTERVAL + 10 min buffer)
- Alert delay: 15 minutes (two-phase verification)

### Troubleshooting

**Container unhealthy:**
```bash
docker exec navarino-orca-bridge python3 /app/scripts/healthcheck.py
docker exec navarino-orca-bridge cat /app/logs/health_status.txt
```

**Check configuration:**
```bash
docker exec navarino-orca-bridge python3 /app/scripts/check_config.py
```

**View logs:**
```bash
docker logs navarino-orca-bridge --tail 100 -f
```

**Restart container:**
```bash
docker compose restart
```
