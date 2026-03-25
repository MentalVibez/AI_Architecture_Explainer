"""
app/services/pipeline/public_worker.py

Async background task for public static analysis jobs.

Called by FastAPI BackgroundTasks — this is the function registered with
background_tasks.add_task() in the public_static_pipeline._enqueue().

Flow:
    1. Clone repo (shallow)
    2. Mark job running
    3. run_review_on_repo() — existing review pipeline
    4. run_onboarding_analysis() — three new analyzers
    5. Write cache entry
    6. Mark job complete

Each step has its own error handling. The function never raises —
failures are written to the job row and/or section sentinels.

Session pattern:
    Uses async_session_factory() from app.core.database — matches the
    existing pattern in your other workers. The session scope is one
    job = one session.
"""

from __future__ import annotations

import logging
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path

log = logging.getLogger(__name__)


async def run_public_static_analysis(
    job_id:     str,
    repo_url:   str,
    branch:     str        = "main",
    commit_sha: str | None = None,
) -> None:
    """
    Entry point for the public static analysis background task.

    This is what BackgroundTasks calls. Owns the full job lifecycle
    for a public analysis job.
    """
    from sqlalchemy import select

    from app.core.database import async_session_factory
    from app.models.analysis import AnalysisJob, AnalysisResult

    log.info("public_worker_started job_id=%s repo=%s", job_id, repo_url)

    async with async_session_factory() as db:
        # ── Fetch job row ───────────────────────────────
        job = await db.scalar(
            select(AnalysisJob).where(AnalysisJob.id == job_id)
        )
        if job is None:
            log.error("public_worker_job_not_found job_id=%s", job_id)
            return

        result = await db.scalar(
            select(AnalysisResult).where(AnalysisResult.job_id == job_id)
        )
        if result is None:
            # Should not happen — job creation creates both rows
            # Create it here as a recovery path
            result = AnalysisResult(
                id=str(uuid.uuid4()),
                job_id=job_id,
            )
            db.add(result)
            await db.flush()

        # ── Mark running ────────────────────────────────
        job.status     = "running"
        job.started_at = datetime.now(UTC)
        await db.commit()

        try:
            with tempfile.TemporaryDirectory() as clone_dir:
                repo_path = Path(clone_dir)

                # ── 1. Clone ────────────────────────────
                await _clone_repo(repo_url, repo_path, branch)

                # ── 2. Resolve commit SHA if not known ──
                if not commit_sha:
                    commit_sha = _read_head_sha(repo_path)
                    if commit_sha:
                        job.commit_sha = commit_sha
                        await db.flush()

                # ── 3. Existing review pipeline ─────────
                # Replace this with your real run_review_on_repo() call.
                # Pattern from reviewer_split_diff.py:
                #
                #   from app.services.reviewer.service import run_review_on_repo, ReviewError
                #   try:
                #       report = await run_review_on_repo(repo_path, branch, commit_sha)
                #       from app.models.review import Review
                #       review = Review.from_report(job_id=job_id, report=report, branch=branch)
                #       db.add(review)
                #       await db.flush()
                #   except ReviewError as exc:
                #       log.warning("review_failed job_id=%s: %s", job_id, exc)
                #       # Don't abort — onboarding analysis can still run

                # ── 4. Onboarding analysis (three analyzers) ──
                from app.services.pipeline.onboarding_assembler_async import (
                    mark_onboarding_failed_if_needed,
                    run_onboarding_analysis,
                )
                await run_onboarding_analysis(
                    job_id    = job_id,
                    repo_path = repo_path,
                    result    = result,
                    db        = db,
                )

                # ── 5. Write cache entry ────────────────
                if commit_sha:
                    # Cache needs sync session — pass None to skip if no sync db
                    # (cache is best-effort; a miss on next request just re-runs)
                    # TODO: if you need cache writes, pass a sync session here
                    pass

            # ── 6. Mark complete ────────────────────────
            job.status       = "complete"
            job.completed_at = datetime.now(UTC)
            await db.commit()

            log.info("public_worker_completed job_id=%s", job_id)

        except Exception as exc:
            log.exception("public_worker_failed job_id=%s: %s", job_id, exc)

            # Write sentinels to any unpopulated sections
            from app.services.pipeline.onboarding_assembler_async import (
                mark_onboarding_failed_if_needed,
            )
            await mark_onboarding_failed_if_needed(job_id, str(exc), db)

            job.status        = "failed"
            job.error_code    = "WORKER_ERROR"
            job.error_message = f"{type(exc).__name__}: {str(exc)[:300]}"
            job.completed_at  = datetime.now(UTC)
            await db.commit()


# ─────────────────────────────────────────────────────────
# Clone utility
# ─────────────────────────────────────────────────────────

async def _clone_repo(repo_url: str, dest: Path, branch: str) -> None:
    """
    Shallow-clone repo_url into dest.

    If your existing codebase has a clone utility (e.g. in reviewer/service.py
    after the split), import and call that instead of this implementation.
    This is a self-contained fallback.
    """
    import asyncio
    import subprocess

    # Try with specified branch first
    cmd = [
        "git", "clone",
        "--depth", "1",
        "--branch", branch,
        "--single-branch",
        repo_url,
        str(dest),
    ]
    try:
        proc = await asyncio.to_thread(
            subprocess.run, cmd,
            capture_output=True, text=True, timeout=120,
        )
        if proc.returncode == 0:
            return
        # Branch not found — try without --branch (uses default)
        if "Remote branch" in proc.stderr or "not found" in proc.stderr.lower():
            cmd_default = [
                "git", "clone", "--depth", "1", "--single-branch",
                repo_url, str(dest),
            ]
            proc2 = await asyncio.to_thread(
                subprocess.run, cmd_default,
                capture_output=True, text=True, timeout=120,
            )
            if proc2.returncode != 0:
                raise RuntimeError(f"Clone failed: {proc2.stderr[:300]}")
            return
        raise RuntimeError(f"Clone failed: {proc.stderr[:300]}")

    except subprocess.TimeoutExpired:
        raise RuntimeError(f"Clone timed out (120s): {repo_url}")


def _read_head_sha(repo_path: Path) -> str | None:
    """Read the HEAD commit SHA from the cloned repo."""
    import subprocess
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_path, capture_output=True, text=True, timeout=5,
        )
        sha = result.stdout.strip()
        return sha if len(sha) == 40 else None
    except Exception:
        return None
