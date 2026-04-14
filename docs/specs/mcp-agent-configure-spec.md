# Plugin-to-Agent Wiring

> **Status**: Implemented. `atk plug`/`unplug` commands handle all agent wiring. `atk mcp add`/`atk mcp remove` have been removed.

## Overview

The `atk plug` command wires an installed plugin into one or more coding agents. ATK adapts to what the plugin offers:

| Plugin has… | `atk plug` does… |
|---|---|
| MCP + SKILL.md | Register MCP server + inject skill |
| MCP only (no SKILL.md) | Register MCP server only |
| SKILL.md only (no MCP) | Inject skill only |
| Neither | Error: "Nothing to plug — plugin has no MCP config or SKILL.md" |

The user does not need to know what a plugin contains. They just say "plug it in" and ATK does the right thing.

When a plugin has an MCP server, it is configured in two steps: (1) **MCP registration** — the agent learns how to connect to the plugin's tool server; and (2) **skill injection** — the plugin's `SKILL.md` is surfaced in the agent's context. When a plugin has only a SKILL.md (e.g., behavioral instructions or coding conventions), only skill injection is performed.

## User Interface

```
atk plug <plugin> [--claude] [--codex] [--gemini] [--auggie] [--opencode] [-y/--force]
atk unplug <plugin> [--claude] [--codex] [--gemini] [--auggie] [--opencode] [-y/--force]
```

At least one agent flag is required. Multiple agent flags may be passed simultaneously. ATK processes them in a fixed order: Claude, Codex, Gemini, Auggie, OpenCode.

**Examples:**

```
# Plug into Claude Code only
atk plug openmemory --claude

# Plug into Claude and Gemini together
atk plug openmemory --claude --gemini

# Plug into all five agents at once
atk plug openmemory --claude --codex --gemini --auggie --opencode

# Plug a skill-only plugin (no MCP server)
atk plug sasha-persona --claude --codex --auggie

# Unplug from a specific agent
atk unplug openmemory --gemini

# Unplug from all agents
atk unplug openmemory --claude --codex --gemini --auggie --opencode
```

### `atk mcp` (Diagnostic/Export)

```
atk mcp <plugin>          # Human-readable MCP config
atk mcp <plugin> --json   # Machine-readable JSON for manual copy-paste
```

`atk mcp` is a read-only diagnostic tool for inspecting and exporting a plugin's MCP configuration. It does not perform any wiring.

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

## Design Principle: References, Not Copies

ATK never copies SKILL.md content into an agent's config. It always writes a **reference** to the plugin's installed SKILL.md path.

This matters because ATK does not track which agents have been configured for a plugin. When a user runs `atk upgrade`, the SKILL.md at its installed path is updated. If an agent holds a reference to that path — whether a native file-include, a symlink, or a natural-language read directive — it will automatically load the updated content the next time it starts. Copied content, by contrast, would silently go stale.

Each agent below uses whatever reference mechanism it natively supports:
- **Claude Code** — `@/abs/path` file-include syntax (native)
- **Codex** — natural-language read directive pointing to the absolute path (Codex reads the file as an agent action; no native include syntax exists)
- **Gemini CLI** — symlink in `~/.gemini/skills/` pointing to the directory containing SKILL.md
- **Auggie** — symlink in `~/.augment/rules/` pointing to the installed SKILL.md
- **OpenCode** — absolute path in the `instructions` array (native)

This principle applies to all future agents added to ATK. Inline content injection is a last resort and must be explicitly justified.

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

**Skill injection:** ATK manages an ATK-owned section in `~/.claude/CLAUDE.md` bounded by `<!-- ATK:BEGIN -->` / `<!-- ATK:END -->` HTML comment markers. It appends a line of the form `@/absolute/path/to/SKILL.md` inside that section. Claude Code inlines all `@`-referenced files into its context at session start. The section is created if it does not exist. Adding the same reference twice is a no-op.

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

**Skill injection:** Codex has no native file-include syntax. ATK manages an ATK-owned section in `~/.codex/AGENTS.md` bounded by `<!-- ATK:BEGIN -->` / `<!-- ATK:END -->` markers and inserts a natural-language read directive of the form:

