# ATK Backlog

> **Status**: Backlog — deferred features and ideas
> **Last Updated**: 2026-01-23

This document collects ideas, deferred features, and future enhancements. Items here may be promoted to `phases/` as priorities evolve.

For the master plan, see `ROADMAP.md`.
---

## Git push 

For .atk registries with remote repositories, enable a config parameter alongside with auto_commit and auto_push to automatically push changes to the remote. 

---
## Manage Agents.md and other prompts through atk

- Deploy/update Agents and skills for coding agents via atk.
- Plugins MCPs define agents rule that are appended to global rules.
- 
---

## Documentation, description and tags/categories for plugins

Usability and quality of life is critical for this tool, so providing valuable insight into how to use the plug-in, what this plug-in is about, as well as categorizing it with tags and maybe categories explicitly should be an essential part of atk. 
I am hesitant regarding explicit categories because those would need to have definitions. Therefore, we need to predict what the categories will be. Otherwise, it's going to be a wild west. If it is going to be wild west, I'd rather use tags which eventually can emerge into categories. 
---

## Deferred Commands

### `atk list`

Fast manifest-only listing (no container queries). Deferred because `atk status` covers the use case for MVP.

```bash
atk list
# Output:
# NAME              DIRECTORY
# OpenMemory        openmemory
# Langfuse          langfuse
```

### `atk doctor`

Validate ATK Home structure, check Docker availability, verify all plugins are valid.

**Rationale**: Status management is complex. Deferred to avoid scope creep.

### `atk config`

View or edit manifest configuration (e.g., `auto_commit` flag).

**Rationale**: Users can edit `manifest.yaml` directly for now.

---

## Deferred Features

### Sensible Lifecycle Defaults by Service Type

Automatically derive lifecycle commands based on `service.type` when not explicitly defined in plugin.yaml.

| Type             | start                           | stop                           | restart                           | logs                              | status                            |
|------------------|---------------------------------|--------------------------------|-----------------------------------|-----------------------------------|-----------------------------------|
| `docker-compose` | `docker compose up -d`          | `docker compose down`          | `docker compose restart`          | `docker compose logs -f`          | `docker compose ps --format json` |
| `docker`         | `docker start {container_name}` | `docker stop {container_name}` | `docker restart {container_name}` | `docker logs -f {container_name}` | `docker inspect {container_name}` |
| `systemd`        | `systemctl start {unit_name}`   | `systemctl stop {unit_name}`   | `systemctl restart {unit_name}`   | `journalctl -u {unit_name} -f`    | `systemctl is-active {unit_name}` |
| `script`         | (no default)                    | (no default)                   | (no default)                      | (no default)                      | (no default)                      |

**Rationale**: Start simple — require explicit commands. Add defaults later when patterns emerge from real usage.

### Restart Fallback to Stop + Start

If `restart` lifecycle command is not defined, automatically run `stop` then `start`.

**Rationale**: Keep Phase 2 simple. Users can define `restart` explicitly if needed.

### `--json` Output Flag

All commands could support `--json` for machine-readable output.

```bash
atk status --json
```

**Rationale**: Useful for scripting and AI agent integration, but human-readable output is sufficient for MVP.

### Verbosity Flags

Control output detail level via logging system:

- Default: Info level (success messages only)
- `-v` / `--verbose`: Debug level (show operations)
- `-q` / `--quiet`: No output (exit code only)

**Implementation**: Control via logging system (info/debug levels), not custom flags.

---

## Ideas & Considerations

### Hooks (Pre/Post Lifecycle)

Deferred — too much lifecycle complication for MVP.

### Git URL Source in Manifest

**Decision: Never** — Avoid data duplication with git. Use git commands directly to manage remotes.

### Plugin Overrides in Manifest

**Decision: Never** — Config lives in plugin directories, not manifest.

### Windows Support

Out of scope initially. Community contribution welcome.

### Dependency Resolution Between Plugins

Out of scope — too complex, limited value for MVP use cases.

---

## Notes

- Items move from here to `phases/` when prioritized
- Keep this document updated as new ideas emerge
- Cross-reference with GitHub issues when available
