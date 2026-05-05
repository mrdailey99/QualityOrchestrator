import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich import box as rbox
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

# Ensure UTF-8 on Windows so box-drawing chars render correctly
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Allow running as `python cli/main.py` without installation
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

app = typer.Typer(
    name="quality-orchestrator",
    help="AI Quality Orchestrator -- analyze PRs, select tests, detect gaps.",
    no_args_is_help=True,
)
console = Console()
_progress = Console(stderr=True)  # progress/status always goes to stderr; stdout stays clean

# Design-system color tokens
_PINK   = "#ff2e7e"   # HIGH risk, accents
_CYAN   = "#5ad8ff"   # secondary neon, links
_GREEN  = "#4be3a4"   # LOW risk, passing
_YELLOW = "#ffd668"   # MED risk

_TIER_COLOR = {"HIGH": _PINK, "MED": _YELLOW, "LOW": _GREEN}

_STUB_MAX_LINES = 50
_FENCE_LANG = {"py": "python", "js": "javascript", "jsx": "jsx", "ts": "typescript", "tsx": "tsx"}


# ---------------------------------------------------------------------------
# analyze — pull PR from GitHub and analyze it
# ---------------------------------------------------------------------------

@app.command()
def analyze(
    pr: Annotated[int, typer.Option("--pr", "-p", help="PR number")],
    repo: Annotated[str, typer.Option("--repo", "-r", help="GitHub repo owner/name")],
    token: Annotated[Optional[str], typer.Option("--token", envvar="GITHUB_TOKEN", help="GitHub token")] = None,
    output_json: Annotated[bool, typer.Option("--json", help="Output raw JSON")] = False,
    output_format: Annotated[str, typer.Option("--format", help="Output format: rich or markdown")] = "rich",
    generate_stubs: Annotated[bool, typer.Option("--generate-stubs", "-g", help="Write stub files for missing coverage")] = False,
    known_test_files: Annotated[Optional[list[str]], typer.Option("--known-test-files", help="Known test file paths (pass once per file)")] = None,
    test_dir: Annotated[Optional[str], typer.Option("--test-dir", "-t", help="Directory to scan for test files")] = None,
    framework: Annotated[str, typer.Option("--framework", help="Stub framework override: auto, pytest, playwright")] = "auto",
    tui: Annotated[bool, typer.Option("--tui", help="Render results in interactive TUI mode")] = False,
) -> None:
    """Analyze a GitHub PR: fetch diff, map tests, score risk."""
    from integrations.github import get_pr_data
    from engine.decision import DecisionEngine

    if not token:
        console.print(
            "[yellow]No GitHub token found.[/] Set GITHUB_TOKEN or pass --token.\n"
            "Get one at: https://github.com/settings/tokens (repo read scope)"
        )
        raise typer.Exit(1)

    with console.status(f"[{_CYAN}]Fetching PR #{pr} from {repo}…[/]"):
        try:
            pr_data = get_pr_data(repo, pr, token)
        except Exception as exc:
            console.print(f"[red]GitHub error:[/] {exc}")
            raise typer.Exit(1)

    # Merge --known-test-files and --test-dir into one list
    all_known = list(known_test_files or [])
    if test_dir:
        all_known.extend(_scan_test_dir(test_dir))
    known = all_known or None

    engine = DecisionEngine()
    result = engine.analyze(
        files_changed=pr_data["files_changed"],
        diff=pr_data.get("diff"),
        repo=repo,
        known_test_files=known,
    )

    if output_json:
        out = {
            "pr": pr,
            "repo": repo,
            "risk_score": result.risk_score,
            "tier": result.tier,
            "score_breakdown": _breakdown_dict(result),
            "selected_tests": result.selected_tests,
            "missing_coverage": result.missing_coverage,
            "rationale": result.rationale,
        }
        typer.echo(json.dumps(out, indent=2))
        return

    if output_format == "markdown":
        stubs = _write_stubs(result.missing_coverage, pr, framework) if (generate_stubs and result.missing_coverage) else None
        typer.echo(_format_markdown(pr, repo, pr_data.get("title", ""), result, stubs=stubs))
        return

    if tui:
        _print_tui(pr, repo, pr_data.get("title", ""), result, framework=framework)
        return

    _print_result(pr, repo, pr_data.get("title", ""), result)

    if generate_stubs and result.missing_coverage:
        _write_stubs(result.missing_coverage, pr, framework)
    elif result.missing_coverage:
        console.print("[dim]Tip: pass --generate-stubs to scaffold test files for the gaps.[/]\n")


