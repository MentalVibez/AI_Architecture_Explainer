
from typing import Optional

import anthropic

from app.core.config import settings

MODEL = "claude-sonnet-4-6"


class AnthropicProvider:
    def __init__(self, api_key: Optional[str] = None) -> None:
        self._client = anthropic.AsyncAnthropic(
            api_key=api_key or settings.anthropic_api_key
        )

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

    async def generate_text(self, prompt: str, system: Optional[str] = None) -> str:
        kwargs: dict = {
            "model": MODEL,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system
        response = await self._client.messages.create(**kwargs)
        return response.content[0].text  # type: ignore[union-attr]
