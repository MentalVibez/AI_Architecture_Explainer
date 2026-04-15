"""add commit column to review_jobs

Revision ID: 0013
Revises: 0012
Create Date: 2026-04-14
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | Sequence[str] | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("review_jobs", sa.Column("commit", sa.String(length=40), nullable=True))


def downgrade() -> None:
    op.drop_column("review_jobs", "commit")
