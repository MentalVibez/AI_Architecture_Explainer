"""
app/services/cache/public_cache.py

Commit-SHA keyed cache for public static analysis results.

All three stubs from the deliverable are now implemented:
  ✓ lookup_public_cache  — queries PublicCacheEntry by cache_key + expiry
  ✓ write_public_cache   — upsert via INSERT ON CONFLICT
  ✓ find_active_job      — queries AnalysisJob for queued/running dedup

Uses sync Session (matches the new public routes layer).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.services.cache.cache_models import CacheHit, CacheWriteResult

ENGINE_VERSION = "1.0.0"


# ─────────────────────────────────────────────────────────
# Key derivation
# ─────────────────────────────────────────────────────────

def make_public_cache_key(
    provider:       str,
    repo_owner:     str,
    repo_name:      str,
    commit_sha:     str,
    engine_version: str = ENGINE_VERSION,
) -> str:
    return (
        f"public"
        f":{provider.lower()}"
        f":{repo_owner.lower()}"
        f":{repo_name.lower()}"
        f":{commit_sha.lower()}"
        f":{engine_version}"
    )


# ─────────────────────────────────────────────────────────
# Cache read
# ─────────────────────────────────────────────────────────

def lookup_public_cache(
    provider:    str,
    repo_owner:  str,
    repo_name:   str,
    commit_sha:  str,
    db:          Session | None = None,
    engine_version: str = ENGINE_VERSION,
) -> CacheHit | None:
    """Return CacheHit if a non-expired entry exists, else None."""
    if db is None:
        return None

    from app.models.analysis import PublicCacheEntry

    cache_key = make_public_cache_key(
        provider, repo_owner, repo_name, commit_sha, engine_version
    )
    now = datetime.now(UTC)

    entry = (
        db.query(PublicCacheEntry)
        .filter(
            PublicCacheEntry.cache_key == cache_key,
            PublicCacheEntry.expires_at > now,
        )
        .first()
    )
    if entry:
        return CacheHit(
            job_id     = str(entry.job_id),
            cache_key  = cache_key,
            expires_at = entry.expires_at.isoformat(),
        )
    return None


# ─────────────────────────────────────────────────────────
# Cache write
# ─────────────────────────────────────────────────────────

def write_public_cache(
    job_id:      str,
    provider:    str,
    repo_owner:  str,
    repo_name:   str,
    commit_sha:  str,
    ttl_seconds: int,
    db:          Session | None = None,
    engine_version: str = ENGINE_VERSION,
) -> CacheWriteResult:
    """Upsert a cache entry after a public job completes."""
    cache_key  = make_public_cache_key(
        provider, repo_owner, repo_name, commit_sha, engine_version
    )
    expires_at = datetime.now(UTC) + timedelta(seconds=ttl_seconds)

    if db is None:
        return CacheWriteResult(
            written    = False,
            cache_key  = cache_key,
            expires_at = expires_at.isoformat(),
        )

    from app.models.analysis import PublicCacheEntry

    stmt = pg_insert(PublicCacheEntry).values(
        id         = str(uuid.uuid4()),
        cache_key  = cache_key,
        job_id     = job_id,
        provider   = provider,
        repo_owner = repo_owner.lower(),
        repo_name  = repo_name.lower(),
        commit_sha = commit_sha.lower(),
        expires_at = expires_at,
    ).on_conflict_do_update(
        index_elements=["cache_key"],
        set_={
            "job_id":     job_id,
            "expires_at": expires_at,
        },
    )
    db.execute(stmt)
    db.commit()

    return CacheWriteResult(
        written    = True,
        cache_key  = cache_key,
        expires_at = expires_at.isoformat(),
    )


# ─────────────────────────────────────────────────────────
# Deduplication check
# ─────────────────────────────────────────────────────────

def find_active_job(
    provider:    str,
    repo_owner:  str,
    repo_name:   str,
    commit_sha:  str | None,
    scope:       str,
    db:          Session | None = None,
) -> str | None:
    """Return job_id if a queued or running job exists for this repo+commit."""
    if db is None:
        return None

    from app.models.analysis import AnalysisJob

    query = (
        db.query(AnalysisJob)
        .filter(
            AnalysisJob.scope      == scope,
            AnalysisJob.provider   == provider.lower(),
            AnalysisJob.repo_owner == repo_owner.lower(),
            AnalysisJob.repo_name  == repo_name.lower(),
            AnalysisJob.status.in_(["queued", "running"]),
        )
    )
    if commit_sha:
        query = query.filter(AnalysisJob.commit_sha == commit_sha.lower())

    existing = query.first()
    return str(existing.id) if existing else None
