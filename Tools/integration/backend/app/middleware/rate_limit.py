"""
Simple in-process IP-based rate limiter.

No Redis dependency. Uses an in-memory dict with TTL cleanup.
Good enough for initial deployment — replace with Redis when
you need cross-process or multi-instance rate limiting.

Limits:
    Free tier: MAX_REVIEWS_PER_DAY per IP per day
    Burst:     MAX_REVIEWS_PER_HOUR per IP per hour (catches hammering)

Usage in routes:
    from app.middleware.rate_limit import check_review_rate_limit
    await check_review_rate_limit(request)
"""
import time
import asyncio
from collections import defaultdict
from fastapi import HTTPException, Request

MAX_REVIEWS_PER_DAY  = 3
MAX_REVIEWS_PER_HOUR = 2

# {ip: [(timestamp, "day"/"hour")]}
_review_log: dict[str, list[tuple[float, str]]] = defaultdict(list)
_lock = asyncio.Lock()


def _get_client_ip(request: Request) -> str:
    """Extract real client IP, respecting Railway/Vercel proxy headers."""
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip
    return request.client.host if request.client else "unknown"


async def check_review_rate_limit(request: Request) -> None:
    """
    Check rate limits for a review submission.
    Raises HTTP 429 if exceeded.
    Call at the start of POST /api/review.
    """
    ip = _get_client_ip(request)
    now = time.time()
    one_hour_ago = now - 3600
    one_day_ago  = now - 86400

    async with _lock:
        # Prune old entries
        _review_log[ip] = [
            (ts, bucket) for (ts, bucket) in _review_log[ip]
            if ts > one_day_ago
        ]

        entries = _review_log[ip]
        hourly = sum(1 for ts, _ in entries if ts > one_hour_ago)
        daily  = len(entries)

        if hourly >= MAX_REVIEWS_PER_HOUR:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "RATE_LIMITED",
                    "message": f"Maximum {MAX_REVIEWS_PER_HOUR} reviews per hour. "
                               "Please wait before submitting another.",
                    "retry_after_seconds": int(one_hour_ago + 3600 - now + 60),
                },
                headers={"Retry-After": str(int(one_hour_ago + 3600 - now + 60))},
            )

        if daily >= MAX_REVIEWS_PER_DAY:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "RATE_LIMITED",
                    "message": f"Maximum {MAX_REVIEWS_PER_DAY} reviews per day. "
                               "Come back tomorrow.",
                    "retry_after_seconds": int(one_day_ago + 86400 - now + 60),
                },
                headers={"Retry-After": str(int(one_day_ago + 86400 - now + 60))},
            )

        _review_log[ip].append((now, "review"))
