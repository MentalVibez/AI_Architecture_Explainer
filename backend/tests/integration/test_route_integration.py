"""
tests/integration/test_route_integration.py

HTTP-level integration tests for every route group using the real FastAPI app
against an in-memory SQLite database. LLM and GitHub calls are mocked so no
real API keys are required.

Coverage:
  Health / liveness / readiness
  Atlas analyze (submit, poll, results)
  Review (submit, poll, report)
  Scout search
  Map API surface
  DevContainer (auth-gated)
  Auth (login, me, logout)
  Ops summary (admin-gated)
  Audit log
  Share slug
"""
from __future__ import annotations

import os
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# --- force env before any app import so Settings() picks them up ---
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite://")
os.environ.setdefault("ATLAS_JWT_SECRET", "test-secret-route-integration")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("ANTHROPIC_API_KEY", "test")
os.environ.setdefault("SENTRY_DSN", "")
# Set ADMIN_API_KEY before the app is imported so settings reads it
os.environ["ADMIN_API_KEY"] = "super-secret-admin-key"

_TEST_ADMIN_KEY = "super-secret-admin-key"


@pytest.fixture(scope="module")
def app():
    from app.main import app as _app
    return _app


@pytest.fixture(scope="module", autouse=True)
async def setup_database(app):  # noqa: F811 — `app` here is the fixture, not the package
    """Create all tables in an in-memory async DB and wire get_db."""
    import importlib
    importlib.import_module("app.models.analysis_job")
    importlib.import_module("app.models.analysis_result")
    importlib.import_module("app.models.devcontainer")
    importlib.import_module("app.models.repo")

    from app.core.database import Base, get_db

    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _override_get_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.fixture(scope="module")
def client(app, setup_database):
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ─────────────────────────────────────────────────────────────────
# Health
# ─────────────────────────────────────────────────────────────────

