import datetime
import enum
import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import String, Integer, Text, Date, DateTime, Numeric, Enum, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ReceivableType(str, enum.Enum):
    PARTS_SERVICE_200 = "parts_service_200"
    WHOLESALE_220 = "wholesale_220"
    FACTORY_2612 = "factory_2612"


class Receivable(Base):
    __tablename__ = "receivables"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("meetings.id"), nullable=False)
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id"), nullable=False)
    receivable_type: Mapped[ReceivableType] = mapped_column(Enum(ReceivableType), nullable=False)
    schedule_number: Mapped[str] = mapped_column(String(20), nullable=False)
    current_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    over_30: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    over_60: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    over_90: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    total_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    meeting: Mapped["Meeting"] = relationship(back_populates="receivables")
    store: Mapped["Store"] = relationship()

    __table_args__ = (
        Index("ix_receivables_meeting_id", "meeting_id"),
        Index("ix_receivables_store_id", "store_id"),
    )


class FIChargeback(Base):
    __tablename__ = "fi_chargebacks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("meetings.id"), nullable=False)
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id"), nullable=False)
    account_number: Mapped[str] = mapped_column(String(20), nullable=False)
    account_description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    current_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    over_90_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    meeting: Mapped["Meeting"] = relationship(back_populates="fi_chargebacks")
    store: Mapped["Store"] = relationship()

    __table_args__ = (
        Index("ix_fi_chargebacks_meeting_id", "meeting_id"),
        Index("ix_fi_chargebacks_store_id", "store_id"),
    )


class ContractInTransit(Base):
    __tablename__ = "contracts_in_transit"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("meetings.id"), nullable=False)
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id"), nullable=False)
    deal_number: Mapped[str] = mapped_column(String(50), nullable=False)
    customer_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    sale_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    days_in_transit: Mapped[int] = mapped_column(Integer, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    lender: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    meeting: Mapped["Meeting"] = relationship(back_populates="contracts_in_transit")
    store: Mapped["Store"] = relationship()

    __table_args__ = (
        Index("ix_contracts_in_transit_meeting_id", "meeting_id"),
        Index("ix_contracts_in_transit_store_id", "store_id"),
    )


class Prepaid(Base):
    __tablename__ = "prepaids"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("meetings.id"), nullable=False)
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id"), nullable=False)
    gl_account: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    meeting: Mapped["Meeting"] = relationship(back_populates="prepaids")
    store: Mapped["Store"] = relationship()

    __table_args__ = (
        Index("ix_prepaids_meeting_id", "meeting_id"),
        Index("ix_prepaids_store_id", "store_id"),
    )


class PolicyAdjustment(Base):
    __tablename__ = "policy_adjustments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("meetings.id"), nullable=False)
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id"), nullable=False)
    gl_account: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    adjustment_date: Mapped[Optional[datetime.date]] = mapped_column(Date, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    meeting: Mapped["Meeting"] = relationship(back_populates="policy_adjustments")
    store: Mapped["Store"] = relationship()

    __table_args__ = (
        Index("ix_policy_adjustments_meeting_id", "meeting_id"),
        Index("ix_policy_adjustments_store_id", "store_id"),
    )
