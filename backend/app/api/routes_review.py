"""
Review API routes. Three endpoints:
    POST /api/review/          — submit a repo for review, returns job_id
    GET  /api/review/{job_id}  — poll job status
    GET  /api/review/results/{result_id} — fetch completed report

Beta feature: public GitHub repos only.
"""
import uuid
import logging
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.review import Review
from app.models.review_job import ReviewJob
from app.middleware.rate_limit import check_review_rate_limit
from app.services.review_worker import process_review_job
from app.services.reviewer.utils.repo_url import normalize_repo_url

router = APIRouter(prefix="/api/review", tags=["review"])
logger = logging.getLogger(__name__)


# ── Schemas ───────────────────────────────────────────────────────────────────

class ReviewRequest(BaseModel):
    repo_url: str
    branch: str | None = None
    commit: str | None = None


class ReviewJobResponse(BaseModel):
    job_id: str
    status: str
    message: str


class ReviewStatusResponse(BaseModel):
    job_id: str
    status: str
    result_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _validate_and_normalize(repo_url: str, branch: str | None) -> tuple[str, str]:
    try:
        normalized = normalize_repo_url(repo_url)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "INVALID_URL", "message": str(exc)},
        )
    return normalized.canonical_url, branch or "main"


# ── POST /api/review/ ─────────────────────────────────────────────────────────

@router.post("/", response_model=ReviewJobResponse, status_code=202)
async def submit_review(
    req: ReviewRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Submit a public GitHub repo for review. Returns job_id immediately."""
    await check_review_rate_limit(request)

    canonical_url, branch = _validate_and_normalize(req.repo_url, req.branch)

    job = ReviewJob(repo_url=canonical_url, branch=branch, status="queued")
    db.add(job)
    await db.commit()
    await db.refresh(job)

    background_tasks.add_task(
        _run_background_review,
        job_id=job.id,
        repo_url=canonical_url,
        branch=branch,
        commit=req.commit,
    )

    logger.info("review_submitted job_id=%s repo=%s branch=%s", job.id, canonical_url, branch)

    return ReviewJobResponse(
        job_id=str(job.id),
        status="queued",
        message=f"Review queued. Poll /api/review/{job.id} for status.",
    )


# ── GET /api/review/{job_id} ──────────────────────────────────────────────────

@router.get("/{job_id}", response_model=ReviewStatusResponse)
async def poll_review(
    job_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Poll review job status."""
    try:
        uid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(404, "Invalid job_id format")

    job = await db.get(ReviewJob, uid)
    if not job:
        raise HTTPException(404, "Review job not found")

    review = await db.scalar(select(Review).where(Review.job_id == uid))

    return ReviewStatusResponse(
        job_id=str(job.id),
        status=job.status,
        result_id=str(review.id) if review else None,
        error_code=job.error_code,
        error_message=job.error_message,
        created_at=job.created_at,
        completed_at=job.completed_at,
    )


# ── GET /api/review/results/{result_id} ──────────────────────────────────────

@router.get("/results/{result_id}")
async def fetch_review_result(
    result_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Fetch a completed review report."""
    try:
        uid = uuid.UUID(result_id)
    except ValueError:
        raise HTTPException(404, "Invalid result_id format")

    review = await db.get(Review, uid)
    if not review:
        raise HTTPException(404, "Review result not found")

    return {
        "result_id": str(review.id),
        "job_id": str(review.job_id),
        "repo_url": review.repo_url,
        "commit": review.commit,
        "branch": review.branch,
        "created_at": review.created_at.isoformat(),
        "completed_at": review.completed_at.isoformat() if review.completed_at else None,
        # Engine metadata
        "ruleset_version": review.ruleset_version,
        "depth_level": review.depth_level,
        "confidence_label": review.confidence_label,
        # Score summary
        "overall_score": review.overall_score,
        "verdict_label": review.verdict_label,
        "production_suitable": review.production_suitable,
        "anti_gaming_verdict": review.anti_gaming_verdict,
        "scores": {
            "security": review.security_score,
            "testing": review.testing_score,
            "maintainability": review.maintainability_score,
            "reliability": review.reliability_score,
            "operational_readiness": review.operations_score,
            "developer_experience": review.developer_experience_score,
        },
        # Full payloads
        "scorecard": review.scorecard_json,
        "findings": review.findings_json,
        "coverage": review.coverage_json,
        "depth": review.depth_json,
        "anti_gaming": review.anti_gaming_json,
        "summary": review.summary_json,
        "meta": review.meta_json,
        # Error info if applicable
        "error_code": review.error_code,
        "error_message": review.error_message,
    }


# ── Background task wrapper ───────────────────────────────────────────────────

async def _run_background_review(
    job_id: uuid.UUID,
    repo_url: str,
    branch: str,
    commit: str | None,
) -> None:
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        job = await db.get(ReviewJob, job_id)
        await process_review_job(
            job_id=job_id,
            repo_url=repo_url,
            branch=branch,
            commit=commit,
            db=db,
            job=job,
        )
