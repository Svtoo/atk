# Phase 1: Core CLI ✅

> **Status**: Complete
> **Last Updated**: 2026-01-23

Phase 0 (Foundation) and Phase 1 (Core CLI) implementation details.

## Phase 0: Foundation ✅

- [x] Create new repo `atk` with clean structure
- [x] Set up Python project (pyproject.toml, uv)
- [x] Define plugin YAML schema (full spec in `specs/plugin-schema.md`)
- [x] Implement schema validation (17 tests)
- [x] CLI skeleton with version banner

## Phase 1: Core CLI ✅

### 1.1 Infrastructure ✅
- [x] Create `manifest_schema.py` — Pydantic models for manifest.yaml
- [x] Create `home.py` — ATK Home resolution and validation
  - [x] `get_atk_home()` — resolve ATK_HOME env var or default ~/.atk/
  - [x] `validate_atk_home(path)` — returns ValidationResult with errors
  - [x] `ATKHomeNotInitializedError` exception
- [x] Create `exit_codes.py` with constants (0-7)
- [x] Create `validation.py` with ValidationResult dataclass

### 1.2 `atk init` ✅
- [x] Implement `atk init [directory]` command
  - [x] Resolve target directory (argument > ATK_HOME > ~/.atk/)
  - [x] Create directory structure (manifest.yaml, plugins/, .gitignore)
  - [x] Initialize git repository
  - [x] Create initial commit
  - [x] No-op if already initialized (idempotent)
  - [x] Exit code 1 if path exists but is invalid
- [x] Tests with temporary directory fixture (12 tests)

### 1.3 `atk add` ✅
- [x] Implement plugin directory name sanitization
  - [x] Regex validation: `^[a-z][a-z0-9]*(-[a-z0-9]+)*$`
  - [x] Generate from display name (lowercase, replace spaces/underscores with hyphens)
  - [x] Strip special characters and injection attempts
- [x] Implement `atk add <source>` command
  - [x] Detect source type (directory vs single file)
  - [x] Validate source contains valid plugin.yaml
  - [x] Copy files to plugins/<directory>/
  - [x] Update manifest.yaml with new plugin entry
  - [ ] Run install lifecycle event (if defined) — deferred to Phase 2
  - [ ] Git commit (if auto_commit: true) — deferred to 1.6
  - [x] Overwrite if directory exists (recovery scenario)
- [x] Tests for both source types (18 tests)

### 1.4 `atk remove`
- [x] Implement `atk remove <plugin>` command
  - [x] Find plugin by name OR directory in manifest
  - [ ] Run stop lifecycle event (graceful shutdown) — deferred to Phase 2
  - [x] Remove plugin directory
  - [x] Remove entry from manifest
  - [ ] Git commit (if auto_commit: true) — deferred to Phase 1.6
  - [x] No-op if plugin not found (idempotent)
- [x] Tests (9 tests: 5 unit, 4 CLI)
- [x] Clean error messages (no Pydantic URLs) via `errors.py`
- [x] `require_initialized_home()` helper for CLI commands

### 1.5 Git Integration ✅
- [x] Extract git operations to `git.py` module (currently inline in init.py)
  - [x] `git_init(path)` — initialize git repo
  - [x] `git_add(path, files)` — stage files
  - [x] `git_commit(path, message)` — commit with message (returns False if nothing to commit)
  - [x] `is_git_repo(path)` — check if directory is git repo
  - [x] `has_staged_changes(path)` — check if there are staged changes
- [x] Tests for git operations (11 tests)
- [x] Wire up auto_commit in add/remove commands

### 1.6 Exit Codes ✅
- [x] Create `exit_codes.py` with constants (0-7)
- [x] Use exit codes consistently across all commands

---

## Deferred to Phase 2

The following items were deferred from Phase 1:
- Run `install` lifecycle event on `atk add` (1.3)
- Run `stop` lifecycle event on `atk remove` (1.4)
- `atk status` command (depends on lifecycle events)

See `phase-2-lifecycle.md` for Phase 2 details.