# ---------------------------------------------------------------------------
# analyze-local — no GitHub needed; pass file paths directly
# ---------------------------------------------------------------------------

@app.command(name="analyze-local")
def analyze_local(
    files: Annotated[list[str], typer.Argument(help="Changed source files")],
    output_json: Annotated[bool, typer.Option("--json", help="Output raw JSON")] = False,
    output_format: Annotated[str, typer.Option("--format", help="Output format: rich or markdown")] = "rich",
    generate_stubs: Annotated[bool, typer.Option("--generate-stubs", "-g", help="Write stubs for missing coverage")] = False,
    framework: Annotated[str, typer.Option("--framework", help="Stub framework override: auto, pytest, playwright")] = "auto",
    test_dir: Annotated[Optional[str], typer.Option("--test-dir", "-t", help="Directory to scan for test files")] = None,
    tui: Annotated[bool, typer.Option("--tui", help="Render results in interactive TUI mode")] = False,
) -> None:
    """Analyze a list of changed files locally — no GitHub token required."""
    from engine.decision import DecisionEngine

    known = _scan_test_dir(test_dir) if test_dir else None

    engine = DecisionEngine()
    result = engine.analyze(files_changed=files, known_test_files=known)

    if output_json:
        typer.echo(json.dumps({
            "risk_score": result.risk_score,
            "tier": result.tier,
            "score_breakdown": _breakdown_dict(result),
            "selected_tests": result.selected_tests,
            "missing_coverage": result.missing_coverage,
            "rationale": result.rationale,
        }, indent=2))
        return

    if output_format == "markdown":
        stubs = _write_stubs(result.missing_coverage, None, framework) if (generate_stubs and result.missing_coverage) else None
        typer.echo(_format_markdown(None, None, "local analysis", result, stubs=stubs))
        return

    if tui:
        _print_tui(None, None, "local analysis", result, framework=framework)
        return

    _print_result(None, None, "local analysis", result)

    if generate_stubs and result.missing_coverage:
        _write_stubs(result.missing_coverage, None, framework)


# ---------------------------------------------------------------------------
# list-tests — discover test files in the current repo
# ---------------------------------------------------------------------------

@app.command(name="list-tests")
def list_tests(
    directory: Annotated[str, typer.Argument(help="Root directory to scan")] = ".",
) -> None:
    """List all test files discovered in the repo (uses git ls-files, falls back to walk)."""
    from engine.mapping import is_test_file

    try:
        proc = subprocess.run(
            ["git", "ls-files"],
            capture_output=True, text=True, cwd=directory, timeout=30,
        )
        if proc.returncode != 0:
            raise RuntimeError("git ls-files failed")
        files = [f for f in proc.stdout.splitlines() if f]
    except Exception:
        files = []
        for p in Path(directory).rglob("*"):
            if p.is_file():
                rel = str(p.relative_to(directory)).replace("\\", "/")
                files.append(rel)

    for f in files:
        if is_test_file(f):
            typer.echo(f)


# ---------------------------------------------------------------------------
# serve — start the FastAPI server
# ---------------------------------------------------------------------------

@app.command()
def serve(
    host: Annotated[str, typer.Option("--host", envvar="QO_HOST")] = "0.0.0.0",
    port: Annotated[int, typer.Option("--port", envvar="QO_PORT")] = 8000,
) -> None:
    """Start the Quality Orchestrator API server."""
    try:
        import uvicorn
    except ImportError:
        console.print("[red]uvicorn not installed.[/] Run: pip install uvicorn[standard]")
        raise typer.Exit(1)

    console.print(f"[{_CYAN}]Starting API on http://{host}:{port}[/]")
    import uvicorn
    uvicorn.run("api.main:app", host=host, port=port, reload=False)


# ---------------------------------------------------------------------------
# Helpers — rendering
# ---------------------------------------------------------------------------

def _breakdown_dict(result) -> Optional[dict]:
    """Serialize score_breakdown to a plain dict for JSON output."""
    bd = result.score_breakdown
    if bd is None:
        return None
    return {"volume": bd.volume, "category": bd.category, "coverage": bd.coverage}


