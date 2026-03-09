"""Phase 2: accountability models (users, assignments, responses, notifications, attendance)

Revision ID: b28c3e47a1d0
Revises: a19875f15fe2
Create Date: 2026-03-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b28c3e47a1d0'
down_revision: Union[str, None] = 'a19875f15fe2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Users
    op.create_table('users',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('google_id', sa.String(length=255), nullable=True),
        sa.Column('avatar_url', sa.String(length=500), nullable=True),
        sa.Column('role', sa.Enum('CORPORATE', 'GM', 'MANAGER', 'VIEWER', name='userrole'), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('google_id'),
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=False)

    # Flag Assignments
    op.create_table('flag_assignments',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('flag_id', sa.Uuid(), nullable=False),
        sa.Column('assigned_to_id', sa.Uuid(), nullable=False),
        sa.Column('assigned_by_id', sa.Uuid(), nullable=False),
        sa.Column('status', sa.Enum('PENDING', 'ACKNOWLEDGED', 'RESPONDED', 'OVERDUE', 'ESCALATED', name='assignmentstatus'), nullable=False),
        sa.Column('deadline', sa.Date(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['flag_id'], ['flags.id']),
        sa.ForeignKeyConstraint(['assigned_to_id'], ['users.id']),
        sa.ForeignKeyConstraint(['assigned_by_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_flag_assignments_flag_id', 'flag_assignments', ['flag_id'], unique=False)
    op.create_index('ix_flag_assignments_assigned_to_id', 'flag_assignments', ['assigned_to_id'], unique=False)

    # Flag Responses
    op.create_table('flag_responses',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('flag_id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('assignment_id', sa.Uuid(), nullable=True),
        sa.Column('response_text', sa.Text(), nullable=False),
        sa.Column('action_taken', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['flag_id'], ['flags.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['assignment_id'], ['flag_assignments.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_flag_responses_flag_id', 'flag_responses', ['flag_id'], unique=False)
    op.create_index('ix_flag_responses_user_id', 'flag_responses', ['user_id'], unique=False)

    # Notifications
    op.create_table('notifications',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('notification_type', sa.Enum('FLAG_ASSIGNED', 'DEADLINE_REMINDER', 'OVERDUE_NOTICE', 'ESCALATION', 'RESPONSE_RECEIVED', name='notificationtype'), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('reference_id', sa.Uuid(), nullable=True),
        sa.Column('is_read', sa.Boolean(), nullable=False),
        sa.Column('email_sent', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_notifications_user_id', 'notifications', ['user_id'], unique=False)

    # Meeting Attendance
    op.create_table('meeting_attendance',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('meeting_id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('role_in_meeting', sa.String(length=50), nullable=True),
        sa.Column('attended', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['meeting_id'], ['meetings.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_meeting_attendance_meeting_id', 'meeting_attendance', ['meeting_id'], unique=False)
    op.create_index('ix_meeting_attendance_user_id', 'meeting_attendance', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_meeting_attendance_user_id', table_name='meeting_attendance')
    op.drop_index('ix_meeting_attendance_meeting_id', table_name='meeting_attendance')
    op.drop_table('meeting_attendance')
    op.drop_index('ix_notifications_user_id', table_name='notifications')
    op.drop_table('notifications')
    op.drop_index('ix_flag_responses_user_id', table_name='flag_responses')
    op.drop_index('ix_flag_responses_flag_id', table_name='flag_responses')
    op.drop_table('flag_responses')
    op.drop_index('ix_flag_assignments_assigned_to_id', table_name='flag_assignments')
    op.drop_index('ix_flag_assignments_flag_id', table_name='flag_assignments')
    op.drop_table('flag_assignments')
    op.drop_index('ix_users_email', table_name='users')
    op.drop_table('users')
    # Drop enums
    op.execute("DROP TYPE IF EXISTS userrole")
    op.execute("DROP TYPE IF EXISTS assignmentstatus")
    op.execute("DROP TYPE IF EXISTS notificationtype")
