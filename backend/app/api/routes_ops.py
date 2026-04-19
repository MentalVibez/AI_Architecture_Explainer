from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.services.github_service import github_auth_snapshot
from app.models.analysis_job import AnalysisJob
from app.models.review import Review
from app.models.review_job import ReviewJob
from app.schemas.ops_response import (
    ExternalServiceStatusResponse,
    OpsSnapshotResponse,
    QueueMetricsResponse,
    RecentFailureResponse,
)

router = APIRouter(prefix="/api/ops", tags=["ops"])


@router.get("/summary", response_model=OpsSnapshotResponse)
async def get_ops_summary(db: AsyncSession = Depends(get_db)) -> OpsSnapshotResponse:
    now = datetime.now(UTC)
    recent_cutoff = now - timedelta(hours=24)

    atlas_jobs_result = await db.execute(
        select(AnalysisJob).options(selectinload(AnalysisJob.repo))
    )
    atlas_jobs = atlas_jobs_result.scalars().all()

    review_jobs_result = await db.execute(select(ReviewJob))
    review_jobs = review_jobs_result.scalars().all()

    review_results_result = await db.execute(select(Review))
    review_results = review_results_result.scalars().all()
    review_results_by_job = {str(review.job_id): review for review in review_results}

    atlas_metrics = _atlas_metrics(atlas_jobs, recent_cutoff)
    review_metrics = _review_metrics(review_jobs, recent_cutoff)
    recent_failures = _recent_failures(
        atlas_jobs=atlas_jobs,
        review_jobs=review_jobs,
        review_results_by_job=review_results_by_job,
        recent_cutoff=recent_cutoff,
    )
    github = ExternalServiceStatusResponse(**github_auth_snapshot())
    attention_message = _combine_attention_messages(
        _github_attention_message(github),
        _attention_message(atlas_metrics, review_metrics),
    )

    return OpsSnapshotResponse(
        status=_ops_status(atlas_metrics, review_metrics, github),
        attention_message=attention_message,
        github=github,
        atlas=atlas_metrics,
        review=review_metrics,
        recent_failures=recent_failures[:5],
        generated_at=now,
    )


def _atlas_metrics(
    jobs: list[AnalysisJob],
    recent_cutoff: datetime,
) -> QueueMetricsResponse:
    queued = sum(1 for job in jobs if job.status == "queued")
    running = sum(1 for job in jobs if job.status == "running")
    completed_recent = [
        job
        for job in jobs
        if job.status == "completed" and _is_recent(job.completed_at, recent_cutoff)
    ]
    failed_recent = [
        job
        for job in jobs
        if job.status == "failed" and _is_recent(job.completed_at, recent_cutoff)
    ]

    return QueueMetricsResponse(
        queued=queued,
        running=running,
        completed_last_24h=len(completed_recent),
        failed_last_24h=len(failed_recent),
        average_duration_seconds=_average_duration_seconds(completed_recent),
        oldest_queued_seconds=_oldest_age_seconds(
            [job for job in jobs if job.status == "queued"],
            attribute="created_at",
        ),
        oldest_running_seconds=_oldest_age_seconds(
            [job for job in jobs if job.status == "running"],
            attribute="started_at",
        ),
    )


def _review_metrics(
    jobs: list[ReviewJob],
    recent_cutoff: datetime,
) -> QueueMetricsResponse:
    queued = sum(1 for job in jobs if job.status == "queued")
    running = sum(1 for job in jobs if job.status == "running")
    completed_recent = [
        job
        for job in jobs
        if job.status == "completed" and _is_recent(job.completed_at, recent_cutoff)
    ]
    failed_recent = [
        job
        for job in jobs
        if job.status == "failed" and _is_recent(job.completed_at, recent_cutoff)
    ]

    return QueueMetricsResponse(
        queued=queued,
        running=running,
        completed_last_24h=len(completed_recent),
        failed_last_24h=len(failed_recent),
        average_duration_seconds=_average_duration_seconds(completed_recent),
        oldest_queued_seconds=_oldest_age_seconds(
            [job for job in jobs if job.status == "queued"],
            attribute="created_at",
        ),
        oldest_running_seconds=_oldest_age_seconds(
            [job for job in jobs if job.status == "running"],
            attribute="started_at",
        ),
    )


