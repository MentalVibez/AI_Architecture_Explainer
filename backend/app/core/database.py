from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

_database_url = settings.resolved_database_url
_connect_args = (
    {"statement_cache_size": 0}
    if "pgbouncer=true" in _database_url and _database_url.startswith("postgresql+asyncpg://")
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
