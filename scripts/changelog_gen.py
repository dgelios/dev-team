#!/usr/bin/env python3
"""
changelog_gen.py — deterministic CHANGELOG.md generator for a single version
folder under .dev-team/projects/<slug>/<version>/.

Writes a human-readable changelog built mechanically from:
  - task.md            (what was asked of this version)
  - bump_type.txt      (patch/minor/major/initial)
  - parent_version.txt (previous version, if any)
  - results/classification.txt (bug-fix/feature-add/...)
  - spec/spec.md       (current + parent for diff)
  - code/              (file-level diff vs parent)
  - tests/             (file-level diff vs parent)

For v1.0.0 (no parent) produces an "Initial release" changelog: task summary +
key [MUST] requirements from the spec.

Usage:
  python scripts/changelog_gen.py --slug <slug> --version <vX.Y.Z>
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import re
import sys
from pathlib import Path
from typing import Iterable


PROJECTS_ROOT = Path(".dev-team/projects")
CHANGELOG_NAME = "CHANGELOG.md"

_REQ_PATTERN = re.compile(r"^\s*\d+\.\s+`?\[(MUST|SHOULD|NICE)\]`?\s*(.+?)\s*$", re.MULTILINE)


# --- file helpers ----------------------------------------------------------


def read_text(path: Path) -> str | None:
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8", errors="replace")


def read_line(path: Path) -> str | None:
    text = read_text(path)
    if text is None:
        return None
    stripped = text.strip()
    return stripped or None


def list_files(root: Path) -> set[Path]:
    """Return every file under root as a relative Path."""
    if not root.is_dir():
        return set()
    out: set[Path] = set()
    for p in root.rglob("*"):
        if p.is_file():
            out.add(p.relative_to(root))
    return out


def file_hash(path: Path) -> str:
    h = hashlib.sha1()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# --- spec helpers ----------------------------------------------------------


def extract_requirements(spec_text: str | None) -> list[tuple[str, str]]:
    """Return a list of (level, requirement text) from the `## Requirements` section."""
    if not spec_text:
        return []
    # Take the section that follows `## Requirements` and stops at the next top-level heading.
    m = re.search(r"(?ms)^##\s+Requirements\s*\n(.*?)(?=^##\s+|\Z)", spec_text)
    section = m.group(1) if m else spec_text
    results: list[tuple[str, str]] = []
    for match in _REQ_PATTERN.finditer(section):
        level, text = match.group(1), match.group(2).strip()
        results.append((level, text))
    return results


def requirements_diff(
    parent: list[tuple[str, str]], current: list[tuple[str, str]]
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Return (added, removed) requirements comparing parent -> current."""
    parent_set = {(lvl, txt) for lvl, txt in parent}
    current_set = {(lvl, txt) for lvl, txt in current}
    added = [pair for pair in current if pair in (current_set - parent_set)]
    removed = [pair for pair in parent if pair in (parent_set - current_set)]
    return added, removed


# --- file diff between two version dirs ------------------------------------


def diff_dirs(parent_dir: Path, current_dir: Path) -> tuple[list[str], list[str], list[str]]:
    """Return (added, modified, removed) relative file paths as sorted strings."""
    parent_files = list_files(parent_dir)
    current_files = list_files(current_dir)

    added = sorted(str(p).replace("\\", "/") for p in current_files - parent_files)
    removed = sorted(str(p).replace("\\", "/") for p in parent_files - current_files)

    modified: list[str] = []
    for rel in sorted(parent_files & current_files):
        if file_hash(parent_dir / rel) != file_hash(current_dir / rel):
            modified.append(str(rel).replace("\\", "/"))
    return added, modified, removed


# --- changelog rendering ---------------------------------------------------


def _bullet(items: Iterable[str], empty: str = "(none)") -> list[str]:
    items = list(items)
    if not items:
        return [f"  {empty}"]
    return [f"  - `{x}`" for x in items]


