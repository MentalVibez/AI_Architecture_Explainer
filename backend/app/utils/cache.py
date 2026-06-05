"""Cache utilities for analyzing repos."""
import json
from datetime import datetime, timedelta
from pathlib import Path


class FileCache:
    """Simple file-based cache for analysis results (7-day TTL)."""

    DEFAULT_TTL_DAYS = 7

    def __init__(self, cache_dir: str = "./cache", fallback_dir: str | None = None):
        primary = Path(cache_dir)
        try:
            primary.mkdir(parents=True, exist_ok=True)
            self.cache_dir = primary
        except OSError:
            if fallback_dir is None:
                raise
            fallback = Path(fallback_dir)
            fallback.mkdir(parents=True, exist_ok=True)
            self.cache_dir = fallback

    def _get_cache_path(self, key: str) -> Path:
        """Get cache file path from key."""
        return self.cache_dir / f"{key}.json"

    def _is_expired(self, cache_path: Path, ttl_days: int = DEFAULT_TTL_DAYS) -> bool:
        """Check if cache entry has expired."""
        if not cache_path.exists():
            return True

        mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        age = datetime.now() - mtime
        return age > timedelta(days=ttl_days)

    def get(self, key: str) -> dict | None:
        """Retrieve from cache if valid.

        Args:
            key: Cache key (e.g., repo URL)

        Returns:
            Cached value or None if expired/missing
        """
        cache_path = self._get_cache_path(key)

        if self._is_expired(cache_path):
            return None

        try:
            with open(cache_path) as f:
                return json.load(f)
        except Exception:
            return None

    def set(self, key: str, value: dict) -> None:
        """Store in cache.

        Args:
            key: Cache key
            value: Data to cache
        """
        cache_path = self._get_cache_path(key)

        try:
            with open(cache_path, "w") as f:
                json.dump(value, f)
        except Exception:
            pass  # Silently fail on cache write

    def delete(self, key: str) -> None:
        """Delete cache entry."""
        cache_path = self._get_cache_path(key)
        cache_path.unlink(missing_ok=True)

    def clear(self) -> None:
        """Delete all cache entries."""
        for cache_file in self.cache_dir.glob("*.json"):
            cache_file.unlink()

    def prune_expired(self, ttl_days: int = DEFAULT_TTL_DAYS) -> int:
        """Delete expired cache entries.

        Returns:
            Number of files deleted
        """
        deleted = 0
        for cache_file in self.cache_dir.glob("*.json"):
            if self._is_expired(cache_file, ttl_days):
                cache_file.unlink()
                deleted += 1

        return deleted
