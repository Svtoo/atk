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

## The Zero-Friction Principle

ATK exists so users can run `atk add <name>` and have a working tool — no debugging, no manual setup, no guesswork.
Every plugin you create must uphold this contract:

### If ATK says "installed", it works

When `install.sh` exits 0, the service must be fully operational. Not "mostly working", not "working if you also
install X" — **fully working**. If any dependency is missing or any step fails, the script must exit non-zero with a
clear error message. ATK interprets exit 0 as success. Lying about success leaves the user with a broken service and
no idea why.

### Fail fast with clear errors

Do not print warnings and continue. Do not silently skip failed steps. If something is wrong, **stop immediately** and
tell the user exactly:
1. What is missing or broken
2. How to fix it (specific commands, not vague suggestions)
3. What to run after fixing it (e.g., "then run `atk install <name>` again")

Bad:
```bash
# DON'T: warn and continue — user gets a broken service
if ! command -v ollama &>/dev/null; then
  echo "Warning: Ollama not found, embeddings may not work"
fi
```

Good:
```bash
# DO: fail fast with actionable instructions
if ! command -v ollama &>/dev/null; then
  echo "ERROR: Ollama is required but not installed."
  echo ""
  echo "Install Ollama:"
  echo "  macOS:  brew install ollama"
  echo "  Linux:  curl -fsSL https://ollama.com/install.sh | sh"
  echo "  Other:  https://ollama.com/download"
  echo ""
  echo "Then run: atk install <name>"
  exit 1
fi
```

### Check every dependency before doing work

Before cloning repos, building images, or starting services, verify that all prerequisites are met:
- **External tools** (e.g., Ollama, Node.js, Python): check they are installed and running if needed
- **Models or data** (e.g., ML models): check if already available, download if not, fail if download fails
- **Ports**: ATK checks port conflicts before `start`, but `install.sh` should verify service-specific requirements
- **Network**: if the install needs to download something, verify connectivity

### Be specific about what's happening

Tell the user what each step is doing, especially slow operations:
```bash
echo "  Pulling model 'mxbai-embed-large' (~669MB)..."
echo "  ✓ Model already available — skipping download"
echo "  Building Docker images (this may take a few minutes)..."
echo "  ✅ API: http://localhost:8787"
```

### Health checks must actually verify the service

Do not `sleep 5` and hope for the best. Use retry loops that actually hit the service endpoint:
```bash
for i in $(seq 1 15); do
  if curl -sf http://localhost:8787/ >/dev/null 2>&1; then
    echo "  ✅ API: http://localhost:8787"
    break
  fi
  [ "$i" -eq 15 ] && { echo "  ❌ API failed to start"; exit 1; }
  sleep 2
done
```

The same applies to `start.sh` — if it exits 0, the service must be up and healthy.

### The user's time is sacred

Every minute a user spends debugging a broken install is a failure of the plugin author. Front-load the work:
validate dependencies, pull models, check connectivity — all before the expensive operations (cloning, building,
starting). If something will fail, fail early.

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
7. You don't have to declare explicit scripts. You can if it's a one-liner bash; you can directly put it in plugin.yaml
   file.

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

## Registry Plugins vs In-Repo Plugins

There are two contexts for creating plugins:

| Context      | Directory                      | Added via                                         | Who uses it                                               |
|--------------|--------------------------------|---------------------------------------------------|-----------------------------------------------------------|
| **In-repo**  | `project-root/.atk/`           | `atk add github.com/org/repo` or `atk add ./path` | Project authors adding ATK support to their own tool      |
| **Registry** | `atk-registry/plugins/<name>/` | `atk add <name>`                                  | Curators packaging third-party tools for the ATK registry |

### Registry Plugin Rules

- Plugin files live directly in `atk-registry/plugins/<name>/` (no `.atk/` subdirectory)
- **`index.yaml` is auto-generated by CI** — never edit it manually. CI runs `scripts/generate_index.py` on push.
- When ATK fetches a registry plugin, it sparse-checkouts `plugins/<name>/` and copies its contents to
  `~/.atk/plugins/<name>/`
- Registry plugins must be self-contained: all lifecycle scripts, compose files, Dockerfiles, and config files must be
  inside the plugin directory

### Build-from-Source Plugins

When a plugin builds from upstream source (not pre-built images):

- **Pin to a specific tag or commit** — never use `main` or `latest`. Upstream breaking changes will silently break
  your plugin.
- `install.sh` should `rm -rf vendor/` then `git clone --depth 1 --branch <tag>` — idempotent, always fresh.
- `uninstall.sh` should remove the vendor clone, built images, and volumes.
- Reference vendor files via relative paths from the plugin directory (e.g., `./vendor/Repo/backend`).

## Testing Your Plugin

**Always test through ATK itself.** Do not just validate YAML — run the full lifecycle.

### Testing Workflow

```bash
# 1. Add the plugin locally (from the registry repo root)
cd atk-registry
atk add ./plugins/<name>

# 2. Verify status
atk status

# 3. Test stop/start cycle
atk stop <name>
atk status              # should show stopped
atk start <name>
atk status              # should show running, ports healthy

# 4. Test MCP output
atk mcp <name>          # verify JSON is correct

# 5. Test uninstall/install cycle (idempotency)
atk uninstall <name> --force
# verify: no containers, no volumes, no vendor clone
atk install <name>
atk status              # should show running again

# 6. Clean up when done
atk remove <name> --force
```

### What to Verify at Each Step

| Command         | Check                                                               |
|-----------------|---------------------------------------------------------------------|
| `atk add`       | Exit 0, env var prompts work, install completes, health checks pass |
| `atk status`    | Shows `running`, all ports marked `✓`, ENV `✓`                      |
| `atk stop`      | Exit 0, containers actually removed                                 |
| `atk start`     | Exit 0, containers restart cleanly                                  |
| `atk mcp`       | Correct JSON: transport, command, args, env all match plugin.yaml   |
| `atk uninstall` | Exit 0, all resources cleaned up (containers, volumes, vendor)      |
| `atk install`   | Exit 0, full re-setup from scratch works (idempotency)              |

### `atk uninstall` vs `atk remove`

- `atk uninstall` — runs stop + uninstall lifecycle but **keeps the plugin in the manifest**. The plugin directory
  and manifest entry remain.
- `atk remove` — runs stop + uninstall + **deletes the plugin directory and manifest entry**. Full cleanup.

Use `atk uninstall` → `atk install` to test idempotency. Use `atk remove` for final cleanup.

## Practical Notes

- **Port conflicts**: Before testing, check that no other containers are using the same ports. Stale containers from
  previous manual setups are a common cause of install failures.
- **Health checks take time**: Docker compose health checks may need 5-30 seconds. Install scripts should include
  a wait loop with retries (e.g., `curl --retry 10 --retry-delay 2`).
- **`set -e` in scripts**: Use `set -e` in `install.sh` (fail fast on errors). Do NOT use `set -e` in `stop.sh` or
  `uninstall.sh` (partial cleanup is better than no cleanup).
- **Lifecycle one-liners**: For simple commands (e.g., `docker compose up -d`), put them directly in `plugin.yaml`
  instead of creating separate shell scripts. Only create scripts when the logic is non-trivial.
