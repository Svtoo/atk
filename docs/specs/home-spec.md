# ATK Home Specification

> **Status**: Approved
> **Last Updated**: 2026-01-29

## Overview

**ATK Home** is the local git-backed repository that stores the manifest and all installed plugins. Every mutation is
committed to git, enabling rollback, sync across machines, and full audit trail.

## Location Resolution

ATK Home location is resolved in this order:

1. **`ATK_HOME` environment variable** — if set, use this path
2. **Default** — `~/.atk/`

This allows:

- Custom locations for users who prefer non-default paths
- Easy testing without polluting `~/.atk/`
- Multiple ATK installations on the same machine (advanced use case)

## Directory Structure

```
~/.atk/                           # ATK Home (default location)
├── .git/                         # Git repository
├── manifest.yaml                 # Installed plugins with source references
├── plugins/
│   ├── openmemory/
│   │   ├── plugin.yaml           # Plugin definition (from source, gitignored)
│   │   ├── docker-compose.yml    # Service configuration (from source, gitignored)
│   │   ├── .env                  # Secrets (gitignored)
│   │   └── custom/               # User customizations (tracked)
│   │       ├── overrides.yaml    # Merged with plugin.yaml at runtime
│   │       ├── my-script.sh      # User-defined scripts
│   │       └── docker-compose.override.yml  # Docker Compose overrides
│   └── langfuse/
│       └── ...
└── .gitignore                    # Plugin files + *.env patterns
```

### What Gets Tracked in Git

| Path | Tracked | Notes |
|------|---------|-------|
| `manifest.yaml` | ✅ | Source of truth for installed plugins |
| `plugins/*/.env` | ❌ | Secrets, never committed |
| `plugins/*/custom/**` | ✅ | User customizations |
| `plugins/*/*` (other) | ❌ | Fetched from source on install |

### Gitignore Pattern

The root `.gitignore` uses this pattern:
```gitignore
# Ignore all plugin contents
plugins/*/*

# But keep custom directories
!plugins/*/custom/
!plugins/*/custom/**

# Always ignore secrets
*.env
```

This ensures:
- Plugin files from upstream are not tracked (fetched on `atk install --all`)
- User customizations in `custom/` are tracked and sync across machines
- Secrets are never committed

## Manifest Schema

The manifest tracks installed plugins and their sources.

```yaml
schema_version: "2026-01-22"

config:
  auto_commit: true               # Commit after mutations (default: true)

plugins:
  - name: "OpenMemory"            # Display name (user-friendly)
    directory: openmemory         # Sanitized directory name
    source:                       # Where plugin came from (for upgrades)
      type: registry              # registry | git | local
      ref: abc123def              # Git commit hash (for registry/git sources)
  - name: "Langfuse"
    directory: langfuse
    source:
      type: git
      url: github.com/langfuse/langfuse
      ref: def456abc
  - name: "Custom Tool"
    directory: custom-tool
    source:
      type: local                 # No ref for local sources
```

### Source Types

| Type | Description | Upgradeable |
|------|-------------|-------------|
| `registry` | From ATK registry | ✅ `atk upgrade` fetches latest |
| `git` | From git repository | ✅ `atk upgrade` fetches latest |
| `local` | From local filesystem | ❌ Must re-add to update |

### Design Rationale

- **Objects from the start**: Avoids painful migration when we add more plugin fields later
- **Flexible display names**: Users can name plugins whatever they want
- **Sanitized directories**: Directory names follow strict validation for safety
- **Source tracking**: Enables `atk upgrade` to fetch updates
- **Commit hash pinning**: Reproducible installs across machines
- **Single source of truth**: Manifest says "what's installed and where from"

## Plugin Directory Validation

Plugin **directory names** must match: `^[a-z][a-z0-9-]*[a-z0-9]$`

| Rule                       | Example Valid | Example Invalid |
|----------------------------|---------------|-----------------|
| Lowercase only             | `langfuse`    | `LangFuse`      |
| Alphanumeric + hyphens     | `open-memory` | `open_memory`   |
| Must start with letter     | `my-plugin`   | `1plugin`       |
| Must end with alphanumeric | `plugin-v2`   | `plugin-`       |
| No consecutive hyphens     | `my-plugin`   | `my--plugin`    |
| Minimum 2 characters       | `ab`          | `a`             |

Display names (`name` field) have no restrictions—they are for human readability only.

## Git Commit Strategy

**Only mutations commit**. Read-only operations do not create commits.

| Command                     | Commits? | Reason                                                    |
|-----------------------------|----------|-----------------------------------------------------------|
| `atk init`                  | Yes      | Creates manifest and .gitignore                           |
| `atk add <plugin>`          | Yes      | Adds plugin to manifest                                   |
| `atk upgrade <plugin>`      | Yes      | Updates manifest with new source ref                      |
| `atk remove <plugin>`       | Yes      | Removes plugin from manifest, deletes files               |
| `atk start/stop/restart`    | No       | Service control, no file changes (restart = stop + start) |
| `atk install`               | No       | Fetches plugins + runs install lifecycle                  |
| `atk status`                | No       | Read-only                                                 |
| `atk logs`                  | No       | Read-only                                                 |
| `atk run <plugin> <script>` | No       | Executes script, no file changes                          |

If `auto_commit: false`, user must manually commit changes.

## User Customizations

