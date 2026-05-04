"""Tests for cli/main.py — markdown rendering and stub truncation."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from cli.main import _format_markdown, _md_path, _run_command, _truncate_stub


# ---------------------------------------------------------------------------
# Unit: _run_command
# ---------------------------------------------------------------------------

class TestRunCommand:
    def test_python_only_uses_pytest(self):
        cmd = _run_command(["tests/engine/test_decision.py", "tests/engine/test_mapping.py"])
        assert cmd.startswith("pytest")
        assert "npx" not in cmd

    def test_js_only_uses_playwright(self):
        cmd = _run_command(["tests/api/user.spec.js", "tests/lib/fraud.spec.js"])
        assert cmd.startswith("npx playwright test")
        assert "pytest" not in cmd

    def test_mixed_emits_both_commands(self):
        cmd = _run_command(["tests/engine/test_decision.py", "tests/api/user.spec.js"])
        assert "pytest" in cmd
        assert "npx playwright test" in cmd

    def test_single_py_file(self):
        cmd = _run_command(["tests/engine/test_risk.py"])
        assert "pytest" in cmd
        assert "tests/engine/test_risk.py" in cmd

    def test_single_js_file(self):
        cmd = _run_command(["tests/api/user.spec.js"])
        assert "npx playwright test" in cmd
        assert "tests/api/user.spec.js" in cmd


# ---------------------------------------------------------------------------
# Unit: _md_path — markdown injection defence
# ---------------------------------------------------------------------------

class TestMdPath:
    def test_clean_path_unchanged(self):
        assert _md_path("tests/api/user.spec.js") == "tests/api/user.spec.js"

    def test_backtick_escaped(self):
        assert _md_path("tests/api/use`r.spec.js") == "tests/api/use&#96;r.spec.js"

    def test_triple_backtick_escaped(self):
        result = _md_path("tests/api/```evil.spec.js")
        assert "```" not in result

    def test_multiple_backticks_all_escaped(self):
        result = _md_path("a`b`c")
        assert result == "a&#96;b&#96;c"


# ---------------------------------------------------------------------------
# Stub truncation (T3)
# ---------------------------------------------------------------------------

class TestStubTruncation:
    def test_short_stub_unchanged(self):
        content = "\n".join(f"line {i}" for i in range(10))
        assert _truncate_stub(content, "tests/foo.py") == content

    def test_long_stub_truncated_at_50(self):
        content = "\n".join(f"line {i}" for i in range(100))
        result = _truncate_stub(content, "tests/foo.py")
        assert len(result.splitlines()) == 51  # 50 lines + truncation notice
        assert "truncated" in result
        assert "tests/foo.py" in result

    def test_exactly_50_lines_unchanged(self):
        content = "\n".join(f"line {i}" for i in range(50))
        assert _truncate_stub(content, "tests/foo.py") == content

    def test_python_truncation_uses_hash_comment(self):
        content = "\n".join(f"line {i}" for i in range(60))
        result = _truncate_stub(content, "tests/api/payment.py")
        assert result.endswith("# ... truncated — full stub at tests/api/payment.py")

    def test_js_truncation_uses_slash_comment(self):
        content = "\n".join(f"line {i}" for i in range(60))
        result = _truncate_stub(content, "tests/api/user.spec.js")
        assert result.endswith("// ... truncated — full stub at tests/api/user.spec.js")

    def test_ts_truncation_uses_slash_comment(self):
        content = "\n".join(f"line {i}" for i in range(60))
        result = _truncate_stub(content, "tests/Button.spec.tsx")
        assert result.endswith("// ... truncated — full stub at tests/Button.spec.tsx")


# ---------------------------------------------------------------------------
# Markdown output
# ---------------------------------------------------------------------------

class TestMarkdownOutput:
    def test_contains_header(self, engine):
        result = engine.analyze(["src/api/user.js"])
        md = _format_markdown(1, "owner/repo", "Test PR", result)
        assert "## Quality Orchestrator" in md

    def test_contains_dedup_marker(self, engine):
        result = engine.analyze(["src/api/user.js"])
        md = _format_markdown(1, "owner/repo", "Test PR", result)
        assert "<!-- quality-orchestrator -->" in md

    def test_lists_mapped_tests_as_checkboxes(self, engine):
        result = engine.analyze(["src/api/user.js"])
        md = _format_markdown(1, "owner/repo", "Test PR", result)
        assert "tests/api/user.spec.js" in md
        assert "- [x]" in md

    def test_shows_risk_tier(self, engine):
        result = engine.analyze(["src/api/payment/charges.js"])
        md = _format_markdown(1, "owner/repo", "Test PR", result)
        assert any(tier in md for tier in ("HIGH", "MED", "LOW"))

    def test_risk_score_displayed(self, engine):
        result = engine.analyze(["src/api/user.js"])
        md = _format_markdown(1, "owner/repo", "Test PR", result)
        assert str(result.risk_score) in md

    def test_hero_line_does_not_repeat_score(self, engine):
        result = engine.analyze(["src/api/user.js"])
        md = _format_markdown(1, "owner/repo", "Test PR", result)
        hero_line = [l for l in md.splitlines() if "/ 100" in l][0]
        # score should appear once (in the bold badge), not twice
        assert hero_line.count(str(result.risk_score)) == 1

    def test_backtick_in_path_is_escaped(self, engine):
        result = engine.analyze(["src/api/user.js"])
        # Manually inject a backtick path into the result to test sanitization
        result.selected_tests = ["tests/api/use`r.spec.js"]
        md = _format_markdown(1, "owner/repo", "Test PR", result)
        assert "use`r" not in md
        assert "&#96;" in md

    def test_backtick_in_missing_path_is_escaped(self, engine):
        result = engine.analyze(["src/lib/new_module.js"], known_test_files=[])
        result.missing_coverage = ["src/lib/use`r.js"]
        md = _format_markdown(1, "owner/repo", "Test PR", result)
        assert "use`r" not in md
        assert "&#96;" in md

    def test_shows_missing_coverage(self, engine):
        result = engine.analyze(
            ["src/api/user.js", "src/lib/new_module.js"],
            known_test_files=["tests/api/user.spec.js"],
        )
        md = _format_markdown(1, "owner/repo", "Test PR", result)
        assert "Missing Coverage" in md
        assert "src/lib/new_module.js" in md

    def test_missing_coverage_as_unchecked_boxes(self, engine):
        result = engine.analyze(
            ["src/api/user.js", "src/lib/new_module.js"],
            known_test_files=["tests/api/user.spec.js"],
        )
        md = _format_markdown(1, "owner/repo", "Test PR", result)
        assert "- [ ]" in md

    def test_missing_coverage_suggests_stub_command(self, engine):
        result = engine.analyze(
            ["src/lib/new_module.js"],
            known_test_files=[],
        )
        md = _format_markdown(1, "owner/repo", "Test PR", result)
        assert "@qo stub" in md

    def test_footer_contains_bot_commands(self, engine):
        result = engine.analyze(["src/api/user.js"])
        md = _format_markdown(1, "owner/repo", "Test PR", result)
        assert "@qo" in md

    def test_yaml_files_excluded_from_missing_coverage(self, engine):
        result = engine.analyze(
            ["src/api/user.js", "action.yml", ".github/workflows/ci.yml"],
            known_test_files=["tests/api/user.spec.js"],
        )
        md = _format_markdown(1, "owner/repo", "Test PR", result)
        assert "action.yml" not in md
        assert "ci.yml" not in md

    def test_run_command_uses_pytest_for_python_tests(self, engine):
        result = engine.analyze(["src/api/user.py"])
        md = _format_markdown(1, "owner/repo", "Test PR", result)
        assert "pytest" in md

    def test_run_command_uses_playwright_for_js_tests(self, engine):
        result = engine.analyze(["src/api/user.js"])
        md = _format_markdown(1, "owner/repo", "Test PR", result)
        assert "npx playwright test" in md


class TestMarkdownWithStubs:
    def test_stubs_section_present_when_stubs_passed(self, engine):
        result = engine.analyze(["src/lib/new_module.py"])
        stubs = [("tests/lib/test_new_module.py", "import pytest\n\ndef test_foo():\n    pass\n")]
        md = _format_markdown(1, "owner/repo", "Test PR", result, stubs=stubs)
        assert "Generated Stubs" in md
        assert "tests/lib/test_new_module.py" in md

    def test_no_stubs_section_when_none(self, engine):
        result = engine.analyze(["src/api/user.js"])
        md = _format_markdown(1, "owner/repo", "Test PR", result)
        assert "Generated Stubs" not in md

    def test_stub_content_embedded_in_details(self, engine):
        result = engine.analyze(["src/lib/new_module.py"])
        stubs = [("tests/lib/test_new_module.py", "def test_foo():\n    pass\n")]
        md = _format_markdown(1, "owner/repo", "Test PR", result, stubs=stubs)
        assert "<details>" in md
        assert "def test_foo" in md

    def test_python_stub_uses_python_fence(self, engine):
        result = engine.analyze(["src/lib/new_module.py"])
        stubs = [("tests/lib/test_new_module.py", "import pytest\n")]
        md = _format_markdown(1, "owner/repo", "Test PR", result, stubs=stubs)
        assert "```python" in md

    def test_ts_stub_uses_typescript_fence(self, engine):
        result = engine.analyze(["src/lib/new_module.py"])
        stubs = [("tests/lib/new_module.spec.ts", "import { test } from '@playwright/test';\n")]
        md = _format_markdown(1, "owner/repo", "Test PR", result, stubs=stubs)
        assert "```typescript" in md
