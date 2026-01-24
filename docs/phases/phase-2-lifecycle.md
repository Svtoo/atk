# Phase 2: Service Lifecycle

> **Status**: Complete ✅
> **Last Updated**: 2026-01-24

Service lifecycle commands: start, stop, restart, status, logs, run, install.

## Deferred from Phase 1

- [x] Run `install` lifecycle event on `atk add`
- [x] Run `stop` lifecycle event on `atk remove`
- [x] `atk status` command

## Overview

Phase 2 adds the ability to control plugin services. All lifecycle commands are **plugin-agnostic** — they execute whatever the plugin defines in `plugin.yaml`.

**Key Design Decisions:**
- Lifecycle commands come from `plugin.yaml` `lifecycle` section
- **No sensible defaults** — plugin must define commands explicitly (deferred to backlog)
- Commands run in plugin directory as working directory
- Exit codes passed through from underlying commands
- Warning if lifecycle command not defined (fail loudly, not silently)

---

## 2.1 Lifecycle Infrastructure ✅

### 2.1.1 Plugin Loader ✅
- [x] Create `plugin.py` module
  - [x] `load_plugin(atk_home, identifier)` — load plugin by name or directory
  - [x] Returns `(PluginSchema, plugin_dir)` tuple
  - [x] Error if plugin not found (exit code 4)
- [x] Tests for plugin loading (6 tests)

### 2.1.2 Lifecycle Executor ✅
- [x] Create `lifecycle.py` module
  - [x] `run_lifecycle_command(plugin, plugin_dir, command_name)` — execute lifecycle command
  - [x] `LifecycleCommand = Literal["install", "start", "stop", "restart", "logs", "status"]`
  - [x] Get command from `plugin.lifecycle.<command_name>`
  - [x] Raise `LifecycleCommandNotDefinedError` if command not defined
  - [x] Run in plugin directory as cwd
  - [x] Stream stdout/stderr to terminal
  - [x] Return exit code from command
- [x] Tests for lifecycle execution (6 tests)

---

## 2.2 `atk install` ✅

Run the install lifecycle command for plugin(s). Used for:
1. **Update**: Re-run install after plugin files changed
2. **Bootstrap**: Install all plugins on new machine after `git clone`

- [x] Implement `atk install <plugin>` command
  - [x] Find plugin by name or directory
  - [x] Run `install` lifecycle command
  - [x] Show warning if `install` not defined (fail loudly)
  - [x] Report output to user
- [x] Implement `atk install --all`
  - [x] Install all plugins in manifest order
  - [x] Continue on failure, report summary
  - [x] Track skipped plugins (no install defined)
- [x] CLI integration with proper exit codes
- [x] Tests (9 tests: unit + CLI)

**Workflow:**
- `atk add` = copy files + run install (adding new plugins)
- `atk install` = run install only (update or bootstrap)

---

## 2.3 `atk start` ✅

- [x] Implement `atk start <plugin>` command
  - [x] Find plugin by name or directory
  - [x] Run `start` lifecycle command
  - [x] Show warning if `start` not defined (fail loudly)
  - [x] Report success/failure
- [x] Implement `atk start --all`
  - [x] Start all plugins in manifest order
  - [x] Continue on failure, report summary
  - [x] Track skipped plugins (no start defined)
- [x] CLI integration with proper exit codes
- [x] Tests (11 tests: unit + CLI)

---

## 2.4 `atk stop` ✅

- [x] Implement `atk stop <plugin>` command
  - [x] Find plugin by name or directory
  - [x] Run `stop` lifecycle command
  - [x] Show warning if `stop` not defined (fail loudly)
  - [x] Report success/failure
- [x] Implement `atk stop --all`
  - [x] Stop all plugins in **reverse** manifest order
  - [x] Continue on failure, report summary
  - [x] Track skipped plugins (no stop defined)
- [x] CLI integration with proper exit codes
- [x] Tests (8 tests: unit + CLI)

---

## 2.5 `atk restart` ✅

- [x] Implement `atk restart <plugin>` command
  - [x] Find plugin by name or directory
  - [x] Run `restart` lifecycle command
  - [x] Error if `restart` not defined (no automatic stop+start fallback)
  - [x] Report success/failure
- [x] Implement `atk restart --all`
  - [x] Stop all (reverse order), then start all (manifest order)
  - [x] Aborts start phase if stop phase has failures
- [x] CLI integration with proper exit codes
- [x] Tests (12 tests: unit + CLI)

---

## 2.6 `atk status` ✅

- [x] Implement `atk status [plugin]` command
  - [x] If plugin specified: show status for that plugin
  - [x] If no plugin: show status for all plugins
- [x] Status display format:
  ```
  NAME              STATUS    PORTS
  OpenMemory        running   8787
  Langfuse          stopped   -
  ```
- [x] Run `status` lifecycle command to get state
- [x] Parse output to determine: running, stopped, unknown
- [x] CLI integration with proper exit codes
- [x] Tests (14 tests: 5 unit + 2 get_all + 7 CLI)

---

## 2.7 `atk logs` ✅

- [x] Implement `atk logs <plugin>` command
  - [x] Find plugin by name or directory
  - [x] Run `logs` lifecycle command
  - [x] Stream output to terminal
- [ ] Future: `--follow`, `--tail` flags (defer to backlog)
- [x] CLI integration with proper exit codes
- [x] Tests (4 tests)

---

## 2.8 `atk run` ✅

- [x] Implement `atk run <plugin> <script>` command
  - [x] Find plugin by name or directory
  - [x] Look for script in plugin root directory
  - [x] Execute script, pass through exit code
- [x] Script discovery: `<plugin_dir>/<script>` or `<plugin_dir>/<script>.sh`
- [x] CLI integration with proper exit codes
- [x] Tests (6 tests)

---

## 2.9 Wire Up Deferred Items ✅

### Install Lifecycle on Add

The `install` lifecycle command is called on `atk add`. By convention, **install is also update** — running `atk add` on an existing plugin re-copies files and re-runs install (idempotent).

- [x] Update `atk add` to run `install` lifecycle after copying files
  - [x] Skip silently if `install` not defined (optional lifecycle command)
  - [x] Report install output to user
  - [x] Fail `atk add` if install command fails (exit code 6)
  - [x] Clean up plugin directory and manifest entry on install failure
- [x] Tests for install lifecycle (4 tests)

### Stop Lifecycle on Remove

- [x] Update `atk remove` to run `stop` lifecycle before removing files
  - [x] Skip silently if `stop` not defined
  - [x] Continue with removal even if stop fails (warn user)
- [x] Tests for stop lifecycle on remove (3 tests)

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

- [x] All lifecycle commands implemented and tested
- [x] Go over all commands and flags manually and test them
- [x] `atk add` runs install lifecycle
- [x] `atk remove` runs stop lifecycle
- [x] `atk status` shows plugin states
- [x] Documentation updated

