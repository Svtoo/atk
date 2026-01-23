# ATK Future Ideas & Backlog

> **Status**: Backlog — features and ideas for post-MVP consideration
> **Last Updated**: 2026-01-23

This document collects ideas, deferred features, and future enhancements that are explicitly **not in MVP scope**. Items here may be promoted to the roadmap as priorities evolve.

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

## Post-MVP Phases

### Phase 3: Configuration
- `.env` file management per plugin
- Install wizard for required env vars
- Port conflict detection
- `atk mcp <plugin>` — Generate MCP config for IDE

### Phase 4: Plugin Sources
- Create `atk-registry` repo with initial plugins
- Install from registry by name (`atk install openmemory`)
- Version pinning in manifest

### Phase 5: Polish
- Interactive TUI (optional, on top of CLI)
- Documentation and examples
- Error messages and help text

### Phase 6: Community
- Publish to PyPI
- Install from Git URL (`atk install github.com/org/repo`)
- Contribution guide for registry
- CI/CD for registry (validate plugin YAMLs)

### Phase 7: AI Agent Integration
- MCP server for AI agent control
- Rules for user agents to create new plugins
- Agent-friendly documentation
- Structured output for AI agent consumption (JSON mode)

### Phase 8: MCP Management for 3rd Party Tools
- Automatically install managed MCP to:
  - Claude Code
  - Codex
  - Gemini CLI
  - ...

### Phase 9: Data Backup
- Backup and restore data that plugins produce (e.g., OpenMemory's .lmdb database, Langfuse's ClickHouse database)
- TBD

### Phase 10: Rules/Skills and Agent.md Management
- Manage agent rules and skills via ATK
- TBD

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

- Items move from here to `atk-roadmap.md` when prioritized
- Keep this document updated as new ideas emerge
- Cross-reference with GitHub issues when available

