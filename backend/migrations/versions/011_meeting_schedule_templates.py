"""Add template fields to meeting_schedules and google_calendar_event_id to meetings.

Revision ID: k17l2n36j0m9
Revises: j06k1m25i9l8
Create Date: 2026-03-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'k17l2n36j0m9'
down_revision: Union[str, None] = 'j06k1m25i9l8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Template fields on meeting_schedules
    op.add_column('meeting_schedules', sa.Column('template_name', sa.String(100), nullable=True))
    op.add_column('meeting_schedules', sa.Column('default_attendee_ids', sa.JSON(), nullable=True))
    op.add_column('meeting_schedules', sa.Column('auto_create_meetings', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('meeting_schedules', sa.Column('reminder_days_before', sa.Integer(), nullable=False, server_default='2'))

    # Google Calendar event ID on meetings
    op.add_column('meetings', sa.Column('google_calendar_event_id', sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column('meetings', 'google_calendar_event_id')
    op.drop_column('meeting_schedules', 'reminder_days_before')
    op.drop_column('meeting_schedules', 'auto_create_meetings')
    op.drop_column('meeting_schedules', 'default_attendee_ids')
    op.drop_column('meeting_schedules', 'template_name')
