import datetime
from sqlalchemy import Integer, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Inventory(Base):
    __tablename__ = "inventory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Fields to add (from schedules 237, 240, 277):
    # store_id (FK -> stores)
    # meeting_id (FK -> meetings)
    # schedule_type (enum: 237_new, 237_used, 240_demos, 277_floorplan)
    # stock_number (str)
    # vin (str)
    # year, make, model, trim
    # days_in_stock (int)
    # cost (decimal)
    # floorplan_amount (decimal)
    # floorplan_interest (decimal)
    # status (str)
    # notes (text) - for handwritten annotations
