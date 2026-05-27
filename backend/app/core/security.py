from __future__ import annotations

import asyncio
import hmac
import time
from collections import defaultdict
from collections.abc import Awaitable, Callable

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.config import settings

ADMIN_HEADER = "x-atlas-admin-key"


def client_ip(request: Request) -> str:
    direct_ip = request.client.host if request.client else "unknown"
    if direct_ip in settings.trusted_proxies:
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()
    return direct_ip


def require_admin(request: Request) -> None:
    configured = settings.admin_api_key.strip()
    if not configured:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not found",
        )

    supplied = request.headers.get(ADMIN_HEADER, "")
    if not hmac.compare_digest(supplied, configured):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not found",
        )


class PublicRouteLimiter:
    def __init__(self) -> None:
        self._events: dict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()
        self._redis = None

    async def check(
        self,
        request: Request,
        *,
        route: str,
        burst_limit: int,
        burst_window_seconds: int,
        daily_limit: int,
        subject: str | None = None,
    ) -> None:
        now = time.time()
        daily_window = 86400
        ip = client_ip(request)
        key_parts = [route, ip]
        if subject:
            key_parts.append(subject.lower())
        key = ":".join(key_parts)

        if settings.redis_url:
            await self._check_redis(
                key=key,
                now=now,
                burst_limit=burst_limit,
                burst_window_seconds=burst_window_seconds,
                daily_limit=daily_limit,
                daily_window=daily_window,
            )
            return

        async with self._lock:
            events = [ts for ts in self._events[key] if ts > now - daily_window]
            burst_count = sum(1 for ts in events if ts > now - burst_window_seconds)

            if burst_count >= burst_limit:
                retry_after = max(1, int((events[-burst_limit] + burst_window_seconds) - now))
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "RATE_LIMITED",
                        "message": "Too many requests. Please wait before retrying.",
                        "retry_after_seconds": retry_after,
                    },
                    headers={"Retry-After": str(retry_after)},
                )

            if len(events) >= daily_limit:
                retry_after = max(1, int((events[0] + daily_window) - now))
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "RATE_LIMITED",
                        "message": "Daily request limit reached. Please try again later.",
                        "retry_after_seconds": retry_after,
                    },
                    headers={"Retry-After": str(retry_after)},
                )

            events.append(now)
            self._events[key] = events

    async def _check_redis(
        self,
        *,
        key: str,
        now: float,
        burst_limit: int,
        burst_window_seconds: int,
        daily_limit: int,
        daily_window: int,
    ) -> None:
        redis = await self._redis_client()
        redis_key = f"rate:{key}"
        await redis.zremrangebyscore(redis_key, 0, now - daily_window)
        burst_count = await redis.zcount(redis_key, now - burst_window_seconds, now)
        daily_count = await redis.zcard(redis_key)

        if int(burst_count) >= burst_limit:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "RATE_LIMITED",
                    "message": "Too many requests. Please wait before retrying.",
                    "retry_after_seconds": burst_window_seconds,
                },
                headers={"Retry-After": str(burst_window_seconds)},
            )

        if int(daily_count) >= daily_limit:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "RATE_LIMITED",
                    "message": "Daily request limit reached. Please try again later.",
                    "retry_after_seconds": daily_window,
                },
                headers={"Retry-After": str(daily_window)},
            )

        member = f"{now:.6f}"
        await redis.zadd(redis_key, {member: now})
        await redis.expire(redis_key, daily_window)

    async def _redis_client(self):
        if self._redis is None:
            from redis.asyncio import Redis

            self._redis = Redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._redis


public_route_limiter = PublicRouteLimiter()


class ContentSizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject request bodies larger than max_bytes before any route handler runs.

    Prevents large payloads from consuming memory or reaching the GitHub fetch
    pipeline. 64 KB is more than enough for any JSON body this API accepts.
    """

    def __init__(self, app, max_bytes: int = 65_536) -> None:
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_bytes:
            from starlette.responses import PlainTextResponse

            return PlainTextResponse(status_code=413, content="Request body too large")
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=(), payment=()",
        )
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
        )
        response.headers.setdefault(
            "Strict-Transport-Security",
            "max-age=63072000; includeSubDomains",
        )
        return response
