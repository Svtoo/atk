# MCP Agent Configuration

> **Status**: Draft — awaiting implementation

## Overview

The `atk mcp` command currently outputs MCP configuration for the user to copy and paste into their tools manually. This spec extends it to configure coding agents directly on the user's behalf.

When the user adds an ATK plugin, they typically want all their coding tools configured to use it — not just one. This feature lets the user specify any combination of supported agents and ATK will configure all of them in a single invocation, with the user confirming each action before it is taken.

## User Interface

```
atk mcp <plugin> [--claude] [--codex] [--auggie] [--opencode]
```

Multiple agent flags may be passed simultaneously. ATK processes them in a fixed order: Claude, Codex, Auggie, OpenCode.

**Examples:**

```
# Configure Claude Code only
atk mcp openmemory --claude

# Configure Claude and Codex together
atk mcp openmemory --claude --codex

# Configure all four agents at once
atk mcp openmemory --claude --codex --auggie --opencode
```

Passing no agent flags preserves the existing behavior: ATK prints the MCP configuration as plaintext (or JSON with `--json`) for the user to copy manually.

The `--json` flag and any agent flag are mutually exclusive. ATK exits with an error if both are provided.

## Confirmation Flow

Before taking any action for an agent, ATK **always** asks for confirmation. It shows the user exactly what it is about to do and prompts for approval. Confirmation is per-agent: the user may accept some and decline others within the same invocation.

For agents configured via their CLI:

```
[Claude Code] Will run:
  claude mcp add --scope user my-plugin /path/to/server.sh

Proceed? [y/N]
```

For agents configured by editing a file directly:

```
[Auggie] Will add to ~/.augment/settings.json:
  "my-plugin": {
    "type": "stdio",
    "command": "/path/to/server.sh",
    "args": ["--port", "8080"],
    "env": {}
  }

Proceed? [y/N]
```

If the user declines, ATK skips that agent and moves on to the next one. The outcome for each agent (configured, skipped, or failed) is reported at the end.

## Missing Environment Variables

If the plugin has environment variables that are not yet set, ATK warns about each one before the confirmation prompt. It then proceeds with the confirmation regardless — the user decides whether to configure the agent now or after running `atk setup`.

Variables with no value are omitted from the agent configuration entirely. Passing a placeholder value (like `<NOT_SET>`) to an agent's CLI or config would silently corrupt the configuration.

## Agents

### Claude Code

**Mechanism:** `claude mcp add` CLI.

**Scope:** Always `--scope user` (global, user-level configuration). ATK does not offer project or local scope for this command. Scope concepts are Claude Code internals and subject to change; ATK takes a firm opinion to keep things simple.

**Stdio transport:**
```
claude mcp add --scope user [-e KEY=VAL ...] <plugin-name> <command> [args...]
```

**SSE transport:**
```
claude mcp add --transport sse --scope user [-e KEY=VAL ...] <plugin-name> <url>
```

Env vars are passed as individual `-e KEY=VAL` flags, one per variable. Only variables with resolved values are included.

---

### Codex

**Mechanism:** `codex mcp add` CLI. Writes to `~/.codex/config.toml`.

**Stdio transport:**
```
codex mcp add [--env KEY=VAL ...] <plugin-name> -- <command> [args...]
```

Note the `--` separator between the server name and the command — this is required by Codex's CLI parser.

**HTTP/SSE transport:**
```
codex mcp add [--env KEY=VAL ...] <plugin-name> --url <url>
```

Env vars are passed as individual `--env KEY=VAL` flags (Codex uses `--env`, not `-e`).

---

### Auggie

**Mechanism:** `auggie mcp add-json` CLI. Auggie provides two add commands: `mcp add` (flag-based) and `mcp add-json` (takes a single-line JSON string). ATK uses `add-json` because it accepts a structured payload that maps directly from `McpConfigResult` without ambiguity.

**Stdio invocation:**
```
auggie mcp add-json <plugin-name> '{"command":"<cmd>","args":["<arg1>","<arg2>"],"env":{"KEY":"val"}}'
```

**SSE invocation:**
```
auggie mcp add-json <plugin-name> '{"type":"sse","url":"<url>"}'
```

The JSON payload must be a single line — auggie's CLI does not accept multi-line JSON. ATK serialises the payload to compact (non-pretty) JSON before passing it.

Auggie stores its configuration in `~/.augment/settings.json` under the `mcpServers` key and handles file creation and merging itself. ATK does not write to that file directly.

**Important:** Auggie silently rejects any entry where `args` is a JSON string rather than an array; all other `mcpServers` entries are dropped from the list output as a result. ATK always constructs `args` as an array.

---

### OpenCode

**Mechanism:** Direct config file edit. OpenCode's `mcp add` is an interactive TUI command and cannot be scripted. ATK writes to the global OpenCode config file at `~/.config/opencode/opencode.jsonc`, creating it (and any missing parent directories) if it does not exist. This is consistent with how Claude, Codex, and Auggie all write to user-level global configs.

**Stdio format stored (under the `mcp` key):**
```json
"<plugin-name>": {
  "type": "local",
  "command": ["<command>", "<arg1>", "<arg2>"],
  "environment": {
    "KEY": "value"
  },
  "enabled": true
}
```

**Remote (SSE/HTTP) format stored:**
```json
"<plugin-name>": {
  "type": "remote",
  "url": "<url>",
  "enabled": true
}
```

Note: OpenCode uses `environment` (not `env`) for environment variables, and `command` takes a full array including the executable and all arguments (not a separate `args` field). OpenCode also uses `type: "local"` / `type: "remote"` rather than transport names.

## Error Handling

- **Agent not installed:** If the required CLI is not found on `PATH`, ATK reports it clearly and skips that agent.
- **Agent CLI returns non-zero:** ATK reports the exit code and stderr. The remaining agents are still processed.
- **Config file unwritable:** ATK reports the error and skips that agent.
- **Plugin not found:** ATK exits immediately before any agent configuration begins.
- **Plugin has no MCP configuration:** ATK exits immediately before any agent configuration begins.

