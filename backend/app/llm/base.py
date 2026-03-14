from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMProvider(Protocol):
    async def generate_json(self, prompt: str, schema: dict) -> dict:
        """Generate a structured JSON response conforming to the given schema."""
        ...

    async def generate_text(self, prompt: str) -> str:
        """Generate a free-form text response."""
        ...
