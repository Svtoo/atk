---
name: create-atk-plugin
description: Creates an ATK plugin configuration for a project. Use when asked to make a project installable via ATK, create an .atk/ directory, add ATK plugin support, or configure lifecycle management for a dev tool.
---

# Creating an ATK Plugin

You are creating an ATK (Agent Toolkit) plugin. ATK is a CLI tool that manages AI development tools through a
declarative YAML manifest. Users install plugins with `atk add`, configure with `atk setup`, and manage lifecycle with
`atk start/stop/install/uninstall/status/logs`.

## How ATK Works

- **ATK Home**: `~/.atk/` — contains `manifest.yaml` and `plugins/` directory
- **Plugin directory**: `~/.atk/plugins/<name>/` — contains `plugin.yaml`, `.env`, lifecycle scripts.
- **Install**: `uv tool install atk-cli`

## Plugin Sources (How Users Add Plugins)

| Method   | Command                       | What Happens                                  |
|----------|-------------------------------|-----------------------------------------------|
| Registry | `atk add <name>`              | Looks up in atk-registry, fetches via git     |
| Git URL  | `atk add github.com/org/repo` | Sparse-clones repo, extracts `.atk/` dir only |
| Local    | `atk add ./path`              | Copies `.atk/` dir from local path            |

### CRITICAL: The Git Source Flow

When a user runs `atk add github.com/org/repo`, ATK does NOT clone the full repository. It:

1. Sparse-clones the repo (minimal metadata only)
2. Checks out ONLY the `.atk/` directory
3. Copies the CONTENTS of `.atk/` to `~/.atk/plugins/<name>/`
4. Discards the clone

**The full repository is NOT available in the plugin directory.** Only files inside `.atk/` are copied. If your plugin
needs the full repo (e.g., to run a Python project), your `install.sh` must clone it.

## Directory Structure

Create an `.atk/` directory at the root of the project:

```
project-root/
└── .atk/
    ├── plugin.yaml      # Required: plugin schema
    ├── install.sh        # Lifecycle (Optional): install/update
    ├── uninstall.sh      # Lifecycle (Optional): full cleanup
    ├── start.sh          # Lifecycle (Optional): start service
    ├── stop.sh           # Lifecycle (Optional): stop service
    └── status.sh         # Lifecycle (Optional): check if running
```

## plugin.yaml Schema

```yaml
schema_version: "2026-01-23"
name: my-plugin
description: What this plugin does

vendor:
  name: Author Name
  url: https://github.com/org/repo

service:
  type: script  # or docker-compose, docker, systemd

env_vars:
  - name: MY_API_KEY
    required: true
    secret: true
    description: API key for the service
  - name: MY_OPTION
    required: false
    default: "some-value"
    description: Optional configuration

lifecycle:
  install: ./install.sh
  uninstall: ./uninstall.sh
  start: ./start.sh
  stop: ./stop.sh
  status: ./status.sh

mcp:
  transport: stdio
  command: uv
  args: [ "run", "--directory", "$ATK_PLUGIN_DIR/src", "my-tool", "run" ]
  env:
    - MY_API_KEY
```

### Required Fields

- `schema_version`: Always `"2026-01-23"` (current version)
- `name`: Plugin identifier
- `description`: Human-readable description

### Service Types

| Type             | Default Lifecycle                  | When to Use            |
|------------------|------------------------------------|------------------------|
| `docker-compose` | `docker compose up/down`           | Docker-based tools     |
| `docker`         | `docker run/stop`                  | Single container tools |
| `systemd`        | `systemctl start/stop`             | System services        |
| `script`         | Must define all lifecycle commands | Everything else        |

### env_vars: Declaring Environment Variables

Each env var in `plugin.yaml` is prompted during `atk setup` and stored in `.env`. ATK injects `.env` values into all
lifecycle commands via `os.environ`.

**Fields**: `name` (required), `description`, `required` (default: false), `default`, `secret` (default: false)

**IMPORTANT**: Only declare env vars that are actually consumed somewhere:

- By lifecycle scripts (read from `$VAR_NAME` in shell)
- By the application at runtime (read from `os.environ` or equivalent)

### mcp: MCP Server Configuration

If the plugin exposes an MCP server, configure the `mcp` section:

- `transport`: `stdio` or `sse`
- `command`/`args`: For stdio transport. Use `$ATK_PLUGIN_DIR` for paths — ATK substitutes it with the absolute plugin
  directory path
- `endpoint`: For SSE transport
- `env`: List of env var NAMES to include in generated MCP config. **Only list vars the MCP server actually reads
  from `os.environ` at runtime.** Do NOT list vars only used by lifecycle scripts.

## Lifecycle Events: Rules and Patterns

### General Rules

1. **All scripts run with `shell=True`, `cwd=plugin_dir`** — paths are relative to the plugin directory
2. **`.env` vars are merged into environment** — all declared env vars are available as `$VAR_NAME`
3. **Exit code 0 = success** for all commands; for `status`, exit 0 = running, exit 1 = stopped
4. **Pre-flight checks**: ATK checks required env vars before `start` and `install`. Checks port conflicts before
   `start`.
5. **Install/uninstall symmetry**: If `install` is defined, `uninstall` MUST also be defined (schema validation enforces
   this)
6. **No restart command**: ATK runs `stop` then `start` for restart
7. You don't have to declare explicit scripts. You can if it's a one-liner bash; you can directly put it in plugin.yaml file. 

### install — The Most Critical Script

**Install IS update.** There is no separate update command. `atk install` must converge to the desired state every time.

**Idempotency rule**: Always build from scratch. No conditional logic like "if exists, pull; else clone." Always
`rm -rf` and fresh clone/install.

### start — Starting Services

**Always clean stale runtime files** (sockets, PID files) before starting. Daemons often check these on startup and
refuse to start if they exist, even if the old process is dead.

### stop — Stopping Services

**Do NOT use `set -e`** in stop.sh — processes may already be stopped, and that's fine.

### status — Health Check

Exit code 0 = running, non-zero = stopped. Keep it simple.

### uninstall — Full Cleanup

Must remove ALL resources the plugin created

## Environment Variable Audit Checklist

Before finalizing your plugin, verify every env var:

| Question                                              | If No                                    |
|-------------------------------------------------------|------------------------------------------|
| Is this var read by any code at runtime?              | Remove from `env_vars`                   |
| Is this var used by any lifecycle script?             | Remove from `env_vars`                   |
| Is this var read from `os.environ` by the MCP server? | Remove from `mcp.env`                    |
| Does the var have a real consumer?                    | Remove it — phantom vars waste user time |

**Common mistake**: Declaring env vars that sound useful but nothing actually reads. Every var must have a concrete
consumer — either a lifecycle script that reads `$VAR_NAME` or application code that reads `os.environ.get("VAR_NAME")`.

**Install-time vs runtime vars**: Some vars are only used during install (e.g., to write config files). These should be
in `env_vars` but NOT in `mcp.env`. Only vars the MCP server reads from `os.environ` at runtime belong in `mcp.env`.
