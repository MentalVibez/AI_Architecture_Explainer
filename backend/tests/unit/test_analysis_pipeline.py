import httpx
import pytest

from app.services import analysis_pipeline


@pytest.mark.asyncio
async def test_fetch_priority_files_skips_read_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get_file_content(owner: str, repo: str, path: str, client: httpx.AsyncClient) -> str | None:
        if path == "README.md":
            return "# FastAPI"
        if path == "pyproject.toml":
            raise httpx.ReadError("boom")
        return None

    monkeypatch.setattr(analysis_pipeline.github_service, "get_file_content", fake_get_file_content)

    async with httpx.AsyncClient() as client:
        result = await analysis_pipeline._fetch_priority_files(
            owner="tiangolo",
            repo="fastapi",
            tree_paths=["README.md", "pyproject.toml", "docs/guide.md"],
            client=client,
        )

    assert result == {"README.md": "# FastAPI"}
