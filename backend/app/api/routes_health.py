import asyncio

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.services.github_service import github_auth_snapshot
from app.services.intelligence_pipeline import (
    DEEP_SCAN_TIMEOUT_SECONDS,
    REVIEW_TIMEOUT_SECONDS,
    SCORECARD_TIMEOUT_SECONDS,
)

router = APIRouter()


async def _check_database(db: AsyncSession) -> str:
    try:
        await asyncio.wait_for(db.execute(text("SELECT 1")), timeout=2.0)
        return "ok"
    except Exception:
        return "unreachable"


def _llm_status() -> str:
    """Health must stay local; report config state without probing external vendors."""
    return "ok" if settings.anthropic_api_key else "misconfigured"


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)) -> JSONResponse:
    db_status = await _check_database(db)
    llm_status = _llm_status()
    is_healthy = db_status == "ok"

    return JSONResponse(status_code=200 if is_healthy else 503, content={
        "status": "ok" if is_healthy else "degraded",
        "service": "codebase-atlas-backend",
        "llm": llm_status,
        "llm_check_mode": "config_only",
        "database": db_status,
        "github": github_auth_snapshot(),
        "jobs": {
            "execution_mode": "database_worker_queue",
            "topology": "separate_web_and_worker_processes",
            "restart_recovery": True,
            "worker_health_source": "/api/ops/summary",
        },
        "intelligence": {
            "scan_timeout_s": DEEP_SCAN_TIMEOUT_SECONDS,
            "review_timeout_s": REVIEW_TIMEOUT_SECONDS,
            "scorecard_timeout_s": SCORECARD_TIMEOUT_SECONDS,
            "llm_review_enabled": bool(settings.anthropic_api_key),
            "max_files_per_repo": 800,
        },
    })
