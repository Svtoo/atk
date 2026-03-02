# MCP Agent Configuration

> **Status**: MCP registration implemented for all four agents. Skill injection implemented for Claude Code only. Codex/Auggie/OpenCode skill injection and `atk mcp remove` pending.

## Overview

The `atk mcp` command configures coding agents to use a plugin's MCP server. Each supported agent is configured in two steps: (1) **MCP registration** — the agent learns how to connect to the plugin's tool server; and (2) **skill injection** — the plugin's `SKILL.md` is surfaced in the agent's context so it understands how to use those tools.

When the user adds an ATK plugin, they typically want all their coding tools configured to use it — not just one. This feature lets the user specify any combination of supported agents and ATK will configure all of them in a single invocation, with the user confirming each action before it is taken.

## User Interface

```
atk mcp <plugin> [--claude] [--codex] [--auggie] [--opencode]
atk mcp remove <plugin> [--claude] [--codex] [--auggie] [--opencode]
```

Multiple agent flags may be passed simultaneously. ATK processes them in a fixed order: Claude, Codex, Auggie, OpenCode.

**Examples:**

```
# Configure Claude Code only (MCP + skill)
atk mcp openmemory --claude

# Configure Claude and Codex together
atk mcp openmemory --claude --codex

# Configure all four agents at once
atk mcp openmemory --claude --codex --auggie --opencode

# Remove from a specific agent
atk mcp remove openmemory --claude

# Remove from all agents
atk mcp remove openmemory --claude --codex --auggie --opencode
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

## Design Principle: References, Not Copies

ATK never copies SKILL.md content into an agent's config. It always writes a **reference** to the plugin's installed SKILL.md path.

This matters because ATK does not track which agents have been configured for a plugin. When a user runs `atk upgrade`, the SKILL.md at its installed path is updated. If an agent holds a reference to that path — whether a native file-include, a symlink, or a natural-language read directive — it will automatically load the updated content the next time it starts. Copied content, by contrast, would silently go stale.

Each agent below uses whatever reference mechanism it natively supports:
- **Claude Code** — `@/abs/path` file-include syntax (native)
- **Codex** — natural-language read directive pointing to the absolute path (Codex reads the file as an agent action; no native include syntax exists)
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

`atk mcp remove <plugin> [--claude] [--codex] [--auggie] [--opencode]` undoes what `atk mcp` configured: it removes both the MCP server registration and the skill injection for each selected agent. Like the configure command, it asks for confirmation before acting on each agent.

If a flag is omitted, that agent is untouched. No flag means nothing is removed (the command is a no-op with a warning).

### Claude Code

1. Run `claude mcp remove --scope user <plugin-name>` to deregister the MCP server.
2. Remove the `@/…/SKILL.md` line from the ATK-managed section in `~/.claude/CLAUDE.md`. If the ATK section becomes empty after removal, ATK leaves the (now empty) section in place.

### Codex

1. Run `codex mcp remove <plugin-name>` to deregister the MCP server.
2. Remove the read-directive line for this plugin from the ATK-managed section in `~/.codex/AGENTS.md`. If the section becomes empty after removal, ATK leaves the (now empty) section in place.

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
- **Plugin has no MCP configuration:** ATK exits immediately before any agent configuration begins.

