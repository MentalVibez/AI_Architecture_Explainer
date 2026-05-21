"""app/services/agent_service.py

Four-agent analysis pipeline:
  PlannerAgent   — decides which files to fetch based on repo metadata
  RetrievalAgent — fetches file contents via GitHub API tool calls
  SynthesisAgent — produces structured architecture narrative
  DiagramAgent   — generates Mermaid diagram from synthesis output
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.anthropic_provider import AnthropicProvider
from app.models.agent_run import AgentRunORM

logger = logging.getLogger(__name__)

# Hard cap: bound LLM cost and wall time
_MAX_FILES_TO_FETCH = 15
_CONTENT_TRUNCATE_CHARS = 600


async def run_agent_pipeline(run_id: int, result_id: int) -> None:
    """Background task entry point — creates its own DB session to outlive the HTTP request."""
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        run = await db.get(AgentRunORM, run_id)
        if run is None:
            logger.error("agent_run %s not found", run_id)
            return

        run.status = "running"
        await db.commit()

        try:
            provider = AnthropicProvider()
            trace: list[dict[str, Any]] = []

            repo_intel, _ = await _load_repo_intel(result_id, db)
            owner = repo_intel.repo_owner
            repo = repo_intel.repo_name

            planner_result, planner_trace = await _run_planner(
                result_id, repo_intel, db, provider
            )
            trace.append({"agent": "planner", "messages": planner_trace})

            files_to_fetch: list[str] = planner_result.get("files_to_fetch", [])
            files_to_fetch = files_to_fetch[:_MAX_FILES_TO_FETCH]

            retrieved, retrieval_trace = await _run_retrieval(
                files_to_fetch, owner, repo, provider
            )
            trace.append({"agent": "retrieval", "messages": retrieval_trace})

            synthesis_result, synthesis_trace = await _run_synthesis(
                retrieved, repo_intel, provider
            )
            trace.append({"agent": "synthesis", "messages": synthesis_trace})

            mermaid, diagram_trace = await _run_diagram(synthesis_result, provider)
            trace.append({"agent": "diagram", "messages": diagram_trace})

            run.status = "completed"
            run.agent_trace = trace
            run.architecture_narrative = synthesis_result.get("narrative", "")
            run.mermaid_diagram = mermaid
            run.confidence = float(synthesis_result.get("confidence", 0.7))
            run.completed_at = datetime.now(timezone.utc)

        except Exception as exc:
            logger.exception("agent_run %s failed: %s", run_id, exc)
            run.status = "failed"
            run.error = str(exc)
            run.completed_at = datetime.now(timezone.utc)

        await db.commit()


# ---------------------------------------------------------------------------
# Stage 1 — Planner
# ---------------------------------------------------------------------------

async def _run_planner(
    result_id: int,
    repo_intel: Any,
    db: AsyncSession,
    provider: AnthropicProvider,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Returns (structured plan dict, message trace)."""
    from app.models.intelligence import FileIntelligenceORM

    # Build a compact repo summary for the prompt
    entrypoints = repo_intel.graph.entrypoints[:10] if repo_intel.graph else []
    critical_path = repo_intel.graph.critical_path_files[:10] if repo_intel.graph else []
    total_files = repo_intel.total_files_in_repo

    file_meta_summary = (
        f"Repo: {repo_intel.repo_owner}/{repo_intel.repo_name}\n"
        f"Total files: {total_files}\n"
        f"Entrypoints: {', '.join(entrypoints) or 'unknown'}\n"
        f"Critical path: {', '.join(critical_path) or 'unknown'}\n"
    )

    tools = [
        {
            "name": "list_files",
            "description": (
                "List files in this repository filtered by role. "
                "Returns up to 40 files with their path, role, LOC, and complexity score."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "role_filter": {
                        "type": "string",
                        "description": (
                            "Filter by file role. One of: entrypoint, service, module, "
                            "utility, config, test, unknown. Leave empty for all files."
                        ),
                    }
                },
                "required": [],
            },
        }
    ]

    async def tool_executor(name: str, inputs: dict[str, Any]) -> str:
        if name != "list_files":
            return "Unknown tool"
        role_filter = inputs.get("role_filter", "")
        stmt = select(FileIntelligenceORM).where(
            FileIntelligenceORM.result_id == result_id
        )
        if role_filter:
            stmt = stmt.where(FileIntelligenceORM.role == role_filter)
        stmt = stmt.limit(40)
        rows = (await db.execute(stmt)).scalars().all()
        items = [
            {"path": r.path, "role": r.role, "loc": r.loc, "complexity": r.complexity_score}
            for r in rows
        ]
        return json.dumps(items)

    system = (
        "You are an architecture planning agent. Your job is to decide which source files "
        "are most important to fetch and read to understand the architecture of a codebase. "
        "Use the list_files tool to explore file roles, then output a JSON plan."
    )
    messages = [
        {
            "role": "user",
            "content": (
                f"{file_meta_summary}\n\n"
                "Use list_files to explore the codebase, then respond with a JSON object "
                "containing:\n"
                "- analysis_focus: list of strings describing what to look for\n"
                "- questions_to_answer: list of architecture questions\n"
                "- files_to_fetch: list of file paths (most important first, max 15)\n\n"
                "Prioritize entrypoints, service boundaries, config files, and key modules."
            ),
        }
    ]

    trace, final_text = await provider.run_agentic_loop(
        system=system,
        messages=messages,
        tools=tools,
        tool_executor=tool_executor,
        max_iterations=6,
        stage="agent_planner",
    )

    plan = _parse_json_from_text(final_text) or {
        "analysis_focus": [],
        "questions_to_answer": [],
        "files_to_fetch": critical_path[:_MAX_FILES_TO_FETCH],
    }
    return plan, _serialize_trace(trace)


