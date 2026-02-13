<p align="center">
  <img src="assets/logo.png" alt="ATK Logo" width="280px">
</p>

# ATK — AI Tool Kit for Developers

ATK is a developer-side **toolchain and service manager for AI system development**.

It helps you install, run, update, version, and reproduce the growing set of local tools modern AI-assisted development depends on — without Docker sprawl, shell scripts, or "how did I install this again?" moments.

## The problem ATK solves

ATK is built for people who **develop with AI**, not only people who develop AI.

If you build AI systems locally, your setup probably looks like this:

* an MCP server installed from a Git repo
* a tracing or observability tool running in Docker
* a vector database started with a long-forgotten `docker run`
* a TTS or inference service installed via a binary
* CLI tools installed via `pip`, `npm`, or Homebrew
* secrets scattered across `.env` files

It works.

Until you:

* switch machines
* break something
* want to roll back
* onboard someone else
* come back after two months and don’t remember what’s running

ATK exists because this setup is **real**, fragile, and constantly changing — and painful.

## Who ATK is for

ATK is for developers who:

* rely on coding agents (Claude Code, Codex, Augment Code, etc.)
* use MCP servers (local and remote)
* run local services like memory, observability, or vector stores
* care about owning their data and controlling their setup
* want identical setups across machines and tools

ATK is not limited to people building AI models. It is for people **building software with AI systems in the loop**.

## What ATK is (and is not)

### ATK **is**

* a **toolchain and service manager** for developers
* focused on **local, long-lived AI tooling**
* **git-backed and reproducible**
* **CLI-first and automation-friendly**
* designed to be driven by humans *and* coding agents

### ATK is **not**

* an environment manager (Nix, Conda, Devbox)
* infrastructure-as-code (Terraform, Ansible)
* project-scoped
* a production deployment system

If you’re configuring servers, ATK is the wrong tool.
If you’re keeping your **AI dev setup sane**, it’s the right one.

## Mental model

> Think of ATK as **a control plane for your local AI toolchain**.
>
> It sits above package managers, Docker, and agent configs, and keeps everything in sync.

> Think of ATK as **Homebrew + docker-compose + git history** —
> but for AI developer tooling.

* Tools are **plugins**
* Each plugin has a **lifecycle** (install, start, stop, logs, status)
* Everything lives under `~/.atk`
* Every change is **versioned**
* Your setup can be cloned, audited, and rolled back

## A tiny example

```bash
# install ATK
uv tool install atk-cli      # recommended
# or: pip install atk-cli

# initialize ATK Home (defaults to ~/.atk)
atk init

# add a plugin (from the registry)
atk add openmemory

# run it
atk start openmemory
atk status

# generate MCP config JSON for your agent
atk mcp openmemory
```

Your entire setup now lives in `~/.atk/` — a git repository.

Push it. Clone it on another machine. Run `atk install --all`.

## Reproducibility, updates, and drift

AI tooling is not static. MCPs, agents, and local services evolve constantly.
ATK treats **updates and drift as first-class concerns**, not afterthoughts.

AI tooling is not static. MCPs, agents, and local services evolve constantly.
ATK treats **updates as a first-class concern**, not an afterthought.

##

ATK environments are fully reproducible:

* plugins are validated against a **versioned schema**
* additive schema changes are backward-compatible
* plugin versions are **pinned** in a manifest
* secrets live in isolated, gitignored `.env` files
* the entire toolkit directory is **git-backed**

Clone the repo. Run `atk sync`. You get the same toolchain — including tool versions, MCPs, and agent-facing configuration.

## ATK plugins and registry

ATK is built around **plugins**.

A plugin describes how to install, configure, run, update, and integrate a tool or service — including MCPs, local services, CLIs, or agent-facing components.

ATK supports **three ways** to work with plugins:

### 1. Official ATK Registry (vetted plugins)

ATK maintains a growing **registry of vetted plugins** for common and useful tools in AI-assisted development.

