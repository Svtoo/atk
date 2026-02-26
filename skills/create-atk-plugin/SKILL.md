---
name: create-atk-plugin
description: Creates an ATK plugin for a project. Use when asked to make a tool installable via ATK, create plugin files, add ATK support, or configure lifecycle management for a dev tool.
---

# Creating an ATK Plugin

ATK (AI Toolkit) is a CLI that manages AI development tools through a declarative YAML manifest. Users install
plugins with `atk add`, configure with `atk setup`, and manage lifecycle with `atk start/stop/install/uninstall/status/logs`.

- **ATK Home**: `~/.atk/` — contains `manifest.yaml` and `plugins/` directory
- **Plugin directory**: `~/.atk/plugins/<name>/` — contains `plugin.yaml`, `.env`, lifecycle scripts
- **Install ATK**: `uv tool install atk-cli`

## CLI Reference

| Command                     | Purpose                                           |
|-----------------------------|---------------------------------------------------|
| `atk add <source>`          | Add plugin (local path, git URL, or registry name)|
| `atk setup [plugin]`        | Configure environment variables interactively     |
| `atk install [plugin]`      | Run install lifecycle                             |
| `atk uninstall <plugin>`    | Run uninstall lifecycle (keeps manifest entry)    |
| `atk start [plugin]`        | Start service                                     |
| `atk stop [plugin]`         | Stop service                                      |
| `atk restart [plugin]`      | Stop then start (no separate restart lifecycle)   |
| `atk status [plugin]`       | Show plugin status                                |
| `atk logs <plugin>`         | View service logs                                 |
| `atk mcp <plugin>`          | Output MCP configuration JSON                     |
| `atk run <plugin> <script>` | Run a custom script from the plugin directory     |
| `atk remove <plugin>`       | Stop + uninstall + delete plugin entirely         |
| `atk upgrade [plugin]`      | Update to latest version                          |

**`atk uninstall` vs `atk remove`**: `uninstall` runs cleanup but keeps the plugin directory and manifest entry (use to
test idempotency). `remove` is a full wipe — stops, uninstalls, deletes directory and manifest entry.

---

# Part 1: Generic — Applies to All Plugin Types

## The Zero-Friction Principle

ATK exists so users can run `atk add <name>` and have a working tool with no debugging, no manual setup, no guesswork.
Every plugin must uphold this contract.

### If ATK says "installed", it works

When `install.sh` exits 0, the service must be fully operational. If any dependency is missing or any step fails, the
script must exit non-zero with a clear error. ATK interprets exit 0 as success — lying about success leaves the user
with a broken tool and no idea why.

### Fail fast with actionable errors

```bash
# DON'T: warn and continue
if ! command -v ollama &>/dev/null; then
  echo "Warning: Ollama not found, embeddings may not work"
fi

# DO: fail with exact instructions
if ! command -v ollama &>/dev/null; then
  echo "ERROR: Ollama is required but not installed."
  echo "  macOS:  brew install ollama"
  echo "  Linux:  curl -fsSL https://ollama.com/install.sh | sh"
  echo "  Other:  https://ollama.com/download"
  echo "Then run: atk install <name>"
  exit 1
fi
```

### Check every dependency before doing work

Verify prerequisites before any expensive operation (clone, build, start):
- **External tools**: installed AND running if needed
- **Models/data**: available or downloadable; fail if download fails
- **Network**: connectivity if the install needs to download anything

### Health checks must verify the service

No `sleep 5` and hope. Use retry loops that actually hit the endpoint:

```bash
for i in $(seq 1 15); do
  if curl -sf http://localhost:8787/health >/dev/null 2>&1; then
    echo "  ✅ API: http://localhost:8787"
    break
  fi
  [ "$i" -eq 15 ] && { echo "  ❌ API failed to start"; exit 1; }
  sleep 2
done
```

This applies to both `install.sh` and `start.sh` — if they exit 0, the service must be up and healthy.

---

## plugin.yaml Schema

