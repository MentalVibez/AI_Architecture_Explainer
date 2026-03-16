"""
backend/app/models/review.py

SQLAlchemy model for review results. Drop this into the existing
backend/app/models/ directory alongside repos.py, jobs.py, results.py.

Designed to work with the existing SQLAlchemy + Alembic + Supabase stack.
"""
import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Float, DateTime, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB

# Import Base from the existing backend
# from app.core.database import Base


class Review:
    """
    Stores a completed review report.
    One Review row per completed review job.
    JSON columns hold the full structured report payloads.
    """
    __tablename__ = "reviews"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=False, index=True
    )

    # Repo identity
    repo_url: Mapped[str] = mapped_column(String(2048), nullable=False, index=True)
    commit:   Mapped[str] = mapped_column(String(40), nullable=True)
    branch:   Mapped[str] = mapped_column(String(255), default="main")

    # Engine metadata — needed to explain score differences across deployments
    ruleset_version:  Mapped[str] = mapped_column(String(20), nullable=False)
    schema_version:   Mapped[str] = mapped_column(String(10), default="1.0")
    depth_level:      Mapped[str] = mapped_column(String(50), nullable=True)
    confidence_label: Mapped[str] = mapped_column(String(10), nullable=True)

    # Score summary — kept as scalars for easy querying
    overall_score:          Mapped[int] = mapped_column(Integer, nullable=True)
    security_score:         Mapped[int] = mapped_column(Integer, nullable=True)
    testing_score:          Mapped[int] = mapped_column(Integer, nullable=True)
    maintainability_score:  Mapped[int] = mapped_column(Integer, nullable=True)
    reliability_score:      Mapped[int] = mapped_column(Integer, nullable=True)
    ops_score:              Mapped[int] = mapped_column(Integer, nullable=True)
    devex_score:            Mapped[int] = mapped_column(Integer, nullable=True)

    # Verdict summary — for quick display without loading full payload
    verdict_label:          Mapped[str]  = mapped_column(String(50), nullable=True)
    trust_recommendation:   Mapped[str]  = mapped_column(String(20), nullable=True)
    production_suitable:    Mapped[bool] = mapped_column(default=False)
    anti_gaming_verdict:    Mapped[str]  = mapped_column(String(30), nullable=True)

    # Full structured payloads — JSON columns
    # In SQLite: use Text + JSON serialization
    # In Postgres/Supabase: use JSONB for indexing
    scorecard_json:    Mapped[dict] = mapped_column(JSONB, nullable=True)
    findings_json:     Mapped[list] = mapped_column(JSONB, nullable=True)
    coverage_json:     Mapped[dict] = mapped_column(JSONB, nullable=True)
    depth_json:        Mapped[dict] = mapped_column(JSONB, nullable=True)
    anti_gaming_json:  Mapped[dict] = mapped_column(JSONB, nullable=True)
    summary_json:      Mapped[dict] = mapped_column(JSONB, nullable=True)
    meta_json:         Mapped[dict] = mapped_column(JSONB, nullable=True)

    # Failure tracking — specific failure mode, not just generic job error
    error_code:    Mapped[str]  = mapped_column(String(50), nullable=True)
    error_message: Mapped[str]  = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    @classmethod
    def from_report(cls, job_id, report, branch="main") -> "Review":
        """Build a Review row from a completed ReviewReport."""
        sc = report.scorecard
        interp = report.interpretation
        return cls(
            job_id=job_id,
            repo_url=report.repo.url,
            commit=report.repo.commit,
            branch=branch,
            ruleset_version=report.ruleset_version,
            schema_version=report.schema_version,
            depth_level=report.depth.level if report.depth else None,
            confidence_label=report.meta.confidence_label if report.meta else None,
            overall_score=report.meta.overall_score if report.meta else None,
            security_score=sc.security,
            testing_score=sc.testing,
            maintainability_score=sc.maintainability,
            reliability_score=sc.reliability,
            ops_score=sc.operational_readiness,
            devex_score=sc.developer_experience,
            verdict_label=interp.overall_label if interp else None,
            trust_recommendation=interp.trust_recommendation if interp else None,
            production_suitable=interp.production_suitable if interp else False,
            anti_gaming_verdict=report.anti_gaming.overall_verdict if report.anti_gaming else None,
            scorecard_json=sc.model_dump() if sc else None,
            findings_json=[f.model_dump() for f in report.findings],
            coverage_json=report.coverage.model_dump() if report.coverage else None,
            depth_json=report.depth.model_dump() if report.depth else None,
            anti_gaming_json=report.anti_gaming.model_dump() if report.anti_gaming else None,
            summary_json=report.review_summary.model_dump() if report.review_summary else None,
            meta_json=report.meta.model_dump() if report.meta else None,
        )
