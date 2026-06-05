"""Middleware that decodes the Atlas session cookie and stores the current org
(GitHub login) in request.state so the RLS db dependency can set the Postgres
session variable `app.current_org_id` before any query runs.
"""
from __future__ import annotations

from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp


class OrgContextMiddleware(BaseHTTPMiddleware):
    """Populate request.state.org_id from the atlas_session JWT cookie.

    Runs before route handlers so get_rls_db can activate Postgres RLS policies.
    Never raises — missing or invalid tokens result in an empty string.
    """

    def __init__(self, app: ASGIApp, jwt_secret: str) -> None:
        super().__init__(app)
        self._jwt_secret = jwt_secret

    async def dispatch(self, request: Request, call_next) -> Response:
        request.state.org_id = ""
        if self._jwt_secret:
            token = request.cookies.get("atlas_session")
            if token:
                try:
                    payload = jwt.decode(token, self._jwt_secret, algorithms=["HS256"])
                    request.state.org_id = payload.get("login", "")
                except JWTError:
                    pass
        return await call_next(request)
