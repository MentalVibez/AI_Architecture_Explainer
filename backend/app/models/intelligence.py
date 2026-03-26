"""
app/models/intelligence.py
---------------------------
SQLAlchemy ORM models for the deep intelligence layer.

These tables are ADDITIVE to the existing schema (jobs, results).
They extend the existing result with file-level intelligence data.

Migration strategy:
  - Add these as new tables in a single Alembic migration (0011)
  - Foreign key to existing analysis_results table (Integer PK)
  - Never modify existing tables — additive only

Table hierarchy:
  analysis_results (existing, Integer PK)
    └── file_intelligence (one per scanned file per result)
    └── dependency_edges (one per import edge per result)
    └── code_findings (one per finding per result)
    └── production_scores (one per result — the scorecard)
        └── dimension_scores (one per dimension per score)
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class FileIntelligenceORM(Base):
    """
    One row per file per analysis result.
    Stores the core FileIntelligence fields needed for the UI.
    """
    __tablename__ = "file_intelligence"

    id = Column(Integer, primary_key=True, autoincrement=True)
    result_id = Column(Integer, nullable=False, index=True)

    # Core identity
    path = Column(String(512), nullable=False)
    language = Column(String(32), nullable=False, default="unknown")
    role = Column(String(32), nullable=False, default="unknown")

    # Classification
    is_entrypoint = Column(Boolean, nullable=False, default=False)
    is_test = Column(Boolean, nullable=False, default=False)
    is_on_critical_path = Column(Boolean, nullable=False, default=False)

    # Metrics
    loc = Column(Integer, nullable=False, default=0)
    complexity_score = Column(Float, nullable=False, default=0.0)
    function_count = Column(Integer, nullable=False, default=0)
    caller_count = Column(Integer, nullable=False, default=0)

    # Quality signals
    has_type_annotations = Column(Boolean, nullable=False, default=False)
    has_error_handling = Column(Boolean, nullable=False, default=False)
    was_truncated = Column(Boolean, nullable=False, default=False)
    confidence = Column(Float, nullable=False, default=1.0)

    # Stored as comma-separated strings for simple querying
    sensitive_operations = Column(Text, nullable=False, default="")
    framework_signals = Column(Text, nullable=False, default="")

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("result_id", "path", name="uq_file_intelligence_result_path"),
    )


class DependencyEdgeORM(Base):
    """
    One row per dependency edge per analysis result.
    Confirmed + unresolved edges are both stored.
    Unresolved edges are essential for honest graph confidence reporting.
    """
    __tablename__ = "dependency_edges"

    id = Column(Integer, primary_key=True, autoincrement=True)
    result_id = Column(Integer, nullable=False, index=True)

    source_path = Column(String(512), nullable=False)
    target_path = Column(String(512), nullable=True)  # NULL for unresolved
    raw_import = Column(String(512), nullable=False)
    kind = Column(String(32), nullable=False, default="import")

    # confirmed | inferred | unresolved
    confidence = Column(String(16), nullable=False)

    # Null for confirmed edges; reason code for unresolved
    unresolved_reason = Column(String(64), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "result_id", "source_path", "raw_import",
            name="uq_dependency_edge_result_source_import",
        ),
    )


class CodeFindingORM(Base):
    """
    One row per code finding per analysis result.
    Only non-suppressed findings are stored.
    Evidence snippet is stored truncated to 500 chars.
    """
    __tablename__ = "code_findings"

    id = Column(String(8), primary_key=True)
    result_id = Column(Integer, nullable=False, index=True)

    file_path = Column(String(512), nullable=False)
    category = Column(String(32), nullable=False)
    severity = Column(String(16), nullable=False, index=True)
    source = Column(String(16), nullable=False)

    line_start = Column(Integer, nullable=False)
    line_end = Column(Integer, nullable=False)

    evidence_snippet = Column(String(500), nullable=False)
    title = Column(String(256), nullable=False)
    explanation = Column(Text, nullable=False)
    remediation = Column(Text, nullable=True)

    score_impact = Column(Integer, nullable=False, default=0)
    confidence = Column(Float, nullable=False, default=1.0)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class ProductionScoreORM(Base):
    """
    One row per analysis result — the composite scorecard.
    """
    __tablename__ = "production_scores"

    id = Column(Integer, primary_key=True, autoincrement=True)
    result_id = Column(Integer, nullable=False, unique=True, index=True)

    composite_score = Column(Integer, nullable=False)
    composite_label = Column(String(32), nullable=False)

    # Confidence breakdown
    confidence_extraction = Column(Float, nullable=False, default=0.0)
    confidence_graph = Column(Float, nullable=False, default=0.0)
    confidence_finding = Column(Float, nullable=False, default=0.0)
    confidence_score = Column(Float, nullable=False, default=0.0)

    # Finding counts by severity
    critical_count = Column(Integer, nullable=False, default=0)
    high_count = Column(Integer, nullable=False, default=0)
    medium_count = Column(Integer, nullable=False, default=0)
    low_count = Column(Integer, nullable=False, default=0)
    total_findings = Column(Integer, nullable=False, default=0)

    # Graph quality
    graph_semantics_version = Column(Integer, nullable=False, default=2)
    critical_path_algorithm = Column(String(32), nullable=False, default="bfs_depth_2")
    graph_confidence = Column(Float, nullable=False, default=0.0)
    confirmed_edge_count = Column(Integer, nullable=False, default=0)
    unresolved_edge_count = Column(Integer, nullable=False, default=0)

    # Store overall confidence for easy querying
    overall_confidence = Column(Float, nullable=False, default=0.0)

    # Repo identity (denormalized for fast lookup)
    repo_url = Column(Text, nullable=True)
    repo_owner = Column(String(255), nullable=True)
    repo_name = Column(String(255), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    dimension_scores = relationship(
        "DimensionScoreORM",
        backref="production_score",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class DimensionScoreORM(Base):
    """
    One row per scoring dimension per production score.
    Six rows per analysis: security, performance, reliability,
    maintainability, test_coverage, documentation.
    """
    __tablename__ = "dimension_scores"

    id = Column(Integer, primary_key=True, autoincrement=True)
    score_id = Column(
        Integer,
        ForeignKey("production_scores.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    dimension = Column(String(32), nullable=False)
    raw_score = Column(Integer, nullable=False)
    adjusted_score = Column(Integer, nullable=False)
    label = Column(String(32), nullable=False)
    finding_count = Column(Integer, nullable=False, default=0)

    # Deductions stored as newline-separated strings for simple display
    deductions_text = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("score_id", "dimension", name="uq_dimension_scores_score_dimension"),
    )
