"""Fetches repo metadata and file tree from the GitHub API."""
import base64
import logging
from typing import Any

import httpx

from app.core.config import settings

GITHUB_API = "https://api.github.com"
GITHUB_TIMEOUT_SECONDS = 15.0
logger = logging.getLogger(__name__)

_github_auth_state: dict[str, str] = {
    "mode": "token" if settings.github_token else "unauthenticated",
    "status": "configured" if settings.github_token else "not_configured",
    "detail": "",
}


class GitHubError(Exception):
    """Raised for known, user-actionable GitHub API errors."""


def _headers() -> dict[str, str]:
    h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if settings.github_token:
        h["Authorization"] = f"Bearer {settings.github_token}"
    return h


def create_github_client() -> httpx.AsyncClient:
    """Build a reusable GitHub client so callers can share connection pooling."""
    return httpx.AsyncClient(headers=_headers(), timeout=GITHUB_TIMEOUT_SECONDS)


def github_auth_snapshot() -> dict[str, str]:
    return dict(_github_auth_state)


def _set_auth_state(*, mode: str, status: str, detail: str = "") -> None:
    _github_auth_state["mode"] = mode
    _github_auth_state["status"] = status
    _github_auth_state["detail"] = detail


def _handle_response(response: httpx.Response, context: str) -> None:
    if response.status_code == 404:
        raise GitHubError(f"Repository not found or is private ({context})")
    if response.status_code == 403:
        raise GitHubError(
            "GitHub API rate limit reached. Add a GITHUB_TOKEN to increase the limit."
        )
    if response.status_code == 422:
        raise GitHubError(f"GitHub rejected the request ({context}). The repo may be empty.")
    response.raise_for_status()


async def _request_with_auth_fallback(
    client: httpx.AsyncClient,
    path: str,
    *,
    context: str,
    params: dict[str, str] | None = None,
) -> httpx.Response:
    response = await client.get(path, params=params)
    if response.status_code != 401 or "Authorization" not in client.headers:
        if response.status_code < 400:
            mode = "token" if "Authorization" in client.headers else "unauthenticated"
            status = "ok" if mode == "token" else "degraded"
            detail = "" if mode == "token" else "No GITHUB_TOKEN configured; using public API limits."
            _set_auth_state(mode=mode, status=status, detail=detail)
        return response

    logger.warning("GitHub token unauthorized for %s; retrying unauthenticated", context)
    fallback_headers = {
        key: value
        for key, value in client.headers.items()
        if key.lower() != "authorization"
    }
    fallback_kwargs: dict[str, Any] = {
        "headers": fallback_headers,
        "timeout": client.timeout,
    }
    transport = getattr(client, "_transport", None)
    if transport is not None:
        fallback_kwargs["transport"] = transport
    async with httpx.AsyncClient(
        **fallback_kwargs,
    ) as fallback_client:
        fallback_response = await fallback_client.get(path, params=params)
    if fallback_response.status_code < 400:
        _set_auth_state(
            mode="fallback_unauthenticated",
            status="degraded",
            detail="Configured GITHUB_TOKEN was rejected by GitHub; requests are falling back to public API limits.",
        )
        return fallback_response

    _set_auth_state(
        mode="token_rejected",
        status="error",
        detail="Configured GITHUB_TOKEN was rejected by GitHub and unauthenticated fallback also failed.",
    )
    return fallback_response


async def get_repo_metadata(
    owner: str,
    repo: str,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    if client is None:
        async with create_github_client() as new_client:
            return await get_repo_metadata(owner, repo, client=new_client)

    response = await _request_with_auth_fallback(
        client,
        f"{GITHUB_API}/repos/{owner}/{repo}",
        context=f"{owner}/{repo}",
    )
    _handle_response(response, f"{owner}/{repo}")
    return response.json()


async def get_repo_tree(
    owner: str,
    repo: str,
    branch: str = "HEAD",
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    if client is None:
        async with create_github_client() as new_client:
            return await get_repo_tree(owner, repo, branch=branch, client=new_client)

    response = await _request_with_auth_fallback(
        client,
        f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/{branch}",
        context=f"{owner}/{repo} tree",
        params={"recursive": "1"},
    )
    _handle_response(response, f"{owner}/{repo} tree")
    data = response.json()
    return data.get("tree", [])


async def get_file_content(
    owner: str,
    repo: str,
    path: str,
    client: httpx.AsyncClient | None = None,
) -> str | None:
    if client is None:
        async with create_github_client() as new_client:
            return await get_file_content(owner, repo, path, client=new_client)

    response = await _request_with_auth_fallback(
        client,
        f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}",
        context=path,
    )
    if response.status_code == 404:
        return None
    _handle_response(response, path)
    data = response.json()
    if data.get("encoding") == "base64":
        return base64.b64decode(data["content"]).decode("utf-8", errors="replace")
    return data.get("content")
