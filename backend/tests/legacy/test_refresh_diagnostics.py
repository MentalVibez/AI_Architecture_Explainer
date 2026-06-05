"""
tests/legacy/test_refresh_diagnostics.py

Tests for POST /api/results/{result_id}/refresh-diagnostics.

Scenarios:
  - 404 when result does not exist
  - 200 refreshed=False when all three tabs are already populated
  - 422 when raw_evidence is missing repo owner/name (can't clone)
  - 200 refreshed=True when tabs are null — _populate_diagnostic_tabs is
    mocked so no real git clone happens; asserts the tabs are persisted
"""

from unittest.mock import patch

from app.models.analysis_job import AnalysisJob
from app.models.analysis_result import AnalysisResult
from app.models.repo import Repo
from tests.legacy.conftest import TestSessionLocal

# ─────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────

def _minimal_stack() -> dict:
    return {"frontend": [], "backend": [], "database": [], "infra": [], "testing": []}


async def _make_result(
    *,
    setup_risk=None,
    debug_readiness=None,
    change_risk=None,
    raw_evidence=None,
) -> int:
    """Persist a Repo + AnalysisJob + AnalysisResult and return the result id."""
    async with TestSessionLocal() as session:
        repo = Repo(
            github_owner="encode",
            github_repo="starlette",
            github_url="https://github.com/encode/starlette",
        )
        session.add(repo)
        await session.flush()

        job = AnalysisJob(repo_id=repo.id, status="completed")
        session.add(job)
        await session.flush()

        result = AnalysisResult(
            job_id=job.id,
            detected_stack=_minimal_stack(),
            dependencies={"npm": [], "python": []},
            entry_points=[],
            folder_map=[],
            raw_evidence=raw_evidence if raw_evidence is not None else [
                {"repo": {"owner": "encode", "name": "starlette", "default_branch": "main"}}
            ],
            setup_risk=setup_risk,
            debug_readiness=debug_readiness,
            change_risk=change_risk,
        )
        session.add(result)
        await session.commit()
        return result.id


# ─────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────

async def test_refresh_diagnostics_404_on_missing_result(client):
    response = await client.post("/api/results/99999/refresh-diagnostics")
    assert response.status_code == 404


async def test_refresh_diagnostics_noop_when_all_tabs_present(client):
    present = {"scan_state": "found"}
    result_id = await _make_result(
        setup_risk=present,
        debug_readiness=present,
        change_risk=present,
    )

    response = await client.post(f"/api/results/{result_id}/refresh-diagnostics")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["refreshed"] is False


async def test_refresh_diagnostics_422_when_repo_info_missing(client):
    result_id = await _make_result(raw_evidence=[{}])  # no "repo" key

    response = await client.post(f"/api/results/{result_id}/refresh-diagnostics")

    assert response.status_code == 422


async def test_refresh_diagnostics_populates_null_tabs(client):
    result_id = await _make_result()  # all three tabs null

    filled = {"scan_state": "found", "score": 0.8, "level": "low"}

    async def _fake_populate(*, job_id, owner, repo, default_branch, result, db):
        result.setup_risk = filled
        result.debug_readiness = filled
        result.change_risk = filled
        db.add(result)
        await db.flush()

    with patch(
        "app.services.atlas_worker._populate_diagnostic_tabs",
        side_effect=_fake_populate,
    ):
        response = await client.post(f"/api/results/{result_id}/refresh-diagnostics")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["refreshed"] is True

    # Confirm the tabs were actually committed to the DB
    from sqlalchemy import select
    async with TestSessionLocal() as session:
        refreshed = await session.scalar(
            select(AnalysisResult).where(AnalysisResult.id == result_id)
        )
    assert refreshed.setup_risk == filled
    assert refreshed.debug_readiness == filled
    assert refreshed.change_risk == filled


async def test_refresh_diagnostics_correct_owner_repo_passed(client):
    """Ensure the correct owner/repo/branch from raw_evidence reaches _populate_diagnostic_tabs."""
    result_id = await _make_result(
        raw_evidence=[
            {"repo": {"owner": "django", "name": "django", "default_branch": "stable/4.2.x"}}
        ]
    )

    captured: dict = {}

    async def _capture(*, job_id, owner, repo, default_branch, result, db):
        captured.update({"owner": owner, "repo": repo, "default_branch": default_branch})
        result.setup_risk = {"scan_state": "found"}
        result.debug_readiness = {"scan_state": "found"}
        result.change_risk = {"scan_state": "found"}
        db.add(result)
        await db.flush()

    with patch("app.services.atlas_worker._populate_diagnostic_tabs", side_effect=_capture):
        response = await client.post(f"/api/results/{result_id}/refresh-diagnostics")

    assert response.status_code == 200
    assert captured["owner"] == "django"
    assert captured["repo"] == "django"
    assert captured["default_branch"] == "stable/4.2.x"
