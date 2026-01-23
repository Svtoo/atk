# ATK Roadmap

> High-level implementation plan from zero to working version.

## Phase 0: Foundation

- [x] Create new repo `atk` with clean structure
- [x] Set up Python project (pyproject.toml, uv)
- [x] Define plugin YAML schema (full spec in `plugin-schema.md`)
- [x] Implement schema validation

## Phase 1: Core CLI

- [ ] `atk init [directory]` — Initialize manifest directory as git repo
- [ ] `atk add <plugin>` — add from local directory file
- [ ] `atk remove <plugin>` — Remove plugin from manifest
- [ ] `atk status` — List installed plugins and their status
- [ ] Auto-commit on every mutation

## Phase 2: Service Lifecycle

- [ ] `atk start <plugin>` — Start plugin service
- [ ] `atk stop <plugin>` — Stop plugin service
- [ ] `atk logs <plugin>` — View plugin logs
- [ ] `atk install <plugin>` — Install/Update plugin
- [ ] `atk run <plugin> <script>` — Run a plugin script
- [ ] Health checks (HTTP endpoints, container status)
- [ ] Sensible defaults for lifecycle commands
- [ ] Port existing tools repo services to atk plugins

## Phase 3: Configuration

- [ ] `.env` file management per plugin
- [ ] Install wizard for required env vars
- [ ] Port conflict detection
- [ ] `atk mcp <plugin>` — Generate MCP config for IDE

## Phase 4: Plugin Sources

- [ ] Create `atk-registry` repo with initial plugins
- [ ] Install from registry by name (`atk install openmemory`)
- [ ] Version pinning in manifest

## Phase 5: Polish

- [ ] Interactive TUI (optional, on top of CLI)
- [ ] Documentation and examples
- [ ] Error messages and help text

## Phase 6: Community

- [ ] Publish to PyPI
- [ ] Install from Git URL (`atk install github.com/org/repo`)
- [ ] Contribution guide for registry
- [ ] CI/CD for registry (validate plugin YAMLs)

## Phase 7: AI Agent Integration
- [ ] MCP server for AI agent control
- [ ] Rules for user agents to create new plugins
- [ ] Agent-friendly documentation
- [ ] Structured output for AI agent consumption (JSON mode)

## Phase 8: MCP management for 3rd party tools
- [ ] Automatically install managed MCP to:
  - [ ] Claude Code
  - [ ] Codex
  - [ ] Gemini CLI
  - ...

## Phase 9: Data backup
Backup and restore data that plugins produce and is not source code (e.g. OpenMemory's .lmdb database, Langfuse's ClickHouse database, etc.)
- [ ] TBD

## Phase 10: Rules/Skills and Agent.md management via atk 


---

## Milestones

| Milestone             | Definition of Done                             |
|-----------------------|------------------------------------------------|
| **M1: Dogfood**       | Can manage 2+ plugins on local machine via CLI |
| **M2: Multi-machine** | Can sync setup across machines via git         |
| **M3: Public**        | Published to PyPI, registry has 5+ plugins     |

