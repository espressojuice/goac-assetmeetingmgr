import datetime
from sqlalchemy import Integer, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Financial(Base):
    __tablename__ = "financials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Fields to add (receivables, F&I, contracts in transit, wholesale):
    # store_id (FK -> stores)
    # meeting_id (FK -> meetings)
    # report_type (enum: receivables, fni_reserve, contracts_in_transit, wholesale_deals)
    # account_number (str)
    # customer_name (str)
    # amount (decimal)
    # aging_bucket (str) - current, 30, 60, 90, 120+
    # deal_number (str)
    # lender (str)
    # funded (bool)
    # days_outstanding (int)
    # notes (text)
