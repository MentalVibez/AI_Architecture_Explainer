import asyncio

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.services.intelligence_pipeline import (
    DEEP_SCAN_TIMEOUT_SECONDS,
    REVIEW_TIMEOUT_SECONDS,
    SCORECARD_TIMEOUT_SECONDS,
)

router = APIRouter()


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)) -> dict:
    # DB reachability — 2s timeout, never raises
    db_status = "ok"
    try:
        await asyncio.wait_for(db.execute(text("SELECT 1")), timeout=2.0)
    except Exception:
        db_status = "unreachable"

    return {
        "status": "ok",
        "service": "codebase-atlas-backend",
        "llm_configured": bool(settings.anthropic_api_key),
        "database": db_status,
        "intelligence": {
            "scan_timeout_s": DEEP_SCAN_TIMEOUT_SECONDS,
            "review_timeout_s": REVIEW_TIMEOUT_SECONDS,
            "scorecard_timeout_s": SCORECARD_TIMEOUT_SECONDS,
            "llm_review_enabled": bool(settings.anthropic_api_key),
            "max_files_per_repo": 800,
        },
    }
