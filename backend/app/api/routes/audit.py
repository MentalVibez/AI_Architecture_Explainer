"""API routes for audit logging and compliance."""
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.auth import get_current_user
from app.core.database import get_rls_db
from app.schemas.devcontainer import AuditLogListResponse, AuditLogResponse
from app.services.audit_service import AuditService

router = APIRouter(prefix="/api/audit", tags=["audit"])


def _to_response(log) -> AuditLogResponse:
    return AuditLogResponse(
        id=log.id,
        user_id=log.user_id,
        org_id=log.org_id,
        action=log.action,
        resource_type=log.resource_type,
        resource_id=log.resource_id,
        result=log.result,
        created_at=log.created_at,
    )


@router.get("/logs", response_model=AuditLogListResponse)
async def get_audit_logs(
    db: Annotated[AsyncSession, Depends(get_rls_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    """Return paginated audit logs for the authenticated user's org."""
    org_id: str = current_user["login"]
    logs, total = await AuditService.get_org_audit_logs(db, org_id=org_id, offset=offset, limit=limit)
    return AuditLogListResponse(
        logs=[_to_response(log) for log in logs],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/logs/action/{action}", response_model=list[AuditLogResponse])
async def get_logs_by_action(
    action: str,
    db: Annotated[AsyncSession, Depends(get_rls_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    limit: int = Query(100, ge=1, le=500),
):
    """Return logs for a specific action within the authenticated user's org."""
    org_id: str = current_user["login"]
    logs = await AuditService.get_action_logs(db, org_id=org_id, action=action, limit=limit)
    return [_to_response(log) for log in logs]


@router.get("/logs/user/{user_id}", response_model=list[AuditLogResponse])
async def get_logs_by_user(
    user_id: str,
    db: Annotated[AsyncSession, Depends(get_rls_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    limit: int = Query(100, ge=1, le=500),
):
    """Return all actions by a specific user within the authenticated user's org."""
    org_id: str = current_user["login"]
    logs = await AuditService.get_user_activity(db, org_id=org_id, user_id=user_id, limit=limit)
    return [_to_response(log) for log in logs]
