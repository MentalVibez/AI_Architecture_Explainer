"""app/services/metrics_service.py

Fire-and-forget LLM usage recording. Called from AnthropicProvider after
each API call — creates its own DB session so it never blocks the pipeline.
"""

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)

# Sonnet 4.6 pricing (USD per 1M tokens)
_INPUT_COST_PER_M = 3.0
_OUTPUT_COST_PER_M = 15.0


def estimate_cost_usd(input_tokens: int, output_tokens: int) -> float:
    return (input_tokens * _INPUT_COST_PER_M + output_tokens * _OUTPUT_COST_PER_M) / 1_000_000


async def record_llm_usage(
    *,
    stage: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    duration_ms: int,
    result_id: int | None = None,
) -> None:
    """Persist one LLM call record. Never raises — failures are logged and swallowed."""
    try:
        from app.core.database import AsyncSessionLocal
        from app.models.llm_usage import LLMUsageORM

        async with AsyncSessionLocal() as db:
            db.add(LLMUsageORM(
                result_id=result_id,
                stage=stage,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                duration_ms=duration_ms,
            ))
            await db.commit()
    except Exception:
        logger.debug("Failed to record LLM usage — non-critical", exc_info=True)


def schedule_record(
    *,
    stage: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    duration_ms: int,
    result_id: int | None = None,
) -> None:
    """Schedule a fire-and-forget usage record from async context."""
    coro = record_llm_usage(
        stage=stage,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        duration_ms=duration_ms,
        result_id=result_id,
    )
    try:
        asyncio.create_task(coro)
    except RuntimeError:
        # No running event loop — close the coroutine to silence the warning
        coro.close()