```
Read /absolute/path/to/SKILL.md for instructions on using the <plugin-name> MCP tools.
```

Because Codex is an agent with file-reading capability, it follows this directive at session start and loads the live file content. The SKILL.md is never copied — only its absolute path is stored, so plugin updates are reflected automatically. The file and its parent directory are created if they do not exist.

---

### Gemini CLI

**Mechanism:** `gemini mcp add` CLI.

**Scope:** Defaults to `--scope project` (local configuration in the current workspace). ATK uses the default (`project`).

**Stdio transport:**
```
gemini mcp add [--scope user/project] [-e KEY=VAL ...] <plugin-name> <command> [args...]
```

**SSE transport:**
```
gemini mcp add --transport sse [--scope user/project] [-e KEY=VAL ...] <plugin-name> <url>
```

Env vars are passed as individual `-e KEY=VAL` flags, one per variable. Only variables with resolved values are included.

**Skill injection:** ATK creates a **symlink** at `~/.gemini/skills/atk-<plugin-name>` pointing to the directory containing the plugin's `SKILL.md`. Gemini CLI automatically discovers all skills in that directory at startup. Like Auggie, using a symlink ensures that updates via `atk upgrade` are reflected immediately.

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

**Skill injection:** ATK creates a **symlink** at `~/.augment/rules/atk-<plugin-name>.md` pointing to the plugin's installed SKILL.md. Augment automatically loads every `.md` file in `~/.augment/rules/` as a globally applied "always-on" user rule. Because it is a symlink rather than a copy, Augment always reads the live file — plugin updates are reflected automatically without any additional action. If the plugin has no SKILL.md, this step is skipped.

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

**Skill injection:** ATK adds the absolute path of `SKILL.md` to the `instructions` array in `~/.config/opencode/opencode.json`. OpenCode natively resolves file paths in `instructions` and loads their contents at session start. The entry is added only if not already present.

## Removal

`atk unplug <plugin> [--claude] [--codex] [--gemini] [--auggie] [--opencode]` undoes what `atk plug` configured: it removes both the MCP server registration and the skill injection for each selected agent. Like `atk plug`, it asks for confirmation before acting on each agent.

At least one agent flag is required. If a flag is omitted, that agent is untouched.

### Claude Code

1. Run `claude mcp remove --scope user <plugin-name>` to deregister the MCP server.
2. Remove the `@/…/SKILL.md` line from the ATK-managed section in `~/.claude/CLAUDE.md`. If the ATK section becomes empty after removal, ATK leaves the (now empty) section in place.

### Codex

1. Run `codex mcp remove <plugin-name>` to deregister the MCP server.
2. Remove the read-directive line for this plugin from the ATK-managed section in `~/.codex/AGENTS.md`. If the section becomes empty after removal, ATK leaves the (now empty) section in place.

### Gemini CLI

1. Run `gemini mcp remove --scope project <plugin-name>` to deregister the MCP server.
2. Delete the symlink `~/.gemini/skills/atk-<plugin-name>` (the SKILL.md target is left untouched).

### Auggie

1. Run `auggie mcp remove <plugin-name>` to deregister the MCP server.
2. Delete the symlink `~/.augment/rules/atk-<plugin-name>.md` (the SKILL.md target is left untouched).

### OpenCode

1. Remove the plugin's MCP entry from the `mcp` object in `~/.config/opencode/opencode.json`.
2. Remove the SKILL.md path from the `instructions` array in the same file.

Both edits are applied in a single file write.

## Error Handling

- **Agent not installed:** If the required CLI is not found on `PATH`, ATK reports it clearly and skips that agent.
- **Agent CLI returns non-zero:** ATK reports the exit code and stderr. The remaining agents are still processed.
- **Config file unwritable:** ATK reports the error and skips that agent.
- **Plugin not found:** ATK exits immediately before any agent configuration begins.
- **Plugin has no MCP configuration and no SKILL.md:** ATK exits immediately with "Nothing to plug — plugin has no MCP config or SKILL.md."
- **Plugin has SKILL.md but no MCP:** ATK skips MCP registration and only performs skill injection. This is the expected path for instruction-only plugins.

