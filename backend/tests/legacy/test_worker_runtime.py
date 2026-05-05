from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from app.models.analysis_job import AnalysisJob
from app.models.repo import Repo
from app.models.review_job import ReviewJob
from app.services.job_recovery import recover_stale_jobs
from app.services.worker_runtime import (
    _queue_concurrency,
    claim_next_atlas_job,
    claim_next_review_job,
)
from tests.legacy.conftest import TestSessionLocal


def _utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


@pytest.mark.asyncio
async def test_claim_next_atlas_job_marks_job_running():
    async with TestSessionLocal() as session:
        repo = Repo(
            github_owner="encode",
            github_repo="starlette",
            github_url="https://github.com/encode/starlette",
        )
        session.add(repo)
        await session.flush()

        job = AnalysisJob(repo_id=repo.id, status="queued")
        session.add(job)
        await session.commit()

    claim = await claim_next_atlas_job(session_factory=TestSessionLocal)

    assert claim is not None
    assert claim.owner == "encode"
    assert claim.repo == "starlette"

    async with TestSessionLocal() as session:
        claimed_job = await session.get(AnalysisJob, job.id)
        assert claimed_job.status == "running"
        assert claimed_job.started_at is not None


@pytest.mark.asyncio
async def test_claim_next_review_job_preserves_commit():
    async with TestSessionLocal() as session:
        job = ReviewJob(
            repo_url="https://github.com/vercel/next.js",
            branch="canary",
            commit="abcdef1234567890abcdef1234567890abcdef12",
            status="queued",
        )
        session.add(job)
        await session.commit()

    claim = await claim_next_review_job(session_factory=TestSessionLocal)

    assert claim is not None
    assert claim.branch == "canary"
    assert claim.commit == "abcdef1234567890abcdef1234567890abcdef12"

    async with TestSessionLocal() as session:
        claimed_job = await session.get(ReviewJob, claim.job_id)
        assert claimed_job.status == "running"
        assert claimed_job.started_at is not None


@pytest.mark.asyncio
async def test_submit_review_persists_commit_for_worker(client):
    response = await client.post(
        "/api/review/",
        json={
            "repo_url": "https://github.com/vercel/next.js",
            "branch": "canary",
            "commit": "1234567890abcdef1234567890abcdef12345678",
        },
    )

    assert response.status_code == 202
    job_id = UUID(response.json()["job_id"])

    async with TestSessionLocal() as session:
        job = await session.get(ReviewJob, job_id)
        assert job is not None
        assert job.status == "queued"
        assert job.commit == "1234567890abcdef1234567890abcdef12345678"


@pytest.mark.asyncio
async def test_recover_stale_jobs_marks_atlas_and_review_failures():
    async with TestSessionLocal() as session:
        repo = Repo(
            github_owner="fastapi",
            github_repo="fastapi",
            github_url="https://github.com/fastapi/fastapi",
        )
        session.add(repo)
        await session.flush()

        atlas_job = AnalysisJob(
            repo_id=repo.id,
            status="running",
            started_at=datetime.now(UTC) - timedelta(hours=2),
        )
        review_job = ReviewJob(
            repo_url="https://github.com/fastapi/fastapi",
            branch="main",
            status="running",
            started_at=_utcnow_naive() - timedelta(hours=2),
            created_at=_utcnow_naive() - timedelta(hours=2),
        )
        session.add_all([atlas_job, review_job])
        await session.commit()

        summary = await recover_stale_jobs(
            session,
            stale_after_seconds=1800,
        )

        assert summary.atlas == 1
        assert summary.review == 1

    async with TestSessionLocal() as session:
        refreshed_atlas = await session.get(AnalysisJob, atlas_job.id)
        refreshed_review = await session.get(ReviewJob, review_job.id)
        assert refreshed_atlas.status == "failed"
        assert "Worker stopped" in refreshed_atlas.error_message
        assert refreshed_review.status == "failed"
        assert refreshed_review.error_code == "WORKER_RESTARTED"


def test_queue_concurrency_uses_per_queue_settings(monkeypatch):
    monkeypatch.setattr("app.services.worker_runtime.settings.worker_atlas_concurrency", 3)
    monkeypatch.setattr("app.services.worker_runtime.settings.worker_review_concurrency", 2)

    assert _queue_concurrency(("atlas", "review")) == {"atlas": 3, "review": 2}


def test_queue_concurrency_never_drops_below_one(monkeypatch):
    monkeypatch.setattr("app.services.worker_runtime.settings.worker_atlas_concurrency", 0)
    monkeypatch.setattr("app.services.worker_runtime.settings.worker_review_concurrency", -4)

    assert _queue_concurrency(("atlas", "review")) == {"atlas": 1, "review": 1}