Users customize plugins via the `custom/` directory inside each plugin.

### The `custom/` Directory

```
plugins/<plugin>/custom/
├── overrides.yaml              # Merged with plugin.yaml
├── my-script.sh                # User scripts
└── docker-compose.override.yml # Docker Compose overrides
```

Everything in `custom/` is:
- **Tracked in git** — syncs across machines
- **Preserved on upgrade** — `atk upgrade` never touches `custom/`
- **Merged at runtime** — overrides take precedence over upstream

### Plugin Overrides

`custom/overrides.yaml` is merged with the upstream `plugin.yaml`:

```yaml
# custom/overrides.yaml
env_vars:
  - name: MY_CUSTOM_VAR
    required: false
    default: "my-value"

lifecycle:
  start: "./custom/my-start.sh"  # Override upstream's start command
```

**Merge behavior:**
- Objects are deep-merged (user values override upstream)
- Arrays are replaced entirely (not concatenated)

### User Scripts

User scripts live in `custom/` and take precedence over upstream scripts:

```bash
atk run <plugin> <script>
# Resolution order:
# 1. plugins/<plugin>/custom/<script>
# 2. plugins/<plugin>/<script>
```

### Docker Compose Overrides

For Docker Compose plugins, use the standard override pattern:

```yaml
# plugins/langfuse/custom/docker-compose.override.yml
services:
  langfuse:
    ports:
      - "3001:3000"    # Override default port
```

ATK automatically includes override files when running compose commands.

## Environment Variables

Plugins declare environment variables in `plugin.yaml`. ATK manages `.env` files per plugin.

### Storage

- `.env` files live in plugin directories: `plugins/<plugin>/.env`
- `.env` files are gitignored (secrets should not be committed)
- Format is standard dotenv: `KEY=value` per line

### How Env Vars Flow to Services

When ATK runs lifecycle commands (start, stop, install, etc.), it:

1. Reads the plugin's `.env` file
2. Injects those variables into the command's environment
3. Executes the lifecycle command

This means plugin developers can:

- Use `${VAR}` substitution in docker-compose.yml files
- Assume environment variables are set when lifecycle scripts run
- Not worry about referencing `.env` files explicitly

### Required Variables

Lifecycle commands (start, install) fail fast if required env vars are not set. Users must run `atk setup` first.

## Lifecycle Commands (MVP)

| Command                | Purpose         | Default Implementation             |
|------------------------|-----------------|------------------------------------|
| `atk start <plugin>`   | Start service   | `docker compose up -d`             |
| `atk stop <plugin>`    | Stop service    | `docker compose down`              |
| `atk restart <plugin>` | Restart service | stop + start                       |
| `atk status [plugin]`  | Show status     | Check container state              |
| `atk logs <plugin>`    | View logs       | `docker compose logs`              |
| `atk install <plugin>` | Install/Update  | install lifecycle from plugin.yaml |
| `atk setup [plugin]`   | Configure vars  | Interactive prompts for env vars   |

All lifecycle commands are plugin-agnostic — they execute whatever the plugin defines.

## Plugin Sources

ATK supports three plugin source types:

```bash
atk add ./openmemory/              # Local directory
atk add openmemory                 # Registry (by name)
atk add github.com/org/repo        # Git URL
```

| Source Type | Resolution | Upgradeable |
|-------------|------------|-------------|
| Local directory | Path to directory containing `plugin.yaml` | ❌ |
| Registry | Plugin name → fetched from `atk-registry` | ✅ |
| Git URL | Repository URL → looks for `.atk/` directory | ✅ |

### Registry

The ATK registry (`atk-registry` repo) contains curated plugins:

```
atk-registry/
├── plugins/
│   ├── openmemory/
│   │   ├── plugin.yaml
│   │   └── docker-compose.yml
│   └── langfuse/
│       └── ...
└── index.yaml          # Generated manifest for fast lookup
```

### Git URL Convention

For git sources, ATK looks for the `.atk/` directory at repository root:

```
some-repo/
├── .atk/               # ATK plugin definition
│   ├── plugin.yaml
│   └── docker-compose.yml
└── ...                 # Rest of the repository
```

ATK uses sparse checkout to fetch only the `.atk/` directory.

## What's NOT Included

| Feature                      | Status   | Reason                            |
|------------------------------|----------|-----------------------------------|
| Hooks (pre/post lifecycle)   | Deferred | Too much lifecycle complication   |
| Plugin overrides in manifest | Never    | Config lives in plugin dirs       |

## Security Considerations

### Input Validation

- Plugin names are strictly validated (regex above)
- File paths are sanitized (no `..`, no absolute paths)
- Plugin names cannot contain: spaces, slashes, quotes, shell metacharacters

### Command Injection

- **ATK's responsibility**: Validate plugin names before use in paths/commands
- **NOT ATK's responsibility**: Third-party plugin scripts (user's risk)
- **Registry plugins**: Lifecycle commands are known and validated

## Idempotency

All commands are idempotent:

| Command          | Second Run Behavior                                |
|------------------|----------------------------------------------------|
| `atk init`       | No-op if already initialized                       |
| `atk add foo`    | Overwrites if directory exists (recovery scenario) |
| `atk remove foo` | No-op if foo not installed                         |
| `atk start foo`  | No-op if foo already running                       |
| `atk stop foo`   | No-op if foo already stopped                       |

