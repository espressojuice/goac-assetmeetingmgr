import datetime
import enum
import uuid
from typing import Optional, List

from sqlalchemy import String, Text, Date, DateTime, Enum, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class MeetingStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"
    CLOSED = "closed"


class Meeting(Base):
    __tablename__ = "meetings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id"), nullable=False)
    meeting_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    packet_generated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    packet_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    flagged_items_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    status: Mapped[MeetingStatus] = mapped_column(Enum(MeetingStatus), default=MeetingStatus.PENDING, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    closed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"), nullable=True)
    close_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    store: Mapped["Store"] = relationship(back_populates="meetings")
    closed_by: Mapped[Optional["User"]] = relationship(foreign_keys=[closed_by_id])
    new_vehicle_inventory: Mapped[List["NewVehicleInventory"]] = relationship(back_populates="meeting")
    used_vehicle_inventory: Mapped[List["UsedVehicleInventory"]] = relationship(back_populates="meeting")
    service_loaners: Mapped[List["ServiceLoaner"]] = relationship(back_populates="meeting")
    floorplan_reconciliations: Mapped[List["FloorplanReconciliation"]] = relationship(back_populates="meeting")
    parts_inventory: Mapped[List["PartsInventory"]] = relationship(back_populates="meeting")
    parts_analyses: Mapped[List["PartsAnalysis"]] = relationship(back_populates="meeting")
    receivables: Mapped[List["Receivable"]] = relationship(back_populates="meeting")
    fi_chargebacks: Mapped[List["FIChargeback"]] = relationship(back_populates="meeting")
    contracts_in_transit: Mapped[List["ContractInTransit"]] = relationship(back_populates="meeting")
    prepaids: Mapped[List["Prepaid"]] = relationship(back_populates="meeting")
    policy_adjustments: Mapped[List["PolicyAdjustment"]] = relationship(back_populates="meeting")
    open_repair_orders: Mapped[List["OpenRepairOrder"]] = relationship(back_populates="meeting")
    warranty_claims: Mapped[List["WarrantyClaim"]] = relationship(back_populates="meeting")
    missing_titles: Mapped[List["MissingTitle"]] = relationship(back_populates="meeting")
    slow_to_accounting: Mapped[List["SlowToAccounting"]] = relationship(back_populates="meeting")
    flags: Mapped[List["Flag"]] = relationship(back_populates="meeting")

    __table_args__ = (
        Index("ix_meetings_store_id", "store_id"),
    )
