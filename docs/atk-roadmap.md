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

### 1.1 Infrastructure
- [ ] Create `manifest.py` — Pydantic models for manifest.yaml
- [ ] Create `home.py` — ATK Home resolution and validation
  - [ ] `get_atk_home()` — resolve ATK_HOME env var or default ~/.atk/
  - [ ] `is_valid_atk_home(path)` — check if directory is valid ATK Home
  - [ ] `ATKHomeNotInitializedError` exception

### 1.2 `atk init`
- [ ] Implement `atk init [directory]` command
  - [ ] Resolve target directory (argument > ATK_HOME > ~/.atk/)
  - [ ] Create directory structure (manifest.yaml, plugins/, .gitignore)
  - [ ] Initialize git repository
  - [ ] Create initial commit
  - [ ] No-op if already initialized (idempotent)
  - [ ] Exit code 1 if path exists but is invalid
- [ ] Tests with temporary directory fixture

### 1.3 `atk add`
- [ ] Implement plugin directory name sanitization
  - [ ] Regex validation: `^[a-z][a-z0-9-]*[a-z0-9]$`
  - [ ] Generate from display name (lowercase, replace spaces/underscores with hyphens)
- [ ] Implement `atk add <source>` command
  - [ ] Detect source type (directory vs single file)
  - [ ] Validate source contains valid plugin.yaml
  - [ ] Copy files to plugins/<directory>/
  - [ ] Update manifest.yaml with new plugin entry
  - [ ] Run install lifecycle event (if defined)
  - [ ] Git commit (if auto_commit: true)
  - [ ] Overwrite if directory exists (recovery scenario)
- [ ] Tests for both source types

### 1.4 `atk remove`
- [ ] Implement `atk remove <plugin>` command
  - [ ] Find plugin by directory name in manifest
  - [ ] Run stop lifecycle event (graceful shutdown)
  - [ ] Remove plugin directory
  - [ ] Remove entry from manifest
  - [ ] Git commit (if auto_commit: true)
  - [ ] No-op if plugin not found (idempotent)
- [ ] Tests

### 1.5 `atk status`
- [ ] Implement `atk status [plugin]` command
  - [ ] List all plugins if no argument
  - [ ] Show single plugin status if argument provided
  - [ ] Display: name, directory, status (running/stopped/unknown)
  - [ ] Call plugin's status lifecycle event
- [ ] Tests

### 1.6 Git Integration
- [ ] Create `git.py` — Git operations via subprocess
  - [ ] `git_init(path)` — initialize git repo
  - [ ] `git_add(path, files)` — stage files
  - [ ] `git_commit(path, message)` — commit with message
  - [ ] `is_git_repo(path)` — check if directory is git repo
- [ ] Tests for git operations

### 1.7 Exit Codes
- [ ] Create `exit_codes.py` with constants:
  - [ ] SUCCESS = 0
  - [ ] GENERAL_ERROR = 1
  - [ ] INVALID_ARGS = 2
  - [ ] HOME_NOT_INITIALIZED = 3
  - [ ] PLUGIN_NOT_FOUND = 4
  - [ ] PLUGIN_INVALID = 5
  - [ ] DOCKER_ERROR = 6
  - [ ] GIT_ERROR = 7
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

