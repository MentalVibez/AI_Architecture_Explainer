"""add_intelligence_tables

Revision ID: 0011
Revises: 0002
Create Date: 2026-03-25

Adds five tables for the deep intelligence engine:
  - file_intelligence   (per-file metrics, role, signals)
  - dependency_edges    (import graph edges)
  - code_findings       (evidence-backed issues)
  - production_scores   (composite scorecard, one per result)
  - dimension_scores    (per-dimension breakdown, one per dimension per score)

All tables use result_id as an integer FK to analysis_results.id.
No existing tables are modified.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: Union[str, Sequence[str], None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "file_intelligence",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("result_id", sa.Integer(), nullable=False),
        sa.Column("path", sa.String(length=1024), nullable=False),
        sa.Column("language", sa.String(length=32), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("is_entrypoint", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_test", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_on_critical_path", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("loc", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("complexity_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("function_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("caller_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("has_type_annotations", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("has_error_handling", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("was_truncated", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("sensitive_operations", sa.Text(), nullable=True),
        sa.Column("framework_signals", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("result_id", "path", name="uq_file_intelligence_result_path"),
    )

    op.create_table(
        "dependency_edges",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("result_id", sa.Integer(), nullable=False),
        sa.Column("source_path", sa.String(length=1024), nullable=False),
        sa.Column("target_path", sa.String(length=1024), nullable=True),
        sa.Column("raw_import", sa.String(length=512), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.String(length=16), nullable=False),
        sa.Column("unresolved_reason", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "result_id", "source_path", "raw_import",
            name="uq_dependency_edge_result_source_import",
        ),
    )

    op.create_table(
        "code_findings",
        sa.Column("id", sa.String(length=8), nullable=False),
        sa.Column("result_id", sa.Integer(), nullable=False),
        sa.Column("file_path", sa.String(length=1024), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("source", sa.String(length=24), nullable=False),
        sa.Column("line_start", sa.Integer(), nullable=False),
        sa.Column("line_end", sa.Integer(), nullable=False),
        sa.Column("evidence_snippet", sa.String(length=500), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("remediation", sa.Text(), nullable=True),
        sa.Column("score_impact", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_code_findings_result_id", "code_findings", ["result_id"])
    op.create_index("ix_code_findings_severity", "code_findings", ["severity"])

    op.create_table(
        "production_scores",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("result_id", sa.Integer(), nullable=False),
        sa.Column("composite_score", sa.Integer(), nullable=False),
        sa.Column("composite_label", sa.String(length=16), nullable=False),
        sa.Column("confidence_extraction", sa.Float(), nullable=False),
        sa.Column("confidence_graph", sa.Float(), nullable=False),
        sa.Column("confidence_finding", sa.Float(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("critical_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("high_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("medium_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("low_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_findings", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("graph_semantics_version", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("critical_path_algorithm", sa.String(length=32), nullable=False),
        sa.Column("graph_confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("confirmed_edge_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unresolved_edge_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("result_id", name="uq_production_scores_result_id"),
    )

    op.create_table(
        "dimension_scores",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("score_id", sa.Integer(), nullable=False),
        sa.Column("dimension", sa.String(length=32), nullable=False),
        sa.Column("raw_score", sa.Integer(), nullable=False),
        sa.Column("adjusted_score", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=16), nullable=False),
        sa.Column("finding_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("deductions_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("score_id", "dimension", name="uq_dimension_scores_score_dimension"),
        sa.ForeignKeyConstraint(
            ["score_id"], ["production_scores.id"], ondelete="CASCADE"
        ),
    )


def downgrade() -> None:
    op.drop_table("dimension_scores")
    op.drop_table("production_scores")
    op.drop_index("ix_code_findings_severity", table_name="code_findings")
    op.drop_index("ix_code_findings_result_id", table_name="code_findings")
    op.drop_table("code_findings")
    op.drop_table("dependency_edges")
    op.drop_table("file_intelligence")
