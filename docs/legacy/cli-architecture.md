# Tools CLI Architecture

> **Status**: Phase 3 Complete (with configuration management)
> **Last Updated**: 2026-01-09

This document describes the architecture and implementation plan for an interactive CLI/TUI for managing the Tools service stack.

## Overview

The Tools CLI provides a menu-driven terminal interface for managing Docker-based services. Instead of manually editing files and running scripts, users get a guided experience for:

- **Service Management**: Install, update, start, stop, restart individual services
- **Health Monitoring**: Real-time status and health checks
- **Configuration**: Edit environment variables and service settings
- **Dependency Management**: Update vendor repos and dependencies

### Design Goals

1. **Progressive disclosure**: Simple actions upfront, advanced options discoverable
2. **Keyboard-first**: Single-key shortcuts for common operations
3. **Real-time feedback**: Stream build/install output, live health status
4. **Backward compatible**: Existing `./update.sh` continues to work
5. **Declarative services**: Machine-readable metadata enables automation

---

## Architecture

```
tools/
├── cli/                          # CLI package
│   ├── __init__.py
│   ├── __main__.py              # Entry: `python -m cli` or `tools`
│   ├── app.py                   # Textual App class
│   ├── screens/
│   │   ├── main_menu.py         # Service list + actions
│   │   ├── service_detail.py    # Per-service view
│   │   ├── logs_view.py         # Log streaming
│   │   └── config_editor.py     # .env editing
│   ├── services/
│   │   ├── registry.py          # Service discovery
│   │   ├── lifecycle.py         # start/stop/update operations
│   │   └── health.py            # Health check logic
│   └── config/
│       └── settings.py          # User preferences
├── services/
│   ├── openmemory/
│   │   ├── service.yaml         # Service metadata (NEW)
│   │   ├── docker-compose.yml
│   │   └── update.sh
│   └── .../
├── docs/
│   └── cli-architecture.md      # This document
└── update.sh                     # Preserved for scripts/CI
```

### Technology Choice: Textual (Python)

**Why Textual?**
- Modern async-first TUI framework
- CSS-like styling, reactive widgets
- Excellent documentation and active development
- Python ecosystem for Docker SDK integration
- Used by: Trogon, posting, toolong

**Alternatives considered:**

| Framework | Language | Trade-off |
|-----------|----------|-----------|
| Bubble Tea | Go | More polished, but requires Go rewrite |
| Ink | JS/React | Familiar patterns, but adds Node dependency |
| Ratatui | Rust | Fast, but steeper learning curve |
| dialog/whiptail | Bash | Zero deps, but limited interactivity |

---

## Service Metadata Schema

Each service declares its configuration in `service.yaml`:

```yaml
# services/openmemory/service.yaml
name: OpenMemory
description: Persistent memory layer for AI agents
category: core  # core | optional | experimental

vendor:
  url: https://github.com/CaviraOSS/OpenMemory.git
  ref: v1.2.3  # tag, branch, or commit

ports:
  - name: API
    port: 8787
    health_endpoint: /health
  - name: Dashboard
    port: 3737
    health_endpoint: /

env_vars:
  - name: OPENAI_API_KEY
    required: true
    secret: true
    description: OpenAI API key for embeddings
  - name: OPENMEMORY_PORT
    required: false
    default: "8787"

dependencies:
  system:
    - docker
    - docker-compose
  services: []  # other tools services this depends on
```

**Benefits:**
- Auto-discovery of services
- Dynamic menu generation
- Health check configuration
- Validation before install
- Documentation generation

---

## Core Components

### ServiceRegistry

Discovers and loads service metadata:

```python
class ServiceRegistry:
    def discover(self) -> list[ServiceConfig]:
        """Scan services/*/service.yaml"""
    
    def get(self, name: str) -> ServiceConfig:
        """Get specific service config"""
    
    def validate(self, service: ServiceConfig) -> list[str]:
        """Check dependencies, env vars"""
```

### ServiceLifecycle

Manages service operations:

```python
class ServiceLifecycle:
    async def install(self, service: str) -> AsyncIterator[str]:
        """Run update.sh, stream output"""
    
    async def start(self, service: str) -> None:
        """docker compose up -d"""
    
    async def stop(self, service: str) -> None:
        """docker compose down"""
    
    async def restart(self, service: str) -> None:
        """stop + start"""
    
    async def logs(self, service: str, follow: bool) -> AsyncIterator[str]:
        """docker compose logs"""
```

### HealthMonitor

Checks service health:

```python
class HealthMonitor:
    async def check(self, service: str) -> ServiceStatus:
        """Check docker status + health endpoints"""
    
    async def watch(self, services: list[str]) -> AsyncIterator[StatusUpdate]:
        """Continuous health monitoring"""
```

---

## User Interface

### Main Screen

