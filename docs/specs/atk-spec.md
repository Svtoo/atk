# ATK: AI Toolkit Specification

> **Status**: In progress
> **Last Updated**: 2026-01-22

## Problem

Managing AI development tools is fragmented:
- Each tool has its own installation method (Docker, npm, pip, binary)
- Configuration scattered across different locations
- No unified way to version, backup, or sync setups across machines
- Setting up a new machine means hours of manual work

## Vision

A CLI tool that manages AI development tools through a **git-backed, declarative manifest**. Install once, sync everywhere.

```
atk add hindsight         # Copy plugin, update manifest, run install lifecycle, commit
git push                  # Backup/sync to remote
```

## Tenets

| Tenet | Meaning |
|-------|---------|
| **Usability first** | If it's not easy to use, it's not useful |
| **AI agent first-class citizen** | CLI-driven, scriptable, agent-friendly; TUI is optional |
| **Sensible defaults, configurable** | Works out of the box; power users can customize |
| **Declarative** | Manifest describes desired state; tool enforces it |
| **Idempotent** | Running the same command twice = same result |
| **Git-native** | Every change is a commit; rollback = git revert |
| **Transparent** | All config is human-readable YAML; no hidden state |
| **Focused** | Manages tools, not builds them; delegates to Docker/systemd |
| **Test-driven** | Every feature starts with a test; everything automatable is automated |

## Architecture

```mermaid
flowchart TB
    subgraph User["User Machine"]
        CLI[atk CLI]
        Manifest["~/.atk/<br/>manifest.yaml<br/>plugins/<br/>.env files"]
        Services["Running Services<br/>(Docker, systemd, etc.)"]
    end

    subgraph Sources["Plugin Sources"]
        Registry["Curated Registry<br/>(GitHub repo)"]
        DirectGit["Direct Git URL<br/>(any repo with atk.yaml)"]
        LocalYAML["Local YAML file"]
    end

    CLI -->|add| Sources
    CLI -->|manages| Manifest
    CLI -->|start/stop| Services
    Manifest -->|git push| Remote["GitHub/GitLab<br/>(backup & sync)"]
```

### Manifest Directory Structure

```
~/.atk/                           # User-chosen directory
├── .git/                         # Initialized on first run
├── manifest.yaml                 # Installed plugins + versions
├── plugins/
│   ├── hindsight/
│   │   ├── plugin.yaml           # Plugin definition
│   │   ├── docker-compose.yml    # Service config (if applicable)
│   │   └── .env                  # Secrets (gitignored)
│   └── langfuse/
│       └── ...
└── .gitignore                    # *.env, vendor/, etc.
```

### Plugin YAML Schema

Each plugin is described by a `plugin.yaml` with a date-based `schema_version` (`YYYY-MM-DD`).
Its fields, rules and examples are defined in [plugin-schema.md](plugin-schema.md).

## CLI Commands

```bash
atk init [directory]       # Initialize ATK Home directory
atk add <plugin>           # Copy plugin files, update manifest, run install lifecycle, commit
atk remove <plugin>        # Stop plugin, remove files, update manifest, commit
atk list                   # List plugins from manifest (fast, no container queries)
atk start <plugin>         # Start a plugin's service (--all for all plugins)
atk stop <plugin>          # Stop a plugin's service (--all for all plugins)
atk restart <plugin>       # Restart a plugin's service (--all for all plugins)
atk status [plugin]        # Show plugin status (all plugins if none specified)
atk logs <plugin>          # View plugin logs
atk run <plugin> <script>  # Run a plugin script (e.g., atk run hindsight backup)
atk plug <plugin>          # Plug a plugin into coding agents (MCP + skill, adapts to what plugin offers)
atk unplug <plugin>        # Unplug a plugin from coding agents
atk mcp <plugin>           # Show MCP config for manual copy-paste
```

All commands return structured output suitable for AI agent consumption.

## Plugin Sources

| Source | Example | Use Case |
|--------|---------|----------|
| **Registry** | `atk add hindsight` | Curated, tested plugins |
| **Git URL** | `atk add github.com/org/repo` | Any repo with `atk.yaml` |
| **Local** | `atk add ./my-plugin.yaml` | Custom/private plugins |

Registry: `atk-registry` repo (same org), community contributions welcome (Homebrew model).

## Concerns & Mitigations

| Concern | Mitigation |
|---------|------------|
| **Security: arbitrary code execution** | Plugins run shell scripts (like brew, npm). Mitigated by: pinned versions, curated registry, clear warnings, git history for audit. User responsibility for untrusted sources. |
| **Adoption: why would projects add atk.yaml?** | They won't initially. Curated registry maintains YAMLs for popular tools. Users can contribute or roll their own. Low barrier (one YAML file). |
| **Version compatibility** | Schema version in YAML. CLI handles migrations. Breaking changes = major version bump. |
| **Cross-platform** | macOS/Linux first. Windows via community contribution. |
| **Drift: upstream changes break plugins** | Pinned versions by default. Update is explicit. Hash of working version stored for rollback. |
| **Port conflicts** | Configurable ports in schema. Install wizard detects conflicts. |

## Scope

### In Scope
- Plugin installation, update, removal
- Service lifecycle (start/stop/restart/logs)
- Configuration management (.env files)
- Git-backed manifest with auto-commit
- MCP config generation for IDE integration
- Interactive TUI and CLI commands
- Curated plugin registry (separate repo)

### Out of Scope
- Building MCP servers (we manage, not build)
- Dependency resolution between plugins
- Windows support (initially)
- Cloud deployment / remote management
- Plugin marketplace / discovery UI
- Automatic security scanning

## Decisions

| Question | Decision |
|----------|----------|
| **Naming** | `atk` (pronounced "atik") — short, no AI hype |
| **Distribution** | PyPI (`uv tool install atk` or `pip install atk`). Name verified available. |
| **Registry repo** | `atk-registry`, same org |
| **First-run wizard** | `atk init` creates empty local registry (git repo, no upstream). Option to clone existing registry for multi-machine sync. Optional starter pack prompt. |
| **Data backup** | Deferred. Schema is additive; will add `data:` section later. |

## Next Steps

See `docs/atk-roadmap.md` for implementation plan.