def _print_result(pr_number, repo, title, result) -> None:
    """Render analysis in Hacker/CLI-A style: colored terminal log, no panels."""
    score = result.risk_score
    tier = result.tier.upper()
    bd = result.score_breakdown
    tc = _TIER_COLOR.get(tier, "white")

    bar_len = 30
    filled = round(bar_len * score / 100)
    bar = "█" * filled + "░" * (bar_len - filled)

    # Context line
    ctx = []
    if pr_number:
        ctx.append(f"PR #{pr_number}")
    if repo:
        ctx.append(repo)
    if title and title not in ("local analysis", ""):
        ctx.append(title)

    console.print()
    if ctx:
        console.print(f"  [dim]{' · '.join(ctx)}[/]")
    console.print(f"  [{_CYAN}]▌ ANALYSIS COMPLETE[/]")
    console.print()

    # Risk score + bar
    console.print(f"  [dim]risk_score[/]   [{tc}]{score}/100[/]   [dim]tier=[/][bold {tc}]{tier}[/]")
    console.print(f"  [{tc}]{bar}[/]")
    if bd:
        console.print(f"  [dim]breakdown    vol={bd.volume}  cat={bd.category}  cov={bd.coverage}[/]")
    console.print()

    # Selected tests
    test_reasons = {e.test: e.reason for e in result.mapping if e.test}
    if result.selected_tests:
        console.print(f"  [dim]selected_tests:[/]")
        for t in result.selected_tests:
            reason = test_reasons.get(t, "")
            reason_str = f"  [dim]({reason})[/]" if reason and reason not in ("convention", "missing") else ""
            console.print(f"  [{_GREEN}]✓[/]  {t}{reason_str}")
        console.print()
    else:
        console.print(f"  [dim]no tests mapped.[/]")
        console.print()

    # Missing coverage
    if result.missing_coverage:
        console.print(f"  [{tc}]missing_coverage:[/]")
        for m in result.missing_coverage:
            console.print(f"  [{tc}]![/]  {m}")
        console.print()

    # Run command
    if result.selected_tests:
        cmd = _run_command_cli(result.selected_tests)
        console.print(f"  [dim]run:[/]")
        for line in cmd.splitlines():
            console.print(f"  [dim]{line}[/]")
        console.print()


def _print_tui(pr_number, repo, title, result, framework: str = "auto") -> None:
    """Render analysis in TUI/CLI-C style: boxed panels + single-keypress actions."""
    score = result.risk_score
    tier = result.tier.upper()
    bd = result.score_breakdown
    tc = _TIER_COLOR.get(tier, "white")

    bar_len = 30
    filled = round(bar_len * score / 100)
    bar = "█" * filled + "░" * (bar_len - filled)

    ctx_parts = []
    if pr_number:
        ctx_parts.append(f"PR #{pr_number}")
    if repo:
        ctx_parts.append(repo)
    context = "  ".join(ctx_parts) if ctx_parts else "local"

    console.print()

    # ── Risk panel ──────────────────────────────────────────────────────────
    risk_text = Text()
    risk_text.append(f"  {bar}  ", style=tc)
    risk_text.append(f"{score}", style=f"bold {tc}")
    risk_text.append("/100\n", style="dim")
    risk_text.append("  tier=", style="dim")
    risk_text.append(tier, style=f"bold {tc}")
    if bd:
        risk_text.append(f"  ·  vol={bd.volume}  cat={bd.category}  cov={bd.coverage}", style="dim")

    console.print(Panel(
        risk_text,
        title=f"[{_CYAN}]◢ QUALITY ORCHESTRATOR[/]  [dim]{context}[/]",
        title_align="left",
        border_style=_CYAN,
        box=rbox.SQUARE,
        padding=(0, 1),
    ))

    # ── Tests panel ─────────────────────────────────────────────────────────
    if result.selected_tests:
        tests_text = Text()
        for i, t in enumerate(result.selected_tests):
            if i:
                tests_text.append("\n")
            tests_text.append("  ● ", style=_GREEN)
            tests_text.append(t)
        console.print(Panel(
            tests_text,
            title=f"[{_GREEN}]TESTS TO RUN · {len(result.selected_tests)}[/]",
            title_align="left",
            border_style=_GREEN,
            box=rbox.SQUARE,
            padding=(0, 0),
        ))

    # ── Missing panel ────────────────────────────────────────────────────────
    if result.missing_coverage:
        missing_text = Text()
        for i, m in enumerate(result.missing_coverage):
            if i:
                missing_text.append("\n")
            missing_text.append("  ! ", style=_PINK)
            missing_text.append(m)
        console.print(Panel(
            missing_text,
            title=f"[{_PINK}]MISSING COVERAGE · {len(result.missing_coverage)}[/]",
            title_align="left",
            border_style=_PINK,
            box=rbox.SQUARE,
            padding=(0, 0),
        ))

    # ── Keyboard hints ───────────────────────────────────────────────────────
    has_tests = bool(result.selected_tests)
    has_gaps = bool(result.missing_coverage)

    hint_parts = []
    if has_tests:
        hint_parts.append(f"[{_CYAN}][r][/] run")
    if has_gaps:
        hint_parts.append(f"[{_CYAN}][g][/] generate stubs")
    hint_parts.append(f"[{_CYAN}][q][/] quit")

    console.print()
    console.print("  " + "  ·  ".join(hint_parts))

    key = _read_key()
    console.print()

    if key in ("r", "R") and has_tests:
        cmd = _run_command_cli(result.selected_tests)
        console.print(f"  [{_CYAN}]running:[/] [dim]{cmd}[/]")
        console.print()
        subprocess.run(cmd, shell=True)
    elif key in ("g", "G") and has_gaps:
        _write_stubs(result.missing_coverage, pr_number, framework)


