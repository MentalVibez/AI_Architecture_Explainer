"""Add pr_number and pr_repo to review_jobs

Revision ID: 0016
Revises: 0015
Create Date: 2026-05-20
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: Union[str, Sequence[str], None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("review_jobs", sa.Column("pr_number", sa.Integer(), nullable=True))
    op.add_column("review_jobs", sa.Column("pr_repo", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("review_jobs", "pr_repo")
    op.drop_column("review_jobs", "pr_number")
