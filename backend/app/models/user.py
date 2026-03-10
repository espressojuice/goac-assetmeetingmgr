import datetime
import enum
import uuid
from typing import Optional, List

from sqlalchemy import String, Boolean, DateTime, Enum, ForeignKey, Index, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserRole(str, enum.Enum):
    CORPORATE = "corporate"
    GM = "gm"
    MANAGER = "manager"
    VIEWER = "viewer"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    google_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.VIEWER, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_login_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    flag_assignments: Mapped[List["FlagAssignment"]] = relationship(back_populates="assigned_to_user", foreign_keys="FlagAssignment.assigned_to_id")
    flag_responses: Mapped[List["FlagResponseRecord"]] = relationship(back_populates="user")
    notifications: Mapped[List["Notification"]] = relationship(back_populates="user")
    store_associations: Mapped[List["UserStore"]] = relationship(back_populates="user")

    __table_args__ = (
        Index("ix_users_email", "email"),
    )


class UserStore(Base):
    """Association table linking users to the stores they can access."""
    __tablename__ = "user_stores"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id"), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user: Mapped["User"] = relationship(back_populates="store_associations")
    store: Mapped["Store"] = relationship()

    __table_args__ = (
        UniqueConstraint("user_id", "store_id", name="uq_user_store"),
        Index("ix_user_stores_user_id", "user_id"),
        Index("ix_user_stores_store_id", "store_id"),
    )
