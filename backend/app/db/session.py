"""
backend/app/db/session.py

SQLAlchemy engine and session factory — lazy initialization.

The engine and session factory are NOT created at module import time.
This means:
  - Tests can set DATABASE_URL before the first get_db() call
  - The app can start even if the DB is temporarily unreachable
  - Test overrides work cleanly via FastAPI dependency_overrides

get_db() is the only FastAPI dependency. Everything else (get_engine,
get_session_factory) is for internal use and Alembic's env.py.

Configuration:
  DATABASE_URL env var — full SQLAlchemy connection string.
  postgres:// is normalized to postgresql+psycopg2:// automatically.
  ATLAS_SQL_ECHO=true enables query logging (dev only).
"""

from __future__ import annotations

import logging
import os
from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

log = logging.getLogger(__name__)

_ENGINE        = None
_SESSION_FACTORY = None

def get_database_url() -> str:
    url = os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg2://atlas:atlas@localhost:5432/atlas_dev",
    )
    # Railway / Supabase compatibility
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)
    return url

def get_engine():
    """Return the singleton engine, creating it on first call."""
    global _ENGINE
    if _ENGINE is None:
        url  = get_database_url()
        echo = os.environ.get("ATLAS_SQL_ECHO", "false").lower() == "true"
        _ENGINE = create_engine(
            url,
            pool_size        = 5,
            max_overflow     = 10,
            pool_pre_ping    = True,
            pool_recycle     = 1800,
            echo             = echo,
        )
        log.debug("db_engine_created url=%s", url.split("@")[-1])  # log host only
    return _ENGINE

def get_session_factory() -> sessionmaker:
    """Return the singleton session factory, creating it on first call."""
    global _SESSION_FACTORY
    if _SESSION_FACTORY is None:
        _SESSION_FACTORY = sessionmaker(
            bind             = get_engine(),
            autocommit       = False,
            autoflush        = False,
            expire_on_commit = False,
        )
    return _SESSION_FACTORY

def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency. Yields one session per request, closes on exit.

    The session is NOT auto-committed. Route handlers commit explicitly.
    On any exception the session is rolled back before close.

    Usage:
        from app.db.session import get_db
        db: Session = Depends(get_db)
    """
    session = get_session_factory()()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

def reset_engine() -> None:
    """
    Dispose the engine and clear the factory. Used in tests to swap
    DATABASE_URL between test runs without process restart.
    """
    global _ENGINE, _SESSION_FACTORY
    if _ENGINE is not None:
        _ENGINE.dispose()
        _ENGINE        = None
        _SESSION_FACTORY = None

def check_db_connection() -> bool:
    """Verify the DB is reachable. Used by /health route."""
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        log.error("db_health_check_failed: %s", exc)
        return False
