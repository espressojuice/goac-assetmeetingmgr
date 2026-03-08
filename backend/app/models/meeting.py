import datetime
from sqlalchemy import Integer, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Meeting(Base):
    __tablename__ = "meetings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Fields to add:
    # store_id (FK -> stores)
    # meeting_date (date)
    # packet_generated_at (datetime)
    # packet_path (str) - path to generated PDF packet
    # status (enum: scheduled, packet_ready, in_progress, completed)
    # attendees (JSON or relation)
    # notes (text)
