"""
ReviewJob model — queue lifecycle for review jobs.

Separate from AnalysisJob so review state is self-contained
and the existing analysis pipeline is not affected.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ReviewJob(Base):
    __tablename__ = "review_jobs"
    __table_args__ = (
        Index("ix_review_jobs_status_created_at", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # queued | running | completed | failed
    status: Mapped[str] = mapped_column(String(50), default="queued")
    repo_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    branch: Mapped[str] = mapped_column(String(255), server_default="main")
    commit: Mapped[str | None] = mapped_column(String(40), nullable=True)

    # Set on a cache hit — points to an existing Review.id; no FK to avoid cascade issues
    cached_result_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    # Set when the job was triggered by a GitHub PR webhook
    pr_number: Mapped[int | None] = mapped_column(nullable=True)
    pr_repo: Mapped[str | None] = mapped_column(String(255), nullable=True)

    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    review = relationship("Review", back_populates="job", uselist=False)
