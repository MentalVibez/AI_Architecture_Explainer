"""
backend/app/api/routes/review.py

Drop into the existing FastAPI backend alongside analyze.py.
Follows the same job submission → polling → result fetch pattern.
"""
import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, HttpUrl
from sqlalchemy.ext.asyncio import AsyncSession

# These imports are from the existing backend
# from app.core.database import get_db
# from app.models.job import Job, JobStatus
# from app.models.review import Review
# from app.services.reviewer.service import run_review, ReviewError

router = APIRouter(prefix="/api/review", tags=["review"])


class ReviewRequest(BaseModel):
    repo_url: HttpUrl
    branch: str = "main"


class ReviewJobResponse(BaseModel):
    job_id: uuid.UUID
    status: str
    message: str


class ReviewStatusResponse(BaseModel):
    job_id: uuid.UUID
    status: str          # queued | running | completed | failed
    result_id: uuid.UUID | None = None
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


# ── Submit ────────────────────────────────────────────────────────────────────

@router.post("/", response_model=ReviewJobResponse, status_code=202)
async def submit_review(
    req: ReviewRequest,
    background_tasks: BackgroundTasks,
    # db: AsyncSession = Depends(get_db),
):
    """
    Submit a repo for review. Returns job_id immediately.
    Poll /api/review/{job_id} for status.
    """
    # TODO: rate limit check — max 3/day per IP on free tier
    # TODO: repo URL validation (must be public GitHub URL)

    repo_url = str(req.repo_url)

    # Create job record (using existing Job model)
    job = None  # job = Job(type="review", status=JobStatus.QUEUED, meta={"repo_url": repo_url})
    # db.add(job); await db.commit(); await db.refresh(job)

    # Queue the review work
    background_tasks.add_task(_run_review_job, str(job.id) if job else "stub", repo_url, req.branch)

    return ReviewJobResponse(
        job_id=uuid.uuid4(),  # job.id,
        status="queued",
        message="Review job queued. Poll /api/review/{job_id} for status.",
    )


# ── Poll ──────────────────────────────────────────────────────────────────────

@router.get("/{job_id}", response_model=ReviewStatusResponse)
async def poll_review(
    job_id: uuid.UUID,
    # db: AsyncSession = Depends(get_db),
):
    """Poll review job status."""
    # job = await db.get(Job, job_id)
    # if not job or job.type != "review":
    #     raise HTTPException(404, "Review job not found")

    # review = await db.scalar(select(Review).where(Review.job_id == job_id))
    # return ReviewStatusResponse(
    #     job_id=job_id, status=job.status.value,
    #     result_id=review.id if review else None,
    #     error_code=review.error_code if review else None,
    #     error_message=review.error_message if review else None,
    #     created_at=job.created_at, completed_at=review.completed_at if review else None,
    # )
    raise HTTPException(501, "Wire to existing Job model")


# ── Fetch result ──────────────────────────────────────────────────────────────

@router.get("/results/{result_id}")
async def fetch_review_result(
    result_id: uuid.UUID,
    # db: AsyncSession = Depends(get_db),
):
    """Fetch a completed review result."""
    # review = await db.get(Review, result_id)
    # if not review:
    #     raise HTTPException(404, "Review result not found")

    # return {
    #     "result_id": str(result_id),
    #     "repo_url": review.repo_url,
    #     "commit": review.commit,
    #     "overall_score": review.overall_score,
    #     "verdict_label": review.verdict_label,
    #     "production_suitable": review.production_suitable,
    #     "depth_level": review.depth_level,
    #     "confidence_label": review.confidence_label,
    #     "scorecard": review.scorecard_json,
    #     "findings": review.findings_json,
    #     "coverage": review.coverage_json,
    #     "depth": review.depth_json,
    #     "anti_gaming": review.anti_gaming_json,
    #     "summary": review.summary_json,
    #     "meta": review.meta_json,
    # }
    raise HTTPException(501, "Wire to Review model")


# ── Background worker ─────────────────────────────────────────────────────────

async def _run_review_job(job_id: str, repo_url: str, branch: str) -> None:
    """
    Runs in the background. Calls run_review(), stores result.
    All error modes stored as structured error_code + error_message.
    Temp directories are always cleaned up — run_review() handles this.
    """
    # from app.core.database import async_session_factory
    # from app.models.job import Job, JobStatus
    # from app.models.review import Review
    # from app.services.reviewer.service import run_review, ReviewError

    # async with async_session_factory() as db:
    #     job = await db.get(Job, uuid.UUID(job_id))
    #     job.status = JobStatus.RUNNING
    #     await db.commit()
    #
    #     try:
    #         report = await run_review(repo_url=repo_url, branch=branch)
    #         review = Review.from_report(job.id, report, branch=branch)
    #         review.completed_at = datetime.utcnow()
    #         db.add(review)
    #         job.status = JobStatus.COMPLETED
    #         job.result_id = review.id
    #
    #     except ReviewError as e:
    #         review = Review(job_id=job.id, repo_url=repo_url, branch=branch,
    #                         error_code=e.code, error_message=e.message,
    #                         completed_at=datetime.utcnow())
    #         db.add(review)
    #         job.status = JobStatus.FAILED
    #         job.error = f"[{e.code}] {e.message}"
    #
    #     except Exception as e:
    #         job.status = JobStatus.FAILED
    #         job.error = f"[UNEXPECTED] {str(e)[:300]}"
    #
    #     await db.commit()
    pass
