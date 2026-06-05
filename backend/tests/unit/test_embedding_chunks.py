"""
tests/unit/test_embedding_chunks.py

Pure unit tests for extract_chunks() — no DB, no LLM, no network.
"""
from app.services.embedding_service import extract_chunks

_FULL_STACK = {
    "backend": [{"name": "FastAPI", "confidence": 0.95}],
    "frontend": [{"name": "Next.js", "confidence": 0.85}],
}

_FULL_DEPS = {
    "python": ["fastapi", "sqlalchemy", "alembic"],
    "npm": ["react", "next", "tailwindcss"],
}


# ── architecture chunk ────────────────────────────────────────────────────────

def test_architecture_chunk_present_when_summary_given():
    chunks = extract_chunks(1, {}, {}, "A REST API built with FastAPI.")
    types = [t for t, _ in chunks]
    assert "architecture" in types


def test_architecture_chunk_absent_when_no_summary():
    chunks = extract_chunks(1, {}, {}, None)
    types = [t for t, _ in chunks]
    assert "architecture" not in types


def test_architecture_chunk_capped_at_800_chars():
    long_summary = "x" * 1000
    chunks = extract_chunks(1, {}, {}, long_summary)
    arch = next((text for t, text in chunks if t == "architecture"), None)
    assert arch is not None
    assert len(arch) <= 800


# ── stack chunk ───────────────────────────────────────────────────────────────

def test_stack_chunk_present_when_frameworks_detected():
    chunks = extract_chunks(1, _FULL_STACK, {}, None)
    types = [t for t, _ in chunks]
    assert "stack" in types


def test_stack_chunk_contains_framework_names():
    chunks = extract_chunks(1, _FULL_STACK, {}, None, "owner", "repo")
    stack_text = next((text for t, text in chunks if t == "stack"), "")
    assert "FastAPI" in stack_text
    assert "Next.js" in stack_text


def test_stack_chunk_absent_for_empty_stack():
    chunks = extract_chunks(1, {}, {}, None)
    types = [t for t, _ in chunks]
    assert "stack" not in types


def test_stack_chunk_uses_repo_label():
    chunks = extract_chunks(1, _FULL_STACK, {}, None, "acme", "platform")
    stack_text = next((text for t, text in chunks if t == "stack"), "")
    assert "acme/platform" in stack_text


# ── dependency chunks ─────────────────────────────────────────────────────────

def test_npm_dependency_chunk_present():
    chunks = extract_chunks(1, {}, _FULL_DEPS, None)
    types = [t for t, _ in chunks]
    assert "dependency" in types


def test_npm_dependency_chunk_text():
    chunks = extract_chunks(1, {}, {"npm": ["react", "next"]}, None)
    dep_texts = [text for t, text in chunks if t == "dependency"]
    assert any("react" in t for t in dep_texts)


def test_python_dependency_chunk_text():
    chunks = extract_chunks(1, {}, {"python": ["fastapi", "sqlalchemy"]}, None)
    dep_texts = [text for t, text in chunks if t == "dependency"]
    assert any("fastapi" in t for t in dep_texts)


def test_dependency_chunk_absent_when_empty():
    chunks = extract_chunks(1, {}, {"npm": [], "python": []}, None)
    types = [t for t, _ in chunks]
    assert "dependency" not in types


def test_npm_dependency_capped_at_30_items():
    many_pkgs = [f"pkg-{i}" for i in range(50)]
    chunks = extract_chunks(1, {}, {"npm": many_pkgs}, None)
    dep_text = next((text for t, text in chunks if t == "dependency" and "npm" in text), "")
    # Only the first 30 are joined; after that no more items
    assert "pkg-30" not in dep_text


# ── full combined run ─────────────────────────────────────────────────────────

def test_all_chunks_produced_with_full_data():
    chunks = extract_chunks(1, _FULL_STACK, _FULL_DEPS, "A FastAPI + Next.js platform.", "acme", "platform")
    types = [t for t, _ in chunks]
    assert "architecture" in types
    assert "stack" in types
    assert "dependency" in types


def test_no_chunks_with_empty_everything():
    chunks = extract_chunks(1, {}, {}, None)
    assert chunks == []
