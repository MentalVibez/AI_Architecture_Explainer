"""Add cached_result_id to atlas_jobs and review_jobs

Revision ID: 0018
Revises: 0017
Create Date: 2026-05-20
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0018"
down_revision: Union[str, Sequence[str], None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("atlas_jobs", sa.Column("cached_result_id", sa.Integer(), nullable=True))
    op.add_column(
        "review_jobs",
        sa.Column(
            "cached_result_id",
            UUID(as_uuid=True).with_variant(sa.String(36), "sqlite"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("review_jobs", "cached_result_id")
    op.drop_column("atlas_jobs", "cached_result_id")
