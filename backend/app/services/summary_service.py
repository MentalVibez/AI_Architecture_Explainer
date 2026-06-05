"""Generates developer and hiring manager summaries using the LLM."""
import asyncio
from typing import Any

from app.llm.anthropic_provider import AnthropicProvider
from app.llm.prompt_builder import (
    build_developer_summary_prompt,
    build_devcontainer_prompt,
    build_diagram_prompt,
    build_hiring_manager_summary_prompt,
)


async def generate_summaries(evidence: dict[str, Any]) -> dict[str, str]:
    provider = AnthropicProvider()

    developer_summary, hiring_manager_summary, diagram_mermaid = await asyncio.gather(
        provider.generate_text(build_developer_summary_prompt(evidence), stage="developer_summary"),
        provider.generate_text(
            build_hiring_manager_summary_prompt(evidence),
            stage="hiring_manager_summary",
        ),
        provider.generate_text(build_diagram_prompt(evidence), stage="atlas_diagram"),
    )

    return {
        "developer_summary": developer_summary,
        "hiring_manager_summary": hiring_manager_summary,
        "diagram_mermaid": diagram_mermaid,
    }


# JSON schema passed to Claude tool_use for devcontainer generation.
# Keeps Claude's output structurally valid without needing post-processing.
_DEVCONTAINER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "description": "Short container slug"},
        "image": {"type": "string", "description": "Official devcontainer base image URI"},
        "features": {
            "type": "object",
            "description": "ghcr.io/devcontainers/features/* URIs mapped to config objects",
            "additionalProperties": {"type": "object"},
        },
        "postCreateCommand": {
            "type": "string",
            "description": "Shell command(s) to run after the container is created",
        },
        "containerEnv": {
            "type": "object",
            "description": "Environment variables forwarded from the developer's shell",
            "additionalProperties": {"type": "string"},
        },
        "forwardPorts": {
            "type": "array",
            "items": {"type": "integer"},
            "description": "Ports to expose from the container",
        },
        "customizations": {
            "type": "object",
            "description": "IDE customizations (vscode.extensions, vscode.settings)",
        },
        "remoteUser": {"type": "string", "description": "User inside the container"},
    },
    "required": ["name", "image", "postCreateCommand", "remoteUser"],
}


async def generate_devcontainer_config(evidence: dict[str, Any]) -> dict[str, Any]:
    """Generate a repo-specific devcontainer.json using Claude tool-use.

    Uses structured output (tool_use) so the response is always valid JSON
    matching _DEVCONTAINER_SCHEMA. Raises on Anthropic API errors — callers
    should catch and fall back to the deterministic generator.
    """
    provider = AnthropicProvider()
    return await provider.generate_json(
        prompt=build_devcontainer_prompt(evidence),
        schema=_DEVCONTAINER_SCHEMA,
        stage="devcontainer_generation",
    )
