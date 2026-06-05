"""SQLAlchemy models for devcontainer management.

Uses dialect-agnostic column types so the same model works with both
SQLite (dev) and Postgres (staging / production).
"""
from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def _uuid() -> str:
    return str(uuid4())


class Devcontainer(Base):
    """Generated devcontainer configurations (versioned)."""

    __tablename__ = "devcontainers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    job_id: Mapped[int] = mapped_column(Integer, ForeignKey("atlas_jobs.id"), nullable=False, index=True)
    # org_id stores the GitHub login of the user who generated the container.
    # Used as the RLS current_setting key for org isolation on Postgres.
    org_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    config: Mapped[dict] = mapped_column(JSON, nullable=False)
    features: Mapped[list] = mapped_column(JSON, default=list)
    repo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, onupdate=func.now(), nullable=True)


class AuditLog(Base):
    """Immutable audit trail for SOC2 compliance."""

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    org_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)

    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)

    result: Mapped[str] = mapped_column(String(50), nullable=False, default="success")
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False, index=True)


class AnalysisEmbedding(Base):
    """Vector embeddings for semantic search (pgvector on Postgres, text blob on SQLite)."""

    __tablename__ = "analysis_embeddings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    job_id: Mapped[int] = mapped_column(Integer, ForeignKey("atlas_jobs.id"), nullable=False, index=True)
    org_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    chunk_type: Mapped[str] = mapped_column(String(50), nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)

    # On Postgres: vector(1536) added via raw DDL in migration 0024.
    # On SQLite: stored as JSON-encoded float list (Text).
    embedding: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
