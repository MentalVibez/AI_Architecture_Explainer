from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.analysis_result import AnalysisResult
from app.schemas.result_response import AnalysisResultResponse

router = APIRouter(prefix="/api")


@router.get("/results/{result_id}", response_model=AnalysisResultResponse)
async def get_result(result_id: int, db: AsyncSession = Depends(get_db)) -> AnalysisResultResponse:
    result = await db.execute(select(AnalysisResult).where(AnalysisResult.id == result_id))
    analysis = result.scalar_one_or_none()

    if not analysis:
        raise HTTPException(status_code=404, detail="Result not found")

    return AnalysisResultResponse.model_validate(analysis)
