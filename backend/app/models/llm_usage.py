"""app/models/llm_usage.py — per-call LLM token and latency tracking."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class LLMUsageORM(Base):
    """One row per LLM API call. Written fire-and-forget from the provider layer."""

    __tablename__ = "llm_usage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # nullable — not all calls are tied to a specific analysis result
    result_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)

    # pipeline stage label, e.g. "developer_summary", "context_reviewer", "planner"
    stage: Mapped[str] = mapped_column(String(64), nullable=False, default="unknown")

    model: Mapped[str] = mapped_column(String(64), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