```yaml
schema_version: "2026-01-23"
name: my-plugin
description: What this plugin does

vendor:
  name: Author / Upstream Name
  url: https://github.com/org/repo
  docs: https://docs.example.com

service:
  type: docker-compose          # docker-compose | docker | systemd | script
  compose_file: docker-compose.yml   # required for docker-compose
  unit_name: my-service              # required for systemd

ports:
  - port: 8080
    name: api
    protocol: http               # http | https | tcp
    description: Main API endpoint

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
  install:   ./install.sh        # or inline: docker compose pull && docker compose up -d
  uninstall: ./uninstall.sh
  start:     docker compose up -d
  stop:      docker compose down
  status:    docker compose ps --filter "status=running" --services | grep -q my-service
  logs:      docker compose logs -f
  health_endpoint: http://localhost:8080/health

mcp:
  transport: stdio               # stdio | sse
  command: uv
  args: ["run", "--directory", "$ATK_PLUGIN_DIR", "server.py"]
  env:
    - MY_API_KEY
```

### Required fields

- `schema_version`: Always `"2026-01-23"`
- `name`: Plugin identifier
- `description`: Human-readable description

### Service types

| Type             | Default lifecycle                  | When to use             |
|------------------|------------------------------------|-------------------------|
| `docker-compose` | `docker compose up/down`           | Docker-based tools      |
| `docker`         | `docker run/stop`                  | Single container tools  |
| `systemd`        | `systemctl start/stop`             | System services         |
| `script`         | Must define all lifecycle commands | Everything else         |

### env_vars rules

Each declared var is prompted at `atk add/setup` and stored in `.env`. ATK injects all `.env` values into every lifecycle
command via `os.environ`.

**Fields**: `name` (required), `description`, `required` (default: false), `default`, `secret` (default: false)

**IMPORTANT**: Only declare vars that are actually consumed:
- By lifecycle scripts (read as `$VAR_NAME` in shell)
- By the application at runtime (read from `os.environ`)

### mcp section

If the plugin exposes an MCP server:
- `transport`: `stdio` (command-based) or `sse` (URL-based)
- `command`/`args`: For stdio. Use `$ATK_PLUGIN_DIR` for paths — ATK substitutes it with the plugin's absolute path
- `endpoint`: For SSE
- `env`: List of env var **names** to inject into the MCP process at runtime. Only include vars the MCP server reads
  from `os.environ` — do NOT list vars only used by lifecycle scripts

**stdio example:**
```yaml
mcp:
  transport: stdio
  command: uv
  args: ["run", "--directory", "$ATK_PLUGIN_DIR", "server.py"]
  env:
    - MY_API_KEY
```

**sse example:**
```yaml
mcp:
  transport: sse
  endpoint: http://localhost:8080/mcp
```

`atk mcp <plugin>` outputs JSON for MCP client configuration:
```json
{
  "my-plugin": {
    "command": "uv",
    "args": ["run", "--directory", "/Users/.../.atk/plugins/my-plugin", "server.py"],
    "env": { "MY_API_KEY": "secret-value" }
  }
}
```

---

## Lifecycle Events: Rules and Patterns

**General rules:**
1. All scripts run with `cwd=plugin_dir` — paths are relative to the plugin directory
2. `.env` vars are merged into the environment before any command runs
3. Exit 0 = success; for `status`, exit 0 = running, non-zero = stopped
4. ATK checks required env vars before `start` and `install`. Checks port conflicts before `start`.
5. If `install` is defined, `uninstall` MUST also be defined (enforced by schema validation)
6. No restart command — ATK runs `stop` then `start` for restart
7. For simple one-liners, put the command directly in `plugin.yaml` instead of creating a separate script

### install — The most critical script

**Install IS update.** There is no separate update command. `atk install` must converge to desired state every time.

**Idempotency rule**: Always build from scratch. Always `rm -rf` and fresh clone/install — no conditional
"if exists, pull; else clone" logic.

Use `set -e` in `install.sh`: fail fast on errors.

### start

**Always clean stale runtime files** (sockets, PID files) before starting — daemons often refuse to start if these
exist, even if the old process is dead.

### stop

**Do NOT use `set -e`** in `stop.sh` — processes may already be stopped, and that's fine. Partial cleanup is better
than no cleanup.

### status

Exit 0 = running, non-zero = stopped. Keep it simple.

### uninstall

Must remove ALL resources the plugin created: containers, images, volumes, vendor clones, data directories.

Do NOT use `set -e` in `uninstall.sh` — same reasoning as stop.

---

## Environment Variable Audit Checklist

Before finalizing your plugin, verify every env var:

