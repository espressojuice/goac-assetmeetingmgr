import datetime
from sqlalchemy import Integer, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Operations(Base):
    __tablename__ = "operations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Fields to add (open ROs, warranty claims, missing titles, employee roster):
    # store_id (FK -> stores)
    # meeting_id (FK -> meetings)
    # report_type (enum: open_ro, warranty_claim, missing_title, employee_roster)
    # ro_number (str)
    # customer_name (str)
    # advisor (str)
    # days_open (int)
    # amount (decimal)
    # claim_number (str)
    # claim_status (str)
    # title_status (str)
    # employee_name (str)
    # department (str)
    # notes (text)
