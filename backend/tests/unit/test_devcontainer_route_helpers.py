"""
tests/unit/test_devcontainer_route_helpers.py

Pure unit tests for the private helpers in routes/devcontainer.py:
  - _languages_from_stack
  - _frameworks_from_stack
  - _build_setup_sh
  - _build_zip (ZIP structure)
"""
import io
import json
import zipfile

from app.api.routes.devcontainer import (
    _build_setup_sh,
    _build_zip,
    _frameworks_from_stack,
    _languages_from_stack,
)

# ── _languages_from_stack ─────────────────────────────────────────────────────

def test_languages_fastapi_maps_to_python():
    stack = {"backend": [{"name": "FastAPI", "confidence": 0.9}]}
    assert _languages_from_stack(stack) == ["python"]


def test_languages_nextjs_maps_to_node():
    stack = {"frontend": [{"name": "Next.js", "confidence": 0.8}]}
    assert _languages_from_stack(stack) == ["node"]


def test_languages_deduplicates():
    stack = {
        "backend": [{"name": "FastAPI"}, {"name": "Django"}],
    }
    langs = _languages_from_stack(stack)
    assert langs.count("python") == 1


def test_languages_empty_stack_returns_python_default():
    assert _languages_from_stack({}) == ["python"]


def test_languages_unknown_framework_excluded():
    stack = {"backend": [{"name": "Rails"}]}
    langs = _languages_from_stack(stack)
    assert langs == ["python"]  # falls back to default


def test_languages_multiple_categories():
    stack = {
        "backend": [{"name": "FastAPI"}],
        "frontend": [{"name": "Next.js"}],
    }
    langs = _languages_from_stack(stack)
    assert "python" in langs
    assert "node" in langs


# ── _frameworks_from_stack ────────────────────────────────────────────────────

def test_frameworks_normalises_dots_and_hyphens():
    stack = {"frontend": [{"name": "Next.js"}]}
    fws = _frameworks_from_stack(stack)
    assert "nextjs" in fws


def test_frameworks_deduplicates_same_key():
    stack = {"backend": [{"name": "FastAPI"}, {"name": "FastAPI"}]}
    fws = _frameworks_from_stack(stack)
    assert fws.count("fastapi") == 1


def test_frameworks_empty_stack_is_empty():
    assert _frameworks_from_stack({}) == []


def test_frameworks_only_covers_backend_and_frontend():
    stack = {
        "runtime": [{"name": "Docker"}],   # runtime excluded
        "backend": [{"name": "Flask"}],
    }
    fws = _frameworks_from_stack(stack)
    assert "flask" in fws
    assert "docker" not in fws


# ── _build_setup_sh ───────────────────────────────────────────────────────────

def test_setup_sh_contains_shebang():
    sh = _build_setup_sh({"postCreateCommand": "pip install -r requirements.txt"})
    assert sh.startswith("#!/usr/bin/env bash")


def test_setup_sh_splits_chained_commands():
    config = {"postCreateCommand": "pip install -r requirements.txt && npm install"}
    sh = _build_setup_sh(config)
    assert "pip install -r requirements.txt" in sh
    assert "npm install" in sh


def test_setup_sh_empty_command_shows_placeholder():
    sh = _build_setup_sh({})
    assert "No post-create commands" in sh


def test_setup_sh_contains_success_echo():
    sh = _build_setup_sh({})
    assert "Atlas devcontainer setup complete" in sh


# ── _build_zip ────────────────────────────────────────────────────────────────

_SAMPLE_CONFIG = {
    "name": "atlas-dev-python",
    "image": "mcr.microsoft.com/devcontainers/python:3-3.11",
    "features": {"ghcr.io/devcontainers/features/git:latest": {}},
    "postCreateCommand": "pip install -r requirements.txt",
    "remoteUser": "vscode",
}


def test_zip_contains_devcontainer_json():
    buf = _build_zip(_SAMPLE_CONFIG, version=1)
    with zipfile.ZipFile(buf) as zf:
        names = zf.namelist()
    assert ".devcontainer/devcontainer.json" in names


def test_zip_contains_setup_sh():
    buf = _build_zip(_SAMPLE_CONFIG, version=1)
    with zipfile.ZipFile(buf) as zf:
        names = zf.namelist()
    assert ".devcontainer/setup.sh" in names


def test_zip_contains_readme():
    buf = _build_zip(_SAMPLE_CONFIG, version=2)
    with zipfile.ZipFile(buf) as zf:
        names = zf.namelist()
    assert "README.md" in names


def test_zip_devcontainer_json_is_valid():
    buf = _build_zip(_SAMPLE_CONFIG, version=1)
    with zipfile.ZipFile(buf) as zf:
        content = zf.read(".devcontainer/devcontainer.json")
    parsed = json.loads(content)
    assert parsed["name"] == "atlas-dev-python"


def test_zip_readme_mentions_version():
    buf = _build_zip(_SAMPLE_CONFIG, version=3)
    with zipfile.ZipFile(buf) as zf:
        readme = zf.read("README.md").decode()
    assert "v3" in readme


def test_zip_returns_seeked_buffer():
    buf = _build_zip(_SAMPLE_CONFIG, version=1)
    assert isinstance(buf, io.BytesIO)
    assert buf.tell() == 0