| Question                                              | If no                                    |
|-------------------------------------------------------|------------------------------------------|
| Is this var read by any lifecycle script?             | Remove from `env_vars`                   |
| Is this var read by the application at runtime?       | Remove from `env_vars`                   |
| Is this var read by the MCP server from `os.environ`? | Remove from `mcp.env`                    |
| Does the var have a concrete consumer?                | Remove it — phantom vars waste user time |

**Common mistake**: Vars used only during install (e.g., to write config files) belong in `env_vars` but NOT in
`mcp.env`. Only vars the MCP server reads at runtime belong in `mcp.env`.

---

## Plugin Documentation Conventions

ATK uses two documentation files by convention. Neither is declared in `plugin.yaml` — they
are discovered by filename. Both are content, not behavior.

### `README.md` — Help file

**Always include a `README.md`** in your plugin directory. This is the canonical help file:
`atk help <plugin>` reads and renders it in the terminal.

A good plugin README includes:

1. **Name and one-line description** — what this plugin is for
2. **Overview** — brief explanation of the upstream tool and why it's useful
3. **Installation** — the exact `atk add` command and any prerequisites (e.g., "requires Docker")
4. **Environment variables** — a table with names, defaults, and descriptions
5. **Usage** — how to interact with the plugin after install (e.g., `atk mcp`, `atk logs`, web UI URL)
6. **MCP tools** — if the plugin exposes MCP tools, list them with brief descriptions
7. **Links** — upstream documentation, repository

Example structure:
```markdown
# My Plugin

One-line description of what it does.

## Overview
Brief description of the upstream tool and its purpose.

## Installation
Requires: Docker, [any other prereqs]
```bash
atk add my-plugin
```

## Environment Variables
| Variable      | Default | Description        |
|---------------|---------|--------------------|
| MY_API_KEY    | —       | API key (required) |
| MY_OPTION     | "value" | Optional setting   |

## Usage
After install: http://localhost:8080
MCP config: `atk mcp my-plugin`

## Links
- [Upstream repository](https://github.com/org/repo)
```
```

### `SKILL.md` — Agent skill file

If your plugin exposes an MCP server, **include a `SKILL.md`** with instructions for AI
agents on how to use it effectively. ATK injects this file into agent configuration when
running `atk mcp --claude` (and future agent integrations).

A good SKILL.md includes:
- What this MCP is for and why it exists
- What the tools do (brief, usage-oriented — not a copy of the API docs)
- When to use it and when not to
- Any critical usage patterns or caveats

Keep it concise. Agents read this as system-level instruction, not documentation.

```markdown
# My Plugin — Skill

Brief description of what this MCP provides and its purpose.

## Tools

- **tool_name**: What it does and when to use it
- **other_tool**: What it does and when to use it

## Usage Patterns

Key patterns or workflows an agent should know about.

## Notes

Any caveats, limitations, or non-obvious behaviors.
```

---

## Common Plugin Patterns

### Pattern: MCP-only (no service)

```yaml
schema_version: "2026-01-23"
name: GitHub MCP
description: GitHub API integration via MCP

env_vars:
  - name: GITHUB_TOKEN
    required: true
    secret: true
    description: GitHub personal access token

mcp:
  transport: stdio
  command: npx
  args: ["-y", "@github/mcp-server"]
  env:
    - GITHUB_TOKEN
```

No `service`, no lifecycle — just `atk setup` then `atk mcp`.

### Pattern: Docker service with MCP bridge

```yaml
service:
  type: docker-compose
  compose_file: docker-compose.yml

lifecycle:
  install: docker compose pull && docker compose up -d
  uninstall: docker compose down --rmi local --volumes
  start: docker compose up -d
  stop: docker compose down
  status: docker compose ps --filter "status=running" --services | grep -q my-service
  logs: docker compose logs -f
  health_endpoint: http://localhost:8080/health

mcp:
  transport: stdio
  command: uv
  args: ["run", "--directory", "$ATK_PLUGIN_DIR", "server.py"]
  env:
    - MY_API_KEY
```

### Pattern: Build from upstream source

When the plugin builds from a vendor repo (not pre-built images), use a custom `install.sh`:

```bash
#!/bin/bash
set -e
PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENDOR_URL="https://github.com/org/repo.git"
VENDOR_REF="v2.3.1"   # Pin to a specific tag or commit — NEVER use main or latest

