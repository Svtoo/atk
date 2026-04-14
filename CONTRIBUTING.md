# Contributing to ATK

Thanks for your interest. ATK is an early-stage tool — contributions are welcome.

## Getting started

```bash
git clone https://github.com/Svtoo/atk
cd atk
uv sync --dev
make install-hooks   # Install pre-commit hook
make sync-skills     # Copy skills to agent directories
```

## Development workflow

### Pre-commit hook

`make install-hooks` installs a git pre-commit hook that:

1. Runs `make check` (ruff lint, mypy type-check, pytest) — commit is blocked if any fail
2. Runs `make sync-skills` — copies skills to agent-specific directories

The hook is local (`.git/hooks/pre-commit`) and not tracked in git. Run `make install-hooks` after cloning.

### Skills

ATK includes skills (structured prompts) for AI coding agents. The source of truth is `skills/<name>/SKILL.md` at the project root. Skills are agent-agnostic — they work with any agent that supports structured prompts.

`make sync-skills` copies skills to agent-specific directories where they are discoverable:

| Agent | Target directory | Discovery |
|-------|-----------------|-----------|
| Claude Code | `.claude/skills/<name>/SKILL.md` | Auto-discovered as `/name` slash commands |

The agent directories (`.claude/skills/`) are gitignored — they contain derived copies, not source files. Always edit `skills/<name>/SKILL.md`, never the copies.

To add a new skill: create `skills/<your-skill>/SKILL.md` and run `make sync-skills`.

## Making changes

- Open an issue first for non-trivial changes.
- Keep PRs focused — one concern per PR.
- Match existing code style (ruff + mypy strict).

## Tests

All code changes must include automated tests.

```bash
# Run the full test suite
uv run pytest

# Lint and type-check
uv run ruff check src tests
uv run mypy src

# All of the above in one command
make check
```

If you're adding a command or changing CLI behaviour, also test it manually:

```bash
uv run atk <your command>
```

The CI must pass before a PR is merged.

## Releases

Releases are managed via the `/release` skill (or `make release` for manual local builds). See `skills/release/SKILL.md` for the full process.

Key points:
- Versioning uses **hatch-vcs** — version is derived from git tags (`vX.Y.Z`), not hardcoded
- CI runs on push to `main`; publish to PyPI triggers on tag push matching `v*.*.*`
- PyPI does not allow re-uploads — once a version is published, it is permanent

## Submitting a PR

1. Fork and create a branch from `main`.
2. Write or update tests for your change.
3. Run `make check` — all must pass.
4. Open a PR with a clear description of what changed and why.

## Adding a registry plugin

Submit a PR to [atk-registry](https://github.com/Svtoo/atk-registry), not this repo.
See the registry README for schema requirements.

