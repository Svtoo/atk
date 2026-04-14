# Git Sync Specification

> **Status**: Approved
> **Last Updated**: 2026-04-14

## Overview

ATK Home is a git-backed repository. Phase 1 introduced `auto_commit` — every mutation creates a local commit. Git Sync extends this with remote synchronization: users can add a remote, auto-push after mutations, and see the repository state in `atk status`.

## Design Principles

1. **Proxy, don't reinvent.** `atk git` passes arguments straight to `git` in ATK_HOME. Users already know git.
2. **Push is best-effort.** Auto-push failures warn but never fail the mutation. The commit already succeeded locally.
3. **Sensible defaults.** `auto_push` defaults to `false`. Users opt in after adding a remote.

## `atk git [args...]`

Thin proxy that runs `git <args>` in ATK_HOME.

### Behavior

1. Resolve ATK_HOME (env var or `~/.atk/`)
2. Validate ATK Home is initialized (exit 3 if not)
3. Require git available (exit 7 if not)
4. Execute `git <args>` in ATK_HOME with stdin/stdout/stderr passed through (no capture)
5. Return git's exit code

### Examples

```bash
atk git remote add origin git@github.com:user/dotfiles-atk.git
atk git remote show origin
atk git push
atk git pull
atk git log --oneline -5
atk git status
atk git diff
```

### Edge Cases

- No arguments (`atk git`) — passes no args to git, which prints git help. Acceptable.
- Interactive commands (`atk git rebase -i`) — works because stdin/stdout are passed through.
- Destructive commands (`atk git reset --hard`) — user's responsibility. ATK does not guard against this.

## `auto_push` Configuration

New field in the manifest `config` section.

### Manifest Schema

```yaml
config:
  auto_commit: true    # Existing (default: true)
  auto_push: false     # New (default: false)
```

### Rules

| `auto_commit` | `auto_push` | Remote exists | Behavior |
|---------------|-------------|---------------|----------|
| true | true | yes | Commit + push |
| true | true | no | Commit only, warn "no remote configured" |
| true | false | any | Commit only (current behavior) |
| false | true | any | Neither — `auto_push` requires `auto_commit` |
| false | false | any | Neither (current behavior) |

### Push Semantics

- Pushes the current branch to its upstream tracking branch
- Command: `git push` (no force, no explicit remote/branch — uses git defaults)
- On failure: print warning to stderr, do not exit with error
- On success: silent (consistent with auto_commit behavior)

## Enhanced `atk status` — Repository Section

After the plugin status table, `atk status` displays a repository section.

### Output Format

**With remote:**
```
Repository:
  Branch:      main
  Remote:      origin -> git@github.com:user/dotfiles-atk.git
  Sync:        2 ahead, 0 behind
  Last commit: Add plugin 'sasha-rules' (2m ago)
  Working dir: clean
```

**Without remote:**
```
Repository:
  Branch:      main
  Remote:      (none)
  Last commit: Add plugin 'sasha-rules' (2m ago)
  Working dir: clean
```

**With dirty working directory:**
```
Repository:
  Branch:      main
  Remote:      origin -> git@github.com:user/dotfiles-atk.git
  Sync:        0 ahead, 0 behind
  Last commit: Initialize ATK Home (3d ago)
  Working dir: 1 modified, 2 untracked
```

**No remote tracking branch:**
```
Repository:
  Branch:      main
  Remote:      origin -> git@github.com:user/dotfiles-atk.git
  Sync:        (no tracking branch)
  Last commit: Add plugin 'openmemory' (1h ago)
  Working dir: clean
```

### Fields

| Field | Source | Notes |
|-------|--------|-------|
| Branch | `git branch --show-current` | Current branch name |
| Remote | `git remote get-url origin` | First remote name + URL. `(none)` if no remotes |
| Sync | `git rev-list --left-right --count HEAD...@{upstream}` | Ahead/behind upstream. Omitted if no remote. `(no tracking branch)` if remote exists but no tracking |
| Last commit | `git log -1 --format='%s (%cr)'` | Subject + relative time |
| Working dir | `git status --porcelain` | `clean` if empty, otherwise count by category |

### Error Handling

If any git query fails (e.g., empty repo with no commits), the Repository section gracefully degrades — show what's available, skip what's not.

## Auto-Push Wiring

Mutations that auto-commit (`add`, `remove`, `upgrade`) gain auto-push:

```
mutation happens
  -> if auto_commit:
       git add -A
       git commit -m "..."
       -> if auto_push:
            git push (best-effort, warn on failure)
```

### Warning Messages

- No remote: `Warning: auto_push enabled but no remote configured. Run: atk git remote add origin <url>`
- Push failed: `Warning: auto-push failed: <git error message>`

## Exit Codes

`atk git` uses git's own exit codes (passed through). No new ATK exit codes needed.

For auto-push failures within mutations, the mutation still exits 0 (the commit succeeded).
