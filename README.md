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

# ATK: AI Tool Kit for Developers

ATK is a **CLI plugin manager for AI-assisted development**.

Install MCP servers and local AI services with one command. Plug them into every coding agent you use (Claude Code, Codex, Gemini CLI, Augment Code, OpenCode) at the same time. Keep your entire setup git-backed, reproducible, and upgradeable.

> **Install. Plug. Done.**
> `atk add github` → `atk plug github --claude --codex --auggie`

<p align="center">
  <img src="assets/demo-hero.gif" alt="ATK: plug one MCP into multiple agents" width="700px">
</p>

---

## Quick start

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/getting-started/installation/) (`brew install uv` on macOS).

```bash
# Install ATK
uv tool install atk-cli        # or: pip install atk-cli

# Initialize ATK Home (~/.atk, a git repo)
atk init

# Browse the registry, install a plugin
atk search
atk add fetch

# Plug it into your coding agents: MCP registration + skill injection in one go
atk plug fetch --claude        # add --codex --gemini --auggie --opencode as needed

# See what's installed and running
atk status
```

Your entire setup lives in `~/.atk/`, a git repository. Push it. Clone it on another machine. Run `atk install --all` to reinstall every plugin from the manifest. Everything comes back exactly as you left it.

<p align="center">
  <img src="assets/demo-status.gif" alt="atk status: live service dashboard" width="700px">
</p>

---

## The problem

If you use coding agents seriously, your setup probably looks like this:

- MCP servers installed from random Git repos, each with its own README to follow
- Local services started with long-forgotten `docker run` commands
- Agent configs hand-edited in JSON files scattered across your machine
- The same MCP configured differently in Claude, Codex, and Augment because you did it three times manually
- Secrets in `.env` files with no connection to anything

It works. Until you switch machines, break something, want to roll back, or come back after two months and have no idea what's running or how it got there.

ATK exists because this setup is **real, fragile, and universal**.

---

## What ATK does

**Discover and install AI tools from a curated registry**

```bash
atk search                  # browse vetted plugins
atk add github              # install in one command, prompts for config
atk status                  # see what's running, ports, env status
```

**Plug tools into all your coding agents at once**

```bash
atk plug github --claude --codex --gemini --auggie --opencode
```

One command. ATK registers the MCP server with each agent's native mechanism and injects the plugin's skill. No manual JSON editing across multiple apps. Plugins that ship only a `SKILL.md` (no MCP server) work too, so instruction-only plugins like coding personas are first-class.

**Teach your agents how to use the tools**

