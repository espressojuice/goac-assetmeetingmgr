import datetime
import enum
import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import String, Integer, Text, DateTime, Numeric, Enum, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PartsCategory(str, enum.Enum):
    PARTS_242 = "parts_242"
    TIRES_243 = "tires_243"
    GAS_OIL_GREASE_244 = "gas_oil_grease_244"


class PartsInventory(Base):
    __tablename__ = "parts_inventory"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("meetings.id"), nullable=False)
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id"), nullable=False)
    category: Mapped[PartsCategory] = mapped_column(Enum(PartsCategory), nullable=False)
    gl_account: Mapped[str] = mapped_column(String(20), nullable=False)
    total_value: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    meeting: Mapped["Meeting"] = relationship(back_populates="parts_inventory")
    store: Mapped["Store"] = relationship()

    __table_args__ = (
        Index("ix_parts_inventory_meeting_id", "meeting_id"),
        Index("ix_parts_inventory_store_id", "store_id"),
    )


class PartsAnalysis(Base):
    __tablename__ = "parts_analysis"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("meetings.id"), nullable=False)
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id"), nullable=False)
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)
    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_of_sales: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    average_investment: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    true_turnover: Mapped[Optional[Decimal]] = mapped_column(Numeric(4, 2), nullable=True)
    months_no_sale: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    obsolete_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    stock_order_performance: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    outstanding_orders_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    processed_orders_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    receipts_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    meeting: Mapped["Meeting"] = relationship(back_populates="parts_analyses")
    store: Mapped["Store"] = relationship()

    __table_args__ = (
        Index("ix_parts_analysis_meeting_id", "meeting_id"),
        Index("ix_parts_analysis_store_id", "store_id"),
    )
