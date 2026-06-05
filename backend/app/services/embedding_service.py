"""Chunk extraction and text-based semantic search for analysis results.

Embeddings (vector(1536) column) are populated when a VOYAGE_API_KEY is
configured. Without it, chunk_text is still stored and full-text search
uses Postgres tsvector / SQLite LIKE.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.devcontainer import AnalysisEmbedding

logger = logging.getLogger(__name__)


# ── Chunk extraction ──────────────────────────────────────────────────────────

def _flatten_frameworks(detected_stack: dict) -> list[str]:
    names = []
    for items in detected_stack.values():
        for item in items:
            name = item.get("name", "") if isinstance(item, dict) else item
            if name:
                names.append(name)
    return names


def extract_chunks(
    result_id: int,
    detected_stack: dict,
    dependencies: dict,
    developer_summary: str | None,
    repo_owner: str = "",
    repo_name: str = "",
) -> list[tuple[str, str]]:
    """Return (chunk_type, chunk_text) pairs suitable for full-text indexing.

    Called with data from AtlasResult — no DB access needed.
    """
    chunks: list[tuple[str, str]] = []
    repo_label = f"{repo_owner}/{repo_name}" if repo_owner else str(result_id)

    # Architecture summary (richest signal for search)
    if developer_summary:
        chunks.append(("architecture", developer_summary[:800]))

    # Stack + frameworks
    fw = _flatten_frameworks(detected_stack)
    if fw:
        chunks.append(("stack", f"{repo_label} uses {', '.join(fw)}"))

    # NPM dependencies
    npm = dependencies.get("npm", [])
    if npm:
        chunks.append(("dependency", f"npm: {', '.join(str(d) for d in npm[:30])}"))

    # Python dependencies
    py = dependencies.get("python", [])
    if py:
        chunks.append(("dependency", f"python: {', '.join(str(d) for d in py[:30])}"))

    return chunks


# ── Embedding generation (optional — requires VOYAGE_API_KEY) ─────────────────

async def _embed_text(text_: str) -> list[float] | None:
    """Call Voyage AI to produce a 1024-dim embedding. Returns None if unconfigured."""
    try:
        import os
        api_key = os.getenv("VOYAGE_API_KEY", "")
        if not api_key:
            return None
        import voyageai  # type: ignore[import]
        client = voyageai.AsyncClient(api_key=api_key)
        result = await client.embed([text_], model="voyage-3-lite")
        return result.embeddings[0]
    except Exception as exc:
        logger.debug("voyage embedding skipped: %s", exc)
        return None


# ── Persistence ───────────────────────────────────────────────────────────────

class EmbeddingService:
    @staticmethod
    async def generate_embeddings(
        session: AsyncSession,
        job_id: int,
        org_id: str,
        detected_stack: dict,
        dependencies: dict,
        developer_summary: str | None,
        repo_owner: str = "",
        repo_name: str = "",
    ) -> list[AnalysisEmbedding]:
        """Extract text chunks, optionally embed them, and persist to DB."""
        chunks = extract_chunks(
            result_id=job_id,
            detected_stack=detected_stack,
            dependencies=dependencies,
            developer_summary=developer_summary,
            repo_owner=repo_owner,
            repo_name=repo_name,
        )
        rows: list[AnalysisEmbedding] = []
        for chunk_type, chunk_text in chunks:
            vec = await _embed_text(chunk_text)
            # Store vector as JSON string — the DB column is TEXT on SQLite,
            # vector(1536) on Postgres. The search query handles both.
            embedding_str = json.dumps(vec) if vec else None
            row = AnalysisEmbedding(
                job_id=job_id,
                org_id=org_id,
                chunk_type=chunk_type,
                chunk_text=chunk_text,
                embedding=embedding_str,
            )
            session.add(row)
            rows.append(row)

        if rows:
            await session.flush()
            logger.info("embedding_chunks_stored job_id=%d count=%d", job_id, len(rows))
        return rows

    @staticmethod
    async def search(
        session: AsyncSession,
        query: str,
        org_id: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Full-text search across chunk_text.

        Uses Postgres tsvector when available, LIKE otherwise.
        """
        from app.core.config import settings

        is_postgres = settings.resolved_database_url.startswith("postgresql")

        if is_postgres:
            sql = text("""
                SELECT
                    ae.job_id,
                    ae.chunk_type,
                    ae.chunk_text,
                    ts_rank(to_tsvector('english', ae.chunk_text),
                            websearch_to_tsquery('english', :q)) AS score
                FROM analysis_embeddings ae
                WHERE ae.org_id = :org_id
                  AND to_tsvector('english', ae.chunk_text)
                      @@ websearch_to_tsquery('english', :q)
                ORDER BY score DESC
                LIMIT :limit
            """)
        else:
            # SQLite fallback: simple LIKE search
            sql = text("""
                SELECT
                    ae.job_id,
                    ae.chunk_type,
                    ae.chunk_text,
                    1.0 AS score
                FROM analysis_embeddings ae
                WHERE ae.org_id = :org_id
                  AND lower(ae.chunk_text) LIKE lower(:q_like)
                ORDER BY ae.created_at DESC
                LIMIT :limit
            """)

        params: dict[str, Any] = {"org_id": org_id, "limit": limit}
        if is_postgres:
            params["q"] = query
        else:
            params["q_like"] = f"%{query}%"

        rows = (await session.execute(sql, params)).mappings().all()
        return [dict(r) for r in rows]
