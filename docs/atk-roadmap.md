# ATK Roadmap

> High-level implementation plan from zero to working version.
>
> **Note**: Deferred features and ideas are in `atk-future.md`.

## Phase 0: Foundation ✅

- [x] Create new repo `atk` with clean structure
- [x] Set up Python project (pyproject.toml, uv)
- [x] Define plugin YAML schema (full spec in `plugin-schema.md`)
- [x] Implement schema validation (17 tests)
- [x] CLI skeleton with version banner

## Phase 1: Core CLI (Current)

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

### 1.5 `atk status`
- [ ] Implement `atk status [plugin]` command
  - [ ] List all plugins if no argument
  - [ ] Show single plugin status if argument provided
  - [ ] Display: name, directory, status (running/stopped/unknown)
  - [ ] Call plugin's status lifecycle event
- [ ] Tests

### 1.6 Git Integration
- [ ] Extract git operations to `git.py` module (currently inline in init.py)
  - [ ] `git_init(path)` — initialize git repo
  - [ ] `git_add(path, files)` — stage files
  - [ ] `git_commit(path, message)` — commit with message
  - [ ] `is_git_repo(path)` — check if directory is git repo
- [ ] Tests for git operations

### 1.7 Exit Codes ✅
- [x] Create `exit_codes.py` with constants (0-7)
- [ ] Use exit codes consistently across all commands

## Phase 2: Service Lifecycle

See `atk-future.md` for details. Includes:
- `atk start/stop/restart <plugin>`
- `atk logs <plugin>`
- `atk run <plugin> <script>`
- Health checks and sensible defaults

## Phases 3-10

See `atk-future.md` for details.

---

## Milestones

| Milestone             | Definition of Done                             |
|-----------------------|------------------------------------------------|
| **M1: Dogfood**       | Can manage 2+ plugins on local machine via CLI |
| **M2: Multi-machine** | Can sync setup across machines via git         |
| **M3: Public**        | Published to PyPI, registry has 5+ plugins     |

