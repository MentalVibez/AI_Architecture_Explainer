from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis_job import AnalysisJob
from app.models.review_job import ReviewJob

ATLAS_NO_WORKER_MESSAGE = (
    "No active Atlas worker claimed this job within the queue time budget. "
    "The worker service may be stopped, unhealthy, or pointed at a different database."
)
ATLAS_CAPACITY_MESSAGE = (
    "Atlas queue capacity was saturated and this job waited longer than the queue time budget."
)
REVIEW_NO_WORKER_MESSAGE = (
    "No active Review worker claimed this job within the queue time budget. "
    "The worker service may be stopped, unhealthy, or pointed at a different database."
)
REVIEW_CAPACITY_MESSAGE = (
    "Review queue capacity was saturated and this job waited longer than the queue time budget."
)


@dataclass(slots=True)
class QueueGuardSummary:
    atlas_cleared: int = 0
    review_cleared: int = 0
    root_cause: str | None = None
    recommended_action: str | None = None

    @property
    def total_cleared(self) -> int:
        return self.atlas_cleared + self.review_cleared


async def clear_expired_queued_jobs(
    db: AsyncSession,
    guard_after_seconds: int,
    *,
    now: datetime | None = None,
) -> QueueGuardSummary:
    """Fail queued jobs that waited too long, so users stop polling forever."""
    reference = now or datetime.now(UTC)
    aware_reference = reference if reference.tzinfo else reference.replace(tzinfo=UTC)
    aware_cutoff = aware_reference - timedelta(seconds=guard_after_seconds)
    naive_cutoff = aware_cutoff.replace(tzinfo=None)

    atlas_running = await _running_count(db, AnalysisJob)
    review_running = await _running_count(db, ReviewJob)

    atlas_message = ATLAS_NO_WORKER_MESSAGE if atlas_running == 0 else ATLAS_CAPACITY_MESSAGE
    review_message = REVIEW_NO_WORKER_MESSAGE if review_running == 0 else REVIEW_CAPACITY_MESSAGE

    atlas_cleared = await _clear_atlas_queue(
        db,
        cutoff=aware_cutoff,
        completed_at=aware_reference,
        message=atlas_message,
    )
    review_cleared = await _clear_review_queue(
        db,
        cutoff=naive_cutoff,
        completed_at=naive_cutoff,
        message=review_message,
    )

    await db.commit()

    summary = QueueGuardSummary(atlas_cleared=atlas_cleared, review_cleared=review_cleared)
    if summary.total_cleared:
        summary.root_cause = _root_cause(
            atlas_cleared=atlas_cleared,
            review_cleared=review_cleared,
            atlas_running=atlas_running,
            review_running=review_running,
        )
        summary.recommended_action = _recommended_action(summary.root_cause)
    return summary


async def _running_count(db: AsyncSession, model: type[AnalysisJob] | type[ReviewJob]) -> int:
    rows = await db.scalars(select(model).where(model.status == "running"))
    return len(rows.all())


async def _clear_atlas_queue(
    db: AsyncSession,
    *,
    cutoff: datetime,
    completed_at: datetime,
    message: str,
) -> int:
    result = await db.execute(
        update(AnalysisJob)
        .where(AnalysisJob.status == "queued", AnalysisJob.created_at < cutoff)
        .values(status="failed", error_message=message, completed_at=completed_at)
    )
    return int(result.rowcount or 0)


async def _clear_review_queue(
    db: AsyncSession,
    *,
    cutoff: datetime,
    completed_at: datetime,
    message: str,
) -> int:
    result = await db.execute(
        update(ReviewJob)
        .where(ReviewJob.status == "queued", ReviewJob.created_at < cutoff)
        .values(
            status="failed",
            error_code="QUEUE_TIMEOUT",
            error_message=message,
            completed_at=completed_at,
        )
    )
    return int(result.rowcount or 0)


def _root_cause(
    *,
    atlas_cleared: int,
    review_cleared: int,
    atlas_running: int,
    review_running: int,
) -> str:
    if atlas_cleared and atlas_running == 0:
        return "atlas_worker_inactive"
    if review_cleared and review_running == 0:
        return "review_worker_inactive"
    return "worker_capacity_saturated"


def _recommended_action(root_cause: str | None) -> str | None:
    if root_cause == "atlas_worker_inactive":
        return "Verify the Railway worker service is healthy and running python -m app.worker."
    if root_cause == "review_worker_inactive":
        return (
            "Verify the Railway worker service includes the review queue and shares "
            "DATABASE_URL."
        )
    if root_cause == "worker_capacity_saturated":
        return (
            "Increase worker concurrency or add another worker replica before accepting "
            "more jobs."
        )
    return None
