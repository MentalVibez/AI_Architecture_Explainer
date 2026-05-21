"""app/api/routes_share.py

Resolves a share slug to the result type and canonical ID so the
frontend can redirect to the appropriate result page.

GET /api/r/{slug} → {"type": "atlas"|"review", "id": "<id>"}
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.analysis_result import AtlasResult
from app.models.review import Review

router = APIRouter(prefix="/api/r", tags=["share"])


class SlugResolution(BaseModel):
    type: str
    id: str


@router.get("/{slug}", response_model=SlugResolution)
async def resolve_slug(slug: str, db: AsyncSession = Depends(get_db)) -> SlugResolution:
    atlas_row = (
        await db.execute(select(AtlasResult.id).where(AtlasResult.share_slug == slug))
    ).scalar_one_or_none()
    if atlas_row is not None:
        return SlugResolution(type="atlas", id=str(atlas_row))

    review_row = (
        await db.execute(select(Review.id).where(Review.share_slug == slug))
    ).scalar_one_or_none()
    if review_row is not None:
        return SlugResolution(type="review", id=str(review_row))

    raise HTTPException(status_code=404, detail="Share link not found")
