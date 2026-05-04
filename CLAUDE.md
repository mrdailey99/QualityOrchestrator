# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Git Workflow

**Never commit directly to `main`.** Every change — feature, fix, CI tweak, chore — must go through a branch and PR.

### Branch naming
| Type | Pattern | Example |
|------|---------|---------|
| Feature | `feat/<slug>` | `feat/vitest-stubs` |
| Bug fix | `fix/<slug>` | `fix/fuzzy-threshold` |
| CI / tooling | `ci/<slug>` | `ci/node24-upgrade` |
| Chore / maintenance | `chore/<slug>` | `chore/split-deps` |

### Workflow (every task)
```bash
git checkout -b feat/<name>   # 1. branch off main
# ... make changes ...
git add <files>
git commit -m "..."           # 2. commit
git push -u origin feat/<name> # 3. push branch
gh pr create --fill           # 4. open PR
# review & merge via GitHub   # 5. merge → main
```

A `pre-push` hook (`.githooks/pre-push`) is committed to this repo and blocks direct pushes to `main`. Activate it once after cloning:
```bash
git config core.hooksPath .githooks
```

## Commands

```bash
# Install dependencies
pip install -e .
# or
pip install -r requirements.txt

# Run CLI (after install)
qo analyze --pr-url <url> --token <github_token>
qo analyze-local --files file1.py file2.py
qo serve

# Run CLI without install
python cli/main.py analyze --pr-url <url> --token <github_token>

# Run API server directly
python api/main.py

# Run tests
pytest tests/

# Run single test file
pytest tests/test_engine.py -v
```

## Architecture

Quality Orchestrator is a stateless AI-powered PR analysis tool. It fetches changed files from a GitHub PR, maps them to test files, scores overall risk, and recommends tests to run.

### Entry Points

- **CLI** (`cli/main.py`): Typer app. Commands: `analyze` (GitHub PR), `analyze-local` (local files), `serve` (start API).
- **API** (`api/main.py`): FastAPI app. Endpoints: `POST /analyze-pr`, `GET /health`.

### Core Engine (`engine/`)

- **`decision.py`** — `DecisionEngine` orchestrates the full pipeline: fetch changed files → map to tests → score risk → identify gaps → optionally generate stubs.
- **`mapping.py`** — Maps source files to test files using:
  1. Convention-based path rewriting (e.g., `src/api/user.js` → `tests/api/user.spec.js`)
  2. Fuzzy string matching with ≥0.70 similarity ratio as fallback
- **`risk.py`** — Calculates a 0–100 risk score from weighted file categories. Tiers: HIGH (≥70), MED (40–69), LOW (<40). Category weights: payment/security (5), auth/migrations (4), middleware/models/api (3), config/lib (2), utils/ui (1).

### Generation (`generation/templates.py`)

Generates test stub code for unmapped source files. Supports Playwright (JS/TS) and pytest (Python).

### Integration (`integrations/github.py`)

Wraps PyGithub to fetch PR metadata and changed file paths.

## Environment

Copy `.env.example` to `.env`:
- `GITHUB_TOKEN` — required for `analyze` command and API
- `QO_HOST`, `QO_PORT` — optional API server bind address (defaults: 0.0.0.0:8000)
