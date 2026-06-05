"""GitHub OAuth2 flow + JWT issuance.

Flow:
  1. GET /api/auth/login   → redirect to GitHub authorization URL
  2. GitHub redirects to GET /api/auth/callback?code=...
  3. We exchange the code for an access token, fetch the GitHub user,
     issue a signed JWT, and set it in an httpOnly Secure cookie.
  4. GET /api/auth/me      → return the current user from the JWT cookie.
  5. POST /api/auth/logout → clear the cookie.
"""
from __future__ import annotations

import hmac
import secrets
import time
from typing import Annotated
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from jose import JWTError, jwt
from pydantic import BaseModel

from app.core.config import settings

router = APIRouter(prefix="/api/auth", tags=["auth"])

_GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
_GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
_GITHUB_USER_URL = "https://api.github.com/user"
_COOKIE_NAME = "atlas_session"
_OAUTH_STATE_COOKIE = "atlas_oauth_state"
_ALGORITHM = "HS256"
_OAUTH_STATE_TTL_SECONDS = 600


# ── Models ────────────────────────────────────────────────────────────────────

class UserInfo(BaseModel):
    github_id: int
    login: str
    name: str | None
    email: str | None
    avatar_url: str | None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _issue_jwt(user: UserInfo) -> str:
    now = int(time.time())
    payload = {
        "sub": str(user.github_id),
        "login": user.login,
        "name": user.name,
        "email": user.email,
        "avatar_url": user.avatar_url,
        "iat": now,
        "exp": now + settings.atlas_jwt_ttl_seconds,
    }
    return jwt.encode(payload, settings.atlas_jwt_secret, algorithm=_ALGORITHM)


def _decode_jwt(token: str) -> dict:
    try:
        return jwt.decode(token, settings.atlas_jwt_secret, algorithms=[_ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session")


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.environment != "development",
        samesite="lax",
        max_age=settings.atlas_jwt_ttl_seconds,
        path="/",
    )


def _set_oauth_state_cookie(response: Response, state: str) -> None:
    response.set_cookie(
        key=_OAUTH_STATE_COOKIE,
        value=state,
        httponly=True,
        secure=settings.environment != "development",
        samesite="lax",
        max_age=_OAUTH_STATE_TTL_SECONDS,
        path="/",
    )


def _clear_oauth_state_cookie(response: Response) -> None:
    response.delete_cookie(key=_OAUTH_STATE_COOKIE, path="/")


# ── Dependency: current user ──────────────────────────────────────────────────

async def get_current_user(
    atlas_session: Annotated[str | None, Cookie(alias=_COOKIE_NAME)] = None,
) -> dict:
    """FastAPI dependency: decode JWT cookie and return the user payload."""
    if not atlas_session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return _decode_jwt(atlas_session)


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/login")
async def login(request: Request):
    """Redirect the browser to GitHub's OAuth authorization page."""
    if not settings.github_client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitHub OAuth is not configured (GITHUB_CLIENT_ID missing)",
        )
    state = secrets.token_urlsafe(32)
    params = urlencode({
        "client_id": settings.github_client_id,
        "redirect_uri": settings.atlas_oauth_redirect_uri,
        "scope": "read:user user:email read:org",
        "state": state,
    })
    from fastapi.responses import RedirectResponse
    redirect = RedirectResponse(url=f"{_GITHUB_AUTHORIZE_URL}?{params}")
    _set_oauth_state_cookie(redirect, state)
    return redirect


@router.get("/callback")
async def callback(
    code: str,
    request: Request,
    state: str | None = None,
):
    """GitHub redirects here with ?code=... after the user authorizes."""
    if not settings.github_client_id or not settings.github_client_secret:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="OAuth not configured")

    expected_state = request.cookies.get(_OAUTH_STATE_COOKIE, "")
    supplied_state = state or ""
    if not expected_state or not supplied_state or not hmac.compare_digest(supplied_state, expected_state):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OAuth state",
        )

    async with httpx.AsyncClient() as client:
        # Exchange code for access token
        token_resp = await client.post(
            _GITHUB_TOKEN_URL,
            data={
                "client_id": settings.github_client_id,
                "client_secret": settings.github_client_secret,
                "code": code,
            },
            headers={"Accept": "application/json"},
            timeout=10,
        )
        token_data = token_resp.json()

    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="GitHub OAuth failed")

    async with httpx.AsyncClient() as client:
        user_resp = await client.get(
            _GITHUB_USER_URL,
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
            timeout=10,
        )
        gh_user = user_resp.json()

    user = UserInfo(
        github_id=gh_user["id"],
        login=gh_user["login"],
        name=gh_user.get("name"),
        email=gh_user.get("email"),
        avatar_url=gh_user.get("avatar_url"),
    )

    jwt_token = _issue_jwt(user)

    # Return a response that sets the cookie and redirects to the app
    from fastapi.responses import RedirectResponse
    redirect = RedirectResponse(url="/", status_code=302)
    _clear_oauth_state_cookie(redirect)
    _set_session_cookie(redirect, jwt_token)
    return redirect


@router.get("/me", response_model=UserInfo)
async def me(current_user: Annotated[dict, Depends(get_current_user)]):
    """Return the currently authenticated user."""
    return UserInfo(
        github_id=int(current_user["sub"]),
        login=current_user["login"],
        name=current_user.get("name"),
        email=current_user.get("email"),
        avatar_url=current_user.get("avatar_url"),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response):
    """Clear the session cookie."""
    response.delete_cookie(key=_COOKIE_NAME, path="/")
