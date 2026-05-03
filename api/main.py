import sys
from pathlib import Path

# Allow running from the project root without installation
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional

from engine.decision import DecisionEngine

app = FastAPI(
    title="Quality Orchestrator",
    description="Analyzes GitHub PRs and recommends tests",
    version="0.1.0",
)


class PRAnalysisRequest(BaseModel):
    repo: str
    pr_number: Optional[int] = None
    files_changed: list[str]
    diff: Optional[str] = None
    known_test_files: Optional[list[str]] = None


class FileMappingOut(BaseModel):
    src: str
    test: Optional[str]
    reason: Optional[str] = None


class PRAnalysisResponse(BaseModel):
    repo: Optional[str]
    pr_number: Optional[int]
    risk_score: int
    tier: str
    selected_tests: list[str]
    missing_coverage: list[str]
    rationale: str
    mapping: list[FileMappingOut]


@app.post("/analyze-pr", response_model=PRAnalysisResponse)
async def analyze_pr(request: PRAnalysisRequest) -> PRAnalysisResponse:
    if not request.files_changed:
        raise HTTPException(status_code=422, detail="files_changed must not be empty")

    engine = DecisionEngine()
    result = engine.analyze(
        files_changed=request.files_changed,
        diff=request.diff,
        repo=request.repo,
        known_test_files=request.known_test_files,
    )

    return PRAnalysisResponse(
        repo=request.repo,
        pr_number=request.pr_number,
        risk_score=result.risk_score,
        tier=result.tier,
        selected_tests=result.selected_tests,
        missing_coverage=result.missing_coverage,
        rationale=result.rationale,
        mapping=[
            FileMappingOut(src=m.src, test=m.test, reason=m.reason)
            for m in result.mapping
        ],
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": "0.1.0"}


if __name__ == "__main__":
    import uvicorn
    import os

    uvicorn.run(
        "api.main:app",
        host=os.getenv("QO_HOST", "0.0.0.0"),
        port=int(os.getenv("QO_PORT", "8000")),
        reload=True,
    )
