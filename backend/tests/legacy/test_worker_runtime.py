from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy import select

from app.models.analysis_job import AnalysisJob
from app.models.analysis_result import AnalysisResult
from app.models.repo import Repo
from app.models.review_job import ReviewJob
from app.services import atlas_worker
from app.services.job_recovery import recover_stale_jobs
from app.services.worker_heartbeat import WorkerIdentity, record_worker_heartbeat
from app.services.worker_runtime import (
    _queue_concurrency,
    claim_next_atlas_job,
    claim_next_review_job,
)
from tests.legacy.conftest import TestSessionLocal


def _utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _atlas_evidence(owner: str = "encode", repo: str = "starlette") -> dict:
    return {
        "repo": {"owner": owner, "name": repo, "default_branch": "main"},
        "tree_sha": f"{owner}-{repo}-sha",
        "detected_stack": {
            "frontend": [],
            "backend": [],
            "database": [],
            "infra": [],
            "testing": [],
        },
        "npm_dependencies": [],
        "python_dependencies": [],
        "tree_paths": [],
        "fetched_files": [],
        "readme": "",
    }


def _summaries() -> dict:
    return {
        "diagram_mermaid": "flowchart TD\n  A --> B",
        "developer_summary": "Developer summary",
        "hiring_manager_summary": "Hiring summary",
    }


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
async def test_execute_atlas_job_persists_diagnostic_tabs(monkeypatch):
    monkeypatch.setattr(atlas_worker, "AsyncSessionLocal", TestSessionLocal)

    async def fake_run_analysis(owner, repo):
        return _atlas_evidence(owner, repo), None

    async def fake_generate_summaries(evidence):
        return _summaries()

    async def fake_clone(owner, repo, branch, dest):
        return None

    monkeypatch.setattr(atlas_worker, "run_analysis", fake_run_analysis)
    monkeypatch.setattr(atlas_worker, "generate_summaries", fake_generate_summaries)
    monkeypatch.setattr(atlas_worker, "_clone_repo_for_diagnostics", fake_clone)

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
        job_id = job.id

    await atlas_worker.execute_analysis_job(job_id, "encode", "starlette")

    async with TestSessionLocal() as session:
        job = await session.get(AnalysisJob, job_id)
        result = (
            await session.execute(
                select(AnalysisResult).where(AnalysisResult.job_id == job_id)
            )
        ).scalar_one()

    assert job.status == "completed"
    assert result.setup_risk is not None
    assert result.debug_readiness is not None
    assert result.change_risk is not None
    assert "scan_state" in result.setup_risk


@pytest.mark.asyncio
async def test_execute_atlas_job_marks_diagnostic_tabs_failed_without_failing_job(monkeypatch):
    monkeypatch.setattr(atlas_worker, "AsyncSessionLocal", TestSessionLocal)

    async def fake_run_analysis(owner, repo):
        return _atlas_evidence(owner, repo), None

    async def fake_generate_summaries(evidence):
        return _summaries()

    async def fake_clone(owner, repo, branch, dest):
        raise RuntimeError("clone unavailable")

    monkeypatch.setattr(atlas_worker, "run_analysis", fake_run_analysis)
    monkeypatch.setattr(atlas_worker, "generate_summaries", fake_generate_summaries)
    monkeypatch.setattr(atlas_worker, "_clone_repo_for_diagnostics", fake_clone)

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
        job_id = job.id

    await atlas_worker.execute_analysis_job(job_id, "encode", "starlette")

    async with TestSessionLocal() as session:
        job = await session.get(AnalysisJob, job_id)
        result = (
            await session.execute(
                select(AnalysisResult).where(AnalysisResult.job_id == job_id)
            )
        ).scalar_one()

    assert job.status == "completed"
    assert result.setup_risk["scan_state"] == "scan_failed"
    assert result.debug_readiness["scan_state"] == "scan_failed"
    assert result.change_risk["scan_state"] == "scan_failed"


@pytest.mark.asyncio
async def test_execute_atlas_job_backfills_missing_tabs_on_cache_hit(monkeypatch):
    monkeypatch.setattr(atlas_worker, "AsyncSessionLocal", TestSessionLocal)

    async def fake_run_analysis(owner, repo):
        return _atlas_evidence(owner, repo), None

    async def fake_clone(owner, repo, branch, dest):
        return None

    monkeypatch.setattr(atlas_worker, "run_analysis", fake_run_analysis)
    monkeypatch.setattr(atlas_worker, "_clone_repo_for_diagnostics", fake_clone)

    async with TestSessionLocal() as session:
        repo = Repo(
            github_owner="encode",
            github_repo="starlette",
            github_url="https://github.com/encode/starlette",
        )
        session.add(repo)
        await session.flush()
        original_job = AnalysisJob(repo_id=repo.id, status="completed")
        new_job = AnalysisJob(repo_id=repo.id, status="queued")
        session.add_all([original_job, new_job])
        await session.flush()
        cached_result = AnalysisResult(
            job_id=original_job.id,
            repo_snapshot_sha="encode-starlette-sha",
            detected_stack={
                "frontend": [],
                "backend": [],
                "database": [],
                "infra": [],
                "testing": [],
            },
            dependencies={"npm": [], "python": []},
            entry_points=[],
            folder_map=[],
            raw_evidence=[],
        )
        session.add(cached_result)
        await session.commit()
        new_job_id = new_job.id
        cached_result_id = cached_result.id

    await atlas_worker.execute_analysis_job(new_job_id, "encode", "starlette")

    async with TestSessionLocal() as session:
        job = await session.get(AnalysisJob, new_job_id)
        result = await session.get(AnalysisResult, cached_result_id)

    assert job.status == "completed"
    assert job.cached_result_id == cached_result_id
    assert result.setup_risk is not None
    assert result.debug_readiness is not None
    assert result.change_risk is not None


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


@pytest.mark.asyncio
async def test_record_worker_heartbeat_upserts_worker_status():
    identity = WorkerIdentity(
        worker_id="worker-test-1",
        hostname="test-host",
        process_id=123,
        started_at=datetime.now(UTC),
    )

    await record_worker_heartbeat(
        identity=identity,
        queues=("atlas", "review"),
        session_factory=TestSessionLocal,
    )
    await record_worker_heartbeat(
        identity=identity,
        queues=("review",),
        status="stopping",
        session_factory=TestSessionLocal,
    )

    async with TestSessionLocal() as session:
        from app.models.worker_heartbeat import WorkerHeartbeat

        heartbeat = await session.get(WorkerHeartbeat, identity.worker_id)
        assert heartbeat is not None
        assert heartbeat.hostname == "test-host"
        assert heartbeat.process_id == 123
        assert heartbeat.queues == "review"
        assert heartbeat.status == "stopping"
        assert heartbeat.last_seen_at is not None


def test_queue_concurrency_uses_per_queue_settings(monkeypatch):
    monkeypatch.setattr("app.services.worker_runtime.settings.worker_atlas_concurrency", 3)
    monkeypatch.setattr("app.services.worker_runtime.settings.worker_review_concurrency", 2)

    assert _queue_concurrency(("atlas", "review")) == {"atlas": 3, "review": 2}


def test_queue_concurrency_never_drops_below_one(monkeypatch):
    monkeypatch.setattr("app.services.worker_runtime.settings.worker_atlas_concurrency", 0)
    monkeypatch.setattr("app.services.worker_runtime.settings.worker_review_concurrency", -4)

    assert _queue_concurrency(("atlas", "review")) == {"atlas": 1, "review": 1}