def _recent_failures(
    *,
    atlas_jobs: list[AnalysisJob],
    review_jobs: list[ReviewJob],
    review_results_by_job: dict[str, Review],
    recent_cutoff: datetime,
) -> list[RecentFailureResponse]:
    atlas_failures = [
        RecentFailureResponse(
            kind="atlas",
            repo=_atlas_repo_label(job),
            error_message=job.error_message,
            completed_at=job.completed_at,
        )
        for job in atlas_jobs
        if job.status == "failed" and _is_recent(job.completed_at, recent_cutoff)
    ]

    review_failures = [
        RecentFailureResponse(
            kind="review",
            repo=_review_repo_label(job.repo_url),
            error_message=(
                review_results_by_job.get(str(job.id)).error_message
                if review_results_by_job.get(str(job.id))
                and review_results_by_job.get(str(job.id)).error_message
                else job.error_message
            ),
            completed_at=job.completed_at,
        )
        for job in review_jobs
        if job.status == "failed" and _is_recent(job.completed_at, recent_cutoff)
    ]

    return sorted(
        [*atlas_failures, *review_failures],
        key=lambda item: item.completed_at or datetime.min.replace(tzinfo=UTC),
        reverse=True,
    )


def _average_duration_seconds(jobs: list[AnalysisJob] | list[ReviewJob]) -> int | None:
    durations = [
        int((completed - started).total_seconds())
        for job in jobs
        if (started := _aware_datetime(job.started_at or job.created_at))
        and (completed := _aware_datetime(job.completed_at))
        and completed >= started
    ]
    if not durations:
        return None
    return int(sum(durations) / len(durations))


def _oldest_age_seconds(
    jobs: list[AnalysisJob] | list[ReviewJob],
    *,
    attribute: str,
) -> int | None:
    timestamps = [
        timestamp
        for job in jobs
        if (timestamp := _aware_datetime(getattr(job, attribute, None)))
    ]
    if not timestamps:
        return None
    oldest = min(timestamps)
    return max(0, int((datetime.now(UTC) - oldest).total_seconds()))


def _ops_status(
    atlas: QueueMetricsResponse,
    review: QueueMetricsResponse,
    github: ExternalServiceStatusResponse,
) -> str:
    total_running = atlas.running + review.running
    total_queued = atlas.queued + review.queued
    total_failed = atlas.failed_last_24h + review.failed_last_24h

    if github.status != "ok" or total_failed >= 3 or _attention_message(atlas, review):
        return "watch"
    if total_running > 0 or total_queued > 0:
        return "active"
    return "steady"


def _attention_message(
    atlas: QueueMetricsResponse,
    review: QueueMetricsResponse,
) -> str | None:
    queue_threshold = settings.ops_worker_queue_alert_seconds
    running_threshold = settings.worker_stale_job_seconds

    stuck_queue_names = [
        name
        for name, metrics in (("Atlas", atlas), ("Review", review))
        if metrics.queued > 0
        and metrics.running == 0
        and (metrics.oldest_queued_seconds or 0) >= queue_threshold
    ]
    if stuck_queue_names:
        joined = " and ".join(stuck_queue_names)
        return (
            f"{joined} has queued jobs waiting without an active worker. "
            "Check that the worker service is deployed and healthy."
        )

    slow_queue_names = [
        name
        for name, metrics in (("Atlas", atlas), ("Review", review))
        if (metrics.oldest_running_seconds or 0) >= running_threshold
    ]
    if slow_queue_names:
        joined = " and ".join(slow_queue_names)
        return (
            f"{joined} has a long-running job beyond the stale-job threshold. "
            "Inspect the worker logs before the queue backs up further."
        )

    return None


def _github_attention_message(github: ExternalServiceStatusResponse) -> str | None:
    if github.status in {"ok", "configured"}:
        return None
    return (
        "GitHub API authentication is degraded. "
        f"{github.detail or 'Requests may fall back to public rate limits.'}"
    )


def _combine_attention_messages(*messages: str | None) -> str | None:
    filtered = [message for message in messages if message]
    if not filtered:
        return None
    return " ".join(filtered)


def _atlas_repo_label(job: AnalysisJob) -> str:
    if job.repo:
        return f"{job.repo.github_owner}/{job.repo.github_repo}"
    return f"repo-{job.repo_id}"


def _review_repo_label(repo_url: str) -> str:
    trimmed = repo_url.rstrip("/")
    parts = trimmed.split("/")
    if len(parts) >= 2:
        return f"{parts[-2]}/{parts[-1]}"
    return repo_url


def _is_recent(value: datetime | None, recent_cutoff: datetime) -> bool:
    if not value:
        return False
    return _aware_datetime(value) >= recent_cutoff


def _aware_datetime(value: datetime | None) -> datetime | None:
    if not value:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)
