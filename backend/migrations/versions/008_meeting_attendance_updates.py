"""Update meeting_attendance: rename attended→checked_in, add checked_in_at/checked_in_by_id/updated_at, unique constraint.

Revision ID: h84i9k03g7j6
Revises: g73h8j92f6i5
Create Date: 2026-03-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'h84i9k03g7j6'
down_revision: Union[str, None] = 'g73h8j92f6i5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rename attended → checked_in
    op.alter_column('meeting_attendance', 'attended', new_column_name='checked_in')

    # Drop role_in_meeting column (no longer needed)
    op.drop_column('meeting_attendance', 'role_in_meeting')

    # Add new columns
    op.add_column('meeting_attendance', sa.Column('checked_in_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('meeting_attendance', sa.Column('checked_in_by_id', sa.Uuid(), nullable=True))
    op.add_column('meeting_attendance', sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True))

    # Add FK constraint for checked_in_by_id
    op.create_foreign_key(
        'fk_meeting_attendance_checked_in_by_id',
        'meeting_attendance', 'users',
        ['checked_in_by_id'], ['id'],
    )

    # Add unique constraint on (meeting_id, user_id)
    op.create_unique_constraint(
        'uq_meeting_attendance_meeting_user',
        'meeting_attendance',
        ['meeting_id', 'user_id'],
    )


def downgrade() -> None:
    op.drop_constraint('uq_meeting_attendance_meeting_user', 'meeting_attendance', type_='unique')
    op.drop_constraint('fk_meeting_attendance_checked_in_by_id', 'meeting_attendance', type_='foreignkey')
    op.drop_column('meeting_attendance', 'updated_at')
    op.drop_column('meeting_attendance', 'checked_in_by_id')
    op.drop_column('meeting_attendance', 'checked_in_at')
    op.add_column('meeting_attendance', sa.Column('role_in_meeting', sa.String(50), nullable=True))
    op.alter_column('meeting_attendance', 'checked_in', new_column_name='attended')
