import datetime
from sqlalchemy import Integer, String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Store(Base):
    __tablename__ = "stores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Fields to add:
    # name (str) - dealership name, e.g. "Ashdown Classic Chevrolet"
    # code (str) - internal store code
    # brand (str) - OEM brand
    # address, city, state, zip
    # gm_name (str) - general manager
    # active (bool)
