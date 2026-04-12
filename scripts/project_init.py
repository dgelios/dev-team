#!/usr/bin/env python3
"""
project_init.py — filesystem helper for the dev-team plugin.

Creates and inspects project/version directories under .dev-team/projects/.
Called by the commands/dev-team.md and commands/improve.md orchestrators
so that all filesystem shape is managed in one place.

Commands:
    slugify    --text "<free text>"                       -> prints a slug
    new        --slug <slug>                              -> creates projects/<slug>/v1.0.0/ skeleton
    version    --slug <slug> --new <vX.Y.Z> --from <vX.Y.Z>
                                                          -> creates projects/<slug>/<new>/ skeleton
                                                             and copies code/ + tests/ from <from>
                                                             writes parent_version.txt
    bump       --from <vX.Y.Z> --bump patch|minor|major   -> prints the next version string
    latest     --slug <slug>                              -> prints the highest existing version
    list       --slug <slug>                              -> prints all versions, newest first
    exists     --slug <slug> [--version <vX.Y.Z>]         -> exit 0 if exists, 1 if not
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path
from typing import Iterable


PROJECTS_ROOT = Path(".dev-team/projects")


# --- slug helpers ----------------------------------------------------------


_SLUG_PATTERN = re.compile(r"[^a-z0-9]+")
_STOPWORDS = {"a", "an", "the", "of", "for", "in", "on", "to", "with", "and", "or"}


def slugify(text: str, max_words: int = 4) -> str:
    """Turn a free-form phrase into a short lowercase hyphenated slug.

    - Keeps only a-z, 0-9.
    - Drops common English stopwords.
    - Keeps the first <max_words> remaining tokens.
    """
    lowered = text.strip().lower()
    # Replace any non [a-z0-9] run with a space so we can tokenize.
    tokens = _SLUG_PATTERN.sub(" ", lowered).split()
    meaningful = [t for t in tokens if t and t not in _STOPWORDS]
    if not meaningful:
        meaningful = tokens  # fall back to whatever we had
    selected = meaningful[:max_words]
    slug = "-".join(selected)
    slug = slug.strip("-")
    if not slug:
        raise ValueError(f"Could not derive a slug from input: {text!r}")
    return slug


# --- version helpers -------------------------------------------------------


_SEMVER_PATTERN = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")


def parse_version(ver: str) -> tuple[int, int, int]:
    m = _SEMVER_PATTERN.match(ver)
    if not m:
        raise ValueError(f"Invalid semver (expected vX.Y.Z): {ver!r}")
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def format_version(major: int, minor: int, patch: int) -> str:
    return f"v{major}.{minor}.{patch}"


def bump_version(current: str, level: str) -> str:
    major, minor, patch = parse_version(current)
    if level == "major":
        return format_version(major + 1, 0, 0)
    if level == "minor":
        return format_version(major, minor + 1, 0)
    if level == "patch":
        return format_version(major, minor, patch + 1)
    raise ValueError(f"Unknown bump level: {level!r}")


# --- project path helpers --------------------------------------------------


def project_dir(slug: str) -> Path:
    if not slug or "/" in slug or "\\" in slug:
        raise ValueError(f"Invalid slug: {slug!r}")
    return PROJECTS_ROOT / slug


def version_dir(slug: str, version: str) -> Path:
    parse_version(version)  # validate
    return project_dir(slug) / version


def existing_versions(slug: str) -> list[str]:
    root = project_dir(slug)
    if not root.is_dir():
        return []
    versions = []
    for child in root.iterdir():
        if child.is_dir() and _SEMVER_PATTERN.match(child.name):
            versions.append(child.name)
    versions.sort(key=parse_version, reverse=True)
    return versions


# --- skeleton creation -----------------------------------------------------


_VERSION_SUBDIRS: tuple[str, ...] = ("spec", "code", "tests", "results")


def create_version_skeleton(path: Path) -> None:
    """Create the standard set of subdirectories for a version folder."""
    path.mkdir(parents=True, exist_ok=False)
    for sub in _VERSION_SUBDIRS:
        (path / sub).mkdir()
    # An empty task.md placeholder so the orchestrator knows the expected path.
    (path / "task.md").touch()


def copy_tree(src: Path, dst: Path) -> None:
    """Copy src directory into dst, creating dst if missing, merging otherwise."""
    if not src.is_dir():
        return
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        target = dst / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            shutil.copy2(item, target)


# --- subcommands -----------------------------------------------------------


def cmd_slugify(args: argparse.Namespace) -> int:
    print(slugify(args.text, max_words=args.words))
    return 0


def cmd_new(args: argparse.Namespace) -> int:
    slug = args.slug
    root = project_dir(slug)
    if root.exists():
        print(
            f"Project already exists: {root}. Use /dev-team:improve to add a new version.",
            file=sys.stderr,
        )
        return 2

    initial = version_dir(slug, "v1.0.0")
    create_version_skeleton(initial)
    (initial / "bump_type.txt").write_text("initial\n", encoding="utf-8")

    # Machine-friendly output so the orchestrator can capture values cleanly.
    print(f"project_dir={root}")
    print(f"version=v1.0.0")
    print(f"version_dir={initial}")
    return 0


def cmd_version(args: argparse.Namespace) -> int:
    slug = args.slug
    from_ver = args.from_version
    new_ver = args.new
    bump_type = args.bump  # optional string, just recorded

    root = project_dir(slug)
    if not root.is_dir():
        print(f"Project does not exist: {root}", file=sys.stderr)
        return 2

    src = version_dir(slug, from_ver)
    if not src.is_dir():
        print(f"Source version does not exist: {src}", file=sys.stderr)
        return 2

    dst = version_dir(slug, new_ver)
    if dst.exists():
        print(f"Target version already exists: {dst}", file=sys.stderr)
        return 2

    create_version_skeleton(dst)

    # Inherit the developer-facing artifacts so improvement work starts from parent state.
    copy_tree(src / "code", dst / "code")
    copy_tree(src / "tests", dst / "tests")

    (dst / "parent_version.txt").write_text(f"{from_ver}\n", encoding="utf-8")
    if bump_type:
        (dst / "bump_type.txt").write_text(f"{bump_type}\n", encoding="utf-8")

    print(f"project_dir={root}")
    print(f"version={new_ver}")
    print(f"version_dir={dst}")
    print(f"parent_version={from_ver}")
    return 0


def cmd_bump(args: argparse.Namespace) -> int:
    print(bump_version(args.from_version, args.bump))
    return 0


def cmd_latest(args: argparse.Namespace) -> int:
    versions = existing_versions(args.slug)
    if not versions:
        print(f"No versions found for project: {args.slug}", file=sys.stderr)
        return 2
    print(versions[0])
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    for v in existing_versions(args.slug):
        print(v)
    return 0


def cmd_exists(args: argparse.Namespace) -> int:
    root = project_dir(args.slug)
    if not root.is_dir():
        return 1
    if args.version and not version_dir(args.slug, args.version).is_dir():
        return 1
    return 0


# --- entry point -----------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="project_init.py")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("slugify", help="Derive a slug from free text")
    sp.add_argument("--text", required=True)
    sp.add_argument("--words", type=int, default=4)
    sp.set_defaults(func=cmd_slugify)

    sp = sub.add_parser("new", help="Create a new project at v1.0.0")
    sp.add_argument("--slug", required=True)
    sp.set_defaults(func=cmd_new)

    sp = sub.add_parser("version", help="Create a new version folder inside an existing project")
    sp.add_argument("--slug", required=True)
    sp.add_argument("--new", required=True, help="New version like v1.1.0")
    sp.add_argument("--from", dest="from_version", required=True, help="Source version like v1.0.0")
    sp.add_argument("--bump", choices=["patch", "minor", "major"], default=None)
    sp.set_defaults(func=cmd_version)

    sp = sub.add_parser("bump", help="Compute the next version from a current version")
    sp.add_argument("--from", dest="from_version", required=True)
    sp.add_argument("--bump", choices=["patch", "minor", "major"], required=True)
    sp.set_defaults(func=cmd_bump)

    sp = sub.add_parser("latest", help="Print the highest existing version of a project")
    sp.add_argument("--slug", required=True)
    sp.set_defaults(func=cmd_latest)

    sp = sub.add_parser("list", help="List all versions of a project")
    sp.add_argument("--slug", required=True)
    sp.set_defaults(func=cmd_list)

    sp = sub.add_parser("exists", help="Check if project/version exists (exit 0/1)")
    sp.add_argument("--slug", required=True)
    sp.add_argument("--version", default=None)
    sp.set_defaults(func=cmd_exists)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
