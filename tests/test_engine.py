"""Core engine tests — risk scenarios, mapping, and discovery."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.decision import DecisionEngine
from engine.mapping import convention_map, fuzzy_match, get_file_category, is_test_file
from engine.risk import risk_tier, score_risk


# ---------------------------------------------------------------------------
# Scenario: LOW risk — cosmetic token/UI changes
# ---------------------------------------------------------------------------

class TestLowRiskScenario:
    LOW_FILES = [
        "src/components/Button.jsx",
        "src/components/ButtonGroup.jsx",
        "src/tokens/spacing.js",
    ]

    def test_risk_score_is_low(self, engine):
        result = engine.analyze(self.LOW_FILES)
        assert result.risk_score < 40
        assert result.tier == "low"

    def test_all_files_mapped_to_tests(self, engine):
        result = engine.analyze(self.LOW_FILES)
        assert len(result.selected_tests) == 3
        assert len(result.missing_coverage) == 0

    def test_convention_paths(self, engine):
        result = engine.analyze(self.LOW_FILES)
        assert "tests/components/Button.spec.jsx" in result.selected_tests
        assert "tests/tokens/spacing.spec.js" in result.selected_tests


# ---------------------------------------------------------------------------
# Scenario: MED risk — auth middleware caching
# ---------------------------------------------------------------------------

class TestMedRiskScenario:
    MED_FILES = [
        "src/api/middleware/cache.js",
        "src/api/middleware/auth.js",
        "src/api/user.js",
        "src/api/session.js",
        "src/config/redis.js",
        "src/utils/hash.js",
    ]

    def test_risk_score_is_med(self, engine):
        result = engine.analyze(self.MED_FILES)
        assert 40 <= result.risk_score < 70
        assert result.tier == "med"

    def test_all_six_files_mapped(self, engine):
        result = engine.analyze(self.MED_FILES)
        assert len(result.selected_tests) == 6

    def test_auth_category_detected(self, engine):
        result = engine.analyze(self.MED_FILES)
        assert "auth" in result.rationale.lower() or "middleware" in result.rationale.lower()


# ---------------------------------------------------------------------------
# Scenario: HIGH risk — payment path + new files with no tests
# ---------------------------------------------------------------------------

class TestHighRiskScenario:
    HIGH_FILES = [
        "src/api/payment/charges.js",
        "src/lib/fraud.js",
        "src/lib/errors/FraudError.js",
        "src/api/middleware/auth.js",
        "src/api/user.js",
        "src/models/transaction.js",
        "src/config/stripe.js",
        "src/utils/currency.js",
        "src/api/webhooks.js",
    ]
    EXISTING_TESTS = [
        "tests/api/payment/charges.spec.js",
        "tests/api/middleware/auth.spec.js",
        "tests/api/user.spec.js",
        "tests/models/transaction.spec.js",
        "tests/config/stripe.spec.js",
        "tests/utils/currency.spec.js",
        "tests/api/webhooks.spec.js",
    ]

    def test_risk_score_is_high(self, engine):
        result = engine.analyze(self.HIGH_FILES, known_test_files=self.EXISTING_TESTS)
        assert result.risk_score >= 70
        assert result.tier == "high"

    def test_two_new_files_flagged_missing(self, engine):
        result = engine.analyze(self.HIGH_FILES, known_test_files=self.EXISTING_TESTS)
        assert len(result.missing_coverage) == 2
        assert "src/lib/fraud.js" in result.missing_coverage
        assert "src/lib/errors/FraudError.js" in result.missing_coverage

    def test_existing_tests_selected(self, engine):
        result = engine.analyze(self.HIGH_FILES, known_test_files=self.EXISTING_TESTS)
        assert "tests/api/payment/charges.spec.js" in result.selected_tests
        assert "tests/api/middleware/auth.spec.js" in result.selected_tests

    def test_rationale_mentions_payment(self, engine):
        result = engine.analyze(self.HIGH_FILES, known_test_files=self.EXISTING_TESTS)
        assert "payment" in result.rationale.lower()


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
# Unit: risk_tier
# ---------------------------------------------------------------------------

class TestRiskTier:
    def test_high(self):
        assert risk_tier(70) == "high"
        assert risk_tier(100) == "high"

    def test_med(self):
        assert risk_tier(40) == "med"
        assert risk_tier(69) == "med"

    def test_low(self):
        assert risk_tier(0) == "low"
        assert risk_tier(39) == "low"


# ---------------------------------------------------------------------------
# Integration: no known_test_files falls back to convention mapping
# ---------------------------------------------------------------------------

class TestNoKnownTestFiles:
    def test_convention_mode_maps_all(self, engine):
        result = engine.analyze(["src/api/user.js", "src/lib/fraud.js"])
        assert len(result.missing_coverage) == 0
        assert len(result.selected_tests) == 2

    def test_test_files_in_input_are_skipped(self, engine):
        result = engine.analyze([
            "src/api/user.js",
            "tests/api/user.spec.js",  # should be ignored
        ])
        assert len(result.selected_tests) == 1
        assert "src/api/user.js" not in result.selected_tests

    def test_empty_input_returns_zero_risk(self, engine):
        result = engine.analyze([])
        assert result.risk_score == 0

    def test_yaml_files_excluded_from_analysis(self, engine):
        result = engine.analyze(["src/api/user.js", "action.yml", ".github/workflows/ci.yml"])
        assert "action.yml" not in result.missing_coverage
        assert ".github/workflows/ci.yml" not in result.missing_coverage
        assert len(result.selected_tests) == 1  # only user.js maps


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
        test_files = ["tests/api/user.spec.js"]
        result = engine.analyze(["src/api/user.js"], known_test_files=test_files)
        fuzzy_entry = next((m for m in result.mapping if m.reason == "fuzzy match"), None)
        if fuzzy_entry:
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
            "tests/test_engine.py",
            "src/__tests__/Button.test.tsx",
            "src/api/user.js",
            "src/engine.py",
        ]
        assert len([f for f in files if is_test_file(f)]) == 3
