# ATK Home Specification

> **Status**: Approved
> **Last Updated**: 2026-01-22

## Overview

**ATK Home** is the local git-backed repository that stores the manifest and all installed plugins. Every mutation is
committed to git, enabling rollback, sync across machines, and full audit trail.

## Directory Structure

```
~/.atk/                           # ATK Home (default location)
├── .git/                         # Git repository
├── manifest.yaml                 # General configuration and installed plugins
├── plugins/
│   ├── openmemory/
│   │   ├── plugin.yaml           # Plugin definition (source of truth)
│   │   ├── docker-compose.yml    # Service configuration
│   │   ├── docker-compose.override.yml  # User customizations (tracked)
│   │   ├── .env                  # Secrets (gitignored)
│   │   └── maintenance.sh        # User-defined scripts (in plugin root)
│   └── langfuse/
│       └── ...
└── .gitignore                    # *.env patterns
```

## Manifest Schema

The manifest is **minimal by design**. Plugins are objects mapping display name to directory.

```yaml
schema_version: "2026-01-22"

config:
  auto_commit: true               # Commit after mutations (default: true)

plugins:
  - name: "OpenMemory"            # Display name (user-friendly, any format)
    directory: openmemory         # Sanitized directory name (follows validation rules)
  - name: "Langfuse"
    directory: langfuse
```

### Design Rationale

- **Objects from the start**: Avoids painful migration when we add more plugin fields later
- **Flexible display names**: Users can name plugins whatever they want
- **Sanitized directories**: Directory names follow strict validation for safety
- **No version duplication**: Plugin version lives in `plugins/<dir>/plugin.yaml`
- **No config duplication**: Plugin config lives in plugin directory
- **Single source of truth**: Manifest says "what's installed", plugin dirs say "how it's configured"

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

| Command                     | Commits? | Reason                                        |
|-----------------------------|----------|-----------------------------------------------|
| `atk init`                  | Yes      | Creates manifest and .gitignore               |
| `atk add <plugin>`          | Yes      | Adds plugin to manifest, copies files         |
| `atk remove <plugin>`       | Yes      | Removes plugin from manifest, deletes files   |
| `atk start/stop/restart`    | No       | Service control, no file changes              |
| `atk install`               | No       | Install and/or updates the underlying service |
| `atk status`                | No       | Read-only                                     |
| `atk logs`                  | No       | Read-only                                     |
| `atk run <plugin> <script>` | No       | Executes script, no file changes              |

If `auto_commit: false`, user must manually commit changes.

## User Scripts

Users can add scripts to plugins.

### Location

Scripts/executables live directly in the plugin root directory:

```
plugins/<plugin>/<script>.sh
```

### Execution

```bash
atk run <plugin> <script>
# Example: atk run langfuse maintenance
# Executes: plugins/langfuse/maintenance.sh
```

### Use Cases

1. **Maintenance tasks**: Cache cleanup, database maintenance, log rotation
2. **MCP integration**: AI agents can list and execute scripts programmatically
3. **Custom workflows**: Tasks specific to user's environment or the plugin

Scripts are tracked in git and sync across machines.

## Docker Customization

Users customize Docker services via `docker-compose.override.yml`:

```yaml
# plugins/langfuse/docker-compose.override.yml
services:
  langfuse:
    ports:
      - "3001:3000"    # Override default port
    environment:
      - CUSTOM_VAR=value
```

- Override files are **tracked in git** (not gitignored)
- User customizations persist across updates
- Standard Docker Compose override pattern

## Lifecycle Commands (MVP)

| Command                | Purpose         | Default Implementation             |
|------------------------|-----------------|------------------------------------|
| `atk start <plugin>`   | Start service   | `docker compose up -d`             |
| `atk stop <plugin>`    | Stop service    | `docker compose down`              |
| `atk restart <plugin>` | Restart service | `docker compose restart`           |
| `atk status [plugin]`  | Show status     | Check container state              |
| `atk logs <plugin>`    | View logs       | `docker compose logs`              |
| `atk install <plugin>` | Install/Update  | install lyfecycle from plugin.yaml |

All lifecycle commands are plugin-agnostic,they execute whatever the plugin defines.

## Plugin Sources (MVP)

For MVP, only local YAML files are supported:

```bash
atk add ./my-plugin.yaml
```

### Explicitly NOT Supported

- **Git URL in manifest**: Use git commands directly to manage remotes
- **Registry**: Deferred to post-MVP

### Rationale

- No data duplication: Git URL can be obtained from git itself
- User can modify origin independently; ATK doesn't need to track it
- Keeps manifest minimal and avoids sync issues

## What's NOT Included

| Feature                      | Status   | Reason                            |
|------------------------------|----------|-----------------------------------|
| Hooks (pre/post lifecycle)   | Deferred | Too much lifecycle complication   |
| Git URL source in manifest   | Never    | Avoid data duplication with git   |
| Plugin overrides in manifest | Never    | Config lives in plugin dirs       |
| Registry support             | Post-MVP | Focus on core functionality first |

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

