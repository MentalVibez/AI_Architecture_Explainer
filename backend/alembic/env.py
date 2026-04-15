import asyncio
from logging.config import fileConfig

from sqlalchemy import MetaData, pool
from sqlalchemy.ext.asyncio import async_engine_from_config

import app.models  # noqa: F401 — ensure all existing models are registered
import app.models.analysis  # noqa: F401 — registers account/workspace metadata
from alembic import context
from app.core.config import settings
from app.core.database import Base as CoreBase
from app.models.analysis import Base as AnalysisBase

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override the sqlalchemy.url from our settings
config.set_main_option("sqlalchemy.url", settings.resolved_database_url)

# Merge both metadata objects so autogenerate sees all tables.
# CoreBase: core product models (analysis_job, analysis_result, repo, review, etc.)
# AnalysisBase: account/workspace models that still live in app.models.analysis
_combined = MetaData()
for _table in (
    list(CoreBase.metadata.tables.values())
    + list(AnalysisBase.metadata.tables.values())
):
    # tometadata copies table definitions without duplicating if already present
    if _table.name not in _combined.tables:
        _table.tometadata(_combined)
target_metadata = _combined


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
