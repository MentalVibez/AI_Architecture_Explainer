from __future__ import annotations

import os
import socket
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.database import AsyncSessionLocal
from app.models.worker_heartbeat import WorkerHeartbeat


@dataclass(frozen=True, slots=True)
class WorkerIdentity:
    worker_id: str = field(
        default_factory=lambda: (
            f"{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:8]}"
        )
    )
    hostname: str = field(default_factory=socket.gethostname)
    process_id: int = field(default_factory=os.getpid)
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))


async def record_worker_heartbeat(
    *,
    identity: WorkerIdentity,
    queues: tuple[str, ...],
    status: str = "running",
    session_factory: async_sessionmaker[AsyncSession] = AsyncSessionLocal,
) -> None:
    queue_label = ",".join(queues)
    now = datetime.now(UTC)

    async with session_factory() as db:
        heartbeat = await db.get(WorkerHeartbeat, identity.worker_id)
        if heartbeat is None:
            heartbeat = WorkerHeartbeat(
                worker_id=identity.worker_id,
                hostname=identity.hostname,
                process_id=identity.process_id,
                queues=queue_label,
                status=status,
                started_at=identity.started_at,
                last_seen_at=now,
            )
            db.add(heartbeat)
        else:
            heartbeat.hostname = identity.hostname
            heartbeat.process_id = identity.process_id
            heartbeat.queues = queue_label
            heartbeat.status = status
            heartbeat.last_seen_at = now

        await db.commit()


async def list_worker_heartbeats(
    *,
    session: AsyncSession,
) -> list[WorkerHeartbeat]:
    rows = await session.execute(
        select(WorkerHeartbeat).order_by(WorkerHeartbeat.last_seen_at.desc())
    )
    return list(rows.scalars().all())
