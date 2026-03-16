"""
alembic/versions/xxxx_add_reviews_table.py

Alembic migration to add the reviews table.
Run: alembic revision --autogenerate -m "add reviews table"
Or paste this manually.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade() -> None:
    op.create_table(
        "reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("jobs.id"), nullable=False, index=True),
        sa.Column("repo_url", sa.String(2048), nullable=False, index=True),
        sa.Column("commit", sa.String(40), nullable=True),
        sa.Column("branch", sa.String(255), server_default="main"),
        sa.Column("ruleset_version", sa.String(20), nullable=False),
        sa.Column("schema_version", sa.String(10), server_default="1.0"),
        sa.Column("depth_level", sa.String(50), nullable=True),
        sa.Column("confidence_label", sa.String(10), nullable=True),
        sa.Column("overall_score", sa.Integer, nullable=True),
        sa.Column("security_score", sa.Integer, nullable=True),
        sa.Column("testing_score", sa.Integer, nullable=True),
        sa.Column("maintainability_score", sa.Integer, nullable=True),
        sa.Column("reliability_score", sa.Integer, nullable=True),
        sa.Column("ops_score", sa.Integer, nullable=True),
        sa.Column("devex_score", sa.Integer, nullable=True),
        sa.Column("verdict_label", sa.String(50), nullable=True),
        sa.Column("trust_recommendation", sa.String(20), nullable=True),
        sa.Column("production_suitable", sa.Boolean, server_default="false"),
        sa.Column("anti_gaming_verdict", sa.String(30), nullable=True),
        sa.Column("scorecard_json", postgresql.JSONB, nullable=True),
        sa.Column("findings_json", postgresql.JSONB, nullable=True),
        sa.Column("coverage_json", postgresql.JSONB, nullable=True),
        sa.Column("depth_json", postgresql.JSONB, nullable=True),
        sa.Column("anti_gaming_json", postgresql.JSONB, nullable=True),
        sa.Column("summary_json", postgresql.JSONB, nullable=True),
        sa.Column("meta_json", postgresql.JSONB, nullable=True),
        sa.Column("error_code", sa.String(50), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_reviews_repo_url", "reviews", ["repo_url"])
    op.create_index("ix_reviews_job_id", "reviews", ["job_id"])


def downgrade() -> None:
    op.drop_table("reviews")
