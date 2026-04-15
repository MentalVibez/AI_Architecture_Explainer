import asyncio
import logging
import uuid
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Select, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.analysis_job import AnalysisJob
from app.models.repo import Repo
from app.models.review_job import ReviewJob
from app.services.atlas_worker import execute_analysis_job
from app.services.job_recovery import recover_stale_jobs
from app.services.review_worker import run_review_job

logger = logging.getLogger(__name__)
RECOVERY_INTERVAL_SECONDS = 60


@dataclass(slots=True)
class AtlasClaim:
    job_id: int
    owner: str
    repo: str


@dataclass(slots=True)
class ReviewClaim:
    job_id: uuid.UUID
    repo_url: str
    branch: str
    commit: str | None


async def run_worker_loop() -> None:
    queue_order = _queue_order()
    await _recover_stale_jobs()
    logger.info("worker_started queues=%s", ",".join(queue_order))

    last_recovery = asyncio.get_running_loop().time()
    queue_cycle = deque(queue_order)

    while True:
        worked = False

        for _ in range(len(queue_cycle)):
            queue_name = queue_cycle[0]
            queue_cycle.rotate(-1)

            claim = await _claim_for_queue(queue_name)
            if claim is None:
                continue

            worked = True
            await _run_claim(queue_name, claim)
            break

        now = asyncio.get_running_loop().time()
        if now - last_recovery >= RECOVERY_INTERVAL_SECONDS:
            await _recover_stale_jobs()
            last_recovery = now

        if not worked:
            await asyncio.sleep(settings.worker_poll_interval_seconds)


async def claim_next_atlas_job(
    *,
    session_factory: async_sessionmaker[AsyncSession] = AsyncSessionLocal,
) -> AtlasClaim | None:
    candidate_query = (
        select(AnalysisJob.id, Repo.github_owner, Repo.github_repo)
        .join(Repo, AnalysisJob.repo_id == Repo.id)
        .where(AnalysisJob.status == "queued")
        .order_by(AnalysisJob.created_at.asc(), AnalysisJob.id.asc())
        .limit(1)
    )
    return await _claim_with_update(
        session_factory=session_factory,
        candidate_query=candidate_query,
        update_stmt_builder=lambda row, started_at: (
            update(AnalysisJob)
            .where(AnalysisJob.id == row.id, AnalysisJob.status == "queued")
            .values(status="running", started_at=started_at, error_message=None)
        ),
        row_mapper=lambda row: AtlasClaim(
            job_id=row.id,
            owner=row.github_owner,
            repo=row.github_repo,
        ),
    )


async def claim_next_review_job(
    *,
    session_factory: async_sessionmaker[AsyncSession] = AsyncSessionLocal,
) -> ReviewClaim | None:
    candidate_query = (
        select(ReviewJob.id, ReviewJob.repo_url, ReviewJob.branch, ReviewJob.commit)
        .where(ReviewJob.status == "queued")
        .order_by(ReviewJob.created_at.asc())
        .limit(1)
    )
    return await _claim_with_update(
        session_factory=session_factory,
        candidate_query=candidate_query,
        update_stmt_builder=lambda row, started_at: (
            update(ReviewJob)
            .where(ReviewJob.id == row.id, ReviewJob.status == "queued")
            .values(
                status="running",
                started_at=started_at.replace(tzinfo=None),
                error_code=None,
                error_message=None,
            )
        ),
        row_mapper=lambda row: ReviewClaim(
            job_id=row.id,
            repo_url=row.repo_url,
            branch=row.branch,
            commit=row.commit,
        ),
    )


async def _claim_with_update(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    candidate_query: Select[Any],
    update_stmt_builder: Callable[[Any, datetime], Any],
    row_mapper: Callable[[Any], Any],
) -> Any | None:
    for _ in range(3):
        async with session_factory() as db:
            row = (await db.execute(candidate_query)).first()
            if row is None:
                return None

            started_at = datetime.now(UTC)
            claimed = await db.execute(update_stmt_builder(row, started_at))
            if int(claimed.rowcount or 0) != 1:
                await db.rollback()
                continue

            await db.commit()
            return row_mapper(row)
    return None


async def _claim_for_queue(queue_name: str) -> AtlasClaim | ReviewClaim | None:
    if queue_name == "atlas":
        return await claim_next_atlas_job()
    if queue_name == "review":
        return await claim_next_review_job()
    raise ValueError(f"Unknown queue: {queue_name}")


async def _run_claim(queue_name: str, claim: AtlasClaim | ReviewClaim) -> None:
    try:
        if queue_name == "atlas":
            atlas_claim = claim if isinstance(claim, AtlasClaim) else None
            if atlas_claim is not None:
                await execute_analysis_job(
                    atlas_claim.job_id,
                    atlas_claim.owner,
                    atlas_claim.repo,
                    mark_running=False,
                )
            return

        if queue_name == "review":
            review_claim = claim if isinstance(claim, ReviewClaim) else None
            if review_claim is not None:
                await run_review_job(
                    job_id=review_claim.job_id,
                    repo_url=review_claim.repo_url,
                    branch=review_claim.branch,
                    commit=review_claim.commit,
                    mark_running=False,
                )
            return
    except Exception:
        logger.exception("worker_job_crashed queue=%s claim=%s", queue_name, claim)


def _queue_order() -> tuple[str, ...]:
    configured = [
        item.strip().lower()
        for item in settings.worker_queue_order.split(",")
        if item.strip()
    ]
    valid = [item for item in configured if item in {"atlas", "review"}]
    return tuple(valid or ("atlas", "review"))


async def _recover_stale_jobs() -> None:
    async with AsyncSessionLocal() as db:
        summary = await recover_stale_jobs(db, settings.worker_stale_job_seconds)
    if summary.total:
        logger.warning(
            "worker_recovered_stale_jobs atlas=%d review=%d",
            summary.atlas,
            summary.review,
        )
