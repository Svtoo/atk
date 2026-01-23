# ATK Roadmap

> Master plan from zero to public release.

## Milestones

| Milestone | Definition of Done |
|-----------|-------------------|
| **M1: Dogfood** | Can manage 2+ plugins on local machine via CLI |
| **M2: Multi-machine** | Can sync setup across machines via git |
| **M3: Public** | Published to PyPI, registry has 5+ plugins |

## Phases

| Phase | Name | Status | Summary |
|-------|------|--------|---------|
| 0 | Foundation | ✅ | Project setup, plugin schema, CLI skeleton |
| 1 | Core CLI | ✅ | init, add, remove, git integration |
| 2 | Service Lifecycle | 🔄 | start, stop, restart, status, logs, run |
| 3 | Configuration | ⏳ | .env management, port conflicts, MCP config |
| 4 | Plugin Sources | ⏳ | Registry, git URL sources, version pinning |
| 5 | Polish | ⏳ | Error messages, help text, documentation |
| 6 | Community | ⏳ | PyPI, contribution guide, CI/CD |
| 7 | AI Agent Integration | ⏳ | MCP server, agent-friendly output |
| 8 | MCP Management | ⏳ | Auto-install to Claude Code, Codex, etc. |
| 9 | Data Backup | ⏳ | Backup/restore plugin data |
| 10 | Rules/Skills | ⏳ | Agent.md management |

## Phase Summaries

### Phase 0: Foundation ✅
Project setup, Python tooling (uv, pyproject.toml), plugin YAML schema with Pydantic validation, CLI skeleton with version banner.

### Phase 1: Core CLI ✅
`atk init`, `atk add`, `atk remove` commands. Git-backed manifest with auto-commit. Plugin directory sanitization. Exit codes.

### Phase 2: Service Lifecycle ⏳
`atk start/stop/restart <plugin>`, `atk status`, `atk logs`, `atk run <plugin> <script>`. Lifecycle events from plugin.yaml. Health checks.

### Phase 3: Configuration ⏳
`.env` file management per plugin. Install wizard for required env vars. Port conflict detection. `atk mcp <plugin>` for IDE config.

### Phase 4: Plugin Sources ⏳
Create `atk-registry` repo. Install from registry by name. Git URL sources. Version pinning in manifest.

### Phase 5: Polish ⏳
Error messages, help text, documentation, examples.

### Phase 6: Community ⏳
Publish to PyPI. Contribution guide. CI/CD for registry.

### Phase 7: AI Agent Integration ⏳
MCP server for AI agent control. Agent-friendly documentation. Structured JSON output.

### Phase 8: MCP Management ⏳
Auto-install managed MCP to Claude Code, Codex, Gemini CLI, etc.

### Phase 9: Data Backup ⏳
Backup and restore plugin data (databases, state files).

### Phase 10: Rules/Skills ⏳
Manage agent rules and skills via ATK.

---

## Navigation

- **Detailed phase tasks**: `phases/<phase-N>.md`
- **Specifications**: `specs/`
- **Deferred ideas**: `backlog.md`

