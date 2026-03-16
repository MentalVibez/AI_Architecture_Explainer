"""
Review API routes. Three routes, no extras.

Wire these imports to your actual models before deploying:
    [ ] from app.models.job import Job
    [ ] from app.models.review import Review
    [ ] from app.core.database import get_db
    [ ] from app.services.review_worker import process_review_job
    [ ] register router in app/main.py
"""
import uuid
import logging
from datetime import datetime
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, HttpUrl
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# from app.core.database import get_db
# from app.models.job import Job
# from app.models.review import Review
# from app.middleware.rate_limit import check_review_rate_limit
# from app.services.review_worker import process_review_job
from app.services.reviewer.utils.repo_url import normalize_repo_url

router = APIRouter(prefix="/api/review", tags=["review"])
logger = logging.getLogger(__name__)

SUPPORTED_HOSTS = {"github.com"}


# ── Schemas ───────────────────────────────────────────────────────────────────

class ReviewRequest(BaseModel):
    repo_url: str
    branch:   str | None = None
    commit:   str | None = None


class ReviewJobResponse(BaseModel):
    job_id:  str
    status:  str
    message: str


class ReviewStatusResponse(BaseModel):
    job_id:        str
    status:        str
    result_id:     str | None = None
    error_code:    str | None = None
    error_message: str | None = None
    created_at:    datetime
    completed_at:  datetime | None = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _validate_and_normalize(repo_url: str, branch: str | None) -> tuple[str, str]:
    """
    Validate URL and normalize. Returns (canonical_url, branch).
    Raises HTTP 400 on invalid input — before any job creation.
    """
    try:
        normalized = normalize_repo_url(repo_url)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "INVALID_URL", "message": str(exc)},
        )
    resolved_branch = branch or "main"
    return normalized.canonical_url, resolved_branch


# ── POST /api/review ──────────────────────────────────────────────────────────

@router.post("/", response_model=ReviewJobResponse, status_code=202)
async def submit_review(
    req: ReviewRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    # db: AsyncSession = Depends(get_db),
):
    """Submit a repo for review. Returns job_id immediately."""
    # 1. Rate limit — before any DB work
    # await check_review_rate_limit(request)

    # 2. Validate + normalize URL — fast, no DB
    canonical_url, branch = _validate_and_normalize(req.repo_url, req.branch)

    # 3. Create job record
    # job = Job(type="review", status="queued",
    #           meta={"repo_url": canonical_url, "branch": branch, "commit": req.commit})
    # db.add(job)
    # await db.commit()
    # await db.refresh(job)
    job_id = str(uuid.uuid4())  # replace with job.id

    # 4. Enqueue background work
    background_tasks.add_task(
        _run_background_review,
        job_id=job_id,
        repo_url=canonical_url,
        branch=branch,
        commit=req.commit,
    )

    logger.info("review_submitted job_id=%s repo=%s branch=%s", job_id, canonical_url, branch)

    return ReviewJobResponse(
        job_id=job_id,
        status="queued",
        message=f"Review job queued. Poll /api/review/{job_id} for status.",
    )


# ── GET /api/review/{job_id} ──────────────────────────────────────────────────

@router.get("/{job_id}", response_model=ReviewStatusResponse)
async def poll_review(
    job_id: str,
    # db: AsyncSession = Depends(get_db),
):
    """Poll review job status."""
    # try:
    #     uid = uuid.UUID(job_id)
    # except ValueError:
    #     raise HTTPException(404, "Invalid job_id format")
    #
    # job = await db.get(Job, uid)
    # if not job or job.meta.get("type") != "review":
    #     raise HTTPException(404, "Review job not found")
    #
    # review = await db.scalar(select(Review).where(Review.job_id == uid))
    #
    # return ReviewStatusResponse(
    #     job_id=str(job.id),
    #     status=job.status,
    #     result_id=str(review.id) if review else None,
    #     error_code=getattr(job, "error_code", None),
    #     error_message=getattr(job, "error_message", None),
    #     created_at=job.created_at,
    #     completed_at=getattr(review, "completed_at", None),
    # )
    raise HTTPException(501, "Wire to existing Job model")


# ── GET /api/results/review/{result_id} ──────────────────────────────────────

@router.get("/results/{result_id}")
async def fetch_review_result(
    result_id: str,
    # db: AsyncSession = Depends(get_db),
):
    """
    Fetch a completed review result.
    Returns the full stored Review artifact.
    """
    # try:
    #     uid = uuid.UUID(result_id)
    # except ValueError:
    #     raise HTTPException(404, "Invalid result_id format")
    #
    # review = await db.get(Review, uid)
    # if not review:
    #     raise HTTPException(404, "Review result not found")
    #
    # return {
    #     "result_id":    str(review.id),
    #     "job_id":       str(review.job_id),
    #     "repo_url":     review.repo_url,
    #     "commit":       review.commit,
    #     "branch":       review.branch,
    #     "created_at":   review.created_at.isoformat(),
    #     "completed_at": review.completed_at.isoformat() if review.completed_at else None,
    #     # Engine metadata
    #     "ruleset_version":  review.ruleset_version,
    #     "depth_level":      review.depth_level,
    #     "confidence_label": review.confidence_label,
    #     # Score summary (fast access without JSONB)
    #     "overall_score":    review.overall_score,
    #     "verdict_label":    review.verdict_label,
    #     "production_suitable": review.production_suitable,
    #     "anti_gaming_verdict": review.anti_gaming_verdict,
    #     "scores": {
    #         "security":            review.security_score,
    #         "testing":             review.testing_score,
    #         "maintainability":     review.maintainability_score,
    #         "reliability":         review.reliability_score,
    #         "operational_readiness": review.operations_score,
    #         "developer_experience":  review.developer_experience_score,
    #     },
    #     # Full payloads
    #     "scorecard":    review.scorecard_json,
    #     "findings":     review.findings_json,
    #     "coverage":     review.coverage_json,
    #     "depth":        review.depth_json,
    #     "anti_gaming":  review.anti_gaming_json,
    #     "summary":      review.summary_json,
    #     "meta":         review.meta_json,
    #     # Error info if applicable
    #     "error_code":    review.error_code,
    #     "error_message": review.error_message,
    # }
    raise HTTPException(501, "Wire to Review model")


# ── Background task wrapper ───────────────────────────────────────────────────

async def _run_background_review(
    job_id: str,
    repo_url: str,
    branch: str,
    commit: str | None,
) -> None:
    """
    Thin wrapper — real logic is in process_review_job().
    This layer owns nothing except getting a DB session and calling the worker.
    """
    # async with async_session_factory() as db:
    #     job = await db.get(Job, uuid.UUID(job_id))
    #     await process_review_job(
    #         job_id=job.id,
    #         repo_url=repo_url,
    #         branch=branch,
    #         commit=commit,
    #         db=db,
    #         job=job,
    #     )
    pass  # remove this line when wired
