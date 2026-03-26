"""add review tables

Revision ID: 0002
Revises: 046b2f30983d
Create Date: 2026-03-15
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# JSONB on Postgres, plain JSON on SQLite (dev)
_JSON = postgresql.JSONB().with_variant(sa.JSON(), "sqlite")

revision: str = "0002"
down_revision: str = "046b2f30983d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # review_jobs: job lifecycle tracking
    op.create_table(
        "review_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("status", sa.String(50), server_default="queued", nullable=False),
        sa.Column("repo_url", sa.String(2048), nullable=False),
        sa.Column("branch", sa.String(255), server_default="main"),
        sa.Column("error_code", sa.String(50), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime, nullable=True),
        sa.Column("completed_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_review_jobs_status", "review_jobs", ["status"])

    # reviews: result payload
    op.create_table(
        "reviews",
        # Identity
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("review_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Repo
        sa.Column("repo_url", sa.String(2048), nullable=False),
        sa.Column("commit", sa.String(40), nullable=True),
        sa.Column("branch", sa.String(255), server_default="main"),
        # Engine metadata
        sa.Column("ruleset_version", sa.String(20), nullable=True),
        sa.Column("schema_version", sa.String(10), server_default="1.0"),
        sa.Column("depth_level", sa.String(50), nullable=True),
        sa.Column("confidence_label", sa.String(10), nullable=True),
        # Score scalars
        sa.Column("overall_score", sa.Integer, nullable=True),
        sa.Column("security_score", sa.Integer, nullable=True),
        sa.Column("testing_score", sa.Integer, nullable=True),
        sa.Column("maintainability_score", sa.Integer, nullable=True),
        sa.Column("reliability_score", sa.Integer, nullable=True),
        sa.Column("operations_score", sa.Integer, nullable=True),
        sa.Column("developer_experience_score", sa.Integer, nullable=True),
        # Verdict scalars
        sa.Column("verdict_label", sa.String(50), nullable=True),
        sa.Column("trust_recommendation", sa.String(20), nullable=True),
        sa.Column("production_suitable", sa.Boolean, server_default="false"),
        sa.Column("anti_gaming_verdict", sa.String(30), nullable=True),
        # Full payloads
        sa.Column("scorecard_json", _JSON, nullable=True),
        sa.Column("findings_json", _JSON, nullable=True),
        sa.Column("coverage_json", _JSON, nullable=True),
        sa.Column("depth_json", _JSON, nullable=True),
        sa.Column("anti_gaming_json", _JSON, nullable=True),
        sa.Column("summary_json", _JSON, nullable=True),
        sa.Column("meta_json", _JSON, nullable=True),
        # Failure tracking
        sa.Column("error_code", sa.String(50), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        # Timestamps
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_reviews_job_id", "reviews", ["job_id"])
    op.create_index("ix_reviews_repo_url", "reviews", ["repo_url"])
    op.create_index("ix_reviews_created", "reviews", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_reviews_created", "reviews")
    op.drop_index("ix_reviews_repo_url", "reviews")
    op.drop_index("ix_reviews_job_id", "reviews")
    op.drop_table("reviews")
    op.drop_index("ix_review_jobs_status", "review_jobs")
    op.drop_table("review_jobs")
