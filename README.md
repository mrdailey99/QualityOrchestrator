# Quality Orchestrator

AI-powered PR analysis tool. Fetches changed files from a GitHub PR (or your local working tree), maps them to test files, scores overall risk, and recommends the exact tests to run — or generates stubs for gaps.

---

## Quick Start

```bash
pip install -r requirements.txt   # installs all deps
# or: pip install -e ".[all]"     # editable install with all extras

# Analyze a GitHub PR
qo analyze --pr 42 --repo owner/repo --token $GITHUB_TOKEN

# Analyze files you're about to commit (no token needed)
qo analyze-staged

# Analyze an explicit file list
qo analyze-local src/api/user.js src/lib/fraud.js
```

---

## Commands

### `qo analyze`

Fetch a GitHub PR's diff and analyze it.

```
qo analyze --pr <number> --repo <owner/repo> [options]
```

| Option | Description |
|--------|-------------|
| `--pr`, `-p` | PR number (required) |
| `--repo`, `-r` | GitHub repo in `owner/repo` form (required) |
| `--token` | GitHub token (or set `GITHUB_TOKEN` env var) |
| `--format` | Output format: `rich` (default) or `markdown` |
| `--json` | Emit raw JSON instead of formatted output |
| `--tui` | Interactive TUI with single-keypress run/stub actions |
| `--generate-stubs`, `-g` | Write test stub files for uncovered source files |
| `--known-test-files` | Explicit test file paths (pass once per file) |
| `--test-dir`, `-t` | Directory to scan for test files |
| `--framework` | Stub generator: `auto` (default), `pytest`, `playwright` |

```bash
# Rich output (default)
qo analyze --pr 42 --repo acme/api

# Markdown for CI comment
qo analyze --pr 42 --repo acme/api --format markdown

# With test-dir to count "Running N of M tests"
qo analyze --pr 42 --repo acme/api --test-dir tests/

# Generate stubs for files with no coverage
qo analyze --pr 42 --repo acme/api --generate-stubs
```

---

### `qo analyze-local`

Analyze a list of source files without a GitHub token.

```
qo analyze-local <file>... [options]
```

Accepts the same `--format`, `--json`, `--tui`, `--generate-stubs`, `--test-dir`, `--framework` flags as `analyze`.

```bash
qo analyze-local src/api/user.js src/lib/fraud.js
qo analyze-local src/api/user.js --test-dir tests/ --format markdown
```

---

### `qo analyze-staged`

Auto-detect changed files from git and analyze them — no token required. Designed for pre-commit / pre-push workflows.

```
qo analyze-staged [options]
```

| Option | Description |
|--------|-------------|
| `--staged` / `--all` | Staged files only (default) vs all changes vs HEAD |
| `--base`, `-b` | Compare branch tip against this base (e.g. `main`) |
| `--format` | `rich` (default) or `markdown` |
| `--json` | Raw JSON output |
| `--tui` | Interactive TUI mode |
| `--generate-stubs`, `-g` | Write stubs for uncovered files |
| `--test-dir`, `-t` | Directory to scan for known test files |
| `--framework` | Stub framework: `auto`, `pytest`, `playwright` |

```bash
# Staged files only (pre-commit)
qo analyze-staged

# All changes vs HEAD
qo analyze-staged --all

# Everything on this branch vs main (pre-push)
qo analyze-staged --base main

# Markdown output with total test count
qo analyze-staged --base main --test-dir tests/ --format markdown
```

---

### `qo install-hooks`

Wire QO into git's pre-push or pre-commit hook. On `HIGH` risk + missing coverage the hook exits 1 and blocks the push/commit.

```
qo install-hooks [options]
```

| Option | Description |
|--------|-------------|
| `--hook-type` | `pre-push` (default) or `pre-commit` |
| `--base` | Base branch for pre-push comparison (default: `main`) |
| `--force` | Overwrite an existing non-QO hook |
| `--uninstall` | Remove a previously installed QO hook |

```bash
# Install pre-push hook (blocks HIGH-risk pushes with gaps)
qo install-hooks

# Install pre-commit hook instead
qo install-hooks --hook-type pre-commit

# Remove a hook
qo install-hooks --uninstall

# Bypass the hook for a single push
git push --no-verify
```

---

### `qo list-tests`

Discover and print all test files in a directory. Uses `git ls-files` (respects `.gitignore`) with a filesystem-walk fallback. Use this to verify test file discovery before running `qo analyze`.

```
qo list-tests [directory]
```

```bash
# List all test files in the current repo
qo list-tests

# List tests in a specific directory
qo list-tests packages/api/tests/
```

---

### `qo serve`

Start the Quality Orchestrator REST API server.

```
qo serve [--host HOST] [--port PORT]
```

Defaults to `0.0.0.0:8000`. Override via `QO_HOST` / `QO_PORT` env vars or CLI flags.

```bash
qo serve
qo serve --port 9000
```

**Endpoints:**

- `POST /analyze-pr` — same as `qo analyze`, accepts JSON body with `pr`, `repo`, `token`
- `GET /health` — liveness check

---

## GitHub Actions

Add to `.github/workflows/quality.yml`:

```yaml
- uses: your-org/quality-orchestrator@main
  with:
    github-token: ${{ secrets.GITHUB_TOKEN }}
    repo: ${{ github.repository }}
    pr-number: ${{ github.event.pull_request.number }}
```

The action posts a Markdown analysis comment to the PR with risk tier, selected tests, and missing coverage gaps.

---

## Risk Scoring

Risk is scored 0–100 from three additive components:

| Component | Weight | Description |
|-----------|--------|-------------|
| Volume | 0–20 | `files × 2`, capped at 20 |
| Category | 0–50 | Highest-weight category × 10 (payment/security=5, auth/migrations=4, middleware/models/api=3, config/lib=2, utils/components/ui/styles=1) |
| Coverage | 0–30 | Fraction of testable files with no mapped test × 30 |

**Tiers:** `HIGH` ≥ 70 · `MED` 40–69 · `LOW` < 40

---

## Environment

Copy `.env.example` to `.env`:

```
GITHUB_TOKEN=ghp_...        # required for analyze and API
QO_HOST=0.0.0.0             # optional, default 0.0.0.0
QO_PORT=8000                # optional, default 8000
```

---

## Development

```bash
# Install all deps
pip install -r requirements.txt
# or editable with all extras:
pip install -e ".[all]"

# Run tests
pytest tests/

# Run a single test module
pytest tests/engine/test_risk.py -v
```
