from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AtlasJob(Base):
    __tablename__ = "atlas_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    repo_id: Mapped[int] = mapped_column(ForeignKey("repos.id"))
    # queued | running | completed | failed
    status: Mapped[str] = mapped_column(String(50), default="queued")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    repo = relationship("Repo")
    result = relationship("AtlasResult", back_populates="job", uselist=False)


# Backward-compat alias used by routes_analysis.py imports
AnalysisJob = AtlasJob