rm -rf "$PLUGIN_DIR/vendor"
git clone --depth 1 --branch "$VENDOR_REF" "$VENDOR_URL" "$PLUGIN_DIR/vendor/Repo"
docker compose build
docker compose up -d
```

**Always pin to a specific tag or commit.** Using `main` or `latest` means upstream breaking changes silently break
your plugin.

`uninstall.sh` must remove the vendor clone, built images, and volumes.

---

## Custom Scripts (atk run)

Plugins can ship auxiliary scripts alongside their lifecycle commands. Any script placed in the plugin directory is
runnable by users with `atk run <plugin> <script>`. ATK looks for:
1. `plugins/<name>/<script>`
2. `plugins/<name>/<script>.sh`

Example — a `backup.sh` shipped with a database plugin:
```bash
#!/bin/bash
docker compose exec my-plugin pg_dump mydb > "$ATK_PLUGIN_DIR/backup.sql"
echo "Backup saved to $ATK_PLUGIN_DIR/backup.sql"
```
Users run it with: `atk run my-plugin backup`

---

## User Customization (custom/)

ATK supports user overrides — plugin authors do NOT need to create these:

- `~/.atk/plugins/<name>/custom/overrides.yaml` — deep-merged into `plugin.yaml`
- `~/.atk/plugins/<name>/custom/docker-compose.override.yml` — auto-injected into docker compose commands

---

## Testing Protocol

**Always test through ATK itself.** Do not just validate YAML — run the full lifecycle:

```bash
# 1. Add plugin
atk add <source>          # see source-specific sections below

# 2. Verify initial state
atk status                # should show running

# 3. Test stop/start cycle
atk stop <name>
atk status                # should show stopped
atk start <name>
atk status                # should show running, ports healthy

# 4. Test MCP output
atk mcp <name>            # verify JSON is correct

# 5. Test idempotency
atk uninstall <name> --force
# verify: no containers, no volumes, no vendor clone
atk install <name>
atk status                # should show running again

# 6. Clean up
atk remove <name> --force
```

### What to verify at each step

| Command         | Check                                                               |
|-----------------|---------------------------------------------------------------------|
| `atk add`       | Exit 0, env var prompts work, install completes, health checks pass |
| `atk status`    | Shows `running`, all ports marked `✓`, ENV `✓`                      |
| `atk stop`      | Exit 0, service actually stopped                                    |
| `atk start`     | Exit 0, service restarts cleanly                                    |
| `atk mcp`       | Correct JSON: transport, command, args, env all match plugin.yaml   |
| `atk uninstall` | Exit 0, all resources cleaned up (containers, volumes, vendor)      |
| `atk install`   | Exit 0, full re-setup from scratch works (idempotency)              |

### Practical notes

- **Port conflicts**: Check that no other containers are using the same ports before testing.
- **Health checks take time**: Docker Compose health checks may need 5–30 seconds. Use `--retry` loops.
- **`set -e` in scripts**: Use in `install.sh`. Do NOT use in `stop.sh` or `uninstall.sh`.
- **Lifecycle one-liners**: For simple commands, put them inline in `plugin.yaml` instead of creating scripts.

---
# Part 2: Installation Type — Local Path

**Used when**: Installing a plugin from the local filesystem — typically during plugin development, or for
plugins not published anywhere.

## Directory Structure

Point `atk add` at any directory containing `plugin.yaml`:

```
my-plugin/            ← atk add ./my-plugin
├── plugin.yaml       # Required
├── install.sh        # Optional
├── docker-compose.yml
└── README.md
```

Or, when adding ATK support to an existing project in-place:

```
project-root/
└── .atk/             ← atk add ./.atk  (from project root)
    ├── plugin.yaml
    └── ...
```

ATK also accepts a single YAML file: `atk add ./plugin.yaml`

## How ATK Adds a Local Plugin

ATK copies the entire source directory to `~/.atk/plugins/<name>/`. The full source directory becomes the plugin
directory — all files inside it are available.

```bash
# From project root
atk add ./.atk

# From parent directory
atk add ./my-project/.atk

# From registry repo during development
atk add ./plugins/my-plugin
```

## Development Workflow

Local source is ideal for iterating on a plugin:

```bash
# Edit files in .atk/ or my-plugin/
# Re-add to pick up changes
atk remove <name> --force
atk add ./.atk
```

---

# Part 3: Installation Type — Registry Plugin

**Used when**: Publishing a plugin to the ATK registry so users can install it with just `atk add <name>`.

## Directory Structure

Plugin files live directly in `atk-registry/plugins/<name>/` — **no `.atk/` subdirectory**:

```
atk-registry/
└── plugins/
    └── my-plugin/        ← this entire directory is the plugin
        ├── plugin.yaml   # Required
        ├── install.sh    # Optional
        ├── docker-compose.yml
        └── README.md     # Strongly recommended
