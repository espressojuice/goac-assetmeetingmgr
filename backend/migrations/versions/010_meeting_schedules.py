"""Create meeting_schedules table for cadence enforcement.

Revision ID: j06k1m25i9l8
Revises: i95j0l14h8k7
Create Date: 2026-03-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'j06k1m25i9l8'
down_revision: Union[str, None] = 'i95j0l14h8k7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create meetingcadence enum type (PostgreSQL only; SQLite ignores)
    meetingcadence = sa.Enum(
        'weekly', 'biweekly', 'first_and_third', 'second_and_fourth', 'custom',
        name='meetingcadence',
    )
    meetingcadence.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'meeting_schedules',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('store_id', sa.Uuid(), sa.ForeignKey('stores.id'), nullable=False, unique=True),
        sa.Column('cadence', meetingcadence, nullable=False, server_default='biweekly'),
        sa.Column('preferred_day_of_week', sa.Integer(), nullable=True),
        sa.Column('preferred_time', sa.Time(), nullable=True),
        sa.Column('minimum_per_month', sa.Integer(), nullable=False, server_default='2'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by_id', sa.Uuid(), sa.ForeignKey('users.id'), nullable=True),
    )

    op.create_index('ix_meeting_schedules_store_id', 'meeting_schedules', ['store_id'])


def downgrade() -> None:
    op.drop_index('ix_meeting_schedules_store_id')
    op.drop_table('meeting_schedules')
    # Drop enum type (PostgreSQL only)
    sa.Enum(name='meetingcadence').drop(op.get_bind(), checkfirst=True)
