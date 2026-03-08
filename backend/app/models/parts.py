import datetime
from sqlalchemy import Integer, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Parts(Base):
    __tablename__ = "parts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Fields to add (from GL 242-244, monthly parts analysis):
    # store_id (FK -> stores)
    # meeting_id (FK -> meetings)
    # report_type (enum: gl_242, gl_243, gl_244, monthly_analysis)
    # account_number (str)
    # account_name (str)
    # balance (decimal)
    # prior_month_balance (decimal)
    # variance (decimal)
    # category (str) - parts, accessories, etc.
    # obsolescence_amount (decimal)
    # special_order_aging (int) - days
