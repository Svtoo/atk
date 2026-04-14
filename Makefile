.PHONY: test check release install-local install-pypi uninstall sync-skills install-hooks

# TDD cycle - run often
test:
	uv run pytest

# Pre-commit validation - lint, type check, tests
check:
	uv run ruff check src tests
	uv run mypy src
	uv run pytest

# Sync skills from skills/ to agent-specific directories
# Source of truth: skills/<name>/SKILL.md
# Currently supported agents: Claude Code (.claude/skills/)
sync-skills:
	@mkdir -p .claude/skills
	@for dir in skills/*/; do \
		name=$$(basename "$$dir"); \
		mkdir -p ".claude/skills/$$name"; \
		cp "$$dir"SKILL.md ".claude/skills/$$name/SKILL.md" 2>/dev/null || true; \
	done
	@echo "Skills synced to .claude/skills/"

# Install git pre-commit hook that runs check + sync-skills
install-hooks:
	@echo '#!/bin/sh' > .git/hooks/pre-commit
	@echo 'make check || exit 1' >> .git/hooks/pre-commit
	@echo 'make sync-skills' >> .git/hooks/pre-commit
	@chmod +x .git/hooks/pre-commit
	@echo "Pre-commit hook installed."

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

