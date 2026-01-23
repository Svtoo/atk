# Phase 2: Service Lifecycle

> **Status**: Planning
> **Last Updated**: 2026-01-23

Service lifecycle commands: start, stop, restart, status, logs, run.

## Deferred from Phase 1

- [ ] Run `install` lifecycle event on `atk add`
- [ ] Run `stop` lifecycle event on `atk remove`
- [ ] `atk status` command

## Overview

Phase 2 adds the ability to control plugin services. All lifecycle commands are **plugin-agnostic** — they execute whatever the plugin defines in `plugin.yaml`.

**Key Design Decisions:**
- Lifecycle commands come from `plugin.yaml` `lifecycle` section
- Sensible defaults based on `service.type` (docker-compose, docker, systemd, script)
- Commands run in plugin directory as working directory
- Exit codes passed through from underlying commands

---

## 2.1 Lifecycle Infrastructure

### 2.1.1 Plugin Loader
- [ ] Create `plugin.py` module
  - [ ] `load_plugin(atk_home, identifier)` — load plugin by name or directory
  - [ ] Returns `PluginSchema` with resolved paths
  - [ ] Error if plugin not found (exit code 4)
- [ ] Tests for plugin loading (5+ tests)

### 2.1.2 Lifecycle Executor
- [ ] Create `lifecycle.py` module
  - [ ] `run_lifecycle_command(plugin, command_name)` — execute lifecycle command
  - [ ] Resolve command: custom → default for service type → error
  - [ ] Run in plugin directory as cwd
  - [ ] Stream stdout/stderr to terminal
  - [ ] Return exit code from command
- [ ] Default commands by service type:
  - [ ] `docker-compose`: `docker compose up -d`, `docker compose down`, etc.
  - [ ] `docker`: `docker start/stop {container_name}`
  - [ ] `systemd`: `systemctl start/stop {unit_name}`
  - [ ] `script`: must define in plugin.yaml (no default)
- [ ] Tests for lifecycle execution (8+ tests)

---

## 2.2 `atk start`

- [ ] Implement `atk start <plugin>` command
  - [ ] Find plugin by name or directory
  - [ ] Run `start` lifecycle command
  - [ ] Report success/failure
- [ ] Implement `atk start --all`
  - [ ] Start all plugins in manifest order
  - [ ] Continue on failure, report summary
- [ ] CLI integration with proper exit codes
- [ ] Tests (6+ tests: unit + CLI)

---

## 2.3 `atk stop`

- [ ] Implement `atk stop <plugin>` command
  - [ ] Find plugin by name or directory
  - [ ] Run `stop` lifecycle command
  - [ ] Report success/failure
- [ ] Implement `atk stop --all`
  - [ ] Stop all plugins in **reverse** manifest order
  - [ ] Continue on failure, report summary
- [ ] CLI integration with proper exit codes
- [ ] Tests (6+ tests: unit + CLI)

---

## 2.4 `atk restart`

- [ ] Implement `atk restart <plugin>` command
  - [ ] Find plugin by name or directory
  - [ ] Run `restart` lifecycle command (or stop + start if not defined)
  - [ ] Report success/failure
- [ ] Implement `atk restart --all`
  - [ ] Stop all (reverse order), then start all (manifest order)
- [ ] CLI integration with proper exit codes
- [ ] Tests (4+ tests)

---

## 2.5 `atk status`

- [ ] Implement `atk status [plugin]` command
  - [ ] If plugin specified: show status for that plugin
  - [ ] If no plugin: show status for all plugins
- [ ] Status display format:
  ```
  NAME              STATUS    PORTS
  OpenMemory        running   8787
  Langfuse          stopped   -
  ```
- [ ] Run `status` lifecycle command to get state
- [ ] Parse output to determine: running, stopped, error, unknown
- [ ] CLI integration with proper exit codes
- [ ] Tests (6+ tests)

---

## 2.6 `atk logs`

- [ ] Implement `atk logs <plugin>` command
  - [ ] Find plugin by name or directory
  - [ ] Run `logs` lifecycle command
  - [ ] Stream output to terminal
- [ ] Future: `--follow`, `--tail` flags (defer to backlog)
- [ ] CLI integration with proper exit codes
- [ ] Tests (4+ tests)

---

## 2.7 `atk run`

- [ ] Implement `atk run <plugin> <script>` command
  - [ ] Find plugin by name or directory
  - [ ] Look for script in plugin root directory
  - [ ] Execute script, pass through exit code
- [ ] Script discovery: `<plugin_dir>/<script>` or `<plugin_dir>/<script>.sh`
- [ ] CLI integration with proper exit codes
- [ ] Tests (4+ tests)

---

## 2.8 Wire Up Deferred Items

- [ ] Update `atk add` to run `install` lifecycle after copying files
- [ ] Update `atk remove` to run `stop` lifecycle before removing files
- [ ] Tests for lifecycle integration in add/remove (4+ tests)

---

## Test Fixtures

- [ ] Create test plugin fixtures with lifecycle commands
  - [ ] `tests/fixtures/plugins/lifecycle-plugin/` — docker-compose type
  - [ ] Mock docker commands for testing (or use script type)

---

## Exit Codes

| Code | Name | Used By |
|------|------|---------|
| 0 | SUCCESS | All commands on success |
| 3 | HOME_NOT_INITIALIZED | All commands |
| 4 | PLUGIN_NOT_FOUND | All commands |
| 6 | DOCKER_ERROR | start, stop, restart, status, logs |

---

## Definition of Done

- [ ] All lifecycle commands implemented and tested
- [ ] `atk add` runs install lifecycle
- [ ] `atk remove` runs stop lifecycle
- [ ] `atk status` shows plugin states
- [ ] 40+ new tests
- [ ] Documentation updated

