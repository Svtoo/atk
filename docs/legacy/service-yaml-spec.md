# service.yaml Specification

Machine-readable metadata for services managed by the Tools CLI.

## Schema

```yaml
# Required fields
name: Service Name
description: Brief description of what this service does
category: core | optional | experimental

# Optional: Vendor repository
vendor:
  url: https://github.com/org/repo.git
  ref: main  # tag, branch, or commit

# Optional: Network ports
ports:
  - name: API
    port: 8080
    health_endpoint: /health  # Optional HTTP GET endpoint for health checks

# Optional: Environment variables
env_vars:
  - name: API_KEY
    required: true
    secret: true
    default: null
    description: API key for authentication

# Optional: Dependencies
dependencies:
  system:
    - docker
    - docker-compose
  services:
    - other-service

# Optional: Lifecycle commands
lifecycle:
  start: docker compose up -d
  stop: docker compose down
  restart: docker compose restart
  install: ./update.sh
  logs: docker compose logs
  status: docker compose ps --quiet | grep -q . && exit 0 || exit 1
```

## Lifecycle Commands

All lifecycle commands are **optional**. If not specified, the CLI falls back to sensible defaults:

| Command | Default Behavior | Purpose |
|---------|------------------|---------|
| `start` | `docker compose up -d` | Start the service |
| `stop` | `docker compose down` | Stop the service |
| `restart` | `stop` + `start` | Restart the service |
| `install` | `./update.sh` | Install/update the service |
| `logs` | `docker compose logs` | View service logs |
| `status` | Check docker containers | Check if service is running |

### Command Context

- All commands run with `cwd` set to the service directory
- Commands are executed via shell (`/bin/sh -c`)
- Exit code 0 = success, non-zero = failure
- For `status`: exit 0 = running, non-zero = stopped

### Examples

**Docker Compose Service (default):**
```yaml
# No lifecycle section needed - uses docker-compose defaults
```

**Systemd Service:**
```yaml
lifecycle:
  start: sudo systemctl start myservice
  stop: sudo systemctl stop myservice
  restart: sudo systemctl restart myservice
  status: systemctl is-active --quiet myservice
  logs: journalctl -u myservice -n 100
  install: sudo apt-get install -y myservice
```

**Custom Script:**
```yaml
lifecycle:
  start: ./scripts/start.sh
  stop: ./scripts/stop.sh
  restart: ./scripts/restart.sh
  status: pgrep -f myservice > /dev/null
  logs: tail -f /var/log/myservice.log
  install: ./scripts/install.sh
```

**Python Service:**
```yaml
lifecycle:
  start: uv run python server.py &
  stop: pkill -f "python server.py"
  status: pgrep -f "python server.py" > /dev/null
  logs: tail -f logs/server.log
  install: uv sync
```

## Health Checks

The CLI checks service health in this order:

1. **Custom status command** (if `lifecycle.status` is set)
2. **Docker container status** (if docker-compose.yml exists)
3. **HTTP health endpoint** (if `ports[].health_endpoint` is set)

If no health check is available, the service is assumed to be running if it was started successfully.

## Notes

- Use `health_endpoint: null` for services that don't have HTTP health endpoints
- The `status` command should exit 0 if running, non-zero if stopped
- Commands can use environment variables from the service's `.env` file

