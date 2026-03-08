import datetime
import enum
from sqlalchemy import Integer, String, Text, DateTime, Enum, func
from sqlalchemy.orm import Mapped, mapped_column

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

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    store_id: Mapped[int] = mapped_column(Integer, nullable=False)
    meeting_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    category: Mapped[FlagCategory] = mapped_column(Enum(FlagCategory), nullable=False)
    severity: Mapped[FlagSeverity] = mapped_column(Enum(FlagSeverity), nullable=False)
    field_name: Mapped[str] = mapped_column(String(255), nullable=False)
    field_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    threshold: Mapped[str | None] = mapped_column(String(255), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[FlagStatus] = mapped_column(Enum(FlagStatus), default=FlagStatus.OPEN, nullable=False)
    response_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    responded_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    responded_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
