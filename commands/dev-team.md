---
description: Run the 6-role dev-team pipeline on a task description (creates v1.0.0 of a new project)
argument-hint: "[--project <slug>] <task description>"
---

# dev-team

Orchestrate a 6-role artifact-first development pipeline using project subagents:
`dev-team-ba` → `dev-team-techlead` → `dev-team-dev` → `dev-team-ba-review` → `dev-team-tester` → `dev-team-builder` *(conditional)*.

The raw arguments are:

$ARGUMENTS

---

## Orchestrator Behavior

When this command is invoked, you (the orchestrator) must:

### 0. Parse arguments

Raw `$ARGUMENTS` may contain an optional flag `--project <slug>` followed by the task description.

1. If the first token is `--project`, read the next token as PROJECT_SLUG and treat the rest as the TASK description. Validate that the slug matches `[a-z0-9-]+` — reject other characters.
2. Otherwise, derive PROJECT_SLUG automatically from the task by running:
   ```
   python scripts/project_init.py slugify --text "<task>"
   ```
   Capture its stdout as PROJECT_SLUG.
3. The full task text (without the `--project <slug>` prefix if present) becomes TASK.

### 1. Create project skeleton

1. Run:
   ```
   python scripts/project_init.py new --slug <PROJECT_SLUG>
   ```
2. If exit code is non-zero because the project already exists, stop and instruct the user to use `/dev-team:improve <slug> <description>` instead. Do NOT proceed with the pipeline.
3. On success, parse the script's stdout to capture:
   - `project_dir=...`
   - `version=v1.0.0`
   - `version_dir=...` → this is `PROJECT_DIR`
4. Write the task description to `PROJECT_DIR/task.md`.
5. Confirm `PROJECT_DIR` and `PROJECT_DIR/task.md` exist before continuing.

### 1.5. Initialize memory (first run only)

The plugin ships seed memory templates under its own `memory-templates/` directory. On first run in a workspace, copy them to the workspace-local `.dev-team/memory/` so agents can read and append lessons.

1. If `.dev-team/memory/` does not exist, create it.
2. For each role in `[ba, techlead, dev, ba-review, tester, builder]`:
   - If `.dev-team/memory/<role>-memory.md` does not exist on disk, copy the template from the plugin's `memory-templates/<role>-memory.md` into that path.
   - If the plugin template path is not resolvable at runtime, create the file with a minimal header (`# <Role> Memory\n\n## Lessons Learned\n`).
3. Proceed to Stage 1.

### Canonical paths (resolve relative to PROJECT_DIR)

| Variable | Path |
|---|---|
| `TASK_PATH` | `task.md` |
| `SPEC_PATH` | `spec/spec.md` |
| `ARCHITECTURE_PATH` | `results/architecture.md` |
| `CLASSIFICATION_PATH` | `results/classification.txt` |
| `CODE_DIR` | `code/` |
| `TESTS_DIR` | `tests/` |
| `DEV_SUMMARY_PATH` | `results/dev-summary.md` |
| `DEV_FILELIST_PATH` | `results/dev-files.json` |
| `BA_REVIEW_PATH` | `results/ba-review.md` |
| `QA_REPORT_PATH` | `results/qa-report.md` |
| `QA_FILELIST_PATH` | `results/qa-files.json` |
| `TEST_RESULTS_PATH` | `results/test-results.md` |
| `BUILD_DIR` | `build/` |
| `EXE_PATH` | `build/dist/<AppName>.exe` |

---

### Stage 1 — BA Spec

1. Read `.dev-team/memory/ba-memory.md` and include it in the agent prompt.
2. Invoke `dev-team-ba` in spec mode with:
   - `TASK_PATH`
   - `SPEC_PATH`
   - `CLASSIFICATION_PATH` (BA should write `initial` there for new projects)
3. Verify `SPEC_PATH` exists and is non-empty on disk before continuing.
4. If STATUS is BLOCKED, stop and report to user.
5. After success, append to `.dev-team/memory/ba-memory.md`:
   ```
   - YYYY-MM-DD: <ONE_LINE_LESSON from agent receipt>
   ```

---

### Stage 1.5 — Tech Lead Architecture

1. Read `.dev-team/memory/techlead-memory.md` and include it in the agent prompt.
2. Invoke `dev-team-techlead` with:
   - `SPEC_PATH`
   - `ARCHITECTURE_PATH`
3. Verify `ARCHITECTURE_PATH` exists and is non-empty on disk before continuing.
4. If STATUS is BLOCKED, stop and report to user.
5. After success, append to `.dev-team/memory/techlead-memory.md`:
   ```
   - YYYY-MM-DD: <NOTES from agent receipt>
   ```

---

### Stage 2 — Developer Implementation

1. Read `.dev-team/memory/dev-memory.md` and include it in the agent prompt.
2. Invoke `dev-team-dev` with:
   - `TASK_PATH`
   - `SPEC_PATH`
   - `ARCHITECTURE_PATH`
   - `CODE_DIR`
   - `DEV_SUMMARY_PATH`
   - `DEV_FILELIST_PATH`
