"""Fetches repo metadata and file tree from the GitHub API."""
import base64
from typing import Any

import httpx

from app.core.config import settings

GITHUB_API = "https://api.github.com"
GITHUB_TIMEOUT_SECONDS = 15.0


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


async def get_repo_metadata(
    owner: str,
    repo: str,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    if client is None:
        async with create_github_client() as new_client:
            return await get_repo_metadata(owner, repo, client=new_client)

    response = await client.get(f"{GITHUB_API}/repos/{owner}/{repo}")
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

    response = await client.get(
        f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/{branch}",
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

    response = await client.get(f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}")
    if response.status_code == 404:
        return None
    _handle_response(response, path)
    data = response.json()
    if data.get("encoding") == "base64":
        return base64.b64decode(data["content"]).decode("utf-8", errors="replace")
    return data.get("content")
