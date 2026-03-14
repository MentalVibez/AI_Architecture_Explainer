"""Generates developer and hiring manager summaries using the LLM."""
from typing import Any

from app.llm.anthropic_provider import AnthropicProvider
from app.llm.prompt_builder import (
    build_developer_summary_prompt,
    build_diagram_prompt,
    build_hiring_manager_summary_prompt,
)


async def generate_summaries(evidence: dict[str, Any]) -> dict[str, str]:
    provider = AnthropicProvider()

    developer_summary = await provider.generate_text(build_developer_summary_prompt(evidence))
    hiring_manager_summary = await provider.generate_text(build_hiring_manager_summary_prompt(evidence))
    diagram_mermaid = await provider.generate_text(build_diagram_prompt(evidence))

    return {
        "developer_summary": developer_summary,
        "hiring_manager_summary": hiring_manager_summary,
        "diagram_mermaid": diagram_mermaid,
    }
