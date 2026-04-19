from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.models.analysis_job import AnalysisJob
from app.models.analysis_result import AnalysisResult
from app.models.repo import Repo
from app.models.review import Review
from app.models.review_job import ReviewJob
from tests.legacy.conftest import TestSessionLocal


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _utcnow_naive() -> datetime:
    return _utcnow().replace(tzinfo=None)


@pytest.mark.asyncio
async def test_analysis_status_includes_metadata(client):
    async with TestSessionLocal() as session:
        repo = Repo(
            github_owner="vercel",
            github_repo="next.js",
            github_url="https://github.com/vercel/next.js",
        )
        session.add(repo)
        await session.flush()

        started_at = _utcnow() - timedelta(seconds=45)
        job = AnalysisJob(repo_id=repo.id, status="running", started_at=started_at)
        session.add(job)
        await session.commit()

        job_id = job.id

    response = await client.get(f"/api/analyze/{job_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["phase"] == "analysis"
    assert payload["next_poll_seconds"] == 2
    assert payload["duration_seconds"] >= 40
    assert "Collecting repository evidence" in payload["status_detail"]


@pytest.mark.asyncio
async def test_recent_runs_returns_atlas_and_review_history(client):
    async with TestSessionLocal() as session:
        repo = Repo(
            github_owner="vercel",
            github_repo="next.js",
            github_url="https://github.com/vercel/next.js",
        )
        session.add(repo)
        await session.flush()

        atlas_job = AnalysisJob(repo_id=repo.id, status="completed")
        session.add(atlas_job)
        await session.flush()

        atlas_result = AnalysisResult(
            job_id=atlas_job.id,
            detected_stack={"frontend": ["next.js"]},
            dependencies={"npm": ["next"]},
            entry_points=["app/page.tsx"],
            folder_map=[{"path": "app/page.tsx", "role": "entrypoint"}],
            raw_evidence=[],
            created_at=_utcnow() - timedelta(minutes=10),
        )
        session.add(atlas_result)

        review_job = ReviewJob(
            id=uuid4(),
            repo_url="https://github.com/vercel/next.js",
            branch="main",
            status="completed",
            created_at=_utcnow_naive() - timedelta(minutes=6),
            completed_at=_utcnow_naive() - timedelta(minutes=5),
        )
        session.add(review_job)
        await session.flush()

        review = Review(
            id=uuid4(),
            job_id=review_job.id,
            repo_url=review_job.repo_url,
            branch="main",
            verdict_label="Recommended",
            production_suitable=True,
            created_at=_utcnow_naive() - timedelta(minutes=6),
            completed_at=_utcnow_naive() - timedelta(minutes=5),
        )
        session.add(review)
        await session.commit()

    response = await client.get("/api/history/runs?limit=4")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 2
    assert payload["items"][0]["kind"] == "review"
    assert payload["items"][0]["repo"] == "vercel/next.js"
    assert "result_id=" in payload["items"][0]["href"]
    assert payload["items"][1]["kind"] == "atlas"
    assert payload["items"][1]["href"] == f"/results/{atlas_result.id}"


@pytest.mark.asyncio
async def test_ops_summary_reports_queue_counts_and_recent_failures(client, monkeypatch):
    monkeypatch.setattr(
        "app.api.routes_ops.github_auth_snapshot",
        lambda: {"mode": "token", "status": "ok", "detail": ""},
    )
    async with TestSessionLocal() as session:
        repo = Repo(
            github_owner="fastapi",
            github_repo="fastapi",
            github_url="https://github.com/fastapi/fastapi",
        )
        session.add(repo)
        await session.flush()

        atlas_failed = AnalysisJob(
            repo_id=repo.id,
            status="failed",
            started_at=_utcnow() - timedelta(minutes=8),
            completed_at=_utcnow() - timedelta(minutes=7),
            error_message="Atlas failed during evidence fetch",
        )
        atlas_running = AnalysisJob(
            repo_id=repo.id,
            status="running",
            started_at=_utcnow() - timedelta(minutes=2),
        )
        review_running = ReviewJob(
            id=uuid4(),
            repo_url="https://github.com/fastapi/fastapi",
            branch="main",
            status="running",
            started_at=_utcnow_naive() - timedelta(minutes=1),
            created_at=_utcnow_naive() - timedelta(minutes=1),
        )
        session.add_all([atlas_failed, atlas_running, review_running])
        await session.commit()

    response = await client.get("/api/ops/summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "active"
    assert payload["github"]["status"] in {"configured", "not_configured", "degraded", "error", "ok"}
    assert payload["atlas"]["running"] == 1
    assert payload["atlas"]["failed_last_24h"] == 1
    assert payload["review"]["running"] == 1
    assert payload["recent_failures"][0]["kind"] == "atlas"
    assert payload["recent_failures"][0]["repo"] == "fastapi/fastapi"
    assert payload["atlas"]["oldest_running_seconds"] >= 60
    assert payload["attention_message"] is None


@pytest.mark.asyncio
async def test_ops_summary_detects_worker_backlog_without_runner(client, monkeypatch):
    monkeypatch.setattr(
        "app.api.routes_ops.github_auth_snapshot",
        lambda: {"mode": "token", "status": "ok", "detail": ""},
    )
    async with TestSessionLocal() as session:
        repo = Repo(
            github_owner="tiangolo",
            github_repo="full-stack-fastapi-postgresql",
            github_url="https://github.com/tiangolo/full-stack-fastapi-postgresql",
        )
        session.add(repo)
        await session.flush()

        atlas_queued = AnalysisJob(
            repo_id=repo.id,
            status="queued",
            created_at=_utcnow() - timedelta(minutes=5),
        )
        session.add(atlas_queued)
        await session.commit()

    response = await client.get("/api/ops/summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "watch"
    assert payload["atlas"]["queued"] == 1
    assert payload["atlas"]["oldest_queued_seconds"] >= 240
    assert "without an active worker" in payload["attention_message"]


def test_ops_summary_marks_github_degradation_as_attention() -> None:
    from app.api.routes_ops import _github_attention_message, _ops_status
    from app.schemas.ops_response import ExternalServiceStatusResponse, QueueMetricsResponse

    idle = QueueMetricsResponse(
        queued=0,
        running=0,
        completed_last_24h=0,
        failed_last_24h=0,
    )
    github = ExternalServiceStatusResponse(
        mode="fallback_unauthenticated",
        status="degraded",
        detail="Configured GITHUB_TOKEN was rejected by GitHub; requests are falling back to public API limits.",
    )

    assert _ops_status(idle, idle, github) == "watch"
    assert "GitHub API authentication is degraded" in _github_attention_message(github)
