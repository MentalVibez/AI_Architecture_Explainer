from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("analysis_jobs.id"), unique=True)
    repo_snapshot_sha: Mapped[str | None] = mapped_column(String(40), nullable=True)
    detected_stack: Mapped[dict] = mapped_column(JSON, default=dict)
    dependencies: Mapped[dict] = mapped_column(JSON, default=dict)
    entry_points: Mapped[list] = mapped_column(JSON, default=list)
    folder_map: Mapped[list] = mapped_column(JSON, default=list)
    diagram_mermaid: Mapped[str | None] = mapped_column(Text, nullable=True)
    developer_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    hiring_manager_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    caveats: Mapped[list] = mapped_column(JSON, default=list)
    raw_evidence: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    job = relationship("AnalysisJob", back_populates="result")
