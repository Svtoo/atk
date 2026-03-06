<p align="center">
  <img src="assets/logo.png" alt="ATK Logo" width="280px">
</p>

<p align="center">
  <a href="https://github.com/Svtoo/atk/actions/workflows/ci.yml"><img src="https://github.com/Svtoo/atk/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://codecov.io/gh/Svtoo/atk"><img src="https://codecov.io/gh/Svtoo/atk/branch/main/graph/badge.svg" alt="Coverage"></a>
  <a href="https://pypi.org/project/atk-cli/"><img src="https://img.shields.io/pypi/v/atk-cli" alt="PyPI version"></a>
  <a href="https://pypi.org/project/atk-cli/"><img src="https://img.shields.io/pypi/dm/atk-cli" alt="PyPI downloads"></a>
  <a href="https://pypi.org/project/atk-cli/"><img src="https://img.shields.io/pypi/pyversions/atk-cli" alt="Python versions"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/Svtoo/atk" alt="License"></a>
</p>

# ATK — AI Tool Kit for Developers

ATK is a **CLI plugin manager for AI-assisted development**.

Install MCP servers and local AI services with one command. Wire them into every coding agent you use — Claude Code, Codex, Gemini CLI, Augment Code, OpenCode — simultaneously. Keep your entire setup git-backed, reproducible, and upgradeable.

> **Install. Wire. Done.**
> `atk add github` → `atk mcp add github --claude --codex --auggie`

<p align="center">
  <img src="assets/demo-hero.gif" alt="ATK: wire one MCP into multiple agents" width="700px">
</p>

---

## The problem

If you use coding agents seriously, your setup probably looks like this:

- MCP servers installed from random Git repos, each with its own README to follow
- Local services started with long-forgotten `docker run` commands
- Agent configs hand-edited in JSON files scattered across your machine
- The same MCP configured differently in Claude, Codex, and Augment because you did it three times manually
- Secrets in `.env` files with no connection to anything

It works. Until you switch machines, break something, want to roll back, or come back after two months and have no idea what’s running or how it got there.

ATK exists because this setup is **real, fragile, and universal**.

---

## What ATK does

**Discover and install AI tools from a curated registry**

```bash
atk search                  # browse vetted plugins
atk add github              # install in one command, prompts for config
atk status                  # see what's running, ports, env status
```

**Wire MCPs into all your coding agents at once**

```bash
atk mcp add github --claude --codex --gemini --auggie --opencode
```

One command. ATK calls each agent’s native MCP registration command, or writes the config file directly. No manual JSON editing across multiple apps.

**Teach your agents how to use the tools**

When a plugin ships a `SKILL.md` — usage instructions for AI agents — ATK injects it into each agent’s context automatically. Claude gets `@`-references in `CLAUDE.md`. Codex gets read-directives in `AGENTS.md`. Gemini and Augment Code gets a symlink in `~/.gemini/skills/`, `~/.augment/rules/` respectively. OpenCode gets an entry in its `instructions` array.

Your agent doesn’t just have access to the tool — it knows **how** and **when** to use it.

**Manage the full lifecycle of everything**

```bash
atk start openmemory        # start a service
atk stop langfuse           # stop it
atk logs openmemory         # tail logs
atk upgrade --all           # pull latest for all plugins
atk remove github           # stop + uninstall + delete
```

Every tool — Docker service, MCP server, CLI binary — gets the same uniform interface.

---

## Supported agents

