from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis_job import AnalysisJob
from app.models.review_job import ReviewJob


@dataclass(slots=True)
class RecoverySummary:
    atlas: int = 0
    review: int = 0

    @property
    def total(self) -> int:
        return self.atlas + self.review


async def recover_stale_jobs(
    db: AsyncSession,
    stale_after_seconds: int,
    *,
    now: datetime | None = None,
) -> RecoverySummary:
    """Mark long-running jobs as failed after a worker restart/crash."""
    reference = now or datetime.now(UTC)
    aware_reference = reference if reference.tzinfo else reference.replace(tzinfo=UTC)
    aware_cutoff = aware_reference - timedelta(seconds=stale_after_seconds)
    naive_cutoff = aware_cutoff.replace(tzinfo=None)

    atlas = await _mark_stale_atlas_jobs(db, aware_cutoff, aware_reference)
    review = await _mark_stale_review_jobs(db, naive_cutoff, naive_cutoff)
    await db.commit()
    return RecoverySummary(atlas=atlas, review=review)


async def _mark_stale_atlas_jobs(
    db: AsyncSession,
    cutoff: datetime,
    completed_at: datetime,
) -> int:
    result = await db.execute(
        update(AnalysisJob)
        .where(AnalysisJob.status == "running", AnalysisJob.started_at < cutoff)
        .values(
            status="failed",
            error_message="Worker stopped while the Atlas job was running",
            completed_at=completed_at,
        )
    )
    return int(result.rowcount or 0)


async def _mark_stale_review_jobs(
    db: AsyncSession,
    cutoff: datetime,
    completed_at: datetime,
) -> int:
    result = await db.execute(
        update(ReviewJob)
        .where(ReviewJob.status == "running", ReviewJob.started_at < cutoff)
        .values(
            status="failed",
            error_code="WORKER_RESTARTED",
            error_message="Worker stopped while the review job was running",
            completed_at=completed_at,
        )
    )
    return int(result.rowcount or 0)
