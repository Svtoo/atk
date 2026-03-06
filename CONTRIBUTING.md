# Contributing to ATK

Thanks for your interest. ATK is an early-stage tool — contributions are welcome.

## Getting started

```bash
git clone https://github.com/Svtoo/atk
cd atk
uv sync --dev
```

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
```

If you're adding a command or changing CLI behaviour, also test it manually:

```bash
uv run atk <your command>
```

The CI must pass before a PR is merged.

## Submitting a PR

1. Fork and create a branch from `main`.
2. Write or update tests for your change.
3. Run `make check` — all must pass.
4. Open a PR with a clear description of what changed and why.

## Adding a registry plugin

Submit a PR to [atk-registry](https://github.com/Svtoo/atk-registry), not this repo.
See the registry README for schema requirements.

