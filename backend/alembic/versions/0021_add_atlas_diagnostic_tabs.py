"""Add Atlas diagnostic tab payloads

Revision ID: 0021
Revises: 0020
Create Date: 2026-05-26
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: str | Sequence[str] | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("atlas_results", sa.Column("setup_risk", sa.JSON(), nullable=True))
    op.add_column("atlas_results", sa.Column("debug_readiness", sa.JSON(), nullable=True))
    op.add_column("atlas_results", sa.Column("change_risk", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("atlas_results", "change_risk")
    op.drop_column("atlas_results", "debug_readiness")
    op.drop_column("atlas_results", "setup_risk")
