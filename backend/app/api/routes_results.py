from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.analysis_result import AnalysisResult
from app.schemas.onboarding import CodebaseGuideResponse, OnboardingPlanResponse
from app.schemas.result_response import AnalysisResultResponse
from app.services.onboarding_plan import build_codebase_guide, build_onboarding_plan
from app.utils.field_encryption import decrypt_json

router = APIRouter(prefix="/api")

# Analysis results are written once and never mutated — safe to cache aggressively.
_RESULT_CACHE_CONTROL = "public, max-age=3600, stale-while-revalidate=86400"


class RefreshDiagnosticsResponse(BaseModel):
    status: str
    refreshed: bool


@router.get("/results/{result_id}", response_model=AnalysisResultResponse)
async def get_result(
    result_id: int,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> AnalysisResultResponse:
    result = await db.execute(select(AnalysisResult).where(AnalysisResult.id == result_id))
    analysis = result.scalar_one_or_none()

    if not analysis:
        raise HTTPException(status_code=404, detail="Result not found")

    # Decrypt raw_evidence in-place before serialising — the ORM object is
    # not committed here so this mutation is safe and doesn't hit the DB.
    analysis.raw_evidence = decrypt_json(analysis.raw_evidence)

    response.headers["Cache-Control"] = _RESULT_CACHE_CONTROL
    return AnalysisResultResponse.model_validate(analysis)


@router.get("/results/{result_id}/onboarding", response_model=OnboardingPlanResponse)
async def get_onboarding_plan(
    result_id: int,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> OnboardingPlanResponse:
    analysis = await _load_analysis_result(result_id, db)
    response.headers["Cache-Control"] = _RESULT_CACHE_CONTROL
    return build_onboarding_plan(analysis)


@router.get("/results/{result_id}/guide", response_model=CodebaseGuideResponse)
async def get_codebase_guide(
    result_id: int,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> CodebaseGuideResponse:
    analysis = await _load_analysis_result(result_id, db)
    response.headers["Cache-Control"] = _RESULT_CACHE_CONTROL
    return build_codebase_guide(analysis)


@router.post("/results/{result_id}/refresh-diagnostics", response_model=RefreshDiagnosticsResponse)
async def refresh_diagnostics(
    result_id: int,
    db: AsyncSession = Depends(get_db),
) -> RefreshDiagnosticsResponse:
    """Re-run diagnostic tab analysis for a result that is missing setup/debug/change data.

    Safe to call on any result. Returns refreshed=False immediately if all three
    tabs are already populated.
    """
    from app.services.atlas_worker import _has_all_diagnostic_tabs, _populate_diagnostic_tabs

    analysis = await _load_analysis_result(result_id, db)

    if _has_all_diagnostic_tabs(analysis):
        return RefreshDiagnosticsResponse(status="ok", refreshed=False)

    evidence = (analysis.raw_evidence or [{}])[0]
    repo_info = evidence.get("repo", {})
    owner = repo_info.get("owner", "")
    repo = repo_info.get("name", "")
    default_branch = repo_info.get("default_branch") or "HEAD"

    if not owner or not repo:
        raise HTTPException(
            status_code=422,
            detail="Result is missing repo owner/name in raw_evidence — cannot re-run diagnostics.",
        )

    await _populate_diagnostic_tabs(
        job_id=result_id,
        owner=owner,
        repo=repo,
        default_branch=default_branch,
        result=analysis,
        db=db,
    )
    await db.commit()

    return RefreshDiagnosticsResponse(status="ok", refreshed=True)


async def _load_analysis_result(result_id: int, db: AsyncSession) -> AnalysisResult:
    result = await db.execute(select(AnalysisResult).where(AnalysisResult.id == result_id))
    analysis = result.scalar_one_or_none()

    if not analysis:
        raise HTTPException(status_code=404, detail="Result not found")

    return analysis