def render_initial(
    version: str,
    date_str: str,
    task_text: str,
    requirements: list[tuple[str, str]],
) -> str:
    lines: list[str] = []
    lines.append(f"# {version} — Initial release ({date_str})")
    lines.append("")
    lines.append("## Overview")
    lines.append((task_text or "(no task.md recorded)").strip())
    lines.append("")
    lines.append("## Key requirements")
    must = [text for lvl, text in requirements if lvl == "MUST"]
    should = [text for lvl, text in requirements if lvl == "SHOULD"]
    if must:
        lines.append("### MUST")
        for r in must:
            lines.append(f"- {r}")
        lines.append("")
    if should:
        lines.append("### SHOULD")
        for r in should:
            lines.append(f"- {r}")
        lines.append("")
    if not must and not should:
        lines.append("(no MUST/SHOULD requirements found in spec/spec.md)")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_improvement(
    version: str,
    date_str: str,
    task_text: str,
    parent_version: str,
    bump_type: str,
    classification: str,
    code_added: list[str],
    code_modified: list[str],
    code_removed: list[str],
    tests_added: list[str],
    tests_modified: list[str],
    tests_removed: list[str],
    req_added: list[tuple[str, str]],
    req_removed: list[tuple[str, str]],
) -> str:
    lines: list[str] = []
    header_meta = " | ".join(
        part for part in [date_str, classification, f"bump={bump_type}", f"based on {parent_version}"] if part
    )
    lines.append(f"# {version} ({header_meta})")
    lines.append("")

    lines.append("## Change request")
    lines.append((task_text or "(no task.md recorded)").strip())
    lines.append("")

    lines.append("## Source code changes")
    lines.append("Added:")
    lines.extend(_bullet(code_added))
    lines.append("Modified:")
    lines.extend(_bullet(code_modified))
    lines.append("Removed:")
    lines.extend(_bullet(code_removed))
    lines.append("")

    lines.append("## Test changes")
    lines.append("Added:")
    lines.extend(_bullet(tests_added))
    lines.append("Modified:")
    lines.extend(_bullet(tests_modified))
    lines.append("Removed:")
    lines.extend(_bullet(tests_removed))
    lines.append("")

    lines.append("## Specification changes")
    if req_added:
        lines.append("New requirements:")
        for lvl, text in req_added:
            lines.append(f"- [{lvl}] {text}")
    else:
        lines.append("New requirements: (none)")
    lines.append("")
    if req_removed:
        lines.append("Removed requirements:")
        for lvl, text in req_removed:
            lines.append(f"- [{lvl}] {text}")
    else:
        lines.append("Removed requirements: (none)")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


# --- main ------------------------------------------------------------------


def generate(slug: str, version: str) -> Path:
    version_dir = PROJECTS_ROOT / slug / version
    if not version_dir.is_dir():
        raise FileNotFoundError(f"Version folder does not exist: {version_dir}")

    task_text = read_text(version_dir / "task.md") or ""
    bump_type = read_line(version_dir / "bump_type.txt") or "unknown"
    parent_version = read_line(version_dir / "parent_version.txt")
    classification = read_line(version_dir / "results" / "classification.txt") or bump_type
    current_spec = read_text(version_dir / "spec" / "spec.md")
    date_str = datetime.date.today().isoformat()

    if parent_version is None:
        # Initial release
        reqs = extract_requirements(current_spec)
        output = render_initial(version, date_str, task_text, reqs)
    else:
        parent_dir = PROJECTS_ROOT / slug / parent_version
        if not parent_dir.is_dir():
            raise FileNotFoundError(f"Parent version folder missing: {parent_dir}")

        parent_spec = read_text(parent_dir / "spec" / "spec.md")
        code_a, code_m, code_r = diff_dirs(parent_dir / "code", version_dir / "code")
        tests_a, tests_m, tests_r = diff_dirs(parent_dir / "tests", version_dir / "tests")
        req_added, req_removed = requirements_diff(
            extract_requirements(parent_spec), extract_requirements(current_spec)
        )

        output = render_improvement(
            version=version,
            date_str=date_str,
            task_text=task_text,
            parent_version=parent_version,
            bump_type=bump_type,
            classification=classification,
            code_added=code_a,
            code_modified=code_m,
            code_removed=code_r,
            tests_added=tests_a,
            tests_modified=tests_m,
            tests_removed=tests_r,
            req_added=req_added,
            req_removed=req_removed,
        )

    target = version_dir / CHANGELOG_NAME
    target.write_text(output, encoding="utf-8")
    return target


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="changelog_gen.py")
    p.add_argument("--slug", required=True)
    p.add_argument("--version", required=True)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        path = generate(args.slug, args.version)
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except Exception as e:  # noqa: BLE001 - surface unexpected errors plainly
        print(f"error: {type(e).__name__}: {e}", file=sys.stderr)
        return 2
    print(f"changelog_path={path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
