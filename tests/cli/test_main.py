"""Tests for cli/main.py — markdown rendering and stub truncation."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pytest
from cli.main import _format_markdown, _truncate_stub


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
# Markdown output (D11)
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

    def test_lists_mapped_tests(self, engine):
        result = engine.analyze(["src/api/user.js"])
        md = _format_markdown(1, "owner/repo", "Test PR", result)
        assert "tests/api/user.spec.js" in md

    def test_shows_risk_tier(self, engine):
        result = engine.analyze(["src/api/payment/charges.js"])
        md = _format_markdown(1, "owner/repo", "Test PR", result)
        assert any(tier in md for tier in ("HIGH", "MED", "LOW"))

    def test_shows_missing_coverage(self, engine):
        result = engine.analyze(
            ["src/api/user.js", "src/lib/new_module.js"],
            known_test_files=["tests/api/user.spec.js"],
        )
        md = _format_markdown(1, "owner/repo", "Test PR", result)
        assert "Missing Coverage" in md
        assert "src/lib/new_module.js" in md

    def test_yaml_files_excluded_from_missing_coverage(self, engine):
        result = engine.analyze(
            ["src/api/user.js", "action.yml", ".github/workflows/ci.yml"],
            known_test_files=["tests/api/user.spec.js"],
        )
        md = _format_markdown(1, "owner/repo", "Test PR", result)
        assert "action.yml" not in md
        assert "ci.yml" not in md


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
