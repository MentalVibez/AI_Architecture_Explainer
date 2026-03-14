"""Fetches repo metadata and file tree from the GitHub API."""
from typing import Any

import httpx

from app.core.config import settings

GITHUB_API = "https://api.github.com"


def _headers() -> dict[str, str]:
    h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if settings.github_token:
        h["Authorization"] = f"Bearer {settings.github_token}"
    return h


async def get_repo_metadata(owner: str, repo: str) -> dict[str, Any]:
    async with httpx.AsyncClient(headers=_headers(), timeout=15) as client:
        response = await client.get(f"{GITHUB_API}/repos/{owner}/{repo}")
        response.raise_for_status()
        return response.json()


async def get_repo_tree(owner: str, repo: str, branch: str = "HEAD") -> list[dict[str, Any]]:
    async with httpx.AsyncClient(headers=_headers(), timeout=15) as client:
        response = await client.get(
            f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/{branch}",
            params={"recursive": "1"},
        )
        response.raise_for_status()
        data = response.json()
        return data.get("tree", [])


async def get_file_content(owner: str, repo: str, path: str) -> str | None:
    import base64

    async with httpx.AsyncClient(headers=_headers(), timeout=15) as client:
        response = await client.get(f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        data = response.json()
        if data.get("encoding") == "base64":
            return base64.b64decode(data["content"]).decode("utf-8", errors="replace")
        return data.get("content")
