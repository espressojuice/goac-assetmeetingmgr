"""Add user_stores association table for store-scoped access control.

Revision ID: c39d4f58b2e1
Revises: b28c3e47a1d0
Create Date: 2026-03-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c39d4f58b2e1'
down_revision: Union[str, None] = 'b28c3e47a1d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('user_stores',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('store_id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['store_id'], ['stores.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'store_id', name='uq_user_store'),
    )
    op.create_index('ix_user_stores_user_id', 'user_stores', ['user_id'])
    op.create_index('ix_user_stores_store_id', 'user_stores', ['store_id'])


def downgrade() -> None:
    op.drop_index('ix_user_stores_store_id', table_name='user_stores')
    op.drop_index('ix_user_stores_user_id', table_name='user_stores')
    op.drop_table('user_stores')
