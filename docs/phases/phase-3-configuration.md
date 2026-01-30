# Phase 3: Configuration

> **Status**: Complete
> **Last Updated**: 2026-01-30

Environment variable management, port conflict detection, and MCP configuration output.

## Goals

1. Users can configure plugin environment variables through an interactive wizard
2. ATK fails fast when required env vars are missing (before wasting time on failed starts)
3. Users get clear warnings about port conflicts before starting services
4. Users can generate MCP config JSON for pasting into IDE/tool configurations
5. `atk status` shows environment configuration state at a glance

---

## Scenarios

### Scenario 1: Adding a New Plugin

**User story:** I'm adding OpenMemory to my ATK setup for the first time.

**Flow:**
1. `atk add ./openmemory/`
2. ATK copies plugin files
3. ATK detects plugin has required env vars (OPENAI_API_KEY)
4. ATK prompts: `OPENAI_API_KEY (required, secret): `
5. User enters API key (masked input)
6. ATK saves to `plugins/openmemory/.env`
7. ATK runs install lifecycle
8. Success message

**Edge cases:**
- Plugin has no env vars → skip wizard, proceed to install
- User cancels wizard (Ctrl+C) → abort add, clean up copied files
- Install fails after wizard → keep `.env` file (user already entered secrets)

### Scenario 2: Setting Up a New Machine

**User story:** I cloned my ATK home repo on a new laptop. I need to configure all plugins.

**Flow:**
1. `git clone <my-atk-repo> ~/.atk`
2. `atk setup --all`
3. For each plugin with env vars:
   - Show plugin name
   - Prompt for each variable (show defaults if defined)
   - Save to `.env`
4. `atk install --all`
5. `atk start --all`

**Edge cases:**
- Some plugins already have `.env` files (partial setup) → show current values, let user confirm or change
- Plugin has no env vars defined → skip silently
- User wants to skip a plugin → Ctrl+C skips current plugin, asks "Continue with next?"

### Scenario 3: Reconfiguring a Plugin

**User story:** I need to change my API key for Langfuse.

**Flow:**
1. `atk setup langfuse`
2. ATK shows current values (masked for secrets): `LANGFUSE_SECRET_KEY [****xxxx]: `
3. User presses Enter to keep, or types new value
4. ATK updates `.env` file
5. User runs `atk restart langfuse` to apply changes

**Edge cases:**
- Variable was set in environment but not in `.env` → show as "set in environment", offer to persist to `.env`
- User enters empty value for required var → reject, re-prompt

### Scenario 4: Starting a Plugin with Missing Config

**User story:** I try to start a plugin but forgot to run setup.

**Flow:**
1. `atk start openmemory`
2. ATK checks required env vars
3. OPENAI_API_KEY is not set
4. Error: `✗ Missing required environment variables for 'openmemory':`
   `  • OPENAI_API_KEY`
   `Run 'atk setup openmemory' to configure.`
5. Exit code 8

**Edge cases:**
- Multiple missing vars → list all of them
- Var is set in system environment but not `.env` → accept it (still works)
- `--all` flag with some plugins missing vars → fail fast on first, report which plugin

### Scenario 5: Port Conflict (Fail Fast)

**User story:** I try to start a plugin but the port is already in use.

**Flow:**
1. `atk start langfuse`
2. ATK checks ports declared in plugin.yaml
3. Port 3000 is in use
4. Error: `✗ Port 3000 is already in use`
   `  Langfuse requires this port for: Web UI`
   `  Stop the conflicting service or use 'atk restart langfuse' if it's already running.`
5. Exit code 9

**Edge cases:**
- Multiple ports in conflict → list all conflicting ports, then fail
- Plugin declares no ports → skip port check
- User wants to restart same plugin → use `atk restart` which stops first

### Scenario 6: Generating MCP Config

**User story:** I want to add Langfuse MCP to Claude Desktop.

**Flow:**
1. `atk mcp langfuse`
2. ATK reads MCP config from plugin.yaml
3. ATK resolves env var values from `.env`
4. Output:
   ```json
   {
     "langfuse": {
       "command": "docker",
       "args": ["exec", "-i", "langfuse", "npx", "@langfuse/mcp-server"],
       "env": {
         "LANGFUSE_PUBLIC_KEY": "pk-lf-xxx",
         "LANGFUSE_SECRET_KEY": "sk-lf-xxx"
       }
     }
   }
   ```
5. User copies and pastes into Claude Code or other agent's config

**Edge cases:**
- Plugin has no MCP config → error, exit code 5
- Required env var not set → warn, output `"VAR": "<NOT_SET>"`
- SSE transport → output `url` instead of `command`/`args`

### Scenario 7: Status with Env Info

**User story:** I want to see which plugins need configuration.

**Flow:**
1. `atk status`
2. Output shows missing required vars explicitly:
   ```
   NAME          STATUS    PORTS       ENV
   OpenMemory    running   8787 ✓      ✓
   Langfuse      stopped   3000 ✗      ! LANGFUSE_SECRET_KEY, LANGFUSE_PUBLIC_KEY (+2 optional)
   CustomTool    stopped   -           -
   ```
3. Legend: `✓` = all required set, `!` = missing required (listed), `-` = no vars defined
4. Optional vars shown as count only: `(+N optional)`

---

## Acceptance Criteria

### Environment Variables
- [x] `.env` files are created in plugin directories
- [x] `.env` files are gitignored (verified in `.gitignore`)
- [x] Env vars are injected into lifecycle command environment
- [x] Required vars block start/install with clear error message

### Setup Wizard
- [x] `atk add` prompts for env vars before install
- [x] `atk setup <plugin>` allows reconfiguration
- [x] `atk setup --all` configures all plugins
- [x] Secrets use masked input
- [x] Defaults are shown and accepted with Enter
- [x] Existing values shown (masked for secrets)

### Port Conflicts
- [x] Ports checked during `atk start`
- [x] Conflicts produce clear error with port number and description
- [x] Conflicts block start (exit code 9)
- [x] `atk restart` works because it stops first

### Restart Lifecycle Cleanup
- [x] Remove `restart` field from `LifecycleConfig` in `src/atk/plugin_schema.py`
- [x] Update `atk restart` command in `src/atk/cli.py` to always call stop then start
- [x] Update tests to reflect new behavior

### MCP Config
- [x] `atk mcp <plugin>` outputs valid JSON
- [x] Env vars are resolved from `.env`
- [x] Missing vars produce warning and placeholder
- [x] Error if plugin has no MCP config

### Status Enhancement
- [x] `atk status` shows ENV column
- [x] Missing required vars listed explicitly by name
- [x] Unset optional vars shown as count only

---

## Deferred

- **Env var validation**: Pattern matching for API keys, URLs, etc.
- **Port reassignment**: Interactive wizard to change conflicting ports
- **MCP auto-install**: Write directly to Agent's config (Phase 8)
- **Env encryption**: Encrypt secrets at rest

