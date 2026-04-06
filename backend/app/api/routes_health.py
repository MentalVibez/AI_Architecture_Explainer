import asyncio

import httpx
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


async def _check_anthropic() -> str:
    """Probe the Anthropic API with a lightweight models list request.

    Returns "ok", "misconfigured" (no key), or "unreachable" (network/auth error).
    Times out after 3s so it never blocks the health response.
    """
    if not settings.anthropic_api_key:
        return "misconfigured"
    try:
        base = (settings.anthropic_base_url or "https://api.anthropic.com").rstrip("/")
        headers = {
            "x-api-key": settings.anthropic_api_key,
            "anthropic-version": "2023-06-01",
        }
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{base}/v1/models", headers=headers)
        return "ok" if r.status_code < 500 else "unreachable"
    except Exception:
        return "unreachable"


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)) -> dict:
    # Run DB and Anthropic probes concurrently — 2s cap on DB, 3s on Anthropic
    db_status = "ok"
    try:
        await asyncio.wait_for(db.execute(text("SELECT 1")), timeout=2.0)
    except Exception:
        db_status = "unreachable"

    llm_status = await _check_anthropic()

    return {
        "status": "ok",
        "service": "codebase-atlas-backend",
        "llm": llm_status,
        "database": db_status,
        "intelligence": {
            "scan_timeout_s": DEEP_SCAN_TIMEOUT_SECONDS,
            "review_timeout_s": REVIEW_TIMEOUT_SECONDS,
            "scorecard_timeout_s": SCORECARD_TIMEOUT_SECONDS,
            "llm_review_enabled": llm_status == "ok",
            "max_files_per_repo": 800,
        },
    }
