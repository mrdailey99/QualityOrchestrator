import json
import subprocess
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box as rbox

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

_TIER_COLOR = {"high": "red", "med": "yellow", "low": "green"}


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

    with console.status(f"[cyan]Fetching PR #{pr} from {repo}…[/]"):
        try:
            pr_data = get_pr_data(repo, pr, token)
        except Exception as exc:
            console.print(f"[red]GitHub error:[/] {exc}")
            raise typer.Exit(1)

    engine = DecisionEngine()
    result = engine.analyze(
        files_changed=pr_data["files_changed"],
        diff=pr_data.get("diff"),
        repo=repo,
        known_test_files=known_test_files,
    )

    if output_json:
        out = {
            "pr": pr,
            "repo": repo,
            "risk_score": result.risk_score,
            "tier": result.tier,
            "selected_tests": result.selected_tests,
            "missing_coverage": result.missing_coverage,
            "rationale": result.rationale,
        }
        typer.echo(json.dumps(out, indent=2))
        return

    if output_format == "markdown":
        typer.echo(_format_markdown(pr, repo, pr_data.get("title", ""), result))
        return

    _print_result(pr, repo, pr_data.get("title", ""), result)

    if generate_stubs and result.missing_coverage:
        _write_stubs(result.missing_coverage, pr)
    elif result.missing_coverage:
        console.print("[dim]Tip: pass --generate-stubs to scaffold test files for the gaps.[/]\n")


# ---------------------------------------------------------------------------
# analyze-local — no GitHub needed; pass file paths directly
# ---------------------------------------------------------------------------

@app.command(name="analyze-local")
def analyze_local(
    files: Annotated[list[str], typer.Argument(help="Changed source files")],
    output_json: Annotated[bool, typer.Option("--json", help="Output raw JSON")] = False,
    generate_stubs: Annotated[bool, typer.Option("--generate-stubs", "-g", help="Write stubs for missing coverage")] = False,
) -> None:
    """Analyze a list of changed files locally — no GitHub token required."""
    from engine.decision import DecisionEngine

    engine = DecisionEngine()
    result = engine.analyze(files_changed=files)

    if output_json:
        typer.echo(json.dumps({
            "risk_score": result.risk_score,
            "tier": result.tier,
            "selected_tests": result.selected_tests,
            "missing_coverage": result.missing_coverage,
            "rationale": result.rationale,
        }, indent=2))
        return

    _print_result(None, None, "local analysis", result)

    if generate_stubs and result.missing_coverage:
        _write_stubs(result.missing_coverage, None)


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

    console.print(f"[cyan]Starting API on http://{host}:{port}[/]")
    import uvicorn
    uvicorn.run("api.main:app", host=host, port=port, reload=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_markdown(pr_number, repo, title, result) -> str:
    """Render analysis result as a GitHub PR comment (Markdown)."""
    tier = result.tier.upper()
    score = result.risk_score
    tier_icon = {"HIGH": "🔴", "MED": "🟡", "LOW": "🟢"}.get(tier, "⚪")

    lines = ["## Quality Orchestrator", ""]
    lines.append(f"**Risk:** {tier_icon} {tier} ({score}/100)")
    lines.append(f"> {result.rationale}")
    lines.append("")

    if result.selected_tests:
        lines.append(f"### Tests to Run ({len(result.selected_tests)})")
        lines.append("")
        for t in result.selected_tests:
            lines.append(f"- `{t}`")
        lines.append("")
        run_args = " \\\n  ".join(result.selected_tests)
        lines += [
            "<details>",
            "<summary>Run command</summary>",
            "",
            "```bash",
            f"npx playwright test \\\n  {run_args}",
            "```",
            "</details>",
            "",
        ]
    else:
        lines.append("_No test files mapped. Pass `generate-stubs: true` to scaffold._")
        lines.append("")

    if result.missing_coverage:
        lines.append(f"### Missing Coverage ({len(result.missing_coverage)})")
        lines.append("")
        for m in result.missing_coverage:
            lines.append(f"- `{m}`")
        lines.append("")

    lines.append("<!-- quality-orchestrator -->")
    return "\n".join(lines)


def _print_result(pr_number, repo, title, result) -> None:
    score = result.risk_score
    tier = result.tier
    color = _TIER_COLOR.get(tier, "white")

    bar_len = 24
    filled = round(bar_len * score / 100)
    bar = "#" * filled + "-" * (bar_len - filled)

    # Header panel
    header_parts = []
    if pr_number:
        header_parts.append(f"PR #{pr_number}")
    if repo:
        header_parts.append(repo)
    if title:
        header_parts.append(title)
    header = " | ".join(header_parts) if header_parts else "analysis"

    risk_line = Text()
    risk_line.append(f"  RISK [{bar}] {score}/100 ", style=color)
    risk_line.append(f"({tier.upper()})\n", style=f"bold {color}")
    risk_line.append(f"  {result.rationale}", style="dim")

    console.print()
    console.print(Panel(risk_line, title=f"[cyan]Quality Orchestrator[/] {header}", border_style="cyan"))

    # Selected tests
    if result.selected_tests:
        tbl = Table(box=rbox.SIMPLE, show_header=False, padding=(0, 1))
        tbl.add_column(style="green")
        tbl.add_column()
        for t in result.selected_tests:
            tbl.add_row("[+]", t)
        console.print(Panel(tbl, title="[green]Tests to Run[/]", border_style="green"))
    else:
        console.print("[dim]No tests mapped. Pass --generate-stubs to scaffold.[/]")

    # Coverage gaps
    if result.missing_coverage:
        gap_tbl = Table(box=rbox.SIMPLE, show_header=False, padding=(0, 1))
        gap_tbl.add_column(style=color)
        gap_tbl.add_column()
        for m in result.missing_coverage:
            gap_tbl.add_row("[!]", m)
        console.print(Panel(gap_tbl, title=f"[{color}]Missing Coverage ({len(result.missing_coverage)})[/]", border_style=color))

    # CI run snippet
    if result.selected_tests:
        joined = " \\\n    ".join(result.selected_tests)
        console.print(f"[dim]Run:[/]\n  [dim]npx playwright test \\\n    {joined}[/]\n")


def _write_stubs(missing: list[str], pr_number) -> None:
    from generation.templates import generate_stub

    console.print("[yellow]Generating stubs...[/]")
    for src in missing:
        test_path, content = generate_stub(src, pr_number)
        out = Path(test_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8")
        console.print(f"  [green][+][/] {test_path}")
    console.print()


if __name__ == "__main__":
    app()
