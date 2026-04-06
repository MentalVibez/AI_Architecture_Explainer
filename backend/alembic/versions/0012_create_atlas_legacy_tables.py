"""Create atlas_jobs and atlas_results (legacy analysis pipeline tables)

Revision ID: 0012
Revises: 0011
Create Date: 2026-04-06

These are the tables used by the original /api/analyze pipeline.
Renamed from analysis_jobs/analysis_results to avoid conflict with the
new public analysis schema which occupies those table names.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | Sequence[str] | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "atlas_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("repo_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["repo_id"], ["repos.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "atlas_results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("repo_snapshot_sha", sa.String(length=40), nullable=True),
        sa.Column("detected_stack", sa.JSON(), nullable=False),
        sa.Column("dependencies", sa.JSON(), nullable=False),
        sa.Column("entry_points", sa.JSON(), nullable=False),
        sa.Column("folder_map", sa.JSON(), nullable=False),
        sa.Column("diagram_mermaid", sa.Text(), nullable=True),
        sa.Column("developer_summary", sa.Text(), nullable=True),
        sa.Column("hiring_manager_summary", sa.Text(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("caveats", sa.JSON(), nullable=False),
        sa.Column("raw_evidence", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["atlas_jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id"),
    )


def downgrade() -> None:
    op.drop_table("atlas_results")
    op.drop_table("atlas_jobs")
