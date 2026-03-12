"""Add previous_flag_id and escalation_level columns to flags table.

Revision ID: e51f6h70d4g3
Revises: d40e5g69c3f2
Create Date: 2026-03-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e51f6h70d4g3'
down_revision: Union[str, None] = 'd40e5g69c3f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('flags', sa.Column('previous_flag_id', sa.Uuid(), sa.ForeignKey('flags.id'), nullable=True))
    op.add_column('flags', sa.Column('escalation_level', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    op.drop_column('flags', 'escalation_level')
    op.drop_column('flags', 'previous_flag_id')
