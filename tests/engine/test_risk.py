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
        assert score_with_yaml.total == score_without_yaml.total

    def test_all_covered_files_produce_zero_coverage_component(self):
        score = score_risk(["src/api/user.js"], [])
        score_with_yaml = score_risk(["src/api/user.js", "ci.yml", "README.md"], [])
        assert score.total == score_with_yaml.total

    def test_empty_files_returns_zero(self):
        assert score_risk([], []).total == 0

    def test_breakdown_components_sum_to_total(self):
        bd = score_risk(["src/api/payment/charges.js", "src/lib/fraud.js"], ["src/lib/fraud.js"])
        assert bd.total == min(bd.volume + bd.category + bd.coverage, 100)

    def test_volume_capped_at_20(self):
        # 11 testable files × 2 = 22, capped to 20
        files = [f"src/api/file{i}.js" for i in range(11)]
        bd = score_risk(files, [])
        assert bd.volume == 20

    def test_category_capped_at_50(self):
        bd = score_risk(["src/api/payment/charges.js"], [])
        assert bd.category == 50  # payment weight=5, 5*10=50

    def test_coverage_zero_when_all_mapped(self):
        bd = score_risk(["src/api/user.js"], [])
        assert bd.coverage == 0

    def test_coverage_30_when_all_missing(self):
        bd = score_risk(["src/lib/fraud.js"], ["src/lib/fraud.js"])
        assert bd.coverage == 30


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
