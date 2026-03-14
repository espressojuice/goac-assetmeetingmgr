"""Add meeting close fields: CLOSED status, closed_at, closed_by_id, close_notes.

Revision ID: i95j0l14h8k7
Revises: h84i9k03g7j6
Create Date: 2026-03-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'i95j0l14h8k7'
down_revision: Union[str, None] = 'h84i9k03g7j6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new enum value to meetingstatus type.
    # ALTER TYPE ... ADD VALUE cannot run inside a transaction in PostgreSQL.
    # In SQLite (tests), this is a no-op since enums are just strings.
    op.execute("ALTER TYPE meetingstatus ADD VALUE IF NOT EXISTS 'closed'")

    # Add close-related columns to meetings table
    op.add_column('meetings', sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('meetings', sa.Column('closed_by_id', sa.Uuid(), nullable=True))
    op.add_column('meetings', sa.Column('close_notes', sa.Text(), nullable=True))

    # Add FK constraint for closed_by_id
    op.create_foreign_key(
        'fk_meetings_closed_by_id',
        'meetings', 'users',
        ['closed_by_id'], ['id'],
    )


def downgrade() -> None:
    op.drop_constraint('fk_meetings_closed_by_id', 'meetings', type_='foreignkey')
    op.drop_column('meetings', 'close_notes')
    op.drop_column('meetings', 'closed_by_id')
    op.drop_column('meetings', 'closed_at')
    # Note: PostgreSQL does not support removing enum values
