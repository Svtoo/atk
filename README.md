# atk

**AI Agent Toolkit** — Manage AI development tools through a git-backed, declarative manifest.

> ⚠️ **In active development.** Not functional yet. Everything here is subject to change.

## What is ATK?

ATK is like Homebrew for AI tools. Install once, sync everywhere via git.

```bash
# Install a tool
atk install openmemory

# Sync your setup to a new machine
git clone ~/.atk && atk sync
```

The manifest (`~/.atk/manifest.yaml`) describes your desired state. ATK makes it real. Every action is a git commit, so you can version control your entire AI development environment.

## Vision

- **Declarative** — manifest describes what you want, ATK handles how
- **Git-native** — every change is a commit, sync across machines
- **AI-first** — designed for agents, scriptable, predictable
- **Focused** — manages tools, doesn't build them

## Development

```bash
# Quick TDD cycle
make test

# Full validation (lint + types + tests)
make check
```

## Contributing

1. Fork and clone
2. Run `make check` to verify your setup
3. Make changes (TDD: write tests first)
4. Run `make check` before committing
5. Submit a PR

## License

Apache-2.0
