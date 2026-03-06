"""widen numeric columns to prevent overflow

Revision ID: 004
Revises: 003
Create Date: 2026-03-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # obv_slope_10d: NUMERIC(8,4) -> NUMERIC(20,4) — OBV slopes can be millions
    op.alter_column(
        "technical_snapshots",
        "obv_slope_10d",
        type_=sa.Numeric(20, 4),
        existing_type=sa.Numeric(8, 4),
    )
    # ad_line: NUMERIC(16,4) -> NUMERIC(20,4) — accumulation/distribution can be billions
    op.alter_column(
        "technical_snapshots",
        "ad_line",
        type_=sa.Numeric(20, 4),
        existing_type=sa.Numeric(16, 4),
    )
    # cci_20: NUMERIC(8,4) -> NUMERIC(12,4) — CCI can exceed 1000
    op.alter_column(
        "technical_snapshots",
        "cci_20",
        type_=sa.Numeric(12, 4),
        existing_type=sa.Numeric(8, 4),
    )


def downgrade() -> None:
    op.alter_column(
        "technical_snapshots",
        "obv_slope_10d",
        type_=sa.Numeric(8, 4),
        existing_type=sa.Numeric(20, 4),
    )
    op.alter_column(
        "technical_snapshots",
        "ad_line",
        type_=sa.Numeric(16, 4),
        existing_type=sa.Numeric(20, 4),
    )
    op.alter_column(
        "technical_snapshots",
        "cci_20",
        type_=sa.Numeric(12, 4),
        existing_type=sa.Numeric(8, 4),
    )
