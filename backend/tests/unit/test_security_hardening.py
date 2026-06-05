from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.core import security
from app.main import _validate_production_config


def _request(host: str, headers: dict[str, str] | None = None):
    return SimpleNamespace(
        client=SimpleNamespace(host=host),
        headers=headers or {},
    )


def test_client_ip_ignores_forwarded_for_from_untrusted_client(monkeypatch):
    monkeypatch.setattr(security.settings, "trusted_proxy_hosts", "127.0.0.1")

    request = _request("198.51.100.10", {"x-forwarded-for": "203.0.113.9"})

    assert security.client_ip(request) == "198.51.100.10"


def test_client_ip_uses_forwarded_for_from_trusted_proxy(monkeypatch):
    monkeypatch.setattr(security.settings, "trusted_proxy_hosts", "127.0.0.1")

    request = _request("127.0.0.1", {"x-forwarded-for": "203.0.113.9, 10.0.0.1"})

    assert security.client_ip(request) == "203.0.113.9"


def test_require_admin_hides_route_when_key_not_configured(monkeypatch):
    monkeypatch.setattr(security.settings, "admin_api_key", "")

    with pytest.raises(HTTPException) as exc:
        security.require_admin(_request("127.0.0.1"))

    assert exc.value.status_code == 404


def test_require_admin_accepts_matching_header(monkeypatch):
    monkeypatch.setattr(security.settings, "admin_api_key", "test-admin-key")

    security.require_admin(
        _request("127.0.0.1", {security.ADMIN_HEADER: "test-admin-key"})
    )


def test_production_config_rejects_blank_jwt_secret(monkeypatch):
    monkeypatch.setattr(security.settings, "environment", "production")
    monkeypatch.setattr(security.settings, "atlas_jwt_secret", "")

    with pytest.raises(RuntimeError, match="ATLAS_JWT_SECRET"):
        _validate_production_config()


def test_production_config_rejects_missing_redis(monkeypatch):
    monkeypatch.setattr(security.settings, "environment", "production")
    monkeypatch.setattr(security.settings, "atlas_jwt_secret", "a" * 32)
    monkeypatch.setattr(security.settings, "redis_url", "")

    with pytest.raises(RuntimeError, match="REDIS_URL"):
        _validate_production_config()


def test_production_config_accepts_required_security_settings(monkeypatch):
    monkeypatch.setattr(security.settings, "environment", "production")
    monkeypatch.setattr(security.settings, "atlas_jwt_secret", "a" * 32)
    monkeypatch.setattr(security.settings, "redis_url", "redis://localhost:6379/0")
    monkeypatch.setattr(security.settings, "sentry_dsn", "https://examplePublicKey@o0.ingest.sentry.io/0")
    monkeypatch.setattr(security.settings, "admin_api_key", "")

    _validate_production_config()


def test_production_config_rejects_missing_sentry(monkeypatch):
    monkeypatch.setattr(security.settings, "environment", "production")
    monkeypatch.setattr(security.settings, "atlas_jwt_secret", "a" * 32)
    monkeypatch.setattr(security.settings, "redis_url", "redis://localhost:6379/0")
    monkeypatch.setattr(security.settings, "sentry_dsn", "")

    with pytest.raises(RuntimeError, match="SENTRY_DSN"):
        _validate_production_config()


def test_public_route_limiter_enforces_burst_limit():
    limiter = security.PublicRouteLimiter()
    request = _request("198.51.100.10")

    async def run_checks():
        await limiter.check(
            request,
            route="analyze",
            burst_limit=1,
            burst_window_seconds=60,
            daily_limit=10,
            subject="owner/repo",
        )
        with pytest.raises(HTTPException) as exc:
            await limiter.check(
                request,
                route="analyze",
                burst_limit=1,
                burst_window_seconds=60,
                daily_limit=10,
                subject="owner/repo",
            )
        assert exc.value.status_code == 429

    import asyncio

    asyncio.run(run_checks())