```

When ATK fetches a registry plugin, it sparse-checkouts `plugins/<name>/` and copies its contents to
`~/.atk/plugins/<name>/` — same result as local and git installs, just sourced from the registry repo.

## Self-Contained Requirement

Registry plugins must be completely self-contained. All lifecycle scripts, Dockerfiles, compose files, and config
must be inside the plugin directory. No references to files outside `plugins/<name>/`.

## index.yaml

**Never edit `index.yaml` manually.** CI auto-generates it by running `scripts/generate_index.py` on every push.

## Testing a Registry Plugin Locally

```bash
cd atk-registry

# Test via local path (mirrors what users get)
atk add ./plugins/<name>

# Run full lifecycle test
atk status
atk stop <name>
atk start <name>
atk mcp <name>
atk uninstall <name> --force
atk install <name>
atk remove <name> --force
```

## Publishing

1. Place plugin files in `atk-registry/plugins/<name>/`
2. Validate: `make validate`
3. Commit and push — CI auto-generates `index.yaml`

---

## Pre-Publish Validation Checklist

- [ ] `plugin.yaml` has `schema_version`, `name`, `description`
- [ ] If `lifecycle.install` is defined, `lifecycle.uninstall` is also defined
- [ ] Port numbers match between `plugin.yaml` and `docker-compose.yml`
- [ ] Env vars use `${VAR:-default}` syntax in docker-compose
- [ ] MCP server uses `$ATK_PLUGIN_DIR` for paths (not hardcoded paths)
- [ ] Lifecycle scripts are executable (`chmod +x`)
- [ ] `install.sh` uses `set -e`; `stop.sh` and `uninstall.sh` do NOT use `set -e`
- [ ] Health endpoint returns HTTP 200 when healthy
- [ ] `README.md` exists and covers: purpose, prerequisites, env vars, usage
- [ ] Tested: full lifecycle cycle (add → status → stop → start → uninstall → install → remove)
- [ ] Build-from-source plugins: pinned to a specific tag or commit (not `main`/`latest`)
- [ ] Registry plugins: `make validate` passes

---

# Part 4: Installation Type — In-Repo Plugin (Git URL)

**Used when**: A project author adds ATK support directly to their own tool's repository so users can install it with
`atk add github.com/org/repo` or `atk add git@github.com:org/repo`.

## Directory Structure

Create a `.atk/` directory at the **root** of the project repository:

```
project-root/
└── .atk/
    ├── plugin.yaml      # Required
    ├── install.sh       # Optional: custom install logic
    ├── uninstall.sh     # Optional: full cleanup
    ├── start.sh         # Optional: start service
    ├── stop.sh          # Optional: stop service
    ├── status.sh        # Optional: health check
    └── README.md        # Strongly recommended
```

## How ATK Fetches a Git Plugin — CRITICAL

When a user runs `atk add github.com/org/repo`, ATK does NOT clone the full repository. It:

1. Sparse-clones the repo (minimal metadata only)
2. Checks out **only** the `.atk/` directory
3. Copies the **contents** of `.atk/` to `~/.atk/plugins/<name>/`
4. Discards the clone

**The full repository is NOT available in the plugin directory.** Only files inside `.atk/` are copied.
If your plugin needs the full repo (e.g., to run a Python project), `install.sh` must clone it explicitly.

Git shorthand is supported: `github.com/org/repo` → `https://github.com/org/repo`

## Plugin Requires the Full Repo at Runtime

If your plugin IS the project in the repository, `install.sh` must clone the full repo:

```bash
#!/bin/bash
set -e
PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

rm -rf "$PLUGIN_DIR/src"
git clone --depth 1 https://github.com/org/my-tool.git "$PLUGIN_DIR/src"
cd "$PLUGIN_DIR/src"
uv sync
```

Reference the clone via `$ATK_PLUGIN_DIR` (substituted at runtime to the plugin's absolute path).

## Testing

```bash
# Test locally during development
atk add ./.atk

# Test via git URL (as users will install it)
atk add github.com/org/repo

# Clean up
atk remove <name> --force
```