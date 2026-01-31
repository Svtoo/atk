<p align="center">
  <img src="assets/logo.png" alt="ATK Logo" width="300px">
</p>

# atk

**A**I **T**ool**K**it — Manage AI development tools through a git-backed, declarative manifest.

> ⚠️ **In active development.** Core functionality works. Registry and remote sources coming soon.

## The Problem

If you use AI coding assistants like Claude Code, Cursor, or Windsurf, you've probably set up local tools: memory servers, observability platforms, text-to-speech, custom MCP servers. Each one has its own installation method, configuration location, and startup procedure.

Setting up a new machine? Hours of work. Keeping multiple machines in sync? Good luck. Sharing your setup with a teammate? Copy-paste chaos.

## The Solution

ATK manages your AI development tools the way you manage code: **declaratively, with git**.

```bash
# Initialize your toolkit
atk init

# Add a tool from the registry
atk add piper-tts

# Start it
atk start piper-tts

# Your entire setup is now in ~/.atk/ — a git repo
# Push it, clone it on another machine, run `atk install --all`
```

Every `atk add` and `atk remove` is a git commit. Your AI development environment becomes reproducible, versionable, and portable.

## How It Works

```
~/.atk/                           # Your toolkit (a git repo)
├── manifest.yaml                 # What's installed
├── plugins/
│   ├── piper-tts/
│   │   ├── plugin.yaml           # Plugin definition
│   │   ├── docker-compose.yml    # How it runs
│   │   └── .env                  # Your secrets (gitignored)
│   └── langfuse/
│       └── ...
└── .gitignore
```

Plugins define their own lifecycle: how to install, start, stop, check status, view logs. ATK orchestrates. You stay in control.

## Key Features

**Git-Native Workflow**
```bash
# On your main machine
atk add openmemory
git push

# On your laptop
git pull
atk install --all
atk start --all
```

**MCP Integration**
```bash
# Generate config for Claude Code, Cursor, etc.
atk mcp piper-tts
# Outputs ready-to-paste JSON with your env vars resolved
```

**Unified Lifecycle**
```bash
atk start piper-tts      # Start a service
atk stop piper-tts       # Stop it
atk restart piper-tts    # Restart
atk status               # See what's running
atk logs piper-tts       # View logs
```

**Environment Management**
```bash
atk setup langfuse       # Interactive prompt for API keys
# Secrets stored in .env files, automatically gitignored
```

**Port Conflict Detection**
```bash
atk start openmemory
# Error: Port 8787 already in use by another process
```

## Plugin Sources

| Source | Example | Use Case |
|--------|---------|----------|
| **Registry** | `atk add piper-tts` | Curated, tested plugins |
| **Local** | `atk add ./my-plugin/` | Your own tools |
| **Git URL** | `atk add github.com/org/repo` | Any repo with plugin.yaml *(coming soon)* |

The [atk-registry](https://github.com/sashajdn/atk-registry) follows the Homebrew model: community-maintained plugin definitions for popular tools.

## Example: Adding Piper TTS

```bash
# Add the plugin
$ atk add piper-tts
✓ Copied plugin files to ~/.atk/plugins/piper-tts
✓ Running install lifecycle...
✓ Added to manifest
✓ Committed: "Add plugin: Piper TTS"

# Configure it
$ atk setup piper-tts
PIPER_VOICE [en_GB-alba-medium]: en_US-lessac-medium
✓ Saved to .env

# Start it
$ atk start piper-tts
✓ Started Piper TTS

# Get MCP config for your AI assistant
$ atk mcp piper-tts
{
  "piper-tts": {
    "command": "./mcp-server.sh",
    "env": {
      "PIPER_TTS_URL": "http://localhost:5847"
    }
  }
}
```

## Design Principles

| Principle | What It Means |
|-----------|---------------|
| **Declarative** | Manifest describes desired state; ATK enforces it |
| **Idempotent** | Running the same command twice = same result |
| **Git-native** | Every mutation is a commit; rollback = `git revert` |
| **Transparent** | All config is human-readable YAML; no hidden state |
| **AI-first** | CLI-driven, scriptable, agent-friendly |
| **Focused** | Manages tools, doesn't build them |

## Installation

```bash
# With uv (recommended)
uv tool install atk

# With pip
pip install atk
```

*Note: Not yet published to PyPI. For now, install from source.*

## Development

Built with test-driven development and close to 100% coverage.

```bash
# Run tests
make test

# Full validation (lint + types + tests)
make check
```

## Roadmap

| Phase | Status | Description |
|-------|--------|-------------|
| Core CLI | ✅ | init, add, remove, git integration |
| Service Lifecycle | ✅ | start, stop, restart, status, logs |
| Configuration | ✅ | .env management, port conflicts, MCP config |
| Plugin Sources | 🔄 | Registry, git URL sources, upgrade command |
| Polish | ⏳ | Error messages, documentation |
| Community | ⏳ | PyPI, contribution guide |

## Contributing

1. Fork and clone
2. Run `make check` to verify your setup
3. Make changes (TDD: write tests first)
4. Run `make check` before committing
5. Submit a PR

## License

Apache-2.0
