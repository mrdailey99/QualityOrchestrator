from dataclasses import dataclass, field
from typing import Optional

from engine.mapping import convention_map, fuzzy_match, get_file_category, is_test_file
from engine.risk import score_risk, risk_tier


@dataclass
class FileMappingEntry:
    src: str
    test: Optional[str]
    reason: Optional[str] = None
    confidence: Optional[float] = None


@dataclass
class AnalysisResult:
    selected_tests: list[str]
    missing_coverage: list[str]
    risk_score: int
    tier: str
    rationale: str
    mapping: list[FileMappingEntry] = field(default_factory=list)


class DecisionEngine:
    def analyze(
        self,
        files_changed: list[str],
        diff: Optional[str] = None,
        repo: Optional[str] = None,
        known_test_files: Optional[list[str]] = None,
    ) -> AnalysisResult:
        selected: list[str] = []
        missing: list[str] = []
        mapping: list[FileMappingEntry] = []

        test_files_set = set(known_test_files) if known_test_files else None

        for src in files_changed:
            if is_test_file(src):
                continue

            convention = convention_map(src)
            reason: Optional[str] = None
            test_file: Optional[str] = None
            confidence: Optional[float] = None

            if test_files_set is not None:
                # Validate the convention path actually exists
                if convention and convention in test_files_set:
                    test_file = convention
                    reason = "convention"
                else:
                    # Try fuzzy match against known files
                    fuzzy_result = fuzzy_match(src, known_test_files)
                    if fuzzy_result:
                        test_file, confidence = fuzzy_result
                        reason = "fuzzy match"
            else:
                # No known_test_files: trust convention mapping
                test_file = convention
                if test_file:
                    reason = "convention"

            if test_file:
                cat = get_file_category(src)
                reason = reason or (cat if cat else "convention")
                selected.append(test_file)
                mapping.append(FileMappingEntry(src=src, test=test_file, reason=reason, confidence=confidence))
            else:
                missing.append(src)
                # Still record where the test should live
                mapping.append(FileMappingEntry(src=src, test=convention, reason="missing"))

        # Deduplicate preserving order
        seen: set[str] = set()
        unique_tests: list[str] = []
        for t in selected:
            if t not in seen:
                seen.add(t)
                unique_tests.append(t)

        score = score_risk(files_changed, missing, diff)
        tier = risk_tier(score)
        rationale = self._rationale(files_changed, missing, score, tier)

        return AnalysisResult(
            selected_tests=unique_tests,
            missing_coverage=missing,
            risk_score=score,
            tier=tier,
            rationale=rationale,
            mapping=mapping,
        )

    def _rationale(
        self,
        files: list[str],
        missing: list[str],
        score: int,
        tier: str,
    ) -> str:
        categories: set[str] = set()
        for f in files:
            cat = get_file_category(f)
            if cat:
                categories.add(cat)

        label = tier.upper()
        parts = [f"{label} risk ({score}/100)."]
        if categories:
            parts.append(f"Touches: {', '.join(sorted(categories))}.")
        if missing:
            parts.append(f"{len(missing)} file(s) with no test coverage detected.")
        else:
            parts.append("All changed files have mapped tests.")
        return " ".join(parts)
