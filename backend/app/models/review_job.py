"""
ReviewJob model — queue lifecycle for review jobs.

Separate from AnalysisJob so review state is self-contained
and the existing analysis pipeline is not affected.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ReviewJob(Base):
    __tablename__ = "review_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # queued | running | completed | failed
    status: Mapped[str] = mapped_column(String(50), default="queued")
    repo_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    branch: Mapped[str] = mapped_column(String(255), server_default="main")

    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    review = relationship("Review", back_populates="job", uselist=False)
