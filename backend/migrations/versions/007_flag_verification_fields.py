"""Add flag verification fields and new FlagStatus enum values.

Revision ID: g73h8j92f6i5
Revises: f62g7i81e5h4
Create Date: 2026-03-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'g73h8j92f6i5'
down_revision: Union[str, None] = 'f62g7i81e5h4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new enum values to flagstatus type.
    # ALTER TYPE ... ADD VALUE cannot run inside a transaction in PostgreSQL.
    # In SQLite (tests), this is a no-op since enums are just strings.
    op.execute("ALTER TYPE flagstatus ADD VALUE IF NOT EXISTS 'verified'")
    op.execute("ALTER TYPE flagstatus ADD VALUE IF NOT EXISTS 'unresolved'")

    # Add verification columns to flags table
    op.add_column('flags', sa.Column('expected_resolution_date', sa.Date(), nullable=True))
    op.add_column('flags', sa.Column('verified_by_id', sa.Uuid(), nullable=True))
    op.add_column('flags', sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('flags', sa.Column('verification_notes', sa.Text(), nullable=True))

    # Add FK constraint for verified_by_id
    op.create_foreign_key(
        'fk_flags_verified_by_id',
        'flags', 'users',
        ['verified_by_id'], ['id'],
    )

    # Add expected_resolution_date to flag_assignments
    op.add_column('flag_assignments', sa.Column('expected_resolution_date', sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column('flag_assignments', 'expected_resolution_date')
    op.drop_constraint('fk_flags_verified_by_id', 'flags', type_='foreignkey')
    op.drop_column('flags', 'verification_notes')
    op.drop_column('flags', 'verified_at')
    op.drop_column('flags', 'verified_by_id')
    op.drop_column('flags', 'expected_resolution_date')
    # Note: PostgreSQL does not support removing enum values
