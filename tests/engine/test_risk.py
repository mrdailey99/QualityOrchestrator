"""Tests for engine/risk.py — risk scoring and tier classification."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from engine.risk import risk_tier, score_risk


class TestScoreRisk:
    def test_yaml_files_excluded_from_coverage_denominator(self):
        # fraud.js is the only testable file and has no coverage.
        # action.yml must not dilute the denominator from 1 to 2.
        score_with_yaml = score_risk(
            ["src/lib/fraud.js", "action.yml"],
            ["src/lib/fraud.js"],
        )
        score_without_yaml = score_risk(
            ["src/lib/fraud.js"],
            ["src/lib/fraud.js"],
        )
        assert score_with_yaml == score_without_yaml

    def test_all_covered_files_produce_zero_coverage_component(self):
        score = score_risk(["src/api/user.js"], [])
        score_with_yaml = score_risk(["src/api/user.js", "ci.yml", "README.md"], [])
        assert score == score_with_yaml

    def test_empty_files_returns_zero(self):
        assert score_risk([], []) == 0


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
