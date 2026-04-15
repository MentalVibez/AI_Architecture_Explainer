"""
Review API routes. Three endpoints:
    POST /api/review/          — submit a repo for review, returns job_id
    GET  /api/review/{job_id}  — poll job status
    GET  /api/review/results/{result_id} — fetch completed report

Current scope: public GitHub repos only.
"""
import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware.rate_limit import check_review_rate_limit
from app.models.review import Review
from app.models.review_job import ReviewJob
from app.services.reviewer.utils.repo_url import normalize_repo_url

router = APIRouter(prefix="/api/review", tags=["review"])
logger = logging.getLogger(__name__)
REVIEW_POLL_INTERVAL_SECONDS = 5
RETRYABLE_ERROR_CODES = {"REVIEW_TIMEOUT", "ENGINE_ERROR", "UNEXPECTED_BACKEND_ERROR"}


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
    phase: str
    status_detail: str
    result_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    duration_seconds: int
    next_poll_seconds: int | None = None
    retryable: bool | None = None
    suggested_action: str | None = None
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


def _utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _build_review_status_response(job: ReviewJob, review: Review | None) -> ReviewStatusResponse:
    duration_seconds = _duration_seconds(job.created_at, job.completed_at or _utcnow_naive())
    error_code = review.error_code if review and review.error_code else job.error_code
    error_message = review.error_message if review and review.error_message else job.error_message

    return ReviewStatusResponse(
        job_id=str(job.id),
        status=job.status,
        phase=_phase_label(job.status),
        status_detail=_status_detail(job.status, error_code, duration_seconds),
        result_id=str(review.id) if review else None,
        error_code=error_code,
        error_message=error_message,
        duration_seconds=duration_seconds,
        next_poll_seconds=(
            REVIEW_POLL_INTERVAL_SECONDS
            if job.status in {"queued", "running"}
            else None
        ),
        retryable=_is_retryable(job.status, error_code),
        suggested_action=_suggested_action(job.status, error_code),
        created_at=job.created_at,
        completed_at=job.completed_at,
    )


def _duration_seconds(started_at: datetime | None, ended_at: datetime | None) -> int:
    if not started_at or not ended_at:
        return 0
    return max(0, int((ended_at - started_at).total_seconds()))


def _phase_label(status: str) -> str:
    return {
        "queued": "queue",
        "running": "analysis",
        "completed": "complete",
        "failed": "failed",
    }.get(status, "unknown")


def _status_detail(status: str, error_code: str | None, duration_seconds: int) -> str:
    if status == "queued":
        return "Queued and waiting for an available worker."
    if status == "running":
        if duration_seconds >= 90:
            return "Still running. Larger repositories and tool-heavy scans can take longer."
        return "Cloning the repository, running adapters, and building the scorecard."
    if status == "completed":
        if duration_seconds > 0:
            return f"Completed successfully in about {duration_seconds} seconds."
        return "Completed successfully."
    if status == "failed":
        return {
            "INVALID_URL": (
                "The repository URL could not be normalized as a supported "
                "public GitHub repository."
            ),
            "CLONE_FAILED": (
                "The repository could not be cloned. It may be private, "
                "missing, or temporarily unavailable."
            ),
            "REPO_TOO_LARGE": (
                "The repository exceeded the current review size limits "
                "for this public service."
            ),
            "REVIEW_TIMEOUT": (
                "The review exceeded the time budget before the report "
                "could be completed."
            ),
        }.get(
            error_code or "",
            "The review job failed before a report could be completed.",
        )
    return "Review job status is unavailable."


def _is_retryable(status: str, error_code: str | None) -> bool | None:
    if status != "failed":
        return None
    return error_code in RETRYABLE_ERROR_CODES


def _suggested_action(status: str, error_code: str | None) -> str | None:
    if status in {"queued", "running"}:
        return "Keep polling until the report is ready."
    if status != "failed":
        return None
    if error_code == "INVALID_URL":
        return "Check the GitHub URL format and submit the review again."
    if error_code == "CLONE_FAILED":
        return "Verify that the repository is public and reachable, then retry."
    if error_code == "REPO_TOO_LARGE":
        return "Use Atlas or Map first, or try a smaller repository."
    if error_code in RETRYABLE_ERROR_CODES:
        return "Retry the review in a moment. If it keeps failing, inspect backend logs."
    return "Inspect the backend logs before retrying."


# ── POST /api/review/ ─────────────────────────────────────────────────────────

@router.post("/", response_model=ReviewJobResponse, status_code=202)
async def submit_review(
    req: ReviewRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Submit a public GitHub repo for review. Returns job_id immediately."""
    await check_review_rate_limit(request)

    canonical_url, branch = _validate_and_normalize(req.repo_url, req.branch)

    job = ReviewJob(
        repo_url=canonical_url,
        branch=branch,
        commit=req.commit,
        status="queued",
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

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
    return _build_review_status_response(job, review)


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
        "duration_seconds": _duration_seconds(review.created_at, review.completed_at),
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
