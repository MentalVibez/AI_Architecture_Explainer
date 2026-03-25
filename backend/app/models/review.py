"""
Review result model. Stores the completed ReviewReport artifact.

Separation of concerns:
    ReviewJob = queue lifecycle (queued → running → completed/failed)
    Review    = result payload (the report itself)

One Review row per completed job. Failed jobs get a Review row too
(with error_code + error_message set, report fields null).
"""
import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

# JSONB on Postgres, plain JSON on SQLite (dev)
_JSON = JSONB().with_variant(JSON(), "sqlite")

from app.core.database import Base


class Review(Base):
    __tablename__ = "reviews"

    # ── Identity ──────────────────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("review_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Repo identity ─────────────────────────────────────────────────────────
    repo_url: Mapped[str] = mapped_column(String(2048), nullable=False, index=True)
    commit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    branch: Mapped[str] = mapped_column(String(255), server_default="main")

    # ── Engine metadata ───────────────────────────────────────────────────────
    ruleset_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    schema_version: Mapped[str] = mapped_column(String(10), server_default="1.0")
    depth_level: Mapped[str | None] = mapped_column(String(50), nullable=True)
    confidence_label: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # ── Score scalars ─────────────────────────────────────────────────────────
    overall_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    security_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    testing_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    maintainability_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reliability_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    operations_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    developer_experience_score: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ── Verdict scalars ───────────────────────────────────────────────────────
    verdict_label: Mapped[str | None] = mapped_column(String(50), nullable=True)
    trust_recommendation: Mapped[str | None] = mapped_column(String(20), nullable=True)
    production_suitable: Mapped[bool] = mapped_column(Boolean, server_default="false")
    anti_gaming_verdict: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # ── Full report payloads ──────────────────────────────────────────────────
    scorecard_json: Mapped[dict | None] = mapped_column(_JSON, nullable=True)
    findings_json: Mapped[list | None] = mapped_column(_JSON, nullable=True)
    coverage_json: Mapped[dict | None] = mapped_column(_JSON, nullable=True)
    depth_json: Mapped[dict | None] = mapped_column(_JSON, nullable=True)
    anti_gaming_json: Mapped[dict | None] = mapped_column(_JSON, nullable=True)
    summary_json: Mapped[dict | None] = mapped_column(_JSON, nullable=True)
    meta_json: Mapped[dict | None] = mapped_column(_JSON, nullable=True)

    # ── Failure tracking ──────────────────────────────────────────────────────
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    job = relationship("ReviewJob", back_populates="review")

    # ── Factory ───────────────────────────────────────────────────────────────
    @classmethod
    def from_report(cls, job_id: uuid.UUID, report, branch: str = "main") -> "Review":
        """Build a Review row from a completed ReviewReport. Never raises."""
        sc = report.scorecard
        interp = report.interpretation
        meta = report.meta
        return cls(
            job_id=job_id,
            repo_url=report.repo.url,
            commit=report.repo.commit,
            branch=branch,
            ruleset_version=getattr(meta, "ruleset_version", None),
            schema_version=getattr(meta, "schema_version", "1.0"),
            depth_level=report.depth.level if report.depth else None,
            confidence_label=getattr(meta, "confidence_label", None),
            overall_score=getattr(meta, "overall_score", None),
            security_score=sc.security,
            testing_score=sc.testing,
            maintainability_score=sc.maintainability,
            reliability_score=sc.reliability,
            operations_score=sc.operational_readiness,
            developer_experience_score=sc.developer_experience,
            verdict_label=getattr(interp, "overall_label", None),
            trust_recommendation=getattr(interp, "trust_recommendation", None),
            production_suitable=getattr(interp, "production_suitable", False),
            anti_gaming_verdict=(
                report.anti_gaming.overall_verdict if report.anti_gaming else None
            ),
            scorecard_json=sc.model_dump() if sc else None,
            findings_json=[f.model_dump() for f in report.findings],
            coverage_json=report.coverage.model_dump() if report.coverage else None,
            depth_json=report.depth.model_dump() if report.depth else None,
            anti_gaming_json=(
                report.anti_gaming.model_dump() if report.anti_gaming else None
            ),
            summary_json=(
                report.review_summary.model_dump() if report.review_summary else None
            ),
            meta_json=meta.model_dump() if meta else None,
            completed_at=datetime.utcnow(),
        )

    @classmethod
    def from_error(
        cls,
        job_id: uuid.UUID,
        repo_url: str,
        error_code: str,
        error_message: str,
        branch: str = "main",
    ) -> "Review":
        """Build a Review row for a failed job."""
        return cls(
            job_id=job_id,
            repo_url=repo_url,
            branch=branch,
            error_code=error_code,
            error_message=error_message,
            completed_at=datetime.utcnow(),
        )
