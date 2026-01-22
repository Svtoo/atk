.PHONY: test check release

# TDD cycle - run often
test:
	uv run pytest

# Pre-commit validation - lint, type check, tests
check:
	uv run ruff check src tests
	uv run mypy src
	uv run pytest

# Build and publish to PyPI
release:
	uv build
	uv publish

