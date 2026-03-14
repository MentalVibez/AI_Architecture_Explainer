from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import update

from app.api.routes_analysis import router as analysis_router
from app.api.routes_health import router as health_router
from app.api.routes_results import router as results_router
from app.core.config import settings
from app.core.database import AsyncSessionLocal, Base, engine
from app.models.analysis_job import AnalysisJob

limiter = Limiter(key_func=get_remote_address, default_limits=["10/minute"])


async def _recover_stale_jobs() -> None:
    """On startup, reset any jobs stuck in 'running' to 'failed'.

    BackgroundTasks run inside the uvicorn process — if the server
    restarts mid-analysis the job stays 'running' forever without this.
    """
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(AnalysisJob)
            .where(AnalysisJob.status == "running")
            .values(status="failed", error_message="Server restarted during analysis")
        )
        await db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _recover_stale_jobs()
    yield


app = FastAPI(
    title="Codebase Atlas API",
    description="AI-powered architecture analysis for public GitHub repositories",
    version="0.1.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(analysis_router)
app.include_router(results_router)
