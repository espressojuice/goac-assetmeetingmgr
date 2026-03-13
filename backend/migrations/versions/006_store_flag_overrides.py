"""Add store_flag_overrides table for per-store flagging thresholds.

Revision ID: f62g7i81e5h4
Revises: e51f6h70d4g3
Create Date: 2026-03-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f62g7i81e5h4'
down_revision: Union[str, None] = 'e51f6h70d4g3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'store_flag_overrides',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('store_id', sa.Uuid(), sa.ForeignKey('stores.id'), nullable=False),
        sa.Column('rule_name', sa.String(100), nullable=False),
        sa.Column('yellow_threshold', sa.Numeric(), nullable=True),
        sa.Column('red_threshold', sa.Numeric(), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('store_id', 'rule_name', name='uq_store_rule'),
    )
    op.create_index('ix_store_flag_overrides_store_id', 'store_flag_overrides', ['store_id'])


def downgrade() -> None:
    op.drop_index('ix_store_flag_overrides_store_id')
    op.drop_table('store_flag_overrides')
