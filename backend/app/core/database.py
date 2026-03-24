from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

engine = create_async_engine(
    settings.resolved_database_url,
    echo=settings.is_development,
    future=True,
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
async_session_factory = AsyncSessionLocal  # alias for workers


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
