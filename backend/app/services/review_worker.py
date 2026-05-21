"""
Review job worker.

Owns: job lifecycle (running → completed/failed)
Calls: run_review() — owns review execution
Stores: Review row via Review.from_report() or Review.from_error()

Error handling:
    ReviewError   → stored with stable error_code
    Exception     → stored as UNEXPECTED_BACKEND_ERROR, re-raised for logging
"""
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.review import Review
from app.models.review_job import ReviewJob
from app.services.reviewer.service import ReviewError, run_review

logger = logging.getLogger(__name__)


def _utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


async def process_review_job(
    job_id: uuid.UUID,
    repo_url: str,
    branch: str = "main",
    commit: str | None = None,
    db: AsyncSession = None,
    job: ReviewJob = None,
    *,
    mark_running: bool = True,
) -> None:
    """
    Called by the background task runner.
    Manages job state transitions and Review row creation.
    """
    if mark_running:
        job.status = "running"
        job.started_at = _utcnow_naive()
        job.error_code = None
        job.error_message = None
        await db.commit()

    logger.info("review_job_started job_id=%s repo=%s branch=%s", job_id, repo_url, branch)

    # Dedup: if this exact commit was already reviewed successfully, reuse the result
    if commit:
        existing_id = await db.scalar(
            select(Review.id).where(
                Review.repo_url == repo_url,
                Review.commit == commit,
                Review.branch == branch,
                Review.error_code.is_(None),
            )
        )
        if existing_id is not None:
            job.status = "completed"
            job.cached_result_id = existing_id
            job.completed_at = _utcnow_naive()
            await db.commit()
            logger.info(
                "review_cache_hit job_id=%s cached_result_id=%s commit=%s",
                job_id, existing_id, commit,
            )
            return

    try:
        report = await run_review(repo_url=repo_url, branch=branch, commit=commit)

        review = Review.from_report(job_id=job_id, report=report, branch=branch)
        db.add(review)

        job.status = "completed"
        job.completed_at = _utcnow_naive()
        await db.commit()

        logger.info(
            "review_job_completed job_id=%s result_id=%s score=%d depth=%s findings=%d",
            job_id,
            review.id,
            review.overall_score or 0,
            review.depth_level,
            len(report.findings),
        )

        if job.pr_number and job.pr_repo:
            from app.services.pr_comment_service import post_pr_comment
            await post_pr_comment(pr_repo=job.pr_repo, pr_number=job.pr_number, review=review, job=job)

    except ReviewError as exc:
        review = Review.from_error(
            job_id=job_id,
            repo_url=repo_url,
            branch=branch,
            commit=commit,
            error_code=exc.code,
            error_message=exc.message,
        )
        db.add(review)

        job.status = "failed"
        job.error_code = exc.code
        job.error_message = exc.message
        job.completed_at = _utcnow_naive()
        await db.commit()

        logger.warning(
            "review_job_failed job_id=%s error_code=%s message=%s",
            job_id,
            exc.code,
            exc.message,
        )

        if job.pr_number and job.pr_repo:
            from app.services.pr_comment_service import post_pr_comment
            await post_pr_comment(pr_repo=job.pr_repo, pr_number=job.pr_number, review=review, job=job)

    except Exception as exc:
        review = Review.from_error(
            job_id=job_id,
            repo_url=repo_url,
            branch=branch,
            commit=commit,
            error_code="UNEXPECTED_BACKEND_ERROR",
            error_message=f"{type(exc).__name__}: {str(exc)[:300]}",
        )
        db.add(review)

        job.status = "failed"
        job.error_code = "UNEXPECTED_BACKEND_ERROR"
        job.error_message = f"{type(exc).__name__}: {str(exc)[:300]}"
        job.completed_at = _utcnow_naive()
        await db.commit()

        logger.exception("review_job_unexpected_error job_id=%s repo=%s", job_id, repo_url)

        if job.pr_number and job.pr_repo:
            from app.services.pr_comment_service import post_pr_comment
            await post_pr_comment(pr_repo=job.pr_repo, pr_number=job.pr_number, review=review, job=job)

        raise


async def run_review_job(
    job_id: uuid.UUID,
    repo_url: str,
    branch: str = "main",
    commit: str | None = None,
    *,
    mark_running: bool = True,
) -> None:
    async with AsyncSessionLocal() as db:
        job = await db.get(ReviewJob, job_id)
        if job is None:
            return

        await process_review_job(
            job_id=job_id,
            repo_url=repo_url,
            branch=branch,
            commit=commit,
            db=db,
            job=job,
            mark_running=mark_running,
        )
