# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.1] - 2026-04-12

### Fixed
- GitHub Actions release workflow: release notes are now passed through a file (`--notes-file`) instead of an inline shell string, so backtick-wrapped code (e.g. `` `dev-team` `` or `` `.dev-team/memory/` ``) is no longer stripped by shell interpolation.
## [1.0.0] - 2026-04-12

### Added
- Initial release of the `dev-team` plugin.
- Six subagents: `dev-team-ba`, `dev-team-techlead`, `dev-team-dev`, `dev-team-ba-review`, `dev-team-tester`, `dev-team-builder`.
- `/dev-team <task>` slash command that runs a 6-stage artifact-first pipeline.
- Feedback loops: BA Review can send Dev back for one fix pass; Tester can send Dev back for up to three fix passes.
- Workspace-local memory at `.dev-team/memory/` with auto-seeded templates on first run.
- Optional PyInstaller-based Builder stage triggered by GUI / `.exe` keywords in the spec.
- Self-hosted marketplace via `.claude-plugin/marketplace.json`.
- MIT License.

[Unreleased]: https://github.com/dgelios/dev-team/compare/v1.0.1...HEAD
[1.0.1]: https://github.com/dgelios/dev-team/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/dgelios/dev-team/releases/tag/v1.0.0
