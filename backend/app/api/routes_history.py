from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.analysis_job import AnalysisJob
from app.models.analysis_result import AnalysisResult
from app.models.repo import Repo
from app.models.review import Review
from app.schemas.history_response import RecentRunItemResponse, RecentRunsResponse

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("/runs", response_model=RecentRunsResponse)
async def get_recent_runs(
    limit: int = Query(default=8, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
) -> RecentRunsResponse:
    atlas_limit = min(limit, 12)
    review_limit = min(limit, 12)

    atlas_result = await db.execute(
        select(AnalysisResult)
        .join(AnalysisJob, AnalysisResult.job_id == AnalysisJob.id)
        .join(Repo, AnalysisJob.repo_id == Repo.id)
        .where(AnalysisJob.status == "completed")
        .options(selectinload(AnalysisResult.job).selectinload(AnalysisJob.repo))
        .order_by(AnalysisResult.created_at.desc())
        .limit(atlas_limit)
    )
    atlas_items = [
        RecentRunItemResponse(
            id=str(result.id),
            kind="atlas",
            repo=f"{result.job.repo.github_owner}/{result.job.repo.github_repo}",
            href=f"/results/{result.id}",
            title="Architecture workspace",
            completed_at=result.created_at,
        )
        for result in atlas_result.scalars().all()
        if result.job and result.job.repo
    ]

    review_result = await db.execute(
        select(Review)
        .where(Review.completed_at.is_not(None))
        .order_by(Review.completed_at.desc(), Review.created_at.desc())
        .limit(review_limit)
    )
    review_items = [
        RecentRunItemResponse(
            id=str(review.id),
            kind="review",
            repo=_review_repo_label(review.repo_url),
            href=f"/review?result_id={review.id}&repo={_review_repo_label(review.repo_url)}",
            title=(
                f"{review.verdict_label} review result"
                if review.verdict_label
                else "Review result"
            ),
            completed_at=review.completed_at or review.created_at,
        )
        for review in review_result.scalars().all()
    ]

    items = sorted(
        [*atlas_items, *review_items],
        key=lambda item: item.completed_at or datetime.min,
        reverse=True,
    )[:limit]

    return RecentRunsResponse(items=items)


def _review_repo_label(repo_url: str) -> str:
    trimmed = repo_url.rstrip("/")
    parts = trimmed.split("/")
    if len(parts) >= 2:
        return f"{parts[-2]}/{parts[-1]}"
    return repo_url
