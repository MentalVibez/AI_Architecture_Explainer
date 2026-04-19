import httpx
import pytest

from app.services import github_service


@pytest.mark.asyncio
async def test_get_repo_metadata_falls_back_when_token_is_rejected() -> None:
    calls: list[dict[str, str | None]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        auth = request.headers.get("Authorization")
        calls.append({"url": str(request.url), "auth": auth})
        if auth:
            return httpx.Response(401, json={"message": "Bad credentials"})
        return httpx.Response(200, json={"default_branch": "main"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        transport=transport,
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Authorization": "Bearer broken-token",
        },
    ) as client:
        metadata = await github_service.get_repo_metadata("tiangolo", "fastapi", client=client)

    assert metadata["default_branch"] == "main"
    assert len(calls) == 2
    assert calls[0]["auth"] == "Bearer broken-token"
    assert calls[1]["auth"] is None
    assert github_service.github_auth_snapshot()["mode"] == "fallback_unauthenticated"


@pytest.mark.asyncio
async def test_get_repo_metadata_raises_when_fallback_also_fails() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.headers.get("Authorization"):
            return httpx.Response(401, json={"message": "Bad credentials"})
        return httpx.Response(403, json={"message": "rate limited"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        transport=transport,
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Authorization": "Bearer broken-token",
        },
    ) as client:
        with pytest.raises(github_service.GitHubError, match="rate limit reached"):
            await github_service.get_repo_metadata("tiangolo", "fastapi", client=client)

    assert github_service.github_auth_snapshot()["status"] == "error"


@pytest.mark.asyncio
async def test_get_repo_metadata_fallback_follows_redirects() -> None:
    redirected = "https://api.github.com/repositories/160919119"

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.headers.get("Authorization"):
            return httpx.Response(401, json={"message": "Bad credentials"})
        if str(request.url) == "https://api.github.com/repos/tiangolo/fastapi":
            return httpx.Response(301, headers={"location": redirected}, request=request)
        if str(request.url) == redirected:
            return httpx.Response(200, json={"default_branch": "main"})
        return httpx.Response(500, json={"message": "unexpected request"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        transport=transport,
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Authorization": "Bearer broken-token",
        },
    ) as client:
        metadata = await github_service.get_repo_metadata("tiangolo", "fastapi", client=client)

    assert metadata["default_branch"] == "main"
    assert github_service.github_auth_snapshot()["mode"] == "fallback_unauthenticated"