3. Verify `DEV_SUMMARY_PATH` and `DEV_FILELIST_PATH` exist and are non-empty on disk.
4. If STATUS is BLOCKED, stop and report to user.
5. After success, append dated lesson to `.dev-team/memory/dev-memory.md`.

---

### Stage 3 — BA Review

1. Read `.dev-team/memory/ba-memory.md`.
2. Invoke `dev-team-ba-review` with:
   - `SPEC_PATH`
   - `DEV_SUMMARY_PATH`
   - `DEV_FILELIST_PATH`
   - `BA_REVIEW_PATH`
3. Verify `BA_REVIEW_PATH` exists and is non-empty on disk.
4. Check VERDICT:
   - `APPROVED` → proceed to Stage 4
   - `CHANGES REQUESTED` → run one Developer fix pass (Stage 2 again, include `ARCHITECTURE_PATH` and `BA_REVIEW_PATH`), then one BA Review pass (Stage 3 again), then proceed to Stage 4.
   - Max 1 BA fix iteration.
5. After success, append dated lesson to `.dev-team/memory/ba-memory.md`.

---

### Stage 4 — Tester

1. Read `.dev-team/memory/tester-memory.md`.
2. Invoke `dev-team-tester` with:
   - `SPEC_PATH`
   - `DEV_FILELIST_PATH`
   - `TESTS_DIR`
   - `QA_REPORT_PATH`
   - `QA_FILELIST_PATH`
   - `TEST_RESULTS_PATH`
3. Verify `QA_REPORT_PATH`, `QA_FILELIST_PATH`, `TEST_RESULTS_PATH` exist and are non-empty on disk.
4. Check VERDICT:
   - `PASS` → proceed to Final Report
   - `FAIL` → run one Developer fix pass, then one Tester pass. Max 3 tester fix iterations.
5. After success, append dated lesson to `.dev-team/memory/tester-memory.md`.

---

### Stage 5 — Builder *(conditional)*

Run this stage only if the spec's `## Tech Stack` mentions a GUI library (tkinter, PyQt, PySide, customtkinter, Dear PyGui, wxPython) OR the task explicitly mentions `.exe`, `executable`, or `windowed`.

1. Read `.dev-team/memory/builder-memory.md` and include it in the agent prompt.
2. Create `BUILD_DIR` (`build/`) under `PROJECT_DIR`.
3. Invoke `dev-team-builder` with:
   - `SPEC_PATH`
   - `DEV_FILELIST_PATH`
   - `CODE_DIR`
   - `BUILD_DIR`
   - `EXE_PATH`
4. Verify the `.exe` exists at the reported `EXE_PATH` on disk.
5. If STATUS is FAILED or BLOCKED, report to user but do not retry automatically.
6. After success, append dated lesson to `.dev-team/memory/builder-memory.md`.

---

### Stage 6 — Changelog

Always runs as the final artifact step, regardless of classification or Builder outcome. Produces `CHANGELOG.md` at the version folder root next to `bump_type.txt`.

1. Run:
   ```
   python scripts/changelog_gen.py --slug <PROJECT_SLUG> --version v1.0.0
   ```
2. For an initial release (this command always writes v1.0.0), the script emits:
   - Project overview taken from `task.md`
   - `## Key requirements` listing [MUST] and [SHOULD] requirements parsed from `spec/spec.md`
3. Verify `<PROJECT_DIR>/CHANGELOG.md` exists and is non-empty.
4. Include the changelog path in the Final Report under `Artifacts`.

---

### Final Report

Produce a concise human-readable summary. Do NOT paste full file contents.

```
## Dev-Team Pipeline Complete

Project: <PROJECT_SLUG>
Version: <VERSION> (initial)
Task:    <one-line task>

Artifacts (under <PROJECT_DIR>):
  Spec:         <SPEC_PATH>
  Dev Summary:  <DEV_SUMMARY_PATH>
  BA Review:    <BA_REVIEW_PATH>
  QA Report:    <QA_REPORT_PATH>
  Test Results: <TEST_RESULTS_PATH>
  Changelog:    <PROJECT_DIR>/CHANGELOG.md

Source files:   <list from DEV_FILELIST_PATH>
Test files:     <list from QA_FILELIST_PATH>
Executable:     <EXE_PATH if Builder ran, otherwise "N/A">

Final Verdict: ✅ PASS  |  ❌ FAIL  |  ❌ BLOCKED

Next steps:
  To improve this project, run: /dev-team:improve <PROJECT_SLUG> <improvement description>
```

---

## Rules

- One task = one project folder; one run of this command = v1.0.0 inside that project.
- Subsequent changes must go through `/dev-team:improve`, not this command.
- All filesystem shape (project folder, version folder, skeleton, code/tests copy) is produced by `scripts/project_init.py`. Do not create these directories by hand.
- After the version folder exists, agents must pass paths — not large pasted payloads.
- Never rely on chat history as artifact transport.
- Every claimed artifact path must be verified on disk before the next stage begins.
- Keep receipts tiny; do not paste full specs/code/reviews in receipts once artifact files exist.
- All artifact content (specs, summaries, reviews, reports, tests, comments) must be in English only.
