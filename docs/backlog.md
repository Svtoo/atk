# ATK Backlog

> **Status**: Backlog — deferred features and ideas
> **Last Updated**: 2026-01-23

This document collects ideas, deferred features, and future enhancements. Items here may be promoted to `phases/` as priorities evolve.

For the master plan, see `ROADMAP.md`.

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
