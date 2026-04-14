# Phase 11: Git Sync

> **Status**: In Progress
> **Last Updated**: 2026-04-14

Remote synchronization for ATK Home. Users can add a git remote, auto-push after mutations, and see repository state in `atk status`.

## Goals

1. Users can manage the .atk git repo without navigating to the directory
2. Mutations can automatically push to a remote after committing
3. `atk status` shows the git repository state alongside plugin status

---

## Scenarios

### Scenario 1: Git Proxy

**User story:** I want to manage my .atk repo's git remote without `cd ~/.atk`.

**Flow:**
1. `atk git remote add origin git@github.com:user/dotfiles-atk.git`
2. ATK runs `git remote add origin ...` in ATK_HOME
3. Git output passed through to terminal

**Edge cases:**
- ATK Home not initialized -> exit 3
- Git not available -> exit 7
- Invalid git arguments -> git's own error, git's exit code

### Scenario 2: Auto-Push After Mutation

**User story:** I want my plugin changes to automatically sync to my remote.

**Flow:**
1. Edit `manifest.yaml` to set `auto_push: true`
2. `atk add openmemory`
3. ATK adds plugin, commits (auto_commit), pushes (auto_push)
4. Remote now has the latest state

**Edge cases:**
- No remote configured -> warn, don't error
- Push fails (auth, network) -> warn, don't error; commit already succeeded
- `auto_commit: false` with `auto_push: true` -> no push (push requires commit)

### Scenario 3: Repository Status

**User story:** I want to see if my .atk repo is in sync with the remote.

**Flow:**
1. `atk status`
2. ATK shows plugin table (existing behavior)
3. ATK shows Repository section: branch, remote, ahead/behind, last commit, working dir

**Edge cases:**
- No remote -> show `(none)` for remote, omit sync line
- No tracking branch -> show `(no tracking branch)` for sync
- Empty repo (no commits) -> gracefully degrade, show what's available
- Git queries fail -> skip failing fields, show what's available

---

## Tasks

- [ ] Write git-sync-spec.md
- [ ] Update ROADMAP.md with Phase 11
- [ ] Update commands-spec.md with `atk git` command
- [ ] Update home-spec.md with `auto_push` in manifest schema
- [ ] Update backlog.md — promote "Git push" item
- [ ] Add git helper functions to `git.py` (push, branch, remote info, ahead/behind, working dir status)
- [ ] Add `auto_push` field to `ConfigSection` in `manifest_schema.py`
- [ ] Add `atk git` proxy command to `cli.py`
- [ ] Add repository section to `atk status` output
- [ ] Wire auto-push into `add.py`, `remove.py`, `upgrade.py`
- [ ] Update initial manifest in `init.py` with `auto_push: false`
- [ ] Tests for all new functions and behaviors

## Acceptance Criteria

- `atk git remote add origin <url>` successfully adds a remote to .atk
- `atk git push` pushes .atk commits to the remote
- `atk git log --oneline` shows .atk commit history
- Setting `auto_push: true` in manifest causes mutations to push after commit
- Auto-push failure warns but does not fail the mutation
- `atk status` shows Repository section with branch, remote, sync, last commit, working dir
- `atk status` with no remote shows `(none)` gracefully
- `make check` passes (ruff + mypy + pytest)
