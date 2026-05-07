"""Tests for generation/templates.py — stub generation and framework detection."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pytest
from generation.templates import generate_stub


# ---------------------------------------------------------------------------
# Stub generation
# ---------------------------------------------------------------------------

class TestStubGeneration:
    def test_js_stub_path(self):
        path, _ = generate_stub("src/lib/fraud.js", pr_number=1442)
        assert path == "tests/lib/fraud.spec.js"

    def test_js_stub_contains_describe(self):
        _, content = generate_stub("src/lib/fraud.js", framework="playwright")
        assert "test.describe" in content
        assert "fraud" in content

    def test_js_stub_contains_pr_note(self):
        _, content = generate_stub("src/lib/fraud.js", pr_number=1442)
        assert "PR #1442" in content

    def test_python_stub_path(self):
        path, _ = generate_stub("src/api/payment.py")
        assert path == "tests/api/test_payment.py"

    def test_python_stub_has_pytest(self):
        _, content = generate_stub("src/api/payment.py")
        assert "import pytest" in content
        assert "def test_payment" in content

    def test_python_stub_uses_skip_not_raises(self):
        _, content = generate_stub("src/api/payment.py")
        assert "pytest.mark.skip" in content
        assert "pytest.raises(Exception):" not in content


# ---------------------------------------------------------------------------
# Per-file framework detection (T4)
# ---------------------------------------------------------------------------

class TestFrameworkDetection:
    def test_auto_python_file_gets_pytest_stub(self):
        path, content = generate_stub("src/api/user.py", framework="auto")
        assert path.endswith(".py")
        assert "import pytest" in content

    def test_auto_js_file_gets_js_stub(self):
        path, content = generate_stub("src/api/user.js", framework="auto")
        assert path.endswith(".js")
        # auto-detection returns a JS stub (not pytest), runner depends on project config
        assert "import pytest" not in content

    def test_force_pytest_on_js_file(self):
        _, content = generate_stub("src/api/user.js", framework="pytest")
        assert "import pytest" in content

    def test_force_playwright_on_py_file(self):
        _, content = generate_stub("src/api/user.py", framework="playwright")
        assert "playwright" in content.lower()

    def test_force_vitest_stub(self):
        _, content = generate_stub("src/api/user.ts", framework="vitest")
        assert "from 'vitest'" in content
        assert "describe" in content

    def test_force_jest_stub(self):
        _, content = generate_stub("src/api/user.ts", framework="jest")
        assert "describe" in content
        assert "it(" in content
        assert "@playwright" not in content

    def test_force_playwright_stub(self):
        _, content = generate_stub("src/api/user.ts", framework="playwright")
        assert "playwright" in content.lower()
        assert "test.describe" in content

    def test_auto_python_file_in_mixed_repo(self):
        _, py_content = generate_stub("src/engine.py", framework="auto")
        assert "import pytest" in py_content

    def test_invalid_framework_raises(self):
        with pytest.raises(ValueError, match="Unknown framework"):
            generate_stub("src/api/user.py", framework="mocha")
