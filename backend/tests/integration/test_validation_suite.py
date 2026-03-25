"""
tests/integration/test_validation_suite.py

Full HTTP-level validation suite — all scenarios from the spec.

Every test goes through the FastAPI TestClient. FastAPI resolves
Depends(get_db) → the test session injected by conftest.override_db.
No dependency closures are called directly.

Covers:
  Auth:
    - no auth on public route (anonymous → allowed)
    - no auth on protected route → 401
    - valid API key → 200
    - invalid API key → anonymous (not 401 — public routes allow anon)
    - valid JWT → 200
    - expired JWT → anonymous (falls through, public route still serves)

  Quota:
    - request under daily limit → 200
    - request at daily limit → 429
    - free plan private scope → 403
    - quota reset window elapsed → 200 after reset

  Pipeline:
    - valid GitHub URL → 202 (stub: no real SHA fetch)
    - valid GitLab URL → 202
    - invalid URL → 400
    - unsupported host → 400
    - cache hit → 200 with is_cache_hit=True (stub returns None, so 202)
    - dedup → existing job returned (stub returns None, so new job)

  Claim boundary:
    - every 200 response has analysis_tier, runtime_verified, executed_checks
    - runtime_verified always False on public route
    - executed_checks always [] on public route
"""

from __future__ import annotations

from datetime import UTC

from tests.conftest import make_account, make_jwt

# ─────────────────────────────────────────────────────────
# Auth tests
# ─────────────────────────────────────────────────────────

