import datetime
import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import String, Integer, Text, Date, DateTime, Numeric, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class OpenRepairOrder(Base):
    __tablename__ = "open_repair_orders"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("meetings.id"), nullable=False)
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id"), nullable=False)
    ro_number: Mapped[str] = mapped_column(String(50), nullable=False)
    open_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    days_open: Mapped[int] = mapped_column(Integer, nullable=False)
    customer_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    service_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    cp_invoice_date: Mapped[Optional[datetime.date]] = mapped_column(Date, nullable=True)
    amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    meeting: Mapped["Meeting"] = relationship(back_populates="open_repair_orders")
    store: Mapped["Store"] = relationship()

    __table_args__ = (
        Index("ix_open_repair_orders_meeting_id", "meeting_id"),
        Index("ix_open_repair_orders_store_id", "store_id"),
    )


class WarrantyClaim(Base):
    __tablename__ = "warranty_claims"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("meetings.id"), nullable=False)
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id"), nullable=False)
    claim_number: Mapped[str] = mapped_column(String(50), nullable=False)
    claim_date: Mapped[Optional[datetime.date]] = mapped_column(Date, nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    meeting: Mapped["Meeting"] = relationship(back_populates="warranty_claims")
    store: Mapped["Store"] = relationship()

    __table_args__ = (
        Index("ix_warranty_claims_meeting_id", "meeting_id"),
        Index("ix_warranty_claims_store_id", "store_id"),
    )


class MissingTitle(Base):
    __tablename__ = "missing_titles"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("meetings.id"), nullable=False)
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id"), nullable=False)
    stock_number: Mapped[str] = mapped_column(String(50), nullable=False)
    deal_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    customer_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    days_missing: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    meeting: Mapped["Meeting"] = relationship(back_populates="missing_titles")
    store: Mapped["Store"] = relationship()

    __table_args__ = (
        Index("ix_missing_titles_meeting_id", "meeting_id"),
        Index("ix_missing_titles_store_id", "store_id"),
    )


class SlowToAccounting(Base):
    __tablename__ = "slow_to_accounting"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("meetings.id"), nullable=False)
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id"), nullable=False)
    deal_number: Mapped[str] = mapped_column(String(50), nullable=False)
    sale_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    days_to_accounting: Mapped[int] = mapped_column(Integer, nullable=False)
    customer_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    salesperson: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    meeting: Mapped["Meeting"] = relationship(back_populates="slow_to_accounting")
    store: Mapped["Store"] = relationship()

    __table_args__ = (
        Index("ix_slow_to_accounting_meeting_id", "meeting_id"),
        Index("ix_slow_to_accounting_store_id", "store_id"),
    )