# ---------------------------------------------------------------------------
# Stage 2 — Retrieval
# ---------------------------------------------------------------------------

async def _run_retrieval(
    files_to_fetch: list[str],
    owner: str,
    repo: str,
    provider: AnthropicProvider,
) -> tuple[dict[str, str], list[dict[str, Any]]]:
    """Returns ({path: content_snippet}, message trace)."""
    from app.services.github_service import get_file_content

    fetched: dict[str, str] = {}

    tools = [
        {
            "name": "get_file_content",
            "description": "Fetch the content of a file from the GitHub repository.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to repo root (e.g. src/main.py)",
                    }
                },
                "required": ["path"],
            },
        }
    ]

    async def tool_executor(name: str, inputs: dict[str, Any]) -> str:
        if name != "get_file_content":
            return "Unknown tool"
        path = inputs.get("path", "")
        if len(fetched) >= _MAX_FILES_TO_FETCH:
            return "Fetch limit reached."
        content = await get_file_content(owner, repo, path)
        if content is None:
            return f"File not found: {path}"
        snippet = content[:_CONTENT_TRUNCATE_CHARS]
        fetched[path] = snippet
        return snippet

    file_list_text = "\n".join(f"- {p}" for p in files_to_fetch)
    system = (
        "You are a code retrieval agent. Fetch the specified files using the "
        "get_file_content tool, then summarize what you retrieved."
    )
    messages = [
        {
            "role": "user",
            "content": (
                f"Fetch these files from {owner}/{repo}:\n{file_list_text}\n\n"
                "Use get_file_content for each file. After fetching, confirm which files "
                "were retrieved successfully."
            ),
        }
    ]

    trace, _ = await provider.run_agentic_loop(
        system=system,
        messages=messages,
        tools=tools,
        tool_executor=tool_executor,
        max_iterations=_MAX_FILES_TO_FETCH + 2,
        stage="agent_retrieval",
    )

    return fetched, _serialize_trace(trace)


# ---------------------------------------------------------------------------
# Stage 3 — Synthesis
# ---------------------------------------------------------------------------

