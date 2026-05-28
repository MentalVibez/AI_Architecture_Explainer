"""Fix composite_label column length in production_scores

VARCHAR(16) is too short for labels like 'Near Production Ready' (20 chars)
and 'Not Production Ready' (20 chars). Widen to VARCHAR(32).

Revision ID: 0022_fix_composite_label_length
Revises: 0021_add_atlas_diagnostic_tabs
Create Date: 2026-05-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0022_fix_composite_label_length"
down_revision: Union[str, Sequence[str], None] = "0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "production_scores",
        "composite_label",
        existing_type=sa.String(length=16),
        type_=sa.String(length=32),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "production_scores",
        "composite_label",
        existing_type=sa.String(length=32),
        type_=sa.String(length=16),
        existing_nullable=False,
    )
