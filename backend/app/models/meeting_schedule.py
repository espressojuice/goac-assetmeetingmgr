"""Meeting scheduling with cadence enforcement."""

from __future__ import annotations

import datetime
import enum
import uuid
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class MeetingCadence(str, enum.Enum):
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    FIRST_AND_THIRD = "first_and_third"
    SECOND_AND_FOURTH = "second_and_fourth"
    CUSTOM = "custom"


class MeetingSchedule(Base):
    __tablename__ = "meeting_schedules"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stores.id"), nullable=False, unique=True
    )
    cadence: Mapped[MeetingCadence] = mapped_column(
        Enum(MeetingCadence), default=MeetingCadence.BIWEEKLY, nullable=False
    )
    preferred_day_of_week: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )  # 0=Monday, 6=Sunday
    preferred_time: Mapped[Optional[datetime.time]] = mapped_column(
        Time, nullable=True
    )
    minimum_per_month: Mapped[int] = mapped_column(
        Integer, default=2, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Template fields
    template_name: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    default_attendee_ids: Mapped[Optional[list]] = mapped_column(
        JSON, nullable=True
    )  # list of user UUID strings
    auto_create_meetings: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default="false"
    )
    reminder_days_before: Mapped[int] = mapped_column(
        Integer, default=2, nullable=False, server_default="2"
    )

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )
    created_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )

    # Relationships
    store: Mapped["Store"] = relationship()
    created_by: Mapped[Optional["User"]] = relationship(foreign_keys=[created_by_id])

    __table_args__ = (
        Index("ix_meeting_schedules_store_id", "store_id"),
    )