When a plugin ships a `SKILL.md` (usage instructions for AI agents), `atk plug` injects it into each agent's context automatically, in each agent's native format (see [Supported agents](#supported-agents)).

Your agent doesn't just have access to the tool. It knows **how** and **when** to use it.

**Manage the full lifecycle of everything**

```bash
atk start hindsight         # start a service
atk stop langfuse           # stop it
atk logs hindsight          # tail logs
atk upgrade --all           # pull latest for all plugins
atk remove github           # stop + uninstall + delete
```

Every tool, whether a Docker service, an MCP server, or a CLI binary, gets the same uniform interface.

---

## Supported agents

| Agent | MCP registration | Skill injection |
|-------|-----------------|-----------------|
| [Claude Code](https://claude.ai/code) | `claude mcp add` | `~/.claude/CLAUDE.md` |
| [Codex](https://github.com/openai/codex) | `codex mcp add` | `~/.codex/AGENTS.md` |
| [Gemini CLI](https://github.com/google-gemini/gemini-cli) | `gemini mcp add` | `~/.gemini/skills/` (dir symlink) |
| [Augment Code](https://augmentcode.com) | `auggie mcp add-json` | `~/.augment/rules/` |
| [OpenCode](https://opencode.ai) | writes `opencode.jsonc` | `opencode.jsonc` instructions |

`atk plug` drives all of this: pass a flag for each agent you want to target. `atk unplug` reverses it.

---

## Registry

The registry currently ships **20 plugins**:

| | |
|---|---|
| **Code intelligence** | `serena` (LSP-backed symbol navigation and refactors), `codanna` (call graphs and semantic search) |
| **Memory** | `hindsight` (self-hosted agent memory with retain/recall/reflect over MCP) |
| **Web** | `exa` (neural search), `fetch` (URL to Markdown), `playwright` (browser automation) |
| **Dev platforms** | `github`, `gitlab`, `git-local` |
| **Work tools** | `slack`, `notion`, `google-workspace`, `streamlinear` (token-efficient Linear), `metabase` |
| **LLM observability** | `langfuse`, `langfuse-official-mcp` |
| **Claude Code extras** | `claude-dashboard` (live session dashboards), `claude-code-atk` (per-turn skill reminders) |
| **Notes and voice** | `obsidian-local-rest-api`, `piper` (local text-to-speech) |

Registry plugins are reviewed, schema-validated, versioned, and pinned; registry review is what earns the green `verified` maturity you see in `atk status`. Git and local plugins declare their own maturity, and `atk add` asks for confirmation before installing anything below `verified`. Search by keyword: `atk search memory`, `atk search git`.

<p align="center">
  <img src="assets/demo-search.gif" alt="atk search: live registry" width="700px">
</p>

### Spotlight: claude-dashboard

A live, per-chat executive dashboard for Claude Code sessions:

- A localhost server renders a visual `dashboard.html` for the active chat and refreshes it after every turn: glance header, to-dos, heads-up items, session journey
- A top-level landing page covers every project and chat with history, so you can find and review any session at a glance
- Runs entirely on your machine; uses your existing Claude subscription, no API key needed. Stop it any time with `atk stop claude-dashboard`

```bash
atk add claude-dashboard
```

### Spotlight: hindsight

Persistent memory for your agents, self-hosted:

- Agents write what they learn with `retain`, pull it back with `recall`, and ask `reflect` what is true now, all over MCP
- Runs in Docker on your machine or connects to a remote instance; locally, `atk run hindsight backup` dumps the database to `HINDSIGHT_BACKUP_DIR` without downtime
- Ships a `SKILL.md`, the per-turn memory protocol plugged agents follow

```bash
atk add hindsight
```

---

## Command reference

| Command | What it does |
|---------|--------------|
| `atk init` | Initialize ATK Home (`~/.atk`, a git repo) |
| `atk search [query]` | Browse or filter registry plugins |
| `atk add <name\|url\|path>` | Install a plugin, prompts for config |
| `atk setup [plugin] [--all]` | Re-configure environment variables |
| `atk status [plugin]` | Show plugins: running state, ports, env, maturity |
| `atk plug <plugin> [--claude] [--codex] [--gemini] [--auggie] [--opencode]` | Register MCP with agents + inject skill |
| `atk unplug <plugin> [agent flags]` | Unregister from agents (same flags as `plug`) |
| `atk mcp <plugin> [--json]` | Print the resolved MCP config for copy-paste |
| `atk start / stop / restart [plugin] [--all]` | Lifecycle control |
| `atk logs <plugin>` | Tail service logs |
| `atk install [plugin] [--all]` | Run a plugin's install lifecycle |
| `atk uninstall <plugin>` | Run a plugin's uninstall lifecycle |
| `atk upgrade [--all]` | Pull latest plugin version |
| `atk remove <plugin>` | Stop + uninstall + delete |
| `atk help <plugin>` | Render plugin README in terminal |
| `atk run <plugin> <script>` | Run a plugin's custom script |
| `atk doctor` | Repair ATK Home, keep secrets gitignored |
| `atk git <args...>` | Run git in ATK Home (push, pull, log) |

---

## Three ways to add plugins

### 1. Official ATK Registry (vetted plugins)

```bash
atk add hindsight
atk add langfuse
```

The "known good" layer: reviewed, versioned, and pinned (see [Registry](#registry)).

### 2. Git repository plugins (distribution channel)

Any Git repository can become an ATK plugin. Add a `.atk/plugin.yaml` to your repo and users can install it with one line:

```bash
atk add github.com/your-org/your-tool
```

ATK fetches just the `.atk/` directory's contents, validates the plugin, pins it to a commit hash, and manages its lifecycle like any other plugin. This turns ATK into a **distribution channel for AI tooling**, without a centralized gatekeeper.

### 3. Local plugins (personal or internal tooling)

```bash
atk add ./my-plugin
```

`atk add <path>` takes any directory that contains a `plugin.yaml`. The plugin lives in `~/.atk`, fully versioned, same schema. Ideal for personal scripts, internal tools, or plugins in development.

---

## Reproducibility

ATK environments are fully reproducible:

- Plugins are validated against a **versioned schema**
- Plugin versions are **pinned** to exact commit hashes in the manifest
- Secrets live in isolated, gitignored `.env` files
- Every change to ATK Home (add, remove, upgrade) is a **git commit**; rollback is `git revert`
- Additive schema changes are backward-compatible

Clone the repo on a new machine. Run `atk install --all`. You get the same toolchain.

---

## Design principles

| Principle   | Meaning                                               |
| ----------- | ----------------------------------------------------- |
| Declarative | The manifest describes desired state; ATK enforces it |
| Idempotent  | Running the same command twice yields the same result |
| Git-native  | ATK Home changes are commits; rollback = `git revert` |
| Transparent | Human-readable YAML; no hidden state                  |
| AI-first    | CLI-driven, scriptable, agent-friendly                |
| Focused     | Manages tools, doesn't build them                     |

---

## Who ATK is for

Developers who:

- rely on coding agents (Claude Code, Codex, Augment Code, etc.)
- don't want vendor lock-in, or already work with multiple agents
- use MCP servers (local and remote)
- run local services like memory, observability, or vector stores
- care about owning their data and controlling their setup

**ATK is** a git-backed, CLI-first plugin manager for local, long-lived AI tooling, designed to be driven by humans *and* coding agents.

**ATK is not** an environment manager (Nix, Conda, Devbox), infrastructure-as-code (Terraform, Ansible), or a production deployment system. It manages one global, machine-level setup, not per-project config.

If you're configuring servers, ATK is the wrong tool. If you're keeping your **AI dev setup sane**, it's the right one.

---

## For MCP authors: ATK as your distribution layer

If you're building an MCP server, ATK is the easiest way to get it into your users' agents.

**One-command install from your repo**

```bash
atk add github.com/you/your-mcp-server
```

Add a `.atk/plugin.yaml` to your repo (see [Git repository plugins](#2-git-repository-plugins-distribution-channel)) and your users get a working, managed, upgradeable installation from one command.

**Automatic agent wiring, all agents at once**

```bash
atk plug your-mcp-server --claude --codex --gemini --auggie --opencode
```

ATK handles the agent-specific plumbing: native CLI commands for Claude, Codex, and Gemini, JSON config writing for OpenCode, everything. Your users don't need to know which config file to edit or which flags to pass.

**You control how agents use your tool**

Ship a `SKILL.md` alongside your plugin. When users run `atk plug`, ATK injects it into each agent's context automatically (see [Supported agents](#supported-agents)). The agent doesn't just have access, it has instructions. You decide what the agent knows about your tool, how it should use it, and what it should avoid.

### How to add ATK support to your repo

You don't need to write the plugin files by hand. ATK ships a dedicated skill file that tells your coding agent exactly what to build: the schema, lifecycle scripts, `SKILL.md` conventions, testing protocol, and all three distribution patterns.

**[ATK Plugin Creation Skill →](skills/create-atk-plugin/SKILL.md)**

Feed it to your agent and ask:

> *"Create an ATK plugin for [your tool name]. Follow the skill file."*

The agent will produce a complete `plugin.yaml`, install and lifecycle scripts, `SKILL.md`, and `README.md`, ready to ship.

Once the files are ready, test locally then share via your existing repo:

```bash
atk add ./.atk                       # install locally to test
atk add github.com/you/your-repo     # users install from your git URL
```

### Getting listed in the registry

The [ATK registry](https://github.com/Svtoo/atk-registry) is the curated list of plugins available via `atk search`. Submit a PR to add your plugin. Registry plugins are reviewed and must meet the schema requirements; verified plugins get a green `verified` maturity in `atk status`.

---

## Status

ATK is under active development.
Expect fast iteration and opinionated choices.

If this problem resonates with you, try it, and break it.

If ATK saves you time, a ⭐ on [GitHub](https://github.com/Svtoo/atk) goes a long way.
