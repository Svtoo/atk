.PHONY: test check release install-local install-pypi uninstall

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

# Install from local source — editable, so changes are live without reinstalling
install-local:
	uv tool install --editable . --reinstall

# Uninstall (works after either install-local or install-pypi)
uninstall:
	uv tool uninstall atk-cli

# Install stable release from PyPI
install-pypi:
	uv tool install atk-cli --reinstall