```
┌─────────────────────────────────────────────────────────────┐
│  🛠️  Tools Manager                              v0.1.0 [?]  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Services                              Status               │
│  ───────────────────────────────────────────────────────    │
│  ▸ OpenMemory                          ● Running            │
│    Piper TTS                           ● Running            │
│    LangFuse                            ○ Stopped            │
│    LanguageTool                        ◌ Not installed      │
│                                                             │
│  ───────────────────────────────────────────────────────    │
│  [i]nstall  [s]tart  [S]top  [r]estart  [l]ogs  [c]onfig   │
│  [a]ll start  [A]ll stop  [u]pdate all                      │
│                                                             │
│  Press ? for help, q to quit                                │
└─────────────────────────────────────────────────────────────┘
```

### Status Indicators

| Symbol | Meaning |
|--------|---------|
| ● | Running and healthy |
| ◐ | Running, health unknown |
| ○ | Stopped |
| ◌ | Not installed |
| ✕ | Error / unhealthy |

---

## Implementation Phases

### Phase 1: Foundation ✅
> Goal: Basic CLI that can discover and display services

- [x] Create `cli/` package structure
- [x] Define `service.yaml` schema
- [x] Add `service.yaml` to each existing service
- [x] Implement `ServiceRegistry` with discovery
- [x] Implement `HealthMonitor` with docker + HTTP checks
- [x] Create basic Textual app with service list
- [x] Display real-time status for all services

**Deliverable**: `python -m cli` shows service list with live status

### Phase 2: Core Actions ✅
> Goal: Full service lifecycle management

- [x] Implement `ServiceLifecycle.start()` / `stop()` / `restart()`
- [x] Implement `ServiceLifecycle.install()` wrapping update.sh
- [x] Add log streaming view
- [x] Add keyboard shortcuts for all actions
- [ ] Add confirmation dialogs for destructive actions (deferred)
- [x] Handle errors gracefully with user feedback
- [x] **NEW**: Custom lifecycle commands in service.yaml (not just Docker!)

**Deliverable**: Can install, start, stop, restart any service from TUI

**Key Enhancement**: Services can now define custom lifecycle commands in `service.yaml`:
- Supports non-Docker services (systemd, custom scripts, Python processes, etc.)
- Falls back to docker-compose if no custom commands specified
- See `docs/service-yaml-spec.md` for full specification

### Phase 3: Configuration ✅
> Goal: Guided setup and configuration editing

- [x] Create `.env` editor screen
- [x] Validate required env vars per service
- [x] First-run wizard for initial setup
- [x] Per-service config overrides
- [x] Secret masking in UI

**Deliverable**: New users can complete setup entirely through TUI

**Implementation Notes**:
- `cli/screens/config_editor.py`: Full `.env` editor with Input widgets for each env var
- `cli/screens/setup_wizard.py`: First-run wizard shown when required env vars are missing
- Secret values use `password=True` on Input widgets for masking
- Each service has its own `.env` file in its directory (e.g., `services/openmemory/.env`)
- Press `c` in main screen to open config editor for selected service
- Starting a service with missing required env vars triggers the setup wizard

### Phase 4: Polish
> Goal: Production-ready developer tool

- [ ] Add `--help` and non-interactive CLI commands
- [x] Add `pyproject.toml` with `[project.scripts]` entry point (done in Phase 1)
- [ ] Notifications/toasts for background events
- [ ] Persistent user preferences
- [ ] Color themes (light/dark)
- [ ] Comprehensive error messages
- [ ] Documentation: README, CONTRIBUTING, examples

**Deliverable**: Publishable to PyPI, usable by external contributors

---

## CLI Commands (Phase 4)

In addition to the TUI, provide non-interactive commands for scripting:

```bash
# Interactive TUI (default)
tools

# Non-interactive commands
tools list                    # List services and status
tools status [service]        # Check health
tools start <service>         # Start a service
tools stop <service>          # Stop a service
tools restart <service>       # Restart a service
tools install <service>       # Run update.sh for service
tools logs <service> [-f]     # View/follow logs
tools config                  # Show current configuration
tools config set KEY=VALUE    # Set environment variable
```

---

## Testing Strategy

### Unit Tests
- `ServiceRegistry` discovery logic
- `service.yaml` schema validation
- Health check parsing

### Integration Tests
- Docker compose operations (use test fixtures)
- End-to-end install flow

### Manual Testing Checklist
- [ ] Fresh install on clean machine
- [ ] Update existing installation
- [ ] Start/stop individual services
- [ ] Handle missing Docker gracefully
- [ ] Handle network errors in health checks

---

## Open Questions

1. **Dependency ordering**: Should we auto-start dependencies? (e.g., if service A depends on B)
2. **Update notifications**: Check for new versions of vendor repos?
3. **Multi-machine sync**: Any special handling for Git sync workflow?
4. **Windows support**: Textual works on Windows, but shell scripts don't

---

## References

- [Textual Documentation](https://textual.textualize.io/)
- [Docker SDK for Python](https://docker-py.readthedocs.io/)
- [Bubble Tea](https://github.com/charmbracelet/bubbletea) (Go alternative)
- [Trogon](https://github.com/Textualize/trogon) (Textual CLI example)

