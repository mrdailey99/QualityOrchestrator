"""Tests for engine/decision.py — risk scenarios and DecisionEngine integration."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from engine.decision import DecisionEngine


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
        assert len(result.selected_tests) == 1
