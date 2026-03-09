import datetime
import enum
import uuid
from typing import Optional

from sqlalchemy import Integer, String, Text, DateTime, Enum, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class FlagCategory(str, enum.Enum):
    INVENTORY = "inventory"
    PARTS = "parts"
    FINANCIAL = "financial"
    OPERATIONS = "operations"


class FlagSeverity(str, enum.Enum):
    YELLOW = "yellow"
    RED = "red"


class FlagStatus(str, enum.Enum):
    OPEN = "open"
    RESPONDED = "responded"
    ESCALATED = "escalated"


class Flag(Base):
    __tablename__ = "flags"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("meetings.id"), nullable=False)
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id"), nullable=False)
    category: Mapped[FlagCategory] = mapped_column(Enum(FlagCategory), nullable=False)
    severity: Mapped[FlagSeverity] = mapped_column(Enum(FlagSeverity), nullable=False)
    field_name: Mapped[str] = mapped_column(String(255), nullable=False)
    field_value: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    threshold: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[FlagStatus] = mapped_column(Enum(FlagStatus), default=FlagStatus.OPEN, nullable=False)
    response_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    responded_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    responded_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    previous_flag_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("flags.id"), nullable=True)
    escalation_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    meeting: Mapped["Meeting"] = relationship(back_populates="flags")
    store: Mapped["Store"] = relationship()

    __table_args__ = (
        Index("ix_flags_meeting_id", "meeting_id"),
        Index("ix_flags_store_id", "store_id"),
    )
