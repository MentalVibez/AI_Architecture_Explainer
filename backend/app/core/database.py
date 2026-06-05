from collections.abc import AsyncGenerator

from fastapi import Depends, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

_database_url = settings.resolved_database_url
_connect_args = (
    {"statement_cache_size": 0}
    if _database_url.startswith("postgresql+asyncpg://")
    else {}
)

engine = create_async_engine(
    _database_url,
    echo=settings.is_development,
    future=True,
    connect_args=_connect_args,
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
async_session_factory = AsyncSessionLocal  # alias for workers


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def get_rls_db(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AsyncGenerator[AsyncSession, None]:
    """Like get_db but activates Postgres RLS by setting app.current_org_id.

    On SQLite (dev) the SET LOCAL is skipped — SQLite has no session variables.
    The org_id is populated by OrgContextMiddleware from the JWT cookie.
    """
    org_id: str = getattr(request.state, "org_id", "")
    if org_id and _database_url.startswith("postgresql"):
        await db.execute(text("SET LOCAL app.current_org_id = :org_id"), {"org_id": org_id})
    yield db
