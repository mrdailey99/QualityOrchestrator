from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class RiskBreakdown:
    volume: int
    category: int
    coverage: int
    total: int


def score_risk(
    files_changed: list[str],
    missing_coverage: list[str],
    diff: Optional[str] = None,
) -> RiskBreakdown:
    """Compute a 0–100 risk score and return the full breakdown.

    Three additive components, each capped:
      - Volume    (0–20): scales with number of changed files
      - Category  (0–50): driven by the highest-weight risk path (payment, auth, etc.)
      - Coverage  (0–30): fraction of changed files with no test mapped
    """
    from engine.mapping import get_file_category, is_test_file, CATEGORY_WEIGHTS, _TESTABLE_EXTENSIONS

    if not files_changed:
        return RiskBreakdown(volume=0, category=0, coverage=0, total=0)

    # Score is based on testable source files only — YAML, JSON, MD, etc. are excluded
    # from all three components so infrastructure changes don't inflate risk.
    testable = [
        f for f in files_changed
        if not is_test_file(f)
        and Path(f).suffix.lower().lstrip(".") in _TESTABLE_EXTENSIONS
    ]

    if not testable:
        return RiskBreakdown(volume=0, category=0, coverage=0, total=0)

    # 1. Volume
    volume = min(len(testable) * 2, 20)

    # 2. Category — find the single highest-weight category across all changed files
    max_weight = 0
    for f in testable:
        cat = get_file_category(f)
        if cat:
            max_weight = max(max_weight, CATEGORY_WEIGHTS.get(cat, 1))
    category = min(max_weight * 10, 50)

    # 3. Missing coverage ratio
    ratio = len(missing_coverage) / len(testable)
    coverage = int(ratio * 30)

    total = min(volume + category + coverage, 100)
    return RiskBreakdown(volume=volume, category=category, coverage=coverage, total=total)


def risk_tier(score: int) -> str:
    if score >= 70:
        return "high"
    if score >= 40:
        return "med"
    return "low"
