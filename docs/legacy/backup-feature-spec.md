# Backup & Restore Feature Specification

**Status:** Draft  
**Created:** 2026-01-16  
**Author:** Sasha + Claude

## Overview

Add backup and restore capabilities to the tools CLI, allowing users to:
1. Manually backup/restore service data via TUI
2. Optionally enable automated backups via cron
3. Sync backups to cloud storage (e.g., Google Drive) for multi-machine access

## User Stories

1. **As a user**, I want to backup OpenMemory so I can restore it if something breaks
2. **As a user**, I want automated nightly backups without thinking about it
3. **As a user**, I want my backups synced to cloud storage for multi-machine use
4. **As a user**, I want to opt-out specific services (e.g., LangFuse is too large)
5. **As a user**, I want restore to require confirmation (prevent accidents)

---

## Design Concerns

### C1: Restore Must Be Safe
- Restore is destructive (overwrites current data)
- Must require explicit confirmation dialog
- Should NOT be triggered by a single keypress
- Consider: show what will be overwritten, backup age, size

### C2: Cron Should Be "Set and Forget"
- Users configure once, then forget
- TUI is for initial setup, not daily use
- Cron runs independently of TUI

### C3: Per-Service Opt-In
- Some services have data worth backing up (OpenMemory)
- Some are too large (LangFuse with ClickHouse)
- Some have no persistent data (LanguageTool)
- Default should probably be OFF (explicit opt-in)

### C4: Configuration Complexity
- Already have: `service.yaml` (static), `.env` (per-service runtime)
- Adding backup config increases complexity
- Need clear separation: WHAT can be backed up vs. WHAT the user wants

---

## Configuration Architecture

### Layer 1: Service Capabilities (service.yaml)

Declares what CAN be backed up (static, version-controlled):

```yaml
# services/openmemory/service.yaml
data:
  volumes:
    - name: openmemory_data      # Docker volume name (required)
      container: openmemory      # Container to stop during backup (optional)
```

That's it. No strategies, no size hints. The backup logic is simple:
1. Stop the container (if specified)
2. Tar the volume
3. Restart the container

If a service needs something fancier, it can provide a custom script via `lifecycle.backup`.

### Layer 2: User Preferences (backup.yaml)

Declares what the user WANTS backed up (runtime, gitignored):

```yaml
# backup.yaml (at repo root, gitignored)
backup_dir: ~/Google Drive/Backups/tools   # Required
retention_days: 7                           # Optional, default 7

services:
  openmemory: true    # Enable backup
  langfuse: false     # Explicitly disable (or just omit)
```

**Why backup.yaml (not .env):**
- Single place for all backup config
- Clear separation from secrets
- Structured (not just key=value)
- Easy to edit manually

---

## TUI Integration

### New Key Bindings

| Key | Action | Confirmation Required? |
|-----|--------|------------------------|
| `b` | Backup selected service | No (safe operation) |
| `B` | Open backup settings screen | No |
| ??? | Restore | YES (see below) |

### Restore Flow (Safety First)

Restore should NOT be a single keypress. Options:

**Option 1: Two-step confirmation**
1. User presses `R` (or goes to menu)
2. Shows restore screen with:
   - List of available backups (with dates, sizes)
   - Current data age/size
   - Warning message
3. User selects backup and confirms with `Enter`
4. Final confirmation: "Type 'RESTORE' to confirm"

**Option 2: Menu-only access**
- No direct keybinding for restore
- Access via menu: `m` → Restore → Select backup → Confirm

**Option 3: Command-line only**
- TUI only for backup, restore via CLI:
  ```bash
  uv run tools restore openmemory --from=2026-01-15
  ```
- Forces intentional action

### Backup Settings Screen (`B`)

```
┌─ Backup Settings ──────────────────────────────────┐
│                                                     │
│  Backup Directory: ~/Google Drive/Backups/tools    │
│  Retention: 7 days                                  │
│                                                     │
│  Services:                                          │
│  [x] OpenMemory                           [Backup] │
│  [ ] LangFuse                                       │
│  [ ] Piper TTS                                      │
│                                                     │
│  Cron: Not installed                                │
│  [Install Cron Job]                                 │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

## Cron Integration

### How It Works

1. User enables backup for services in TUI
2. User clicks "Install Cron Job"
3. CLI generates and installs crontab entry:
   ```
   0 3 * * * /path/to/tools/scripts/backup-cron.sh >> /tmp/tools-backup.log 2>&1
   ```

### The Cron Script

```bash
#!/bin/bash
# scripts/backup-cron.sh
# Reads backup.yaml and backs up enabled services

TOOLS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$TOOLS_ROOT"

# Use Python to read config and run backups
exec uv run python -m cli.backup --cron
```

### Cron Management in TUI

- Show current cron status (installed/not installed)
- Button to install/uninstall cron job
- Show last backup time and any errors

---

## Open Questions

1. **Where to store backup.yaml?** Repo root (current plan) or `~/.config/tools/`?
2. **Should restore be TUI or CLI-only?** CLI-only is safer.

---

## Implementation Phases

### Phase 1: MVP
- [ ] Add `data:` section to service.yaml spec
- [ ] Create backup.yaml loader
- [ ] Implement backup logic (stop → tar → start)
- [ ] Add `b` keybinding for manual backup of selected service
- [ ] CLI command: `uv run tools restore <service> --from=<backup>`

### Phase 2: TUI Settings
- [ ] Create backup settings screen (`B` key)
- [ ] Edit backup_dir, retention_days
- [ ] Toggle services on/off

### Phase 3: Cron
- [ ] Create backup-cron.sh script
- [ ] Add cron install/uninstall button to settings screen

---

## References

- Current service.yaml spec: `docs/service-yaml-spec.md`
- CLI architecture: `docs/cli-architecture.md`
- OpenMemory backup discussion: 2026-01-16 conversation

