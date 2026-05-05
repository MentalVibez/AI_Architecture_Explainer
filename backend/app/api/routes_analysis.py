from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.models.analysis_job import AnalysisJob
from app.models.repo import Repo
from app.schemas.analyze_request import AnalyzeRequest
from app.schemas.analyze_response import AnalyzeResponse, JobStatusResponse
from app.services.queue_guardian import clear_expired_queued_jobs
from app.utils.github_url import parse_github_url

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/api")
ANALYSIS_POLL_INTERVAL_SECONDS = 2


def _duration_seconds(started_at: datetime | None, ended_at: datetime | None) -> int:
    if not started_at or not ended_at:
        return 0
    started = started_at if started_at.tzinfo else started_at.replace(tzinfo=UTC)
    ended = ended_at if ended_at.tzinfo else ended_at.replace(tzinfo=UTC)
    return max(0, int((ended - started).total_seconds()))


def _phase_label(status: str) -> str:
    return {
        "queued": "queue",
        "running": "analysis",
        "completed": "complete",
        "failed": "failed",
    }.get(status, "unknown")


def _status_detail(status: str, duration_seconds: int) -> str:
    if status == "queued":
        return "Queued and waiting for the analysis worker to start."
    if status == "running":
        if duration_seconds >= 90:
            return (
                "Still running. Larger repositories can take longer while "
                "Atlas finishes evidence collection."
            )
        return "Collecting repository evidence and assembling the Atlas workspace."
    if status == "completed":
        if duration_seconds > 0:
            return f"Completed successfully in about {duration_seconds} seconds."
        return "Completed successfully."
    if status == "failed":
        return "The analysis job failed before the Atlas workspace could be assembled."
    return "Analysis job status is unavailable."


@router.post("/analyze", response_model=AnalyzeResponse)
@limiter.limit("5/minute")
async def create_analysis(
    request: Request,
    body: AnalyzeRequest,
    db: AsyncSession = Depends(get_db),
) -> AnalyzeResponse:
    parsed = parse_github_url(body.repo_url)
    if not parsed:
        raise HTTPException(status_code=422, detail="Could not parse GitHub repo URL")

    owner, repo_name = parsed

    result = await db.execute(select(Repo).where(Repo.github_url == body.repo_url))
    repo = result.scalar_one_or_none()

    if not repo:
        repo = Repo(
            github_owner=owner,
            github_repo=repo_name,
            github_url=body.repo_url,
        )
        db.add(repo)
        await db.flush()

    job = AnalysisJob(repo_id=repo.id, status="queued")
    db.add(job)
    await db.commit()
    await db.refresh(job)

    return AnalyzeResponse(job_id=job.id, status=job.status)


@router.get("/analyze/{job_id}", response_model=JobStatusResponse)
@limiter.limit("30/minute")
async def get_job_status(
    request: Request, job_id: int, db: AsyncSession = Depends(get_db)
) -> JobStatusResponse:
    await clear_expired_queued_jobs(db, settings.worker_queue_guard_seconds)

    result = await db.execute(
        select(AnalysisJob)
        .where(AnalysisJob.id == job_id)
        .options(selectinload(AnalysisJob.result))
    )
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    result_id = job.result.id if job.result else None
    duration_seconds = _duration_seconds(
        job.started_at or job.created_at,
        job.completed_at or datetime.now(UTC),
    )

    return JobStatusResponse(
        job_id=job.id,
        status=job.status,
        phase=_phase_label(job.status),
        status_detail=_status_detail(job.status, duration_seconds),
        result_id=result_id,
        error_message=job.error_message,
        duration_seconds=duration_seconds,
        next_poll_seconds=(
            ANALYSIS_POLL_INTERVAL_SECONDS if job.status in {"queued", "running"} else None
        ),
        created_at=job.created_at,
        completed_at=job.completed_at,
    )
