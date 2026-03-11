"""Add reynolds_site_id column to stores table.

Revision ID: d40e5g69c3f2
Revises: c39d4f58b2e1
Create Date: 2026-03-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd40e5g69c3f2'
down_revision: Union[str, None] = 'c39d4f58b2e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('stores', sa.Column('reynolds_site_id', sa.String(20), nullable=True))
    op.create_index('ix_stores_reynolds_site_id', 'stores', ['reynolds_site_id'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_stores_reynolds_site_id', table_name='stores')
    op.drop_column('stores', 'reynolds_site_id')
