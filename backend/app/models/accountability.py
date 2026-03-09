import datetime
import enum
import uuid
from typing import Optional

from sqlalchemy import String, Text, DateTime, Date, Enum, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AssignmentStatus(str, enum.Enum):
    PENDING = "pending"
    ACKNOWLEDGED = "acknowledged"
    RESPONDED = "responded"
    OVERDUE = "overdue"
    ESCALATED = "escalated"


class NotificationType(str, enum.Enum):
    FLAG_ASSIGNED = "flag_assigned"
    DEADLINE_REMINDER = "deadline_reminder"
    OVERDUE_NOTICE = "overdue_notice"
    ESCALATION = "escalation"
    RESPONSE_RECEIVED = "response_received"


class FlagAssignment(Base):
    __tablename__ = "flag_assignments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    flag_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("flags.id"), nullable=False)
    assigned_to_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    assigned_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[AssignmentStatus] = mapped_column(Enum(AssignmentStatus), default=AssignmentStatus.PENDING, nullable=False)
    deadline: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    flag: Mapped["Flag"] = relationship()
    assigned_to_user: Mapped["User"] = relationship(back_populates="flag_assignments", foreign_keys=[assigned_to_id])
    assigned_by_user: Mapped["User"] = relationship(foreign_keys=[assigned_by_id])

    __table_args__ = (
        Index("ix_flag_assignments_flag_id", "flag_id"),
        Index("ix_flag_assignments_assigned_to_id", "assigned_to_id"),
    )


class FlagResponseRecord(Base):
    """Tracks individual responses to flags (separate from the inline response on Flag model)."""
    __tablename__ = "flag_responses"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    flag_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("flags.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    assignment_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("flag_assignments.id"), nullable=True)
    response_text: Mapped[str] = mapped_column(Text, nullable=False)
    action_taken: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    flag: Mapped["Flag"] = relationship()
    user: Mapped["User"] = relationship(back_populates="flag_responses")
    assignment: Mapped[Optional["FlagAssignment"]] = relationship()

    __table_args__ = (
        Index("ix_flag_responses_flag_id", "flag_id"),
        Index("ix_flag_responses_user_id", "user_id"),
    )


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    notification_type: Mapped[NotificationType] = mapped_column(Enum(NotificationType), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    reference_id: Mapped[Optional[uuid.UUID]] = mapped_column(nullable=True)
    is_read: Mapped[bool] = mapped_column(default=False, nullable=False)
    email_sent: Mapped[bool] = mapped_column(default=False, nullable=False)

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user: Mapped["User"] = relationship(back_populates="notifications")

    __table_args__ = (
        Index("ix_notifications_user_id", "user_id"),
    )


class MeetingAttendance(Base):
    __tablename__ = "meeting_attendance"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("meetings.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    role_in_meeting: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    attended: Mapped[bool] = mapped_column(default=False, nullable=False)

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    meeting: Mapped["Meeting"] = relationship()
    user: Mapped["User"] = relationship()

    __table_args__ = (
        Index("ix_meeting_attendance_meeting_id", "meeting_id"),
        Index("ix_meeting_attendance_user_id", "user_id"),
    )
