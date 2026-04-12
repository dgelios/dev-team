---
description: Add a new version to an existing dev-team project (bug fix, feature, refactor, optimization, doc update)
argument-hint: "<project-slug> [--from <vX.Y.Z>] [--bump patch|minor|major] <improvement description>"
---

# dev-team:improve

Apply an improvement to an existing `.dev-team/projects/<slug>/` project by creating a **new version** folder inside it.

The raw arguments are:

$ARGUMENTS

---

## Orchestrator Behavior

### 0. Parse arguments

Tokens from `$ARGUMENTS`:

1. First token is **PROJECT_SLUG** (required). Must match `[a-z0-9-]+`.
2. Optional flags that may appear in any order before the description:
   - `--from <vX.Y.Z>` — base the improvement on a specific existing version (default: latest).
   - `--bump patch|minor|major` — force a specific semver bump (default: derived from BA classification).
3. Everything remaining is the IMPROVEMENT description.

If PROJECT_SLUG or the description is missing, stop and show usage.

### 1. Resolve project and base version

1. Verify the project exists:
   ```
   python scripts/project_init.py exists --slug <PROJECT_SLUG>
   ```
   If it does not, stop and tell the user to create it first via `/dev-team:dev-team --project <PROJECT_SLUG> <task>`.

2. Determine FROM_VERSION:
   - If the `--from` flag was provided, use it and verify it exists:
     ```
     python scripts/project_init.py exists --slug <PROJECT_SLUG> --version <FROM_VERSION>
     ```
   - Otherwise, read the latest version:
     ```
     python scripts/project_init.py latest --slug <PROJECT_SLUG>
     ```
     Capture its stdout as FROM_VERSION.

3. Set `FROM_VERSION_DIR = .dev-team/projects/<PROJECT_SLUG>/<FROM_VERSION>/`.

### 1.5. Initialize memory (first run only)

Apply the same memory-seeding procedure described in `/dev-team:dev-team`: ensure `.dev-team/memory/` exists and every role file is present (seed from `memory-templates/` or create a minimal header if the template is not resolvable).

### 2. BA Amendment (classify + amended spec)

1. Read `.dev-team/memory/ba-memory.md` and include it in the agent prompt.
2. Invoke `dev-team-ba` in **amendment mode** with:
   - `PARENT_SPEC_PATH = <FROM_VERSION_DIR>/spec/spec.md`
   - `IMPROVEMENT_TEXT` = the IMPROVEMENT description from `$ARGUMENTS`
   - Outputs expected:
     - A **full, updated** spec (not a delta) that incorporates the improvement
     - A **classification** word from this set: `bug-fix | feature-add | refactor | optimization | doc-update | breaking`
3. Wait for BA response. It MUST return the amended spec content and the classification.
4. Capture `CLASSIFICATION` value (one of the six words above). If BA failed to emit a valid classification, default to `feature-add`.

### 3. Compute new version

1. If the `--bump` flag was provided, use it as BUMP.
2. Otherwise, derive BUMP from CLASSIFICATION:
   | Classification | Bump |
   |---|---|
   | `bug-fix` | patch |
   | `doc-update` | patch |
   | `optimization` | patch |
   | `feature-add` | minor |
   | `refactor` | minor |
   | `breaking` | major |
3. Compute NEW_VERSION:
   ```
   python scripts/project_init.py bump --from <FROM_VERSION> --bump <BUMP>
   ```
   Capture its stdout as NEW_VERSION.

### 4. Create the new version folder

1. Run:
   ```
   python scripts/project_init.py version --slug <PROJECT_SLUG> --new <NEW_VERSION> --from <FROM_VERSION> --bump <BUMP>
   ```
2. Parse stdout to confirm:
   - `project_dir=...`
   - `version=<NEW_VERSION>`
   - `version_dir=...` → this is `PROJECT_DIR` for the remaining stages
   - `parent_version=<FROM_VERSION>`
3. Write the IMPROVEMENT description to `PROJECT_DIR/task.md`.
4. Write the full amended spec from step 2 to `PROJECT_DIR/spec/spec.md`.
5. Write `CLASSIFICATION` to `PROJECT_DIR/results/classification.txt`.
6. Verify `PROJECT_DIR/task.md` and `PROJECT_DIR/spec/spec.md` exist and are non-empty before continuing.
7. Note: `code/` and `tests/` in `PROJECT_DIR` are already seeded from `FROM_VERSION_DIR` by the script. Subsequent stages modify them in place.

### Canonical paths (resolve relative to PROJECT_DIR)

Same as in `/dev-team:dev-team`. `SPEC_PATH` was already written above.

---

### Stage-skip rules based on CLASSIFICATION

| Classification | Stages executed |
|---|---|
| `feature-add` | Tech Lead → Dev → BA Review → Tester → Builder* |
| `refactor` | Tech Lead → Dev → BA Review → Tester |
| `optimization` | Tech Lead → Dev → BA Review → Tester |
| `breaking` | Tech Lead → Dev → BA Review → Tester → Builder* |
| `bug-fix` | Dev → BA Review → Tester (skip Tech Lead) |
| `doc-update` | Dev (skip Tech Lead, BA Review, Tester) |

