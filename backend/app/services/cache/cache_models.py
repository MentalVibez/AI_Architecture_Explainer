"""
app/services/cache/cache_models.py

Pydantic models for the public cache layer.
"""

from __future__ import annotations

from pydantic import BaseModel


class CacheHit(BaseModel):
    """Returned by lookup_public_cache when a non-expired entry exists."""
    job_id:     str
    cache_key:  str
    expires_at: str  # ISO 8601 string


class CacheWriteResult(BaseModel):
    """Returned by write_public_cache after attempting to write an entry."""
    written:    bool
    cache_key:  str
    expires_at: str  # ISO 8601 string
