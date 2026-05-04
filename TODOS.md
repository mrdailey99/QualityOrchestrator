# TODOS.md

Items accepted during engineering plan review (2026-05-04) and deferred from the CEO Phase 1 plan.

---

## Phase 1 — Eng Review Follow-ups

### T1: Document `qo list-tests` subcommand
Add a `qo list-tests` subcommand that runs `is_test_file()` across all tracked files and prints
newline-separated paths relative to the repo root. Document it in README as the canonical way to
verify test file discovery before running `qo analyze`.

### T2: Validate `$GITHUB_ACTION_PATH` at runtime
In `action.yml`, add a guard step before `pip install -e "$GITHUB_ACTION_PATH"` that validates
the env var is set and the path exists. Print a clear error if not — the silent failure mode is
a confusing install error with no actionable message.

### T3: Truncate inline stubs at 50 lines
When `--format markdown` embeds a generated stub in a `<details>` block, truncate stub content
at 50 lines and append: `# ... truncated — full stub at <path>`. Prevents 3000-line PR comments
on large source files. Accepted from CEO Reviewer Concern #2.

### T4: Per-file framework detection for monorepos
The current `--framework auto` picks one framework for the whole PR. In a monorepo with both
Python and JS/TS files changed, this produces wrong stubs for half the files. Implement per-file
framework selection in `generate_stub()` based on file extension, falling back to the
`--framework` flag value.

---

## Phase 2 — Framework Expansion

### T5: Vitest / Jest / Mocha stub templates
Add `generation/templates.py` support for Vitest, Jest, and Mocha stub generation. Phase 1 ships
pytest + Playwright only. These cover the majority of JS/TS repos that do not use Playwright for
unit/integration tests.

### T6: `test-dirs:` action input
Add a `test-dirs:` input to `action.yml` for repos with non-standard test directory layouts
(e.g., `packages/foo/tests/` in monorepos). The current `^tests/` anchor in the git ls-files
regex misses nested pytest directories. `test-dirs: "packages/*/tests"` would extend the pattern.

### T13: Cucumber / axe-core / k6 adapters
Adapters for BDD (Cucumber), accessibility (axe-core), and load testing (k6) frameworks. Extends
QO beyond unit/integration tests into the full test ecosystem. Enables `--framework cucumber` etc.

---

## GA Distribution

### T7: PyPI publish
Publish `quality-orchestrator` to PyPI and switch `action.yml` from the `$GITHUB_ACTION_PATH`
install approach to `pip install quality-orchestrator`. Faster cold starts (PyPI cache hits),
removes the constraint that QO must be a public repo for composite action distribution.

---

## Phase 2 — Platform

### T8: Playwright+MCP integration
Auto-generate complete Playwright tests against a live staging environment using MCP browser
control, then post them as PRs. Key differentiator over CloudBees Smart Tests — QO generates
runnable tests, not just stubs.

### T9: GitHub App org-level install
Install once at the org level and every repo is covered. No per-repo workflow file. This is
the enterprise distribution model; the per-repo Action is the on-ramp.

### T10: Cross-repo CI history learning
Learn which tests have historically caught bugs from CI failure history. Weight recommendations
by actual failure frequency. Transforms QO from convention-based to ML-based test selection.

### T11: Analytics dashboard
Coverage trends over time across the org: which files are chronically uncovered, which teams
are adopting QO, whether QO-recommended tests are actually being run. Requires T9 (org-level
install) to have meaningful cross-repo data.

---

## UX

### T14: "Running X of Y tests" display
Show `Running 2 of 143 tests` in the PR comment header. Total count is available from
`--known-test-files` length. Makes the time savings concrete and immediately visible to the
developer reading the comment.
