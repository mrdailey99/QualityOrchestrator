from typing import Optional


def score_risk(
    files_changed: list[str],
    missing_coverage: list[str],
    diff: Optional[str] = None,
) -> int:
    """Compute a 0–100 risk score for a PR.

    Three additive components, each capped:
      - Volume    (0–20): scales with number of changed files
      - Category  (0–50): driven by the highest-weight risk path (payment, auth, etc.)
      - Coverage  (0–30): fraction of changed files with no test mapped
    """
    from engine.mapping import get_file_category, is_test_file, CATEGORY_WEIGHTS

    if not files_changed:
        return 0

    # 1. Volume
    volume = min(len(files_changed) * 2, 20)

    # 2. Category — find the single highest-weight category across all changed files
    max_weight = 0
    for f in files_changed:
        cat = get_file_category(f)
        if cat:
            max_weight = max(max_weight, CATEGORY_WEIGHTS.get(cat, 1))
    category = min(max_weight * 10, 50)

    # 3. Missing coverage ratio
    non_test = [f for f in files_changed if not is_test_file(f)]
    if non_test:
        ratio = len(missing_coverage) / len(non_test)
        coverage = int(ratio * 30)
    else:
        coverage = 0

    return min(volume + category + coverage, 100)


def risk_tier(score: int) -> str:
    if score >= 70:
        return "high"
    if score >= 40:
        return "med"
    return "low"
