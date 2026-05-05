"""Tests for developer workflow commands: analyze-staged helpers, install-hooks."""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pytest
import typer
from click.exceptions import Exit as ClickExit

from cli.main import _get_changed_files, _hook_exit, _hook_script, _find_git_dir
from engine.decision import AnalysisResult
from engine.risk import RiskBreakdown


# ---------------------------------------------------------------------------
# _get_changed_files
# ---------------------------------------------------------------------------

class TestGetChangedFiles:
    def test_staged_uses_cached_flag(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="src/api/user.js\n")
            files = _get_changed_files(staged_only=True)
            cmd = mock_run.call_args[0][0]
            assert "--cached" in cmd
            assert files == ["src/api/user.js"]

    def test_all_uses_head(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="src/api/user.js\n")
            _get_changed_files(staged_only=False)
            cmd = mock_run.call_args[0][0]
            assert "HEAD" in cmd
            assert "--cached" not in cmd

    def test_base_uses_triple_dot(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="src/api/user.js\n")
            _get_changed_files(base="main")
            cmd = mock_run.call_args[0][0]
            assert "main...HEAD" in cmd

    def test_git_failure_returns_empty(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=128, stdout="")
            assert _get_changed_files() == []

    def test_exception_returns_empty(self):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            assert _get_changed_files() == []

    def test_empty_output_returns_empty_list(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="\n\n")
            assert _get_changed_files() == []


# ---------------------------------------------------------------------------
# _hook_exit
# ---------------------------------------------------------------------------

def _make_result(tier: str, missing: list[str]) -> AnalysisResult:
    bd = RiskBreakdown(volume=4, category=30, coverage=10 if missing else 0, total=44)
    return AnalysisResult(
        selected_tests=["tests/api/user.spec.js"],
        missing_coverage=missing,
        risk_score=bd.total,
        tier=tier,
        rationale=f"{tier.upper()} risk.",
        score_breakdown=bd,
    )


class TestHookExit:
    def test_high_risk_with_gaps_exits_1(self):
        result = _make_result("high", ["src/lib/fraud.js"])
        with pytest.raises(ClickExit) as exc_info:
            _hook_exit(result)
        assert exc_info.value.exit_code == 1

    def test_high_risk_no_gaps_does_not_exit(self):
        result = _make_result("high", [])
        _hook_exit(result)  # should not raise

    def test_med_risk_with_gaps_does_not_exit(self):
        result = _make_result("med", ["src/lib/fraud.js"])
        _hook_exit(result)  # should not raise

    def test_low_risk_does_not_exit(self):
        result = _make_result("low", [])
        _hook_exit(result)  # should not raise


# ---------------------------------------------------------------------------
# _hook_script
# ---------------------------------------------------------------------------

class TestHookScript:
    def test_pre_push_uses_base(self):
        script = _hook_script("pre-push", "main")
        assert "--base main" in script
        assert "pre-push" in script

    def test_pre_commit_uses_staged(self):
        script = _hook_script("pre-commit", "main")
        assert "--staged" in script
        assert "--base" not in script

    def test_script_has_qo_marker(self):
        script = _hook_script("pre-push", "main")
        assert "quality-orchestrator" in script

    def test_script_has_shebang(self):
        script = _hook_script("pre-push", "main")
        assert script.startswith("#!/usr/bin/env bash")

    def test_script_has_fallback_to_python(self):
        script = _hook_script("pre-push", "main")
        assert "python" in script
        assert "cli/main.py" in script
