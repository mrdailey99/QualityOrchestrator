import json
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

# Risk weight per path category (used by both mapping and risk scoring)
CATEGORY_WEIGHTS: dict[str, int] = {
    "payment":    5,
    "security":   5,
    "auth":       4,
    "migrations": 4,
    "migration":  4,
    "middleware": 3,
    "models":     3,
    "model":      3,
    "api":        3,
    "config":     2,
    "lib":        2,
    "utils":      1,
    "util":       1,
    "components": 1,
    "component":  1,
    "tokens":     1,
    "ui":         1,
    "styles":     1,
}

# Leading directories that are not meaningful for test path convention
_SRC_ROOTS = {"src", "app", "lib", "source"}

# Extensions that have testable conventions — everything else (YAML, JSON, MD…) is skipped
_TESTABLE_EXTENSIONS = {"py", "js", "ts", "jsx", "tsx"}


def convention_map(src_file: str) -> Optional[str]:
    """Derive the expected test file path from a source file via naming convention.

    src/api/user.js        → tests/api/user.spec.js
    src/components/Btn.tsx → tests/components/Btn.spec.tsx
    src/utils/format.py    → tests/utils/test_format.py
    """
    path = Path(src_file.replace("\\", "/"))
    parts = path.parts
    stem = path.stem
    suffix = path.suffix.lstrip(".")

    if not suffix:
        return None

    # Strip leading source root (src/, app/, etc.)
    start = 1 if parts and parts[0] in _SRC_ROOTS else 0
    dir_parts = parts[start:-1]

    test_dir = "tests/" + "/".join(dir_parts) if dir_parts else "tests"

    if suffix == "py":
        return f"{test_dir}/test_{stem}.py"
    if suffix in ("js", "ts", "jsx", "tsx"):
        return f"{test_dir}/{stem}.spec.{suffix}"

    return None


def fuzzy_match(src_file: str, test_files: list[str]) -> Optional[tuple[str, float]]:
    """Match a source file to the closest test file by stem similarity (≥0.70 ratio).

    Returns (matched_path, confidence_ratio) or None if no match found.
    """
    basename = Path(src_file).stem.lower()
    best: Optional[str] = None
    best_ratio = 0.0
    for t in test_files:
        t_stem = re.sub(r"[.\-_]?(spec|test)$", "", Path(t).stem.lower(), flags=re.I)
        ratio = SequenceMatcher(None, basename, t_stem).ratio()
        if ratio > best_ratio and ratio >= 0.70:
            best_ratio = ratio
            best = t
    return (best, best_ratio) if best else None


def get_file_category(path: str) -> Optional[str]:
    """Return the first risk category whose name appears as a path segment."""
    normalized = path.lower().replace("\\", "/")
    for cat in CATEGORY_WEIGHTS:
        if f"/{cat}/" in normalized or f"/{cat}." in normalized or normalized.startswith(f"{cat}/"):
            return cat
    return None


def detect_js_runner(repo_root: str = ".") -> str:
    """Detect the JS/TS test runner from project config files or package.json.

    Priority: vitest > jest > playwright (config files first, then package.json).
    Falls back to 'vitest' as the modern default.
    """
    root = Path(repo_root)
    vitest_configs = ["vitest.config.ts", "vitest.config.js", "vitest.config.mts", "vitest.config.mjs"]
    if any((root / f).exists() for f in vitest_configs):
        return "vitest"
    jest_configs = ["jest.config.ts", "jest.config.js", "jest.config.json", "jest.config.cjs", "jest.config.mjs"]
    if any((root / f).exists() for f in jest_configs):
        return "jest"
    playwright_configs = ["playwright.config.ts", "playwright.config.js"]
    if any((root / f).exists() for f in playwright_configs):
        return "playwright"
    pkg_path = root / "package.json"
    if pkg_path.exists():
        try:
            pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
            test_script = pkg.get("scripts", {}).get("test", "")
            for runner in ("vitest", "jest", "playwright"):
                if re.search(r"\b" + runner + r"\b", test_script):
                    return runner
            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
            if "vitest" in deps:
                return "vitest"
            if "jest" in deps or "@jest/core" in deps:
                return "jest"
            if "@playwright/test" in deps:
                return "playwright"
        except Exception:
            pass
    return "vitest"


def is_test_file(path: str) -> bool:
    lower = path.lower().replace("\\", "/")
    name = lower.split("/")[-1]
    return any([
        "spec." in lower,
        "test." in lower,
        lower.startswith("tests/"),
        "/tests/" in lower,
        "/test/" in lower,
        "__tests__" in lower,
        "/spec/" in lower,
        name.startswith("test_"),  # pytest convention: test_foo.py
    ])
