"""Tests for engine/mapping.py — convention_map, fuzzy_match, and discovery helpers."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from engine.mapping import convention_map, detect_js_runner, fuzzy_match, get_file_category, is_test_file


# ---------------------------------------------------------------------------
# Unit: convention_map
# ---------------------------------------------------------------------------

class TestConventionMap:
    def test_js_src_api(self):
        assert convention_map("src/api/user.js") == "tests/api/user.spec.js"

    def test_jsx_component(self):
        assert convention_map("src/components/Button.jsx") == "tests/components/Button.spec.jsx"

    def test_nested_js(self):
        assert convention_map("src/api/payment/charges.js") == "tests/api/payment/charges.spec.js"

    def test_python_file(self):
        assert convention_map("src/api/user.py") == "tests/api/test_user.py"

    def test_no_src_prefix(self):
        assert convention_map("api/user.js") == "tests/api/user.spec.js"

    def test_unknown_extension_returns_none(self):
        assert convention_map("src/api/schema.graphql") is None


# ---------------------------------------------------------------------------
# Unit: get_file_category
# ---------------------------------------------------------------------------

class TestGetFileCategory:
    def test_payment_path(self):
        assert get_file_category("src/api/payment/charges.js") == "payment"

    def test_auth_path(self):
        assert get_file_category("src/api/middleware/auth.js") == "auth"

    def test_components_path(self):
        assert get_file_category("src/components/Button.jsx") == "components"

    def test_unknown_path_returns_none(self):
        assert get_file_category("src/foo/bar.js") is None


# ---------------------------------------------------------------------------
# Unit: is_test_file
# ---------------------------------------------------------------------------

class TestIsTestFile:
    def test_spec_file(self):
        assert is_test_file("tests/api/user.spec.js") is True

    def test_test_file(self):
        assert is_test_file("tests/api/user.test.js") is True

    def test_pytest_file(self):
        assert is_test_file("tests/test_user.py") is True

    def test_source_file(self):
        assert is_test_file("src/api/user.js") is False

    def test_test_directory_segment(self):
        assert is_test_file("src/test/user.js") is True

    def test_spec_directory_segment(self):
        assert is_test_file("src/spec/user.js") is True

    def test_jest_tests_directory(self):
        assert is_test_file("src/__tests__/user.js") is True

    def test_pytest_prefix_without_tests_dir(self):
        assert is_test_file("test_utils.py") is True


# ---------------------------------------------------------------------------
# Unit: fuzzy_match
# ---------------------------------------------------------------------------

class TestFuzzyMatch:
    _TEST_FILES = [
        "tests/api/user.spec.js",
        "tests/lib/fraud.spec.js",
        "tests/utils/hash.spec.js",
    ]

    def test_returns_tuple_on_match(self):
        result = fuzzy_match("src/api/user.js", self._TEST_FILES)
        assert result is not None
        path, ratio = result
        assert path == "tests/api/user.spec.js"
        assert isinstance(ratio, float)
        assert ratio >= 0.70

    def test_returns_none_on_empty_list(self):
        assert fuzzy_match("src/api/user.js", []) is None

    def test_returns_none_below_threshold(self):
        assert fuzzy_match("src/zzz_totally_different.js", ["tests/abc.spec.js"]) is None

    def test_matches_closest_stem(self):
        result = fuzzy_match("src/lib/fraud.js", self._TEST_FILES)
        assert result is not None
        path, _ = result
        assert path == "tests/lib/fraud.spec.js"

    def test_confidence_stored_in_mapping(self, engine):
        # src/api/users.js → convention: tests/api/users.spec.js (absent from list)
        # fuzzy matching finds tests/api/user.spec.js at ~0.89 stem similarity
        test_files = ["tests/api/user.spec.js"]
        result = engine.analyze(["src/api/users.js"], known_test_files=test_files)
        fuzzy_entry = next((m for m in result.mapping if m.reason == "fuzzy match"), None)
        assert fuzzy_entry is not None, "Expected fuzzy match; convention path absent so fuzzy should activate"
        assert fuzzy_entry.confidence is not None
        assert 0.0 < fuzzy_entry.confidence <= 1.0


# ---------------------------------------------------------------------------
# Unit: list-tests discovery
# ---------------------------------------------------------------------------

class TestListTestsDiscovery:
    def test_filters_out_source_files(self):
        files = ["src/api/user.js", "src/lib/fraud.js", "README.md"]
        assert [f for f in files if is_test_file(f)] == []

    def test_discovers_spec_files(self):
        files = ["tests/api/user.spec.js", "src/api/user.js"]
        discovered = [f for f in files if is_test_file(f)]
        assert "tests/api/user.spec.js" in discovered
        assert "src/api/user.js" not in discovered

    def test_discovers_pytest_files(self):
        files = ["tests/test_user.py", "tests/test_auth.py", "src/user.py"]
        discovered = [f for f in files if is_test_file(f)]
        assert len(discovered) == 2

    def test_mixed_repo_discovers_all_test_types(self):
        files = [
            "tests/api/user.spec.js",
            "tests/engine/test_decision.py",
            "src/__tests__/Button.test.tsx",
            "src/api/user.js",
            "src/engine.py",
        ]
        assert len([f for f in files if is_test_file(f)]) == 3


# ---------------------------------------------------------------------------
# Unit: detect_js_runner
# ---------------------------------------------------------------------------

class TestDetectJsRunner:
    def test_returns_vitest_when_vitest_config_ts_present(self, tmp_path):
        (tmp_path / "vitest.config.ts").write_text("export default {};")
        assert detect_js_runner(str(tmp_path)) == "vitest"

    def test_returns_vitest_when_vitest_config_js_present(self, tmp_path):
        (tmp_path / "vitest.config.js").write_text("module.exports = {};")
        assert detect_js_runner(str(tmp_path)) == "vitest"

    def test_returns_vitest_when_vitest_config_mts_present(self, tmp_path):
        (tmp_path / "vitest.config.mts").write_text("export default {};")
        assert detect_js_runner(str(tmp_path)) == "vitest"

    def test_returns_jest_when_jest_config_ts_present(self, tmp_path):
        (tmp_path / "jest.config.ts").write_text("export default {};")
        assert detect_js_runner(str(tmp_path)) == "jest"

    def test_returns_jest_when_jest_config_js_present(self, tmp_path):
        (tmp_path / "jest.config.js").write_text("module.exports = {};")
        assert detect_js_runner(str(tmp_path)) == "jest"

    def test_vitest_config_takes_priority_over_jest_config(self, tmp_path):
        (tmp_path / "vitest.config.ts").write_text("export default {};")
        (tmp_path / "jest.config.ts").write_text("module.exports = {};")
        assert detect_js_runner(str(tmp_path)) == "vitest"

    def test_returns_playwright_when_playwright_config_ts_present(self, tmp_path):
        (tmp_path / "playwright.config.ts").write_text("export default {};")
        assert detect_js_runner(str(tmp_path)) == "playwright"

    def test_returns_playwright_when_playwright_config_js_present(self, tmp_path):
        (tmp_path / "playwright.config.js").write_text("module.exports = {};")
        assert detect_js_runner(str(tmp_path)) == "playwright"

    def test_jest_config_takes_priority_over_playwright_config(self, tmp_path):
        (tmp_path / "jest.config.js").write_text("module.exports = {};")
        (tmp_path / "playwright.config.ts").write_text("export default {};")
        assert detect_js_runner(str(tmp_path)) == "jest"

    def test_detects_vitest_from_package_json_test_script(self, tmp_path):
        pkg = {"scripts": {"test": "vitest run"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        assert detect_js_runner(str(tmp_path)) == "vitest"

    def test_detects_jest_from_package_json_test_script(self, tmp_path):
        pkg = {"scripts": {"test": "jest --coverage"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        assert detect_js_runner(str(tmp_path)) == "jest"

    def test_detects_playwright_from_package_json_test_script(self, tmp_path):
        pkg = {"scripts": {"test": "playwright test"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        assert detect_js_runner(str(tmp_path)) == "playwright"

    def test_detects_vitest_from_package_json_deps(self, tmp_path):
        pkg = {"devDependencies": {"vitest": "^1.0.0"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        assert detect_js_runner(str(tmp_path)) == "vitest"

    def test_detects_jest_from_package_json_deps(self, tmp_path):
        pkg = {"devDependencies": {"jest": "^29.0.0"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        assert detect_js_runner(str(tmp_path)) == "jest"

    def test_detects_playwright_from_package_json_deps(self, tmp_path):
        pkg = {"devDependencies": {"@playwright/test": "^1.40.0"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        assert detect_js_runner(str(tmp_path)) == "playwright"

    def test_vitest_dep_takes_priority_over_playwright_dep(self, tmp_path):
        pkg = {"devDependencies": {"vitest": "^1.0.0", "@playwright/test": "^1.40.0"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        assert detect_js_runner(str(tmp_path)) == "vitest"

    def test_falls_back_to_vitest_when_no_config_found(self, tmp_path):
        # empty directory — no config files, no package.json
        assert detect_js_runner(str(tmp_path)) == "vitest"

    def test_falls_back_to_vitest_on_malformed_package_json(self, tmp_path):
        (tmp_path / "package.json").write_text("not valid json {{{{")
        assert detect_js_runner(str(tmp_path)) == "vitest"

    def test_falls_back_to_vitest_when_package_json_has_no_scripts_or_deps(self, tmp_path):
        pkg = {"name": "my-app", "version": "1.0.0"}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        assert detect_js_runner(str(tmp_path)) == "vitest"

    def test_returns_playwright_when_playwright_config_mjs_present(self, tmp_path):
        (tmp_path / "playwright.config.mjs").write_text("export default {};")
        assert detect_js_runner(str(tmp_path)) == "playwright"

    def test_returns_playwright_when_playwright_config_cjs_present(self, tmp_path):
        (tmp_path / "playwright.config.cjs").write_text("module.exports = {};")
        assert detect_js_runner(str(tmp_path)) == "playwright"
