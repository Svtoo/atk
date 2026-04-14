---
name: release
description: Create a new ATK release. Handles pre-flight checks, changelog generation, tagging, pushing, CI verification, and PyPI publication confirmation. Use when asked to cut a release, publish a new version, or ship changes.
argument-hint: "[version, e.g. 0.3.0]"
---

# ATK Release Process

You are performing a release of the `atk-cli` package. This is a critical operation — follow every step in order. Do not skip steps. Do not assume success — verify it.

## Versioning Strategy

ATK uses **hatch-vcs**: the version is derived from git tags at build time, not hardcoded.

- Tags follow `vX.Y.Z` (e.g., `v0.2.1`)
- **Patch** (`Z`): bug fixes, small features, non-breaking changes
- **Minor** (`Y`): new user-facing features, new commands, behavioral changes
- **Major** (`X`): breaking changes to CLI interface, manifest schema, or plugin API
- Pre-`v1.0.0`: minor bumps are for significant milestones; patches are the norm

PyPI receives the version without the `v` prefix (e.g., `0.2.1`).

**CRITICAL**: PyPI does not allow re-uploads. If a version is published, it is permanent. Never force-move a tag that has been pushed. If a mistake is published, bump to the next patch.

---

## Step 0: Determine Version

If version was provided as argument, use `v$ARGUMENTS`. Otherwise:

1. Run `git tag --sort=-v:refname | head -1` to find the current latest tag
2. Run `git log <latest-tag>..HEAD --oneline` to see what changed
3. Classify the changes:
   - Bug fixes only → **patch bump**
   - New features, new commands → **minor bump**
   - Breaking CLI/schema changes → **major bump**
4. Present the proposed version to Sasha with reasoning. Wait for confirmation before proceeding.

---

## Step 1: Pre-Flight Checks

Run ALL of these checks. If ANY fail, stop and report.

### 1a. Clean working tree

```bash
git status --short
```

EXPECT: Empty output (no uncommitted changes). If dirty, stop — all changes must be committed before release.

### 1b. On main branch

```bash
git branch --show-current
```

EXPECT: `main`. Releases are only cut from main.

### 1c. Up to date with remote

```bash
git fetch origin main
git rev-list HEAD..origin/main --count
```

EXPECT: `0` (no commits on origin/main that we don't have). If behind, stop — pull first.

### 1d. Local checks pass

```bash
make check
```

EXPECT: Exit 0. This runs ruff (lint), mypy (types), and pytest (tests). All must be green.

### 1e. CI is green on HEAD

```bash
gh run list --branch main --limit 3
```

EXPECT: The most recent CI run for HEAD is `completed` / `success`. If CI hasn't run for the current HEAD yet, wait or trigger it.

### 1f. No open blockers

Check if there are any issues/PRs that should block this release:

```bash
gh issue list --state open --label "blocker" --limit 5
```

If blockers exist, report them and ask Sasha whether to proceed.

---

## Step 2: Changelog Analysis

Generate a thorough changelog by analyzing what changed since the last release.

### 2a. Identify the last release

```bash
git tag --sort=-v:refname | head -1
```

### 2b. List all commits since last release

```bash
git log <last-tag>..HEAD --oneline --no-merges
```

### 2c. Detailed diff summary

```bash
git diff <last-tag>..HEAD --stat
```

### 2d. Categorize changes

Read each commit and the diff. Organize into categories:

- **New Features**: new commands, new config options, new behaviors
- **Bug Fixes**: corrections to existing behavior
- **Breaking Changes**: anything that changes existing CLI interface, manifest format, or plugin contract
- **Documentation**: spec updates, roadmap changes, new phase docs
- **Internal**: refactors, test improvements, CI changes

### 2e. Draft release notes

Write release notes in this format:

```markdown
## What's New

### <Feature Name>
<2-3 sentence description with usage example>

### <Feature Name>
...

## Bug Fixes
- <one-liner per fix>

## Breaking Changes
- <one-liner with migration guidance>

## Upgrade

\```bash
pip install --upgrade atk-cli
# or
uv tool upgrade atk-cli
\```

<Any migration notes if needed>
```

Present the draft to Sasha for review before proceeding.

---

## Step 3: Manual Testing

Before tagging, manually verify the key changes work. This is NOT optional.

For each new feature or significant change:
1. State what you're testing and why
2. Run the actual command against a real (or temporary) ATK Home
3. Verify the output matches expectations
4. Report PASS or FAIL with evidence

At minimum, always test:
- `atk --version` outputs a valid version
- `atk status` works without errors (if ATK Home exists)

---

## Step 4: Tag and Push

Only proceed here if all previous steps passed and Sasha approved the release notes.

### 4a. Create the tag

```bash
git tag v<VERSION>
```

### 4b. Push the commit and tag

```bash
git push origin main
git push origin v<VERSION>
```

The tag push triggers the Publish to PyPI workflow automatically.

---

## Step 5: Wait for CI

Both workflows must succeed before the release is complete.

### 5a. Monitor CI workflow (triggered by push to main)

```bash
gh run list --branch main --limit 3
```

Wait until the CI run for the current commit shows `completed` / `success`.

### 5b. Monitor Publish workflow (triggered by tag push)

```bash
gh run list --workflow publish.yml --limit 3
```

Wait until the publish run shows `completed` / `success`.

If either workflow fails:
1. Check logs: `gh run view <run-id> --log | tail -50`
2. Report the failure to Sasha
3. Do NOT proceed to creating the GitHub release
4. If the publish failed, the tag is "burned" — PyPI may or may not have the version. Check with `curl -s https://pypi.org/pypi/atk-cli/<VERSION>/json` before deciding next steps.

---

## Step 6: Verify PyPI Publication

```bash
curl -s https://pypi.org/pypi/atk-cli/<VERSION>/json | python3 -c "import sys,json; d=json.load(sys.stdin); print('Version:', d['info']['version']); print('Summary:', d['info']['summary'])"
```

EXPECT: Version matches the release version. If this fails, the publish did not actually land on PyPI — investigate before creating the GitHub release.

---

## Step 7: Create GitHub Release

```bash
gh release create v<VERSION> --title "v<VERSION> — <Short Title>" --notes "<release notes from Step 2>"
```

Use a HEREDOC for multi-line notes:

```bash
gh release create v<VERSION> --title "v<VERSION> — <Title>" --notes "$(cat <<'EOF'
<release notes here>
EOF
)"
```

---

## Step 8: Post-Release Verification

### 8a. Verify the release page exists

```bash
gh release view v<VERSION>
```

### 8b. Verify installability

```bash
uv pip install atk-cli==<VERSION> --dry-run
```

### 8c. Report completion

Summarize to Sasha:
- Version released
- PyPI URL: `https://pypi.org/project/atk-cli/<VERSION>/`
- GitHub release URL: `https://github.com/Svtoo/atk/releases/tag/v<VERSION>`
- CI status: all green
- Publish status: confirmed on PyPI

---

## Failure Recovery

| Failure | Recovery |
|---------|----------|
| CI fails after tag push | Fix the issue, push fix to main, bump to next patch, re-tag |
| Publish fails but PyPI has the version | The version is burned — create GitHub release as-is |
| Publish fails and PyPI does NOT have it | Fix issue, delete the tag (`git tag -d v<X> && git push origin :refs/tags/v<X>`), re-tag same commit |
| Wrong content released | Cannot re-upload to PyPI. Bump patch, fix, release again |
| Tag pushed to wrong commit | If not yet on PyPI: delete remote tag, re-tag correct commit. If on PyPI: bump patch |
