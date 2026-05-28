"""Add queue claim indexes

Revision ID: 0023_add_queue_claim_indexes
Revises: 0022_fix_composite_label_length
Create Date: 2026-05-28
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0023_add_queue_claim_indexes"
down_revision: str | Sequence[str] | None = "0022_fix_composite_label_length"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_atlas_jobs_status_created_at",
        "atlas_jobs",
        ["status", "created_at"],
    )
    op.create_index(
        "ix_review_jobs_status_created_at",
        "review_jobs",
        ["status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_review_jobs_status_created_at", table_name="review_jobs")
    op.drop_index("ix_atlas_jobs_status_created_at", table_name="atlas_jobs")
