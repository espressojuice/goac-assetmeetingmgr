import datetime
import enum
import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import String, Integer, Boolean, Text, DateTime, Numeric, Enum, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class NewVehicleInventory(Base):
    __tablename__ = "new_vehicle_inventory"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("meetings.id"), nullable=False)
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id"), nullable=False)
    stock_number: Mapped[str] = mapped_column(String(50), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    make: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    vin: Mapped[Optional[str]] = mapped_column(String(17), nullable=True)
    days_in_stock: Mapped[int] = mapped_column(Integer, nullable=False)
    floorplan_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    book_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    schedule_237_balance: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    meeting: Mapped["Meeting"] = relationship(back_populates="new_vehicle_inventory")
    store: Mapped["Store"] = relationship()

    __table_args__ = (
        Index("ix_new_vehicle_inventory_meeting_id", "meeting_id"),
        Index("ix_new_vehicle_inventory_store_id", "store_id"),
    )


class UsedVehicleInventory(Base):
    __tablename__ = "used_vehicle_inventory"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("meetings.id"), nullable=False)
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id"), nullable=False)
    stock_number: Mapped[str] = mapped_column(String(50), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    make: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    vin: Mapped[Optional[str]] = mapped_column(String(17), nullable=True)
    days_in_stock: Mapped[int] = mapped_column(Integer, nullable=False)
    book_value: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    market_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    floorplan_balance: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    acquisition_source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    meeting: Mapped["Meeting"] = relationship(back_populates="used_vehicle_inventory")
    store: Mapped["Store"] = relationship()

    __table_args__ = (
        Index("ix_used_vehicle_inventory_meeting_id", "meeting_id"),
        Index("ix_used_vehicle_inventory_store_id", "store_id"),
    )


class ServiceLoaner(Base):
    __tablename__ = "service_loaners"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("meetings.id"), nullable=False)
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id"), nullable=False)
    stock_number: Mapped[str] = mapped_column(String(50), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    make: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    vin: Mapped[Optional[str]] = mapped_column(String(17), nullable=True)
    days_in_service: Mapped[int] = mapped_column(Integer, nullable=False)
    book_value: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    current_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    negative_equity: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    meeting: Mapped["Meeting"] = relationship(back_populates="service_loaners")
    store: Mapped["Store"] = relationship()

    __table_args__ = (
        Index("ix_service_loaners_meeting_id", "meeting_id"),
        Index("ix_service_loaners_store_id", "store_id"),
    )


class ReconciliationType(str, enum.Enum):
    NEW_237 = "new_237"
    USED_240 = "used_240"


class FloorplanReconciliation(Base):
    __tablename__ = "floorplan_reconciliations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("meetings.id"), nullable=False)
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id"), nullable=False)
    reconciliation_type: Mapped[ReconciliationType] = mapped_column(Enum(ReconciliationType), nullable=False)
    book_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    floorplan_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    variance: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    unit_count_book: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    unit_count_floorplan: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    unit_count_variance: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    meeting: Mapped["Meeting"] = relationship(back_populates="floorplan_reconciliations")
    store: Mapped["Store"] = relationship()

    __table_args__ = (
        Index("ix_floorplan_reconciliations_meeting_id", "meeting_id"),
        Index("ix_floorplan_reconciliations_store_id", "store_id"),
    )
