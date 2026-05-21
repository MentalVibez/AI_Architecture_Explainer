from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.analysis_result import AnalysisResult
from app.schemas.onboarding import CodebaseGuideResponse, OnboardingPlanResponse
from app.schemas.result_response import AnalysisResultResponse
from app.services.onboarding_plan import build_codebase_guide, build_onboarding_plan

router = APIRouter(prefix="/api")


@router.get("/results/{result_id}", response_model=AnalysisResultResponse)
async def get_result(result_id: int, db: AsyncSession = Depends(get_db)) -> AnalysisResultResponse:
    result = await db.execute(select(AnalysisResult).where(AnalysisResult.id == result_id))
    analysis = result.scalar_one_or_none()

    if not analysis:
        raise HTTPException(status_code=404, detail="Result not found")

    return AnalysisResultResponse.model_validate(analysis)


@router.get("/results/{result_id}/onboarding", response_model=OnboardingPlanResponse)
async def get_onboarding_plan(
    result_id: int,
    db: AsyncSession = Depends(get_db),
) -> OnboardingPlanResponse:
    analysis = await _load_analysis_result(result_id, db)
    return build_onboarding_plan(analysis)


@router.get("/results/{result_id}/guide", response_model=CodebaseGuideResponse)
async def get_codebase_guide(
    result_id: int,
    db: AsyncSession = Depends(get_db),
) -> CodebaseGuideResponse:
    analysis = await _load_analysis_result(result_id, db)
    return build_codebase_guide(analysis)


async def _load_analysis_result(result_id: int, db: AsyncSession) -> AnalysisResult:
    result = await db.execute(select(AnalysisResult).where(AnalysisResult.id == result_id))
    analysis = result.scalar_one_or_none()

    if not analysis:
        raise HTTPException(status_code=404, detail="Result not found")

    return analysis
