"""
tests/unit/test_audit_service.py

Tests for AuditService using an in-memory async SQLite session.

Coverage:
  - log_action creates an AuditLog row with correct fields
  - log_action raises ValueError when org_id is missing
  - get_org_audit_logs returns only the org's rows + correct total count
  - get_action_logs filters by action type within org
  - get_user_activity filters by user_id within org
  - Logs from a different org are invisible (application-layer isolation)
"""
from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Import models so their tables are registered against Base before create_all
import app.models.analysis_job  # noqa: F401
import app.models.analysis_result  # noqa: F401
from app.core.database import Base
from app.services.audit_service import AuditService

# ── shared async in-memory DB fixture ────────────────────────────────────────

@pytest.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite://", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session

    await engine.dispose()


# ── log_action ────────────────────────────────────────────────────────────────

async def test_log_action_creates_audit_log(db):
    log = await AuditService.log_action(
        db,
        action="generated_devcontainer",
        org_id="acme",
        user_id="alice",
        resource_type="devcontainer",
        resource_id="dc-001",
        details={"job_id": 42, "version": 1},
    )
    await db.commit()

    assert log.id  # UUID was assigned
    assert log.action == "generated_devcontainer"
    assert log.org_id == "acme"
    assert log.user_id == "alice"
    assert log.resource_type == "devcontainer"
    assert log.details == {"job_id": 42, "version": 1}
    assert log.result == "success"


async def test_log_action_default_result_is_success(db):
    log = await AuditService.log_action(db, action="viewed_job", org_id="acme")
    assert log.result == "success"


async def test_log_action_raises_when_org_id_missing(db):
    with pytest.raises(ValueError, match="org_id is required"):
        await AuditService.log_action(db, action="viewed_job", org_id="")


async def test_log_action_stores_error_result(db):
    log = await AuditService.log_action(
        db,
        action="generate_failed",
        org_id="acme",
        result="error",
        error_message="upstream timeout",
    )
    assert log.result == "error"
    assert log.error_message == "upstream timeout"


# ── get_org_audit_logs ────────────────────────────────────────────────────────

async def test_get_org_audit_logs_returns_only_own_org(db):
    await AuditService.log_action(db, action="a1", org_id="acme")
    await AuditService.log_action(db, action="a2", org_id="acme")
    await AuditService.log_action(db, action="other", org_id="other-org")
    await db.commit()

    logs, total = await AuditService.get_org_audit_logs(db, org_id="acme")
    assert total == 2
    assert all(log.org_id == "acme" for log in logs)


async def test_get_org_audit_logs_pagination(db):
    for i in range(5):
        await AuditService.log_action(db, action=f"action-{i}", org_id="acme")
    await db.commit()

    logs, total = await AuditService.get_org_audit_logs(db, org_id="acme", limit=2, offset=0)
    assert total == 5
    assert len(logs) == 2


async def test_get_org_audit_logs_empty_org(db):
    logs, total = await AuditService.get_org_audit_logs(db, org_id="nobody")
    assert logs == []
    assert total == 0


# ── get_action_logs ───────────────────────────────────────────────────────────

async def test_get_action_logs_filters_by_action(db):
    await AuditService.log_action(db, action="generated_devcontainer", org_id="acme")
    await AuditService.log_action(db, action="generated_devcontainer", org_id="acme")
    await AuditService.log_action(db, action="downloaded_devcontainer", org_id="acme")
    await db.commit()

    logs = await AuditService.get_action_logs(db, org_id="acme", action="generated_devcontainer")
    assert len(logs) == 2
    assert all(log.action == "generated_devcontainer" for log in logs)


async def test_get_action_logs_does_not_cross_org(db):
    await AuditService.log_action(db, action="generated_devcontainer", org_id="acme")
    await AuditService.log_action(db, action="generated_devcontainer", org_id="other")
    await db.commit()

    logs = await AuditService.get_action_logs(db, org_id="acme", action="generated_devcontainer")
    assert len(logs) == 1


# ── get_user_activity ─────────────────────────────────────────────────────────

async def test_get_user_activity_returns_only_that_user(db):
    await AuditService.log_action(db, action="a", org_id="acme", user_id="alice")
    await AuditService.log_action(db, action="b", org_id="acme", user_id="alice")
    await AuditService.log_action(db, action="c", org_id="acme", user_id="bob")
    await db.commit()

    logs = await AuditService.get_user_activity(db, org_id="acme", user_id="alice")
    assert len(logs) == 2
    assert all(log.user_id == "alice" for log in logs)


async def test_get_user_activity_does_not_cross_org(db):
    await AuditService.log_action(db, action="a", org_id="acme", user_id="alice")
    await AuditService.log_action(db, action="b", org_id="other", user_id="alice")
    await db.commit()

    logs = await AuditService.get_user_activity(db, org_id="acme", user_id="alice")
    assert len(logs) == 1