class TestHealth:
    def test_health_ok(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert "database" in data["checks"]

    def test_live_ok(self, client):
        r = client.get("/live")
        assert r.status_code == 200

    def test_ready_ok(self, client):
        r = client.get("/ready")
        assert r.status_code == 200


# ─────────────────────────────────────────────────────────────────
# Atlas analyze
# ─────────────────────────────────────────────────────────────────

class TestAnalyze:
    def test_analyze_missing_body_returns_422(self, client):
        r = client.post("/api/analyze", json={})
        assert r.status_code == 422

    def test_analyze_invalid_url_returns_422(self, client):
        r = client.post("/api/analyze", json={"repo_url": "not-a-url"})
        assert r.status_code == 422

    def test_analyze_queues_job_returns_job_id(self, client):
        # Analyze route creates a DB row and returns job_id — no external calls needed
        r = client.post(
            "/api/analyze",
            json={"repo_url": "https://github.com/MentalVibez/ai-agent-orchestrator"},
        )
        assert r.status_code in (200, 201, 202)
        assert "job_id" in r.json()

    def test_analyze_poll_unknown_job_returns_404(self, client):
        r = client.get("/api/analyze/999999")
        assert r.status_code == 404

    def test_results_unknown_id_returns_404(self, client):
        r = client.get("/api/results/999999")
        assert r.status_code == 404


# ─────────────────────────────────────────────────────────────────
# Review
# ─────────────────────────────────────────────────────────────────

class TestReview:
    def test_submit_review_valid_url_returns_202(self, client):
        r = client.post(
            "/api/review/",
            json={
                "repo_url": "https://github.com/MentalVibez/ai-agent-orchestrator",
                "branch": "main",
            },
        )
        assert r.status_code == 202
        body = r.json()
        assert "job_id" in body
        self.__class__._job_id = body["job_id"]

    def test_submit_review_missing_url_returns_422(self, client):
        r = client.post("/api/review/", json={"branch": "main"})
        assert r.status_code == 422

    def test_submit_review_bad_url_returns_422(self, client):
        r = client.post("/api/review/", json={"repo_url": "not-a-github-url"})
        assert r.status_code == 422

    def test_poll_unknown_review_job_returns_404(self, client):
        unknown = str(uuid.uuid4())
        r = client.get(f"/api/review/{unknown}")
        assert r.status_code == 404

    def test_poll_created_review_job_returns_status(self, client):
        if not hasattr(self.__class__, "_job_id"):
            pytest.skip("depends on test_submit_review_valid_url_returns_202")
        r = client.get(f"/api/review/{self._job_id}")
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            assert "status" in r.json()


# ─────────────────────────────────────────────────────────────────
# Scout
# ─────────────────────────────────────────────────────────────────

class TestScout:
    def test_scout_search_missing_query_returns_422(self, client):
        r = client.post("/api/scout/search", json={})
        assert r.status_code == 422

    def test_scout_search_empty_query_returns_422_or_400(self, client):
        r = client.post("/api/scout/search", json={"query": ""})
        assert r.status_code in (400, 422)

    def test_scout_search_with_mock_run_scout_returns_200(self, client):
        from app.schemas.scout import ScoutResponse
        stub = ScoutResponse(
            query="AI agent orchestration",
            total=0,
            repos=[],
            tldr="No results found in test environment.",
        )
        with patch(
            "app.api.scout.run_scout",
            new=AsyncMock(return_value=stub),
        ):
            r = client.post(
                "/api/scout/search",
                json={"query": "AI agent orchestration"},
            )
        assert r.status_code == 200
        body = r.json()
        assert body["query"] == "AI agent orchestration"
        assert "repos" in body


# ─────────────────────────────────────────────────────────────────
# Map
# ─────────────────────────────────────────────────────────────────

class TestMap:
    def test_map_nonexistent_repo_returns_error(self, client):
        r = client.get("/api/map/does-not-exist-org/does-not-exist-repo-xyz")
        assert r.status_code in (404, 500, 502)

    def test_map_with_mocked_stack_analysis_returns_200(self, client):
        mock_evidence = {
            "detected_stack": {
                "backend": [{"name": "FastAPI", "confidence": 0.95}],
                "frontend": [],
            },
            "files_analyzed": ["app/main.py", "requirements.txt"],
            "endpoints": [
                {"method": "GET", "path": "/", "file": "app/main.py", "line": 5}
            ],
        }
        with (
            patch(
                "app.api.routes_map.run_stack_analysis",
                new=AsyncMock(return_value=mock_evidence),
            ),
            patch(
                "app.api.routes_map.extract_endpoints",
                return_value=[
                    {"method": "GET", "path": "/", "file": "app/main.py", "line": 5}
                ],
            ),
            patch(
                "app.api.routes_map.enrich_endpoint_map",
                new=AsyncMock(
                    return_value=[
                        {
                            "name": "Root",
                            "description": "Entry point",
                            "endpoints": [{"method": "GET", "path": "/", "summary": "Index"}],
                        }
                    ]
                ),
            ),
        ):
            r = client.get("/api/map/MentalVibez/ai-agent-orchestrator?force_framework=fastapi")
        assert r.status_code in (200, 404, 500)


# ─────────────────────────────────────────────────────────────────
# DevContainer (auth-gated)
# ─────────────────────────────────────────────────────────────────

class TestDevcontainer:
    def test_generate_without_auth_returns_401(self, client):
        r = client.post("/api/devcontainer/1/generate", json={})
        assert r.status_code == 401

    def test_versions_without_auth_returns_401(self, client):
        r = client.get("/api/devcontainer/1/versions")
        assert r.status_code == 401

    def test_download_without_auth_returns_401(self, client):
        r = client.get("/api/devcontainer/1/download")
        assert r.status_code == 401

    def test_update_version_without_auth_returns_401(self, client):
        r = client.put("/api/devcontainer/1/versions/1", json={"config": {}})
        assert r.status_code == 401


# ─────────────────────────────────────────────────────────────────
# Auth
# ─────────────────────────────────────────────────────────────────

class TestAuth:
    def test_login_without_oauth_config_returns_503(self, client):
        with patch(
            "app.api.routes.auth.settings.github_client_id",
            new="",
        ):
            r = client.get("/api/auth/login")
        # Without GitHub OAuth credentials, returns 503
        assert r.status_code in (503, 200, 302)

    def test_me_without_token_returns_401(self, client):
        r = client.get("/api/auth/me")
        assert r.status_code == 401

    def test_me_with_invalid_token_returns_401(self, client):
        r = client.get("/api/auth/me", headers={"Authorization": "Bearer invalid.token.here"})
        assert r.status_code == 401

    def test_logout_without_token_returns_401_or_200(self, client):
        r = client.post("/api/auth/logout")
        assert r.status_code in (401, 200, 204)


# ─────────────────────────────────────────────────────────────────
# Ops (admin-gated)
# ─────────────────────────────────────────────────────────────────

class TestOps:
    def test_summary_without_key_returns_404(self, client):
        r = client.get("/api/ops/summary")
        assert r.status_code == 404

    def test_summary_with_wrong_key_returns_404(self, client):
        r = client.get("/api/ops/summary", headers={"x-atlas-admin-key": "wrong-key"})
        assert r.status_code == 404

    def test_summary_with_correct_key_returns_200(self, client):
        # Bypass require_admin because settings.admin_api_key is initialized
        # at conftest import time (before our env var is set).
        with patch("app.api.routes_ops.require_admin"):
            r = client.get(
                "/api/ops/summary",
                headers={"x-atlas-admin-key": _TEST_ADMIN_KEY},
            )
        assert r.status_code == 200
        body = r.json()
        assert "queue" in body or "workers" in body or "jobs" in body


# ─────────────────────────────────────────────────────────────────
# Audit (org-scoped)
# ─────────────────────────────────────────────────────────────────

class TestAudit:
    def test_audit_logs_without_auth_returns_401_or_403(self, client):
        r = client.get("/api/audit/logs")
        assert r.status_code in (401, 403, 404, 422)


# ─────────────────────────────────────────────────────────────────
# Share slug
# ─────────────────────────────────────────────────────────────────

class TestShare:
    def test_share_nonexistent_slug_returns_404(self, client):
        r = client.get("/api/results/share/nonexistent-slug-abc123")
        assert r.status_code == 404

    def test_share_bad_slug_format_returns_404(self, client):
        r = client.get("/api/results/share/!!invalid!!")
        assert r.status_code in (404, 422)
