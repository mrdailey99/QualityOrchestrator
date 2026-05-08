# Changelog

All notable changes to Quality Orchestrator are documented here.

## [1.0.3] - 2026-05-08

### Added
- Release workflow now automatically moves the floating major version tag (e.g. `v1`) to the latest release after each publish. Users can now pin `uses: mrdailey99/QualityOrchestrator@v1` and always receive the latest patch within that major without updating their workflow files. Pre-release tags (e.g. `v2.0.0-beta.1`) are excluded from this update.

## [1.0.2] - 2026-05-07

### Added
- `qo stub <file>` CLI subcommand: generate a test stub for any source file directly from the terminal. Supports `--framework`, `--pr`, and `--no-write` (print to stdout instead of writing to disk).
- `.github/workflows/qo-bot.yml`: comment bot that responds to `/qo stub <file>` on pull requests. Generates the stub, commits it to the PR branch, and replies with the path. Permission-gated (write/maintain/admin only) with path traversal protection and failure notifications.
- PR comment footer now shows `/qo stub <file>` (with leading slash) to surface the bot command hint.

## [1.0.1] - 2026-05-07

### Added
- Initial public release: AI-powered PR analysis engine with risk scoring (0–100), test selection, missing coverage detection, and stub generation.
- GitHub Action (`action.yml`) with `github-token`, `generate-stubs`, `framework`, `test-dir`, `fail-on-high`, and `comment-on-low` inputs; `risk-tier` and `risk-score` outputs.
- CLI commands: `analyze`, `analyze-local`, `analyze-staged`, `list-tests`, `install-hooks`, `serve`.
- Auto-detection of JS test runner (vitest/jest/playwright) from project config files.
- PR comment with risk tier badge, test checkbox list, missing coverage section, run command, and generated stub previews.
- Comment deduplication via `<!-- quality-orchestrator -->` marker.