Install by name:

```bash
atk add openmemory
atk add langfuse
```

Examples include:

* popular MCPs (e.g. GitHub, Playwright, design tools)
* local AI infrastructure (memory systems, observability, vector stores)
* tools like OpenMemory, Langfuse, and similar services

Registry plugins are:

* reviewed and schema-validated
* versioned and pinned
* safe to install and update

Think of this as the "known good" layer.

### 2. Git repository plugins (distribution channel)

Any Git repository can become an ATK plugin.

If you are building a tool, MCP, or service that others may want to use, you can add a `.atk` definition to your repository.

Users can then add it directly from the repository URL (ATK looks for a `.atk/` directory at the repo root):

```bash
atk add github.com/your-org/your-tool
```

ATK will:

* validate the plugin against the schema
* pin it to a specific commit hash in the manifest
* manage its lifecycle like any other plugin

(Under the hood, ATK uses sparse checkout to fetch only the `.atk/` directory.)

This turns ATK into a **distribution channel** for AI tooling — without a centralized gatekeeper.

### 3. Local plugins (personal or internal tooling)

You can also define plugins locally for your own use.

These plugins:

* live in your `~/.atk` directory
* are fully versioned and git-backed
* use the same schema and validation

This is ideal for:

* personal scripts and services
* internal tools
* experiments you don’t want to publish

---

ATK lives **above** package managers, Docker, and agent configs.
It doesn’t replace them — it orchestrates them.

## Unified lifecycle

ATK gives every tool the same lifecycle, regardless of how it is installed.

```bash
atk start openmemory
atk stop openmemory
atk restart openmemory
atk status
atk logs openmemory
```

This works whether the tool is:

* a Docker service
* a Python CLI
* a Node binary
* a custom shell-based MCP server

## Design principles

| Principle   | Meaning                                               |
| ----------- | ----------------------------------------------------- |
| Declarative | The manifest describes desired state; ATK enforces it |
| Idempotent  | Running the same command twice yields the same result |
| Git-native  | Every mutation is a commit; rollback = `git revert`   |
| Transparent | Human-readable YAML; no hidden state                  |
| AI-first    | CLI-driven, scriptable, agent-friendly                |
| Focused     | Manages tools, doesn’t build them                     |

## Why ATK exists

ATK was built to solve a real, personal problem: keeping a complex AI developer setup understandable, reproducible, and reversible.

If you’re working with:

* agent frameworks
* MCP servers
* observability and tracing
* local inference
* vector databases
* hybrid stacks of Python, Node, Docker, and binaries

ATK is for you.

## What ATK is evolving into

ATK is evolving into a **control plane for AI-assisted development**.

Planned directions include:

* a full **ATK plugin registry** as a discovery and distribution layer
* proactive configuration of coding agents (e.g. `atk mcp setup claude-code openmemory`)
* automatic binding between MCPs, local services, and agents
* managing `AGENT.md`, `CLAUDE.md`, and similar files centrally
* keeping multiple coding agents in sync to reduce vendor lock-in

The long-term goal:

> **ATK becomes the last MCP you ever need to install.**
>
> Through the ATK MCP, coding agents can install, update, configure, start, stop, and compose all other tools.

Switching agents should feel trivial, because your setup — tools, memory, rules, MCPs — stays identical.

## Installation

```bash
# Recommended
uv tool install atk-cli

# Alternative
pip install atk-cli
```

ATK is distributed via **PyPI** and installs as a single self-contained CLI.

## Roadmap (high level)

* Core CLI and lifecycle management — **done**
* Plugin schema and validation — **done**
* Registry and git-based distribution — **in progress**
* Agent configuration and MCP binding — **planned**
* ATK MCP (self-hosting control plane) — **planned**

## Status

ATK is under active development.
Expect rough edges, fast iteration, and opinionated choices.

If this problem resonates with you, try it — and break it.
