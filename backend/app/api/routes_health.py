import asyncio

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db

router = APIRouter()


async def _check_database(db: AsyncSession) -> str:
    try:
        await asyncio.wait_for(db.execute(text("SELECT 1")), timeout=2.0)
        return "ok"
    except Exception:
        return "unreachable"


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)) -> JSONResponse:
    db_status = await _check_database(db)
    is_healthy = db_status == "ok"

    return JSONResponse(status_code=200 if is_healthy else 503, content={
        "status": "ok" if is_healthy else "degraded",
        "service": "codebase-atlas-backend",
    })
