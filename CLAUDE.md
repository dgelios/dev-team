# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A Claude Code plugin that orchestrates a 6-role AI development pipeline: **BA → TechLead → Dev → BA Review → Tester → Builder (optional)**. It is distributed via the Claude marketplace and installed into `~/.claude/plugins/`.

The plugin has no build step — it is pure Markdown (agent prompts, command scripts) plus two Python utility scripts.

## Commands

```bash
# Slugify a task description
python scripts/project_init.py slugify --text "Build a CSV parser"

# Create a new project skeleton (v1.0.0)
python scripts/project_init.py new --slug <slug>

# Create a new version folder, copying code/ and tests/ from parent
python scripts/project_init.py version --slug <slug> --new v1.1.0 --from v1.0.0 --bump minor

# Compute the next semver
python scripts/project_init.py bump --from v1.0.0 --bump patch

# List / check project versions
python scripts/project_init.py latest --slug <slug>
python scripts/project_init.py list --slug <slug>
python scripts/project_init.py exists --slug <slug> [--version vX.Y.Z]

# Generate CHANGELOG.md for a version
python scripts/changelog_gen.py --slug <slug> --version v1.0.0

# Manual release (PowerShell — maintainers only)
pwsh scripts/release.ps1 -Bump patch   # patch | minor | major | -Version X.Y.Z
pwsh scripts/release.ps1 -Bump patch -DryRun   # preview only
```

## Architecture

### Plugin entry points

| File | Role |
|---|---|
| `commands/dev-team.md` | `/dev-team:dev-team` — orchestrates a full new-project run (v1.0.0) |
| `commands/improve.md` | `/dev-team:improve` — orchestrates an improvement run (new semver version) |
| `agents/dev-team-*.md` | One subagent per role; invoked by the orchestrator commands |
| `.claude-plugin/plugin.json` | Plugin metadata; `version` field is the single source of truth for release versioning |

### Pipeline flow

```
BA (spec.md) → TechLead (architecture.md) → Dev (code/) → BA Review → Tester (tests/) → Builder* (dist/*.exe)
```

Review gates can loop back to Dev:
- **BA Review**: `CHANGES REQUESTED` → 1 Dev fix pass, max 1 iteration
- **Tester**: `FAIL` → Dev fix pass, max 3 iterations
- Any stage: `BLOCKED` → pipeline stops, user is asked for input

Builder only runs when the spec names a GUI library (tkinter, PyQt, etc.) or the task mentions `.exe`/`executable`/`windowed`.

### Artifact layout (at runtime, inside the user's workspace)

All state lives under `.dev-team/` in the workspace where the plugin is used — not in this repo:

```
.dev-team/
├── memory/              ← per-role lesson files, seeded from memory-templates/ on first run
└── projects/
    └── <slug>/
        └── vX.Y.Z/
            ├── task.md, bump_type.txt, parent_version.txt, CHANGELOG.md
            ├── spec/spec.md
            ├── code/
            ├── tests/
            ├── results/   ← architecture.md, dev-summary.md, dev-files.json, ba-review.md, qa-report.md, qa-files.json, test-results.md
            └── build/dist/*.exe
```

`scripts/project_init.py` is the **only** place that creates this directory structure. Orchestrators must call it rather than creating directories directly.

### Agent models

| Agent | Model |
|---|---|
| `dev-team-ba` | opus |
| `dev-team-techlead` | opus |
| `dev-team-dev` | sonnet |
| `dev-team-ba-review` | sonnet |
| `dev-team-tester` | opus |
| `dev-team-builder` | haiku |

### Releasing

Releases are automated via `.github/workflows/auto-release.yml` on every merge to `main`. Bump type is determined by PR labels (`release:minor`, `release:major`, `release:skip`; default: `patch`). The workflow bumps `.claude-plugin/plugin.json`, commits with `chore(release): X.Y.Z`, tags, and creates a GitHub Release.

The manual flow (`scripts/release.ps1`) does the same steps locally and pushes, triggering `.github/workflows/release.yml` via the tag push.

## Key invariants

- Parent versions are immutable once a newer version exists.
- All artifact content (specs, summaries, reviews, code comments) must be in **English only**.
- Every claimed artifact path must be verified on disk before the next pipeline stage begins.
- Agent receipts must be kept tiny — no pasting full file contents once the artifact files exist on disk.
- The `improve` command never modifies the parent version; the new version's `code/` and `tests/` start as copies of the parent.