def _read_key() -> str:
    """Read a single keypress without requiring Enter. Returns '' if not a TTY."""
    if not sys.stdin.isatty():
        return ""
    if sys.platform == "win32":
        import msvcrt
        ch = msvcrt.getwch()
        # getwch returns '\x00' or '\xe0' for special/function keys — skip both bytes
        if ch in ("\x00", "\xe0"):
            msvcrt.getwch()
            return ""
        return ch
    else:
        import tty
        import termios
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            return sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)


# ---------------------------------------------------------------------------
# Helpers — test discovery
# ---------------------------------------------------------------------------

def _scan_test_dir(directory: str) -> list[str]:
    """Return test file paths found in a directory.

    Uses git ls-files when available (respects .gitignore), falls back to
    a filesystem walk.
    """
    from engine.mapping import is_test_file

    d = Path(directory)
    if not d.is_dir():
        console.print(f"[yellow]Warning:[/] --test-dir '{directory}' is not a directory, skipping.")
        return []

    try:
        proc = subprocess.run(
            ["git", "ls-files", directory],
            capture_output=True, text=True, timeout=30,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return [f for f in proc.stdout.splitlines() if f and is_test_file(f)]
    except Exception:
        pass

    cwd = Path(".").resolve()
    return [
        str(p.resolve().relative_to(cwd)).replace("\\", "/")
        for p in d.rglob("*")
        if p.is_file() and is_test_file(str(p))
    ]


# ---------------------------------------------------------------------------
# Helpers — markdown / run commands
# ---------------------------------------------------------------------------

def _truncate_stub(content: str, path: str, max_lines: int = _STUB_MAX_LINES) -> str:
    """Truncate stub content for inline PR comment display."""
    lines = content.splitlines()
    if len(lines) <= max_lines:
        return content
    ext = Path(path).suffix.lower().lstrip(".")
    comment = "//" if ext in ("js", "jsx", "ts", "tsx") else "#"
    return "\n".join(lines[:max_lines]) + f"\n{comment} ... truncated — full stub at {path}"


def _md_path(path: str) -> str:
    """Escape a file path for safe embedding in GitHub Markdown.

    Backticks inside an inline code span break formatting and enable markdown
    injection in the PR comment.
    """
    return path.replace("`", "&#96;")


def _run_command(test_files: list[str]) -> str:
    """Return the shell command for markdown/PR comment display (uses line continuations)."""
    py = [f for f in test_files if f.endswith(".py")]
    js = [f for f in test_files if not f.endswith(".py")]
    parts = []
    if py:
        parts.append("pytest \\\n  " + " \\\n  ".join(_md_path(f) for f in py))
    if js:
        parts.append("npx playwright test \\\n  " + " \\\n  ".join(_md_path(f) for f in js))
    return "\n\n".join(parts)


def _run_command_cli(test_files: list[str]) -> str:
    """Return the shell command for terminal display (plain, no line continuations)."""
    py = [f for f in test_files if f.endswith(".py")]
    js = [f for f in test_files if not f.endswith(".py")]
    parts = []
    if py:
        parts.append("pytest " + " ".join(py))
    if js:
        parts.append("npx playwright test " + " ".join(js))
    return "\n".join(parts)


def _format_markdown(
    pr_number,
    repo,
    title,
    result,
    stubs: Optional[list[tuple[str, str]]] = None,
) -> str:
    """Render analysis result as a GitHub PR comment (Markdown)."""
    tier = result.tier.upper()
    score = result.risk_score
    tier_icon = {"HIGH": "🔴", "MED": "🟡", "LOW": "🟢"}.get(tier, "⚪")

    # Strip the leading "<TIER> risk (<score>/100). " prefix that _rationale()
    # prepends — the hero line already shows tier and score explicitly.
    short_rationale = re.sub(r"^\w+ risk \(\d+/100\)\.\s*", "", result.rationale)

    lines = ["## Quality Orchestrator", ""]
    lines.append(f"**{tier_icon} {tier}** · **`{score} / 100`** · {short_rationale}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── Tests to Run ────────────────────────────────────────────────────────
    if result.selected_tests:
        n = len(result.selected_tests)
        lines.append(f"### 🧪 Tests to Run · {n} {'file' if n == 1 else 'files'}")
        lines.append("")
        for t in result.selected_tests:
            lines.append(f"- [x] `{_md_path(t)}`")
        lines.append("")
        lines += [
            "<details>",
            "<summary>▶&nbsp;Run command</summary>",
            "",
            "```bash",
            _run_command(result.selected_tests),
            "```",
            "",
            "</details>",
            "",
        ]
    else:
        lines.append("_No test files mapped._")
        lines.append("")

    # ── Missing Coverage ─────────────────────────────────────────────────────
    if result.missing_coverage:
        lines.append("---")
        lines.append("")
        n = len(result.missing_coverage)
        lines.append(f"### ⚠️ Missing Coverage · {n} {'file' if n == 1 else 'files'}")
        lines.append("")
        lines.append("These source files have no mapped test — consider adding coverage before merge.")
        lines.append("")
        for m in result.missing_coverage:
            lines.append(f"- [ ] `{_md_path(m)}`")
        lines.append("")
        first = _md_path(result.missing_coverage[0])
        lines.append(f"> 💡 Reply `@qo stub {first}` to generate a test scaffold.")
        lines.append("")

    # ── Generated Stubs ──────────────────────────────────────────────────────
    if stubs:
        lines.append("---")
        lines.append("")
        lines.append("### 📋 Generated Stubs")
        lines.append("")
        for path, content in stubs:
            ext = Path(path).suffix.lower().lstrip(".")
            lang = _FENCE_LANG.get(ext, "text")
            truncated = _truncate_stub(content, path)
            lines += [
                "<details>",
                f"<summary><code>{path}</code></summary>",
                "",
                f"```{lang}",
                truncated,
                "```",
                "",
                "</details>",
                "",
            ]

    # ── Footer ───────────────────────────────────────────────────────────────
    lines.append("---")
    lines.append("")
    lines.append("<sub>⚡ quality-orchestrator &nbsp;·&nbsp; `@qo stub <file>` &nbsp;·&nbsp; `@qo why?` &nbsp;·&nbsp; `@qo run all`</sub>")
    lines.append("")
    lines.append("<!-- quality-orchestrator -->")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helpers — stub generation
# ---------------------------------------------------------------------------

def _write_stubs(
    missing: list[str],
    pr_number,
    framework: str = "auto",
) -> list[tuple[str, str]]:
    """Write stub files to disk and return list of (path, content) pairs."""
    from generation.templates import generate_stub

    results: list[tuple[str, str]] = []
    _progress.print("[yellow]Generating stubs...[/]")
    for src in missing:
        test_path, content = generate_stub(src, pr_number, framework=framework)
        out = Path(test_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8")
        _progress.print(f"  [{_GREEN}][+][/] {test_path}")
        results.append((test_path, content))
    _progress.print()
    return results


if __name__ == "__main__":
    app()
