"""Per-store flag rule threshold overrides."""

from __future__ import annotations

import datetime
import uuid
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class StoreFlagOverride(Base):
    """Per-store override for a flagging rule's thresholds."""

    __tablename__ = "store_flag_overrides"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stores.id"), nullable=False
    )
    rule_name: Mapped[str] = mapped_column(String(100), nullable=False)
    yellow_threshold: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)
    red_threshold: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    store: Mapped["Store"] = relationship()

    __table_args__ = (
        UniqueConstraint("store_id", "rule_name", name="uq_store_rule"),
        Index("ix_store_flag_overrides_store_id", "store_id"),
    )
