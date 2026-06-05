"""Audit logging service for SOC2 compliance."""
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.devcontainer import AuditLog


class AuditService:
    """Log all user actions for compliance and security."""

    @staticmethod
    async def log_action(
        session: AsyncSession,
        action: str,
        org_id: str,
        user_id: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        result: str = "success",
        error_message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditLog:
        """Log a user action.

        Args:
            session: Database session
            action: Action name (e.g., "viewed_analysis", "generated_devcontainer")
            org_id: Organization ID (required for org isolation)
            user_id: User ID or GitHub username
            resource_type: Type of resource (job, devcontainer, user)
            resource_id: ID of the resource
            ip_address: IP address of requester
            user_agent: User-Agent header
            result: Result status (success, permission_denied, error)
            error_message: Error details if failed
            details: Additional metadata

        Returns:
            Created AuditLog entry

        Raises:
            ValueError: If org_id is missing (org isolation breach)
        """
        if not org_id:
            raise ValueError("org_id is required for audit logging")

        log_entry = AuditLog(
            user_id=user_id,
            org_id=org_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            user_agent=user_agent,
            result=result,
            error_message=error_message,
            details=details or {},
        )

        session.add(log_entry)
        await session.flush()  # Ensure written to DB
        return log_entry

    @staticmethod
    async def get_org_audit_logs(
        session: AsyncSession,
        org_id: str,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[list[AuditLog], int]:
        """Fetch audit logs for an organization (with RLS).

        Args:
            session: Database session
            org_id: Organization ID (enforced by RLS)
            offset: Pagination offset
            limit: Max results (capped at 500)

        Returns:
            Tuple of (logs, total_count)
        """
        from sqlalchemy import func, select

        # Enforce org isolation at application layer (RLS should also enforce)
        query = select(AuditLog).where(AuditLog.org_id == org_id).order_by(AuditLog.created_at.desc())

        # Get total count
        count_result = await session.execute(select(func.count(AuditLog.id)).where(AuditLog.org_id == org_id))
        total = count_result.scalar() or 0

        # Paginate
        query = query.offset(offset).limit(min(limit, 500))
        result = await session.execute(query)
        logs = result.scalars().all()

        return logs, total

    @staticmethod
    async def get_action_logs(
        session: AsyncSession,
        org_id: str,
        action: str,
        limit: int = 100,
    ) -> list[AuditLog]:
        """Fetch logs for a specific action type.

        Useful for: "Find all times someone generated a devcontainer"
        """
        from sqlalchemy import select

        query = (
            select(AuditLog)
            .where(AuditLog.org_id == org_id, AuditLog.action == action)
            .order_by(AuditLog.created_at.desc())
            .limit(min(limit, 500))
        )

        result = await session.execute(query)
        return result.scalars().all()

    @staticmethod
    async def get_user_activity(
        session: AsyncSession,
        org_id: str,
        user_id: str,
        limit: int = 100,
    ) -> list[AuditLog]:
        """Fetch all actions by a specific user."""
        from sqlalchemy import select

        query = (
            select(AuditLog)
            .where(AuditLog.org_id == org_id, AuditLog.user_id == user_id)
            .order_by(AuditLog.created_at.desc())
            .limit(min(limit, 500))
        )

        result = await session.execute(query)
        return result.scalars().all()
