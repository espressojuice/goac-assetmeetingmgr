"""Notification API routes — in-app notification center."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, and_, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models.user import User
from app.models.accountability import Notification

router = APIRouter()


@router.get("/notifications")
async def get_my_notifications(
    unread_only: bool = False,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current user's notifications, newest first."""
    query = select(Notification).where(Notification.user_id == current_user.id)

    if unread_only:
        query = query.where(Notification.is_read == False)  # noqa: E712

    query = query.order_by(Notification.created_at.desc()).limit(limit)
    result = await db.execute(query)
    notifications = list(result.scalars().all())

    return [
        {
            "id": str(n.id),
            "type": n.notification_type.value,
            "title": n.title,
            "message": n.message,
            "reference_id": str(n.reference_id) if n.reference_id else None,
            "is_read": n.is_read,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        for n in notifications
    ]


@router.patch("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark a notification as read."""
    try:
        notif_uuid = uuid.UUID(notification_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid notification ID")

    result = await db.execute(
        select(Notification).where(
            and_(
                Notification.id == notif_uuid,
                Notification.user_id == current_user.id,
            )
        )
    )
    notification = result.scalar_one_or_none()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    notification.is_read = True
    await db.commit()

    return {"id": str(notification.id), "is_read": True}


@router.post("/notifications/read-all")
async def mark_all_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark all notifications as read."""
    await db.execute(
        update(Notification)
        .where(
            and_(
                Notification.user_id == current_user.id,
                Notification.is_read == False,  # noqa: E712
            )
        )
        .values(is_read=True)
    )
    await db.commit()
    return {"status": "ok"}


@router.get("/notifications/unread-count")
async def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get count of unread notifications. Used for badge in navbar."""
    result = await db.execute(
        select(func.count(Notification.id)).where(
            and_(
                Notification.user_id == current_user.id,
                Notification.is_read == False,  # noqa: E712
            )
        )
    )
    count = result.scalar() or 0
    return {"unread_count": count}