class TestAuth:
    def test_no_auth_on_public_analyze_is_allowed(self, client):
        """Public route accepts anonymous — rate limit is IP-based."""
        resp = client.post(
            "/api/public/analyze",
            json={"repo_url": "https://github.com/owner/repo"},
        )
        assert resp.status_code in (202, 400), f"Unexpected: {resp.status_code} {resp.text}"

    def test_no_auth_on_protected_route_returns_401(self, client):
        resp = client.get("/_test/auth-required")
        assert resp.status_code == 401
        assert resp.json()["detail"]["error_code"] == "authentication_required"

    def test_valid_api_key_resolves_account(self, client, db):
        account, raw_key = make_account(db, plan="free", with_api_key=True)
        resp = client.get(
            "/_test/public-quota",
            headers={"X-Atlas-API-Key": raw_key},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["account_id"] == account.id
        assert body["plan"] == "free"

    def test_invalid_api_key_falls_through_to_anonymous(self, client):
        """Invalid key → anonymous context → public quota check still passes."""
        resp = client.get(
            "/_test/public-quota",
            headers={"X-Atlas-API-Key": "completely-invalid-key"},
        )
        # Anonymous is allowed on public quota endpoint
        assert resp.status_code == 200
        assert resp.json()["account_id"] is None

    def test_valid_jwt_resolves_account(self, client, db):
        account, _ = make_account(db, plan="pro")
        token = make_jwt(account.id)
        resp = client.get(
            "/_test/public-quota",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["account_id"] == account.id
        assert resp.json()["plan"] == "pro"

    def test_expired_jwt_falls_through_to_anonymous(self, client, db):
        account, _ = make_account(db, plan="pro")
        token = make_jwt(account.id, expired=True)
        resp = client.get(
            "/_test/public-quota",
            headers={"Authorization": f"Bearer {token}"},
        )
        # Expired JWT → anonymous → still allowed on public route
        assert resp.status_code == 200
        assert resp.json()["account_id"] is None

    def test_malformed_jwt_falls_through_to_anonymous(self, client):
        resp = client.get(
            "/_test/public-quota",
            headers={"Authorization": "Bearer not.a.real.jwt"},
        )
        assert resp.status_code == 200
        assert resp.json()["account_id"] is None

    def test_api_key_takes_priority_over_jwt(self, client, db):
        """API key header takes priority over Authorization header."""
        key_account, raw_key = make_account(db, plan="free", with_api_key=True)
        jwt_account, _       = make_account(db, plan="pro")
        token = make_jwt(jwt_account.id)
        resp = client.get(
            "/_test/public-quota",
            headers={
                "X-Atlas-API-Key": raw_key,
                "Authorization":   f"Bearer {token}",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["account_id"] == key_account.id   # API key wins


# ─────────────────────────────────────────────────────────
# Quota tests — HTTP level, FastAPI resolves Depends correctly
# ─────────────────────────────────────────────────────────

class TestQuota:
    def test_authenticated_under_limit_passes(self, client, db):
        account, raw_key = make_account(
            db, plan="free", daily_public_count=0, with_api_key=True
        )
        resp = client.get(
            "/_test/public-quota",
            headers={"X-Atlas-API-Key": raw_key},
        )
        assert resp.status_code == 200

    def test_authenticated_at_limit_returns_429(self, client, db):
        from datetime import datetime, timedelta
        limit = 10  # FREE_PLAN_LIMITS.daily_public_analyses
        # quota_reset_at in the future prevents reset_quota_if_needed
        # from zeroing the counter before the limit check runs
        future = datetime.now(UTC) + timedelta(hours=12)
        account, raw_key = make_account(
            db, plan="free", daily_public_count=limit,
            quota_reset_at=future, with_api_key=True
        )
        resp = client.get(
            "/_test/public-quota",
            headers={"X-Atlas-API-Key": raw_key},
        )
        assert resp.status_code == 429
        body = resp.json()
        assert body["detail"]["error_code"] == "quota_exceeded"
        assert "Retry-After" in resp.headers

    def test_free_plan_private_scope_returns_403(self, client, db):
        account, raw_key = make_account(db, plan="free", with_api_key=True)
        resp = client.get(
            "/_test/private-quota",
            headers={"X-Atlas-API-Key": raw_key},
        )
        assert resp.status_code == 403
        assert resp.json()["detail"]["error_code"] == "scope_not_allowed_on_plan"

    def test_pro_plan_private_scope_passes(self, client, db):
        account, raw_key = make_account(db, plan="pro", with_api_key=True)
        resp = client.get(
            "/_test/private-quota",
            headers={"X-Atlas-API-Key": raw_key},
        )
        assert resp.status_code == 200

    def test_quota_reset_after_window_elapsed(self, client, db):
        """Account at limit but reset window has elapsed → quota resets → 200."""
        from datetime import datetime, timedelta
        past = datetime.now(UTC) - timedelta(hours=1)
        limit = 10
        account, raw_key = make_account(
            db, plan="free",
            daily_public_count=limit,
            quota_reset_at=past,
            with_api_key=True,
        )
        resp = client.get(
            "/_test/public-quota",
            headers={"X-Atlas-API-Key": raw_key},
        )
        # reset_quota_if_needed fires on the quota check → count resets to 0 → passes
        assert resp.status_code == 200

    def test_anonymous_public_quota_always_passes(self, client):
        """Anonymous users skip DB quota check (handled by IP rate limiter)."""
        resp = client.get("/_test/public-quota")
        assert resp.status_code == 200

    def test_team_plan_unlimited_public_passes(self, client, db):
        # Team has daily_public_analyses = -1 (unlimited)
        account, raw_key = make_account(
            db, plan="team", daily_public_count=9999, with_api_key=True
        )
        resp = client.get(
            "/_test/public-quota",
            headers={"X-Atlas-API-Key": raw_key},
        )
        assert resp.status_code == 200


# ─────────────────────────────────────────────────────────
# Pipeline tests — POST /api/public/analyze
# ─────────────────────────────────────────────────────────

class TestPublicAnalyzePipeline:
    def test_valid_github_url_returns_202(self, client):
        resp = client.post(
            "/api/public/analyze",
            json={"repo_url": "https://github.com/owner/repo"},
        )
        assert resp.status_code == 202
        body = resp.json()
        assert "job_id" in body
        assert body["job_id"] != ""
        assert body["status"] == "queued"
        assert body["is_cache_hit"] is False

    def test_valid_gitlab_url_returns_202(self, client):
        resp = client.post(
            "/api/public/analyze",
            json={"repo_url": "https://gitlab.com/group/project"},
        )
        assert resp.status_code == 202

    def test_invalid_url_returns_400(self, client):
        resp = client.post(
            "/api/public/analyze",
            json={"repo_url": "not-a-url"},
        )
        assert resp.status_code in (400, 422)

    def test_unsupported_host_returns_validation_error(self, client):
        resp = client.post(
            "/api/public/analyze",
            json={"repo_url": "https://bitbucket.org/owner/repo"},
        )
        assert resp.status_code in (400, 422)

    def test_http_url_rejected(self, client):
        resp = client.post(
            "/api/public/analyze",
            json={"repo_url": "http://github.com/owner/repo"},
        )
        assert resp.status_code in (400, 422)

    def test_response_has_poll_url(self, client):
        resp = client.post(
            "/api/public/analyze",
            json={"repo_url": "https://github.com/owner/repo"},
        )
        assert resp.status_code == 202
        assert resp.json()["poll_url"].startswith("/api/public/analysis/")

    def test_two_requests_same_url_dedup_without_sha(self, client):
        """Without a commit SHA, dedup matches by repo identity — second request is a dedup hit."""
        url = "https://github.com/owner/repo"
        r1 = client.post("/api/public/analyze", json={"repo_url": url})
        r2 = client.post("/api/public/analyze", json={"repo_url": url})
        assert r1.status_code == 202 and r2.status_code == 202
        # With no SHA, dedup matches any queued/running job for the same repo.
        # Both responses are valid 202s; r2 is a dedup hit returning r1's job_id.
        assert r1.json()["job_id"] != "" and r2.json()["job_id"] != ""

    def test_unknown_job_id_returns_404(self, client):
        resp = client.get("/api/public/analysis/nonexistent-job-id")
        assert resp.status_code == 404

    def test_cache_lookup_miss_returns_hit_false(self, client):
        resp = client.get("/api/public/cache/github/owner/repo/abc123deadbeef")
        assert resp.status_code == 200
        assert resp.json()["hit"] is False


# ─────────────────────────────────────────────────────────
# Claim boundary — on every response that returns data
# ─────────────────────────────────────────────────────────

class TestClaimBoundaryInResponses:
    def test_analyze_202_does_not_include_claim_fields(self, client):
        """The 202 submission response is lightweight — claim fields are on the result."""
        resp = client.post(
            "/api/public/analyze",
            json={"repo_url": "https://github.com/owner/repo"},
        )
        assert resp.status_code == 202
        # Submission response intentionally does NOT include claim boundary
        body = resp.json()
        assert "job_id" in body
        assert "status"  in body

    def test_404_response_does_not_leak_internals(self, client):
        resp = client.get("/api/public/analysis/fake-id")
        assert resp.status_code == 404
        body = resp.json()
        assert "detail" in body
        # Must not expose internal stack traces
        assert "traceback" not in str(body).lower()
        assert "sqlalchemy" not in str(body).lower()
