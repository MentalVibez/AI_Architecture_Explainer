"""Semantic search across analysis chunk embeddings."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.auth import get_current_user
from app.core.database import get_db
from app.services.embedding_service import EmbeddingService

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("")
async def search_analyses(
    q: Annotated[str, Query(min_length=2, max_length=200, description="Search query")],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
):
    """Search analysis chunks by natural language query.

    Uses Postgres full-text search (tsvector) when available.
    Results are scoped to the authenticated user's org.
    """
    org_id: str = current_user["login"]
    if not q.strip():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Query cannot be blank")

    results = await EmbeddingService.search(session=db, query=q.strip(), org_id=org_id, limit=limit)

    # Also search the public pool (analyses run without auth)
    public_results = await EmbeddingService.search(session=db, query=q.strip(), org_id="public", limit=limit)

    # Merge, deduplicate by job_id+chunk_type, sort by score desc
    seen: set[tuple] = set()
    merged = []
    for row in results + public_results:
        key = (row["job_id"], row["chunk_type"])
        if key not in seen:
            seen.add(key)
            merged.append(row)
    merged.sort(key=lambda r: r.get("score", 0), reverse=True)

    return {
        "query": q.strip(),
        "results": merged[:limit],
        "total": len(merged),
    }