_SYNTHESIS_SCHEMA = {
    "type": "object",
    "properties": {
        "narrative": {
            "type": "string",
            "description": "2-4 paragraph architecture narrative",
        },
        "service_boundaries": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "purpose": {"type": "string"},
                    "files": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["name", "purpose", "files"],
            },
        },
        "key_patterns": {
            "type": "array",
            "items": {"type": "string"},
        },
        "confidence": {
            "type": "number",
            "description": "0.0–1.0 confidence in the analysis",
        },
    },
    "required": ["narrative", "service_boundaries", "key_patterns", "confidence"],
}


async def _run_synthesis(
    retrieved: dict[str, str],
    repo_intel: Any,
    provider: AnthropicProvider,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    file_snippets = "\n\n".join(
        f"=== {path} ===\n{content}" for path, content in retrieved.items()
    )
    graph_summary = ""
    if repo_intel.graph:
        g = repo_intel.graph
        graph_summary = (
            f"Graph: {g.files_scanned}/{g.total_files} files scanned, "
            f"{g.confirmed_edge_count} confirmed edges, "
            f"confidence={g.graph_confidence:.2f}"
        )

    prompt = (
        f"Analyze the architecture of {repo_intel.repo_owner}/{repo_intel.repo_name}.\n\n"
        f"{graph_summary}\n\n"
        f"Retrieved file contents:\n{file_snippets}\n\n"
        "Identify service boundaries, key architectural patterns, and produce a clear "
        "narrative explaining how the system is structured."
    )

    result = await provider.generate_json(prompt, _SYNTHESIS_SCHEMA, stage="agent_synthesis")
    # Return a minimal trace record (no tool calls in this stage)
    trace: list[dict[str, Any]] = [{"role": "user", "content": prompt[:200] + "..."}]
    return result, trace


# ---------------------------------------------------------------------------
# Stage 4 — Diagram
# ---------------------------------------------------------------------------

async def _run_diagram(
    synthesis: dict[str, Any],
    provider: AnthropicProvider,
) -> tuple[str, list[dict[str, Any]]]:
    boundaries = synthesis.get("service_boundaries", [])
    boundary_text = "\n".join(
        f"- {b['name']}: {b['purpose']} (files: {', '.join(b['files'][:3])})"
        for b in boundaries
    )
    patterns = ", ".join(synthesis.get("key_patterns", []))

    prompt = (
        "Generate a Mermaid graph TD diagram for a software system with these components:\n\n"
        f"{boundary_text}\n\n"
        f"Key patterns: {patterns}\n\n"
        "Rules:\n"
        "- Use `graph TD` syntax\n"
        "- Label nodes clearly with component names\n"
        "- Show data flow and dependencies with arrows\n"
        "- Output ONLY the Mermaid code block, no explanation\n"
        "- Keep it clean: max 20 nodes"
    )

    system = (
        "You are an architecture diagram agent. Output only valid Mermaid diagram syntax. "
        "No markdown fences, no explanation."
    )
    diagram = await provider.generate_text(prompt, system=system, stage="agent_diagram")
    # Strip ```mermaid fences if the model included them
    diagram = diagram.strip()
    if diagram.startswith("```"):
        lines = diagram.split("\n")
        diagram = "\n".join(
            line for line in lines if not line.strip().startswith("```")
        ).strip()

    trace: list[dict[str, Any]] = [{"role": "user", "content": prompt[:200] + "..."}]
    return diagram, trace


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _load_repo_intel(result_id: int, db: AsyncSession) -> tuple[Any, Any]:
    from app.services.intelligence_persistence import load_intelligence
    return await load_intelligence(result_id, db)


def _parse_json_from_text(text: str) -> dict[str, Any] | None:
    """Extract a JSON object from LLM free-text output."""
    text = text.strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end == 0:
        return None
    try:
        return json.loads(text[start:end])
    except json.JSONDecodeError:
        return None


def _serialize_trace(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert message dicts to JSON-serializable form (strip non-serializable objects)."""
    result = []
    for msg in messages:
        try:
            json.dumps(msg)
            result.append(msg)
        except (TypeError, ValueError):
            result.append({"role": msg.get("role", "unknown"), "content": "[non-serializable]"})
    return result
