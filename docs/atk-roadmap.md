# ATK Roadmap

> High-level implementation plan from zero to working version.

## Phase 0: Foundation

- [ ] Create new repo `atk` with clean structure
- [ ] Set up Python project (pyproject.toml, uv)
- [ ] Define plugin YAML schema (full spec in `plugin-schema.md`)
- [ ] Implement schema validation

## Phase 1: Core CLI

- [ ] `atk init [directory]` — Initialize manifest directory as git repo
- [ ] `atk install <plugin>` — Install from local YAML file
- [ ] `atk remove <plugin>` — Remove plugin from manifest
- [ ] `atk status` — List installed plugins and their status
- [ ] `atk apply` — Ensure running state matches manifest
- [ ] Auto-commit on every mutation

## Phase 2: Service Lifecycle

- [ ] `atk start <plugin>` — Start plugin service
- [ ] `atk stop <plugin>` — Stop plugin service
- [ ] `atk logs <plugin>` — View plugin logs
- [ ] Health checks (HTTP endpoints, container status)
- [ ] Sensible defaults for lifecycle commands

## Phase 3: Plugin Sources

- [ ] Install from Git URL (`atk install github.com/org/repo`)
- [ ] Create `atk-registry` repo with initial plugins
- [ ] Install from registry by name (`atk install openmemory`)
- [ ] Version pinning in manifest

## Phase 4: Configuration

- [ ] `.env` file management per plugin
- [ ] Install wizard for required env vars
- [ ] Port conflict detection
- [ ] `atk mcp <plugin>` — Generate MCP config for IDE

## Phase 5: Polish

- [ ] Interactive TUI (optional, on top of CLI)
- [ ] Structured output for AI agent consumption (JSON mode)
- [ ] Error messages and help text
- [ ] Documentation and examples

## Phase 6: Community

- [ ] Publish to PyPI
- [ ] Port existing tools repo services to atk plugins
- [ ] Contribution guide for registry
- [ ] CI/CD for registry (validate plugin YAMLs)

---

## Milestones

| Milestone | Definition of Done |
|-----------|-------------------|
| **M1: Dogfood** | Can manage 2+ plugins on local machine via CLI |
| **M2: Multi-machine** | Can sync setup across machines via git |
| **M3: Public** | Published to PyPI, registry has 5+ plugins |

