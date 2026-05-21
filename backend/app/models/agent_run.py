"""app/models/agent_run.py — ORM model for multi-agent analysis runs."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AgentRunORM(Base):
    """One row per agent analysis run triggered for a result."""

    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    result_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # queued | running | completed | failed
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued")

    # Full message trace per agent: [{agent, messages, tool_calls}]
    agent_trace: Mapped[list | None] = mapped_column(JSON, nullable=True)

    architecture_narrative: Mapped[str | None] = mapped_column(Text, nullable=True)
    mermaid_diagram: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