`Builder*` runs only if spec's `## Tech Stack` mentions a GUI library or the task mentions `.exe`/`executable`/`windowed` (same rule as `/dev-team:dev-team`).

If a stage is skipped, also skip verification of its artifact path. The Final Report should show `<skipped>` for those paths.

---

### Stage 1.5 — Tech Lead Architecture *(conditional per classification)*

1. Read `.dev-team/memory/techlead-memory.md`.
2. Invoke `dev-team-techlead` with:
   - `SPEC_PATH`
   - `ARCHITECTURE_PATH`
   - `PARENT_ARCHITECTURE_PATH = <FROM_VERSION_DIR>/results/architecture.md` (for context — may not exist)
3. Verify `ARCHITECTURE_PATH` exists and is non-empty.
4. On BLOCKED → stop and report.
5. Append dated note to `.dev-team/memory/techlead-memory.md` on success.

### Stage 2 — Developer Implementation

1. Read `.dev-team/memory/dev-memory.md`.
2. Invoke `dev-team-dev` with:
   - `TASK_PATH`
   - `SPEC_PATH`
   - `ARCHITECTURE_PATH` (if Tech Lead ran; else pass the parent's architecture.md if it exists)
   - `CODE_DIR` (already seeded from parent)
   - `DEV_SUMMARY_PATH`
   - `DEV_FILELIST_PATH`
   - A note that `CODE_DIR` contains the parent version's code as a starting point; changes should modify it to satisfy the new spec.
3. Verify `DEV_SUMMARY_PATH` and `DEV_FILELIST_PATH` exist and are non-empty.
4. On BLOCKED → stop and report.
5. Append dated lesson to `.dev-team/memory/dev-memory.md` on success.

### Stage 3 — BA Review *(skipped for doc-update)*

1. Read `.dev-team/memory/ba-memory.md`.
2. Invoke `dev-team-ba-review` with:
   - `SPEC_PATH`
   - `DEV_SUMMARY_PATH`
   - `DEV_FILELIST_PATH`
   - `BA_REVIEW_PATH`
3. Verdict handling identical to `/dev-team:dev-team` Stage 3 (one Dev fix pass allowed on CHANGES REQUESTED).
4. Append dated lesson on success.

### Stage 4 — Tester *(skipped for doc-update)*

1. Read `.dev-team/memory/tester-memory.md`.
2. Invoke `dev-team-tester` with:
   - `SPEC_PATH`
   - `DEV_FILELIST_PATH`
   - `TESTS_DIR` (already seeded from parent — extend, do not overwrite, existing tests)
   - `QA_REPORT_PATH`
   - `QA_FILELIST_PATH`
   - `TEST_RESULTS_PATH`
3. Verdict handling identical to `/dev-team:dev-team` Stage 4 (up to 3 Dev+Tester fix passes on FAIL).
4. Append dated lesson on success.

### Stage 5 — Builder *(conditional)*

Same as `/dev-team:dev-team` Stage 5. Only runs for classifications `feature-add` or `breaking` when spec signals GUI/`.exe`.

---

### Final Report

```
## Dev-Team Improvement Complete

Project:         <PROJECT_SLUG>
Previous version: <FROM_VERSION>
New version:      <NEW_VERSION> (<BUMP>, <CLASSIFICATION>)
Improvement:      <one-line description>

Artifacts (under .dev-team/projects/<PROJECT_SLUG>/<NEW_VERSION>/):
  Spec:         <SPEC_PATH>
  Architecture: <ARCHITECTURE_PATH or <skipped>>
  Dev Summary:  <DEV_SUMMARY_PATH>
  BA Review:    <BA_REVIEW_PATH or <skipped>>
  QA Report:    <QA_REPORT_PATH or <skipped>>
  Test Results: <TEST_RESULTS_PATH or <skipped>>

Source files:   <list from DEV_FILELIST_PATH>
Test files:     <list from QA_FILELIST_PATH or <skipped>>
Executable:     <EXE_PATH if Builder ran, otherwise "N/A">

Final Verdict: ✅ PASS  |  ❌ FAIL  |  ❌ BLOCKED

Next steps:
  To add another improvement:
    /dev-team:improve <PROJECT_SLUG> <description>
```

---

## Rules

- Improvements never modify the parent version. The parent is an immutable snapshot.
- All new artifacts (spec, architecture, code changes, tests, results) live under the new version folder.
- `code/` and `tests/` in the new version start as exact copies of the parent and are modified by Dev/Tester.
- All filesystem shape is produced by `scripts/project_init.py`. Do not create directories by hand.
- Every claimed artifact path must be verified on disk before the next stage begins.
- Keep receipts tiny; do not paste full specs/code/reviews in receipts once artifact files exist.
- All artifact content must be in English only.