| Agent | MCP registration | Skill injection |
|-------|-----------------|-----------------|
| [Claude Code](https://claude.ai/code) | `claude mcp add` | `~/.claude/CLAUDE.md` |
| [Codex](https://github.com/openai/codex) | `codex mcp add` | `~/.codex/AGENTS.md` |
| [Gemini CLI](https://github.com/google-gemini/gemini-cli) | `gemini mcp add` | `~/.gemini/skills/` (dir symlink) |
| [Augment Code](https://augmentcode.com) | `auggie mcp add-json` | `~/.augment/rules/` |
| [OpenCode](https://opencode.ai) | writes `opencode.jsonc` | `opencode.jsonc` instructions |

You can target one, several, or all at once with agent flags.

---

## Registry

```
$ atk search
11 plugins

  NAME                  DESCRIPTION
    fetch               Web content fetching via MCP
    git-local           Safe Git operations on local repos via MCP
    github              GitHub: search repos, file issues, open PRs from chat
    gitlab              GitLab issues, MRs, file reading via Duo MCP
    google-workspace    Gmail, Drive, Calendar, Docs, Sheets from any AI assistant
    langfuse            Open-source LLM observability and tracing
    notion              Search pages, read/write content, manage databases
    openmemory          Persistent memory layer for AI agents with semantic search
    piper               Local text-to-speech with neural voices
    playwright          Browser automation: screenshots, web interaction, JS execution
    slack               List channels, read history, post messages, look up users
```

All registry plugins are reviewed, schema-validated, and versioned. Installed plugins are marked with `✓`. Search by keyword: `atk search memory`, `atk search git`.

<p align="center">
  <img src="assets/demo-search.gif" alt="atk search — live registry" width="700px">
</p>

---

## Getting started

<details>
<summary><strong>Prerequisite: install uv (recommended Python tool runner)</strong></summary>

- **macOS:** `brew install uv`
- **Other:** [Official Install Guide](https://docs.astral.sh/uv/getting-started/installation/)

</details>

```bash
# Install ATK
uv tool install atk-cli      # recommended
# or: pip install atk-cli

# Initialize ATK Home (defaults to ~/.atk — a git repo)
atk init

# Browse available plugins
atk search

# Add a plugin — installs it and prompts for any config it needs
atk add openmemory

# Check what's running
atk status

# Wire the MCP into your coding agents (with skill instructions)
atk mcp add openmemory --claude --auggie

# See the raw MCP config (copy-paste into any tool that reads JSON)
atk mcp show openmemory
```

Your entire setup lives in `~/.atk/` — a git repository. Push it. Clone it on another machine. Run `atk install --all`. Everything comes back exactly as you left it.

<p align="center">
  <img src="assets/demo-status.gif" alt="atk status — live service dashboard" width="700px">
</p>

---

## Command reference

| Command | What it does |
|---------|--------------|
| `atk search [query]` | Browse or filter registry plugins |
| `atk add <name\|url\|path>` | Install a plugin, prompts for config |
| `atk setup <plugin>` | Re-configure environment variables |
| `atk status` | Show all plugins: running state, ports, env |
| `atk start / stop / restart` | Lifecycle control |
| `atk logs <plugin>` | Tail service logs |
| `atk upgrade [--all]` | Pull latest plugin version |
| `atk remove <plugin>` | Stop + uninstall + delete |
| `atk mcp show <plugin>` | Print MCP config (plaintext or `--json`) |
| `atk mcp add <plugin> [--claude] [--codex] [--gemini] [--auggie] [--opencode]` | Register with agents + inject skill |
| `atk mcp remove <plugin> [agents...]` | Unregister from agents |
| `atk help <plugin>` | Render plugin README in terminal |
| `atk run <plugin> <script>` | Run a plugin's custom script |

---

## ATK plugins and registry

ATK is built around **plugins**.

A plugin describes how to install, configure, run, update, and integrate a tool or service — including MCPs, local services, CLIs, or agent-facing components.

ATK supports **three ways** to work with plugins:

### 1. Official ATK Registry (vetted plugins)

ATK maintains a growing **registry of vetted plugins** for common tools in AI-assisted development.

Install by name:

```bash
atk add openmemory
atk add langfuse
```

Registry plugins are reviewed, schema-validated, versioned, and pinned. Think of this as the "known good" layer.

### 2. Git repository plugins (distribution channel)

Any Git repository can become an ATK plugin. Add a `.atk/plugin.yaml` to your repo and users can install it with one line:

```bash
atk add github.com/your-org/your-tool
```

ATK sparse-clones only the `.atk/` directory, validates the plugin, pins it to a commit hash, and manages its lifecycle like any other plugin. This turns ATK into a **distribution channel for AI tooling** — without a centralized gatekeeper.

### 3. Local plugins (personal or internal tooling)

```bash
atk add ./my-plugin
```

Lives in `~/.atk`, fully versioned, uses the same schema. Ideal for personal scripts, internal tools, or plugins in development.

---

## Reproducibility

ATK environments are fully reproducible:

- Plugins are validated against a **versioned schema**
- Plugin versions are **pinned** to exact commit hashes in the manifest
- Secrets live in isolated, gitignored `.env` files
- Every mutation is a **git commit** — rollback is `git revert`
- Additive schema changes are backward-compatible

Clone the repo on a new machine. Run `atk install --all`. You get the same toolchain.

---

## Unified lifecycle

ATK gives every tool the same lifecycle, regardless of how it is installed.

```bash
atk start openmemory
atk stop openmemory
atk restart openmemory
atk status
atk logs openmemory
```

This works whether the tool is a Docker service, a Python CLI, a Node binary, or a custom shell-based MCP server.

---

## Design principles

| Principle   | Meaning                                               |
| ----------- | ----------------------------------------------------- |
| Declarative | The manifest describes desired state; ATK enforces it |
| Idempotent  | Running the same command twice yields the same result |
| Git-native  | Every mutation is a commit; rollback = `git revert`   |
| Transparent | Human-readable YAML; no hidden state                  |
| AI-first    | CLI-driven, scriptable, agent-friendly                |
| Focused     | Manages tools, doesn't build them                     |

---

## Who ATK is for

ATK is for developers who:

- rely on coding agents (Claude Code, Codex, Augment Code, etc.)
- don't want to be vendor-locked, or work with multiple tools
- use MCP servers (local and remote)
- run local services like memory, observability, or vector stores
- care about owning their data and controlling their setup

ATK is not limited to people building AI models. It is for people **building software with AI systems in the loop**.

---

## What ATK is (and is not)

**ATK is:**
- a toolchain and plugin manager for developers
- focused on local, long-lived AI tooling
- git-backed and reproducible
- CLI-first and automation-friendly
- designed to be driven by humans *and* coding agents

**ATK is not:**
- an environment manager (Nix, Conda, Devbox)
- infrastructure-as-code (Terraform, Ansible)
- a production deployment system
- project-scoped

If you're configuring servers, ATK is the wrong tool.
If you're keeping your **AI dev setup sane**, it's the right one.

---

## Installation

```bash
# Recommended
uv tool install atk-cli

# Alternative
pip install atk-cli
```

ATK is distributed via **PyPI** and installs as a single self-contained CLI. Requires Python 3.11+.

---

## For MCP authors: ATK as your distribution layer

If you’re building an MCP server, ATK is the easiest way to get it into your users’ agents.

### What you get

**One-command install from your repo**

```bash
atk add github.com/you/your-mcp-server
```

ATK sparse-clones only the `.atk/` directory from your repo, validates it, and pins it to a commit hash. Your users run one command and have a working, managed, upgradeable installation.

**Automatic agent wiring — all agents at once**

```bash
atk mcp add your-mcp-server --claude --codex --gemini --auggie --opencode
```

ATK handles the agent-specific plumbing: native CLI commands for Claude and Codex, JSON config writing for OpenCode, everything. Your users don’t need to know which config file to edit or which flags to pass.

**You control how agents use your tool**

Ship a `SKILL.md` alongside your plugin. When users run `atk mcp add`, ATK injects it into each agent’s context automatically:

- **Claude Code**: added to `~/.claude/CLAUDE.md` as an `@`-reference
- **Codex**: added to `~/.codex/AGENTS.md` as a read-directive
- **Augment Code**: symlinked into `~/.augment/rules/` (auto-loaded every session)
- **OpenCode**: added to the `instructions` array in `opencode.jsonc`
- **Gemini CLI**: symlinked into `~/.gemini/skills/`

The agent doesn’t just have access — it has instructions. You decide what the agent knows about your tool, how it should use it, and what it should avoid.

### How to add ATK support to your repo

You don’t need to write the plugin files by hand. ATK ships a dedicated skill file that tells your coding agent exactly what to build: the schema, lifecycle scripts, `SKILL.md` conventions, testing protocol, and all three distribution patterns.

**[ATK Plugin Creation Skill →](skills/create-atk-plugin/SKILL.md)**

Feed it to your agent and ask:

> *"Create an ATK plugin for [your tool name]. Follow the skill file."*

The agent will produce a complete `plugin.yaml`, install and lifecycle scripts, `SKILL.md`, and `README.md` — ready to ship.

Once the files are ready, test locally then share via your existing repo:

```bash
atk add ./.atk                       # install locally to test
atk add github.com/you/your-repo     # users install from your git URL
```

### Getting listed in the registry

The [ATK registry](https://github.com/Svtoo/atk-registry) is the curated list of plugins available via `atk search`. Submit a PR to add your plugin. Registry plugins are reviewed and must meet the schema requirements — verified plugins get a `verified` badge in `atk status`.

---

## Status

ATK is under active development.
Expect fast iteration and opinionated choices.

If this problem resonates with you, try it — and break it.

If ATK saves you time, a ⭐ on [GitHub](https://github.com/Svtoo/atk) goes a long way.
