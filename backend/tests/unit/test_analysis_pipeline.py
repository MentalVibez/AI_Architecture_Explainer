import httpx
import pytest

from app.services import analysis_pipeline
from app.services import route_extractor


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


def test_select_candidate_paths_expands_for_library_style_repos() -> None:
    tree = [
        {"type": "blob", "path": "tests/test_validate_response_recursive/app.py"},
        {"type": "blob", "path": "fastapi-slim/README.md"},
        {"type": "blob", "path": "pyproject.toml"},
    ]

    result = route_extractor._select_candidate_paths(tree, "generic")

    assert "tests/test_validate_response_recursive/app.py" in result


def test_generic_extractor_catches_decorator_routes_when_framework_is_unknown() -> None:
    content = """
from fastapi import FastAPI

app = FastAPI()

@app.get("/health")
async def health():
    return {"ok": True}
"""

    result = route_extractor._extract_routes_from_content(content, "generic", "tests/app.py")

    assert any(route.path == "/health" and route.method == "GET" for route in result)
