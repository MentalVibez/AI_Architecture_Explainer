"""Unit tests for the multi-agent analysis pipeline.

All LLM calls and external I/O are mocked — no real API calls.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.agent_service import (
    _parse_json_from_text,
    _run_diagram,
    _run_synthesis,
    _serialize_trace,
)

# ---------------------------------------------------------------------------
# _parse_json_from_text
# ---------------------------------------------------------------------------

def test_parse_json_from_text_extracts_json_object() -> None:
    text = 'Here is the result: {"files_to_fetch": ["src/main.py"], "confidence": 0.9}'
    result = _parse_json_from_text(text)
    assert result is not None
    assert result["files_to_fetch"] == ["src/main.py"]


def test_parse_json_from_text_returns_none_for_no_json() -> None:
    assert _parse_json_from_text("No JSON here.") is None


def test_parse_json_from_text_handles_empty_string() -> None:
    assert _parse_json_from_text("") is None


# ---------------------------------------------------------------------------
# _serialize_trace
# ---------------------------------------------------------------------------

def test_serialize_trace_returns_serializable_messages() -> None:
    messages = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "world"},
    ]
    result = _serialize_trace(messages)
    assert len(result) == 2
    # Should be JSON-serializable
    json.dumps(result)


def test_serialize_trace_replaces_non_serializable() -> None:
    bad = object()
    messages = [{"role": "assistant", "content": bad}]
    result = _serialize_trace(messages)
    assert len(result) == 1
    assert "[non-serializable]" in result[0]["content"]


# ---------------------------------------------------------------------------
# _run_synthesis
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_synthesis_calls_generate_json_and_returns_result() -> None:
    mock_provider = MagicMock()
    mock_provider.generate_json = AsyncMock(return_value={
        "narrative": "A FastAPI backend with SQLite storage.",
        "service_boundaries": [
            {"name": "API", "purpose": "HTTP layer", "files": ["app/main.py"]}
        ],
        "key_patterns": ["async-first", "dependency injection"],
        "confidence": 0.85,
    })

    mock_repo_intel = MagicMock()
    mock_repo_intel.repo_owner = "testowner"
    mock_repo_intel.repo_name = "testrepo"
    mock_repo_intel.graph = MagicMock()
    mock_repo_intel.graph.files_scanned = 40
    mock_repo_intel.graph.total_files = 100
    mock_repo_intel.graph.confirmed_edge_count = 80
    mock_repo_intel.graph.graph_confidence = 0.88

    retrieved = {"app/main.py": "from fastapi import FastAPI\napp = FastAPI()"}

    result, trace = await _run_synthesis(retrieved, mock_repo_intel, mock_provider)

    assert result["narrative"] == "A FastAPI backend with SQLite storage."
    assert result["confidence"] == 0.85
    assert len(result["service_boundaries"]) == 1
    assert len(trace) > 0
    mock_provider.generate_json.assert_called_once()


# ---------------------------------------------------------------------------
# _run_diagram
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_diagram_strips_mermaid_fences() -> None:
    mock_provider = MagicMock()
    mock_provider.generate_text = AsyncMock(return_value=(
        "```mermaid\ngraph TD\n  A[API] --> B[DB]\n```"
    ))

    synthesis = {
        "service_boundaries": [
            {"name": "API", "purpose": "HTTP layer", "files": ["main.py"]},
            {"name": "DB", "purpose": "Storage", "files": ["models.py"]},
        ],
        "key_patterns": ["async"],
    }

    diagram, trace = await _run_diagram(synthesis, mock_provider)

    assert "```" not in diagram
    assert "graph TD" in diagram
    assert "A[API] --> B[DB]" in diagram


@pytest.mark.asyncio
async def test_run_diagram_accepts_bare_mermaid() -> None:
    mock_provider = MagicMock()
    mock_provider.generate_text = AsyncMock(return_value="graph TD\n  A --> B")

    synthesis: dict = {"service_boundaries": [], "key_patterns": []}
    diagram, _ = await _run_diagram(synthesis, mock_provider)

    assert diagram == "graph TD\n  A --> B"


# ---------------------------------------------------------------------------
# run_agent_pipeline — smoke test that the pipeline completes
# (mocks AsyncSessionLocal and all LLM/GitHub calls)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_agent_pipeline_completes_and_persists(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify the full pipeline runs without real I/O and marks the run completed."""
    from app.services import agent_service

    # Mock DB session
    mock_run = MagicMock()
    mock_run.id = 1
    mock_run.status = "queued"
    mock_run.result_id = 99

    mock_db = AsyncMock()
    mock_db.get.return_value = mock_run
    mock_db.commit = AsyncMock()

    class FakeSessionCtx:
        async def __aenter__(self):
            return mock_db
        async def __aexit__(self, *args):
            pass

    monkeypatch.setattr(
        "app.services.agent_service.AsyncSessionLocal",
        lambda: FakeSessionCtx(),
        raising=False,
    )

    # Fix the import inside run_agent_pipeline
    import app.core.database
    monkeypatch.setattr(app.core.database, "AsyncSessionLocal", lambda: FakeSessionCtx())

    # Mock load_intelligence
    mock_graph = MagicMock()
    mock_graph.entrypoints = ["app/main.py"]
    mock_graph.critical_path_files = ["app/main.py"]
    mock_graph.files_scanned = 10
    mock_graph.total_files = 20
    mock_graph.confirmed_edge_count = 5
    mock_graph.graph_confidence = 0.8

    mock_intel = MagicMock()
    mock_intel.repo_owner = "acme"
    mock_intel.repo_name = "backend"
    mock_intel.graph = mock_graph
    mock_intel.total_files_in_repo = 20

    monkeypatch.setattr(
        agent_service,
        "_load_repo_intel",
        AsyncMock(return_value=(mock_intel, None)),
    )

    # Mock _run_planner
    planner_result = {
        "analysis_focus": ["entrypoints"],
        "questions_to_answer": ["What is the main service?"],
        "files_to_fetch": ["app/main.py"],
    }
    monkeypatch.setattr(
        agent_service,
        "_run_planner",
        AsyncMock(return_value=(planner_result, [])),
    )

    # Mock _run_retrieval
    monkeypatch.setattr(
        agent_service,
        "_run_retrieval",
        AsyncMock(return_value=({"app/main.py": "from fastapi import FastAPI"}, [])),
    )

    # Mock _run_synthesis
    synthesis_result = {
        "narrative": "A simple FastAPI service.",
        "service_boundaries": [],
        "key_patterns": ["async"],
        "confidence": 0.8,
    }
    monkeypatch.setattr(
        agent_service,
        "_run_synthesis",
        AsyncMock(return_value=(synthesis_result, [])),
    )

    # Mock _run_diagram
    monkeypatch.setattr(
        agent_service,
        "_run_diagram",
        AsyncMock(return_value=("graph TD\n  A --> B", [])),
    )

    await agent_service.run_agent_pipeline(run_id=1, result_id=99)

    assert mock_run.status == "completed"
    assert mock_run.architecture_narrative == "A simple FastAPI service."
    assert mock_run.mermaid_diagram == "graph TD\n  A --> B"
    assert mock_run.confidence == 0.8
    mock_db.commit.assert_called()
