"""
tests/conftest.py

Single source of test infrastructure.

DATABASE_URL must be set before any app import triggers get_engine().
Setting it here (before any other import) guarantees the lazy engine
picks up SQLite instead of reaching for Postgres.

SQLite gaps acknowledged:
  - JSONB → JSON (patched via SQLiteTypeCompiler)
  - UUID  → VARCHAR(36) (patched)
  - Partial unique indexes → ignored (SQLite supports WHERE but not all syntax)
  These tests validate routing, auth, and quota logic. A separate Postgres
  lane in CI covers schema fidelity.
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("ATLAS_JWT_SECRET", "test-secret-do-not-use-in-prod")

import hashlib
import secrets
import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes.routes_public_analysis import router as public_router
from app.db.session import get_db
from app.models.analysis import Account, Base

# ─────────────────────────────────────────────────────────
# SQLite compatibility patches — applied once at session start
# ─────────────────────────────────────────────────────────

def _patch_sqlite_types():
    from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler
    if not hasattr(SQLiteTypeCompiler, "visit_JSONB"):
        SQLiteTypeCompiler.visit_JSONB = lambda self, type_, **kw: "JSON"
    if not hasattr(SQLiteTypeCompiler, "visit_UUID"):
        SQLiteTypeCompiler.visit_UUID = lambda self, type_, **kw: "VARCHAR(36)"

_patch_sqlite_types()


# ─────────────────────────────────────────────────────────
# Shared in-memory engine (StaticPool → one connection, all threads)
# ─────────────────────────────────────────────────────────

_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestSession = sessionmaker(bind=_engine, autoflush=False, autocommit=False)


# ─────────────────────────────────────────────────────────
# Table lifecycle — session scope, created once
# ─────────────────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def create_tables():
    Base.metadata.create_all(bind=_engine)
    yield
    Base.metadata.drop_all(bind=_engine)


# ─────────────────────────────────────────────────────────
# Per-test DB session — savepoint pattern for commit-safe isolation
#
# Why savepoints instead of plain rollback:
#   reset_quota_if_needed() calls session.commit() inside the handler.
#   A plain rollback fixture would conflict: the session has already
#   committed, so rollback() at teardown either no-ops or errors.
#
#   Savepoint pattern:
#     1. Begin an outer transaction (the test boundary)
#     2. Create a savepoint before yielding the session
#     3. Override session.commit() to release+re-create the savepoint
#        instead of committing to the DB — keeps state visible within
#        the test but never durably writes to SQLite
#     4. Roll back to the outer transaction at teardown — all state gone
#
#   This means: production code that calls db.commit() works correctly
#   within the test, sees its own writes, but leaves no durable data.
# ─────────────────────────────────────────────────────────

@pytest.fixture
def db(create_tables) -> Generator[Session, None, None]:
    connection = _engine.connect()
    trans      = connection.begin()          # outer transaction — test boundary

    session = _TestSession(bind=connection)
    session.begin_nested()                   # first savepoint

    # Intercept commit() calls from production code:
    # release the current savepoint and open a fresh one so subsequent
    # reads in the same test see the "committed" data, but the outer
    # transaction is never durably written.
    original_commit = session.commit

    def _savepoint_commit():
        # Flush pending writes to the connection (within outer transaction)
        session.flush()
        # Open a new savepoint BEFORE expiring so the reload sees flushed state
        session.begin_nested()
        session.expire_all()                 # force re-read from connection on next access

    session.commit = _savepoint_commit

    try:
        yield session
    finally:
        session.commit = original_commit     # restore before close
        session.close()
        trans.rollback()                     # wipe all test data
        connection.close()


# ─────────────────────────────────────────────────────────
# FastAPI test app — dependency override injects test session
# ─────────────────────────────────────────────────────────

def _build_app() -> FastAPI:
    app = FastAPI(title="Atlas Test App")
    app.include_router(public_router)

    # Minimal protected test route — lets us test quota enforcement
    # via HTTP without needing a real /api/public/analyze submission
    from fastapi import Depends

    from app.api.deps import check_quota, resolve_account
    from app.services.policy.tier_policy import JobScope

    @app.get("/_test/public-quota")
    def _test_public_quota(
        ctx=Depends(resolve_account),
        _q=Depends(check_quota(JobScope.PUBLIC)),
    ):
        return {"ok": True, "plan": ctx.plan.value, "account_id": ctx.account_id}

    @app.get("/_test/private-quota")
    def _test_private_quota(
        ctx=Depends(resolve_account),
        _q=Depends(check_quota(JobScope.PRIVATE)),
    ):
        return {"ok": True}

    @app.get("/_test/auth-required")
    def _test_auth_required(
        ctx=Depends(require_account_dep()),
    ):
        return {"ok": True, "account_id": ctx.account_id}

    return app


def require_account_dep():
    from app.api.deps import require_account
    return require_account


@pytest.fixture(scope="session")
def _base_app():
    return _build_app()


@pytest.fixture
def client(db, _base_app) -> Generator[TestClient, None, None]:
    def _override_get_db():
        try:
            yield db
        finally:
            pass

    _base_app.dependency_overrides[get_db] = _override_get_db
    with TestClient(_base_app, raise_server_exceptions=False) as c:
        yield c
    _base_app.dependency_overrides.clear()


# ─────────────────────────────────────────────────────────
# Account factory
# ─────────────────────────────────────────────────────────

def make_account(
    db: Session,
    plan: str = "free",
    daily_public_count: int = 0,
    daily_private_count: int = 0,
    daily_verified_count: int = 0,
    with_api_key: bool = False,
    quota_reset_at: datetime | None = None,
    verified_credits_remaining: int = 0,
    is_active: bool = True,
) -> tuple[Account, str | None]:
    """
    Create and persist a test Account. Returns (account, raw_api_key).
    raw_api_key is None if with_api_key=False.
    """
    raw_key = key_hash = None
    if with_api_key:
        raw_key  = secrets.token_urlsafe(32)
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    account = Account(
        id                         = str(uuid.uuid4()),
        email                      = f"test-{uuid.uuid4()}@atlas.test",
        plan                       = plan,
        is_active                  = is_active,
        api_key_hash               = key_hash,
        daily_public_count         = daily_public_count,
        daily_private_count        = daily_private_count,
        daily_verified_count       = daily_verified_count,
        verified_credits_remaining = verified_credits_remaining,
        quota_reset_at             = quota_reset_at,
    )
    db.add(account)
    db.commit()
    return account, raw_key


def make_jwt(account_id: str, expired: bool = False) -> str:
    """Generate a signed test JWT."""
    from jose import jwt
    now   = datetime.now(UTC)
    delta = timedelta(hours=-2) if expired else timedelta(hours=1)
    return jwt.encode(
        {"sub": account_id, "exp": now + delta},
        os.environ["ATLAS_JWT_SECRET"],
        algorithm="HS256",
    )


# Export helpers so test modules can import from conftest
__all__ = ["make_account", "make_jwt"]
