
import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import anthropic

from app.core.config import settings

MODEL = "claude-sonnet-4-6"


def _parse_custom_headers(raw: str) -> dict[str, str]:
    """Parse 'Key: Value, Key2: Value2' into a dict."""
    headers = {}
    for part in raw.split(","):
        part = part.strip()
        if ":" in part:
            k, _, v = part.partition(":")
            headers[k.strip()] = v.strip()
    return headers


class AnthropicProvider:
    def __init__(self, api_key: str | None = None) -> None:
        kwargs: dict = {"api_key": api_key or settings.anthropic_api_key}
        if settings.anthropic_base_url:
            kwargs["base_url"] = settings.anthropic_base_url
        if settings.anthropic_custom_headers:
            kwargs["default_headers"] = _parse_custom_headers(settings.anthropic_custom_headers)
        self._client = anthropic.AsyncAnthropic(**kwargs)

    async def generate_json(self, prompt: str, schema: dict) -> dict:
        """Use tool-use to enforce structured JSON output matching the given schema."""
        response = await self._client.messages.create(
            model=MODEL,
            max_tokens=4096,
            tools=[
                {
                    "name": "structured_output",
                    "description": "Return a structured JSON response",
                    "input_schema": schema,
                }
            ],
            tool_choice={"type": "tool", "name": "structured_output"},
            messages=[{"role": "user", "content": prompt}],
        )

        for block in response.content:
            if block.type == "tool_use" and block.name == "structured_output":
                return block.input  # type: ignore[return-value]

        raise ValueError("Anthropic response did not include structured tool output")

    async def run_agentic_loop(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        tool_executor: Callable[[str, dict[str, Any]], Awaitable[str]],
        max_iterations: int = 10,
    ) -> tuple[list[dict[str, Any]], str]:
        """Run an iterative tool-use loop until the model stops calling tools.

        Returns (full_message_trace, final_text_output).
        """
        trace: list[dict[str, Any]] = list(messages)
        final_text = ""

        for _ in range(max_iterations):
            response = await self._client.messages.create(
                model=MODEL,
                max_tokens=4096,
                system=system,
                tools=tools,
                messages=trace,
            )

            # Collect text from this turn
            for block in response.content:
                if hasattr(block, "text"):
                    final_text = block.text

            if response.stop_reason != "tool_use":
                break

            # Build assistant turn from response content
            assistant_turn: dict[str, Any] = {
                "role": "assistant",
                "content": [b.model_dump() for b in response.content],
            }
            trace.append(assistant_turn)

            # Execute each tool call and collect results
            tool_results = []
            tool_blocks = [b for b in response.content if b.type == "tool_use"]
            results = await asyncio.gather(
                *[tool_executor(b.name, b.input) for b in tool_blocks]
            )
            for block, result in zip(tool_blocks, results):
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })

            trace.append({"role": "user", "content": tool_results})

        return trace, final_text

    async def generate_text(self, prompt: str, system: str | None = None) -> str:
        kwargs: dict = {
            "model": MODEL,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system
        response = await self._client.messages.create(**kwargs)
        return response.content[0].text  # type: ignore[union-attr]
