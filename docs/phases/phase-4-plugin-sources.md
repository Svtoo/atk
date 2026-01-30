# Phase 4: Plugin Sources

> **Status**: Planning
> **Last Updated**: 2026-01-30

Registry and git URL sources for plugins, version pinning, and the upgrade command.

## Goals

1. Users can install plugins by name from the ATK registry
2. Users can install plugins from any git repository with an `.atk/` directory
3. Users can upgrade plugins to the latest version from their source
4. Plugin versions are pinned in manifest for reproducible setups
5. User customizations survive upgrades

---

## Scenarios

### Scenario 1: Installing from Registry

**User story:** I want to install OpenMemory without knowing where it lives.

**Flow:**
1. `atk add openmemory`
2. ATK fetches registry index, finds openmemory
3. ATK sparse-checkouts `plugins/openmemory/` from registry
4. ATK copies files to `~/.atk/plugins/openmemory/`
5. ATK updates manifest with source type and commit hash
6. ATK prompts for required env vars
7. ATK runs install lifecycle
8. ATK commits changes

**Edge cases:**
- Plugin not in registry → error with helpful message
- Network unavailable → error, suggest checking connection
- Plugin already installed → error "plugin exists, use `atk upgrade`"

### Scenario 2: Installing from Git URL

**User story:** I want to install a plugin from a GitHub repository.

**Flow:**
1. `atk add github.com/org/some-tool`
2. ATK clones repo with sparse checkout for `.atk/` directory
3. ATK validates `.atk/plugin.yaml` exists and is valid
4. ATK copies `.atk/` contents to `~/.atk/plugins/<name>/`
5. ATK updates manifest with source type, URL, and commit hash
6. ATK prompts for required env vars
7. ATK runs install lifecycle
8. ATK commits changes

**Edge cases:**
- No `.atk/` directory in repo → error with helpful message
- Invalid plugin.yaml → error with validation details
- Private repo user has no access to → git error passed through

### Scenario 3: Upgrading a Plugin

**User story:** I want to update OpenMemory to the latest version.

**Flow:**
1. `atk upgrade openmemory`
2. ATK reads source info from manifest
3. ATK fetches latest from source (registry or git)
4. ATK replaces plugin files (preserving `custom/` directory)
5. ATK updates manifest with new commit hash
6. If new required env vars exist → run setup prompts
7. ATK runs install lifecycle
8. ATK commits changes

**Edge cases:**
- Plugin not installed → error "plugin not found"
- Local source plugin → error "local plugins cannot be upgraded, use `atk add`"
- No changes (already at latest) → no-op, report "already up to date"
- New required env vars → prompt user before proceeding

### Scenario 4: Upgrading All Plugins

**User story:** I want to update all my plugins to latest versions.

**Flow:**
1. `atk upgrade --all`
2. For each upgradeable plugin in manifest:
   - Fetch latest from source
   - Replace files (preserving `custom/`)
   - Update manifest
   - Check for new required env vars
   - Run install lifecycle
3. Report summary: upgraded, skipped (local), failed

**Edge cases:**
- Mix of registry, git, and local plugins → skip local with note
- One plugin fails → continue with others, report failures at end
- Network issues mid-upgrade → partial state, user can re-run

### Scenario 5: Bootstrap on New Machine

**User story:** I cloned my ATK home on a new laptop and need to set it up.

**Flow:**
1. `git clone <my-atk-repo> ~/.atk`
2. `atk setup --all` (configure env vars)
3. `atk install --all`
4. For each plugin in manifest:
   - Fetch from source at pinned version (commit hash)
   - Run install lifecycle
5. All plugins ready

**Edge cases:**
- Pinned version no longer exists → error with details
- Some plugins fail → continue, report summary
- Already have plugin files → skip fetch, just run install

### Scenario 6: User Customizations

**User story:** I customized my Langfuse plugin and want to upgrade without losing changes.

**Flow:**
1. User has `plugins/langfuse/custom/docker-compose.override.yml`
2. `atk upgrade langfuse`
3. ATK replaces all files EXCEPT `custom/` directory
4. User's customizations preserved
5. ATK runs install lifecycle

**Edge cases:**
- User modified files outside `custom/` → overwritten (expected behavior)
- `custom/overrides.yaml` conflicts with new plugin.yaml → user's overrides win

---

## Acceptance Criteria

### Registry Support
- [ ] Create `atk-registry` repository with flat `plugins/` structure
- [ ] CI generates `index.yaml` on merge to main
- [ ] `atk add <name>` resolves from registry
- [ ] Sparse checkout fetches only the plugin directory
- [ ] Manifest records `source.type: registry` and `source.ref: <hash>`

### Git URL Support
- [ ] `atk add <url>` clones and looks for `.atk/` directory
- [ ] Supports common URL formats (github.com/org/repo, full https URLs)
- [ ] Sparse checkout fetches only `.atk/` directory
- [ ] Manifest records `source.type: git`, `source.url`, and `source.ref`

### Upgrade Command
- [ ] `atk upgrade <plugin>` fetches latest and updates
- [ ] `atk upgrade --all` upgrades all upgradeable plugins
- [ ] Preserves `custom/` directory during upgrade
- [ ] Prompts for new required env vars
- [ ] Runs install lifecycle after upgrade
- [ ] Updates manifest with new commit hash
- [ ] Commits changes (if auto_commit enabled)

### Version Pinning
- [ ] Manifest stores commit hash for registry and git sources
- [ ] `atk install --all` fetches at pinned versions (bootstrap)
- [ ] Pinned versions enable reproducible setups

### Customization Preservation
- [ ] `custom/` directory is never modified by ATK
- [ ] `.gitignore` pattern tracks only `custom/` contents
- [ ] `custom/overrides.yaml` merged with plugin.yaml at runtime
- [ ] User scripts in `custom/` take precedence

---

## Implementation Sections

### 4.1 Source Resolution

Determine source type from user input:
1. If path exists locally → local source
2. If matches URL pattern → git source
3. Otherwise → registry lookup

### 4.2 Registry Infrastructure

- Create `atk-registry` repo with `plugins/` directory
- Add CI workflow to generate `index.yaml`
- Implement registry fetch and plugin resolution

### 4.3 Git Source Support

- Implement sparse checkout for `.atk/` directory
- Parse various URL formats (github.com/org/repo, https://...)
- Handle authentication via user's git config

### 4.4 Upgrade Command

- Implement `atk upgrade <plugin>` command
- Implement `atk upgrade --all` flag
- Preserve `custom/` during file replacement
- Detect and prompt for new required env vars

### 4.5 Manifest Source Tracking

- Add `source` field to manifest plugin entries
- Store type, URL (for git), and ref (commit hash)
- Update ref on upgrade

### 4.6 Bootstrap Flow

- Update `atk install --all` to fetch missing plugins
- Fetch at pinned version from manifest
- Handle missing plugins gracefully

### 4.7 Gitignore Updates

- Update `.gitignore` template for new pattern
- Ensure `custom/` directories are tracked
- Ensure plugin files (except custom/) are ignored

---

## Deferred

- **Registry search**: `atk search <query>` — defer to Phase 5
- **Version constraints**: Semver ranges, "latest" tag — keep it simple with commit hashes
- **Automatic updates**: No auto-update mechanism — user controls when to upgrade
- **Private registries**: Single public registry for now

