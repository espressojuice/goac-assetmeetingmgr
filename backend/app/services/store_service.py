"""Service layer for store detail and flag trend queries."""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select, func, case, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.store import Store
from app.models.meeting import Meeting, MeetingStatus
from app.models.flag import Flag, FlagCategory, FlagSeverity, FlagStatus
from app.models.user import User
from app.models.accountability import FlagAssignment


async def get_store_detail(store_id: uuid.UUID, db: AsyncSession) -> Optional[dict]:
    """Assemble rich store detail with stats, meetings, and users.

    Returns None if the store doesn't exist.
    """
    # Fetch store
    result = await db.execute(select(Store).where(Store.id == store_id))
    store = result.scalar_one_or_none()
    if not store:
        return None

    # Fetch completed meetings (most recent first)
    meetings_result = await db.execute(
        select(Meeting)
        .where(Meeting.store_id == store_id)
        .order_by(Meeting.meeting_date.desc())
        .limit(10)
    )
    meetings = list(meetings_result.scalars().all())
    meeting_ids = [m.id for m in meetings]

    # Flag stats across all meetings for this store (single query)
    all_flags_result = await db.execute(
        select(
            func.count(Flag.id).label("total"),
            func.count(case((Flag.severity == FlagSeverity.RED, 1))).label("red"),
            func.count(case((Flag.severity == FlagSeverity.YELLOW, 1))).label("yellow"),
            func.count(case((Flag.status == FlagStatus.OPEN, 1))).label("open"),
            func.count(case((Flag.status == FlagStatus.RESPONDED, 1))).label("responded"),
            func.count(case((Flag.status == FlagStatus.ESCALATED, 1))).label("escalated"),
        ).where(Flag.store_id == store_id)
    )
    all_stats = all_flags_result.one()

    total_flags = all_stats.total or 0
    open_flags = all_stats.open or 0
    responded_flags = all_stats.responded or 0
    response_rate = round((responded_flags / total_flags * 100), 1) if total_flags > 0 else 0.0

    # Most common flag category
    most_common_category = None
    if total_flags > 0:
        cat_result = await db.execute(
            select(Flag.category, func.count(Flag.id).label("cnt"))
            .where(Flag.store_id == store_id)
            .group_by(Flag.category)
            .order_by(func.count(Flag.id).desc())
            .limit(1)
        )
        cat_row = cat_result.first()
        if cat_row:
            most_common_category = cat_row.category.value if hasattr(cat_row.category, "value") else str(cat_row.category)

    total_meetings = len(meetings)
    avg_flags = round(total_flags / total_meetings, 1) if total_meetings > 0 else 0.0

    # Overdue = open flags (refined later with deadline tracking)
    overdue_flags = open_flags

    # Per-meeting flag stats (batch query to avoid N+1)
    meeting_flag_stats = {}
    if meeting_ids:
        per_meeting_result = await db.execute(
            select(
                Flag.meeting_id,
                func.count(Flag.id).label("total"),
                func.count(case((Flag.severity == FlagSeverity.RED, 1))).label("red"),
                func.count(case((Flag.severity == FlagSeverity.YELLOW, 1))).label("yellow"),
                func.count(case((Flag.status == FlagStatus.OPEN, 1))).label("open"),
                func.count(case((Flag.status == FlagStatus.RESPONDED, 1))).label("responded"),
            )
            .where(Flag.meeting_id.in_(meeting_ids))
            .group_by(Flag.meeting_id)
        )
        for row in per_meeting_result.all():
            m_total = row.total or 0
            m_responded = row.responded or 0
            meeting_flag_stats[row.meeting_id] = {
                "total": m_total,
                "red": row.red or 0,
                "yellow": row.yellow or 0,
                "open": row.open or 0,
                "responded": m_responded,
                "response_rate": round((m_responded / m_total * 100), 1) if m_total > 0 else 0.0,
            }

    # Build recent meetings list
    recent_meetings = []
    for m in meetings:
        flags = meeting_flag_stats.get(m.id, {"total": 0, "red": 0, "yellow": 0, "open": 0, "responded": 0, "response_rate": 0.0})
        recent_meetings.append({
            "id": str(m.id),
            "meeting_date": str(m.meeting_date),
            "status": m.status.value,
            "packet_generated_at": m.packet_generated_at.isoformat() if m.packet_generated_at else None,
            "flags": flags,
            "response_rate": flags["response_rate"],
            "packet_url": m.packet_url,
            "flagged_items_url": m.flagged_items_url,
        })

    # Users with assignments to this store's flags
    user_ids_result = await db.execute(
        select(FlagAssignment.assigned_to_id)
        .join(Flag, FlagAssignment.flag_id == Flag.id)
        .where(Flag.store_id == store_id)
        .distinct()
    )
    user_ids = [row[0] for row in user_ids_result.all()]

    users = []
    if user_ids:
        users_result = await db.execute(
            select(User).where(User.id.in_(user_ids))
        )
        for u in users_result.scalars().all():
            users.append({
                "id": str(u.id),
                "name": u.name,
                "email": u.email,
                "role_at_store": u.role.value.replace("_", " ").title(),
            })

    return {
        "store": {
            "id": str(store.id),
            "name": store.name,
            "code": store.code,
            "brand": store.brand,
            "city": store.city,
            "state": store.state,
            "timezone": store.timezone,
            "gm_name": store.gm_name,
            "gm_email": store.gm_email,
            "meeting_cadence": store.meeting_cadence,
            "is_active": store.is_active,
        },
        "stats": {
            "total_meetings": total_meetings,
            "total_flags_all_time": total_flags,
            "current_open_flags": open_flags,
            "current_overdue_flags": overdue_flags,
            "response_rate": response_rate,
            "avg_flags_per_meeting": avg_flags,
            "most_common_flag_category": most_common_category,
            "recurring_issues_count": 0,
        },
        "recent_meetings": recent_meetings,
        "users": users,
    }


async def get_flag_trends(store_id: uuid.UUID, db: AsyncSession, limit: int = 6) -> Optional[dict]:
    """Return flag data over the last N meetings for trend charts.

    Returns None if the store doesn't exist.
    """
    # Verify store exists
    result = await db.execute(select(Store.id).where(Store.id == store_id))
    if not result.scalar_one_or_none():
        return None

    # Get last N completed meetings
    meetings_result = await db.execute(
        select(Meeting)
        .where(
            and_(
                Meeting.store_id == store_id,
                Meeting.status == MeetingStatus.COMPLETED,
            )
        )
        .order_by(Meeting.meeting_date.desc())
        .limit(limit)
    )
    meetings = list(meetings_result.scalars().all())
    meeting_ids = [m.id for m in meetings]

    if not meeting_ids:
        return {"meetings": []}

    # Batch flag stats per meeting
    per_meeting_result = await db.execute(
        select(
            Flag.meeting_id,
            func.count(case((Flag.severity == FlagSeverity.RED, 1))).label("red"),
            func.count(case((Flag.severity == FlagSeverity.YELLOW, 1))).label("yellow"),
            func.count(case((Flag.status == FlagStatus.RESPONDED, 1))).label("responded"),
            func.count(Flag.id).label("total"),
        )
        .where(Flag.meeting_id.in_(meeting_ids))
        .group_by(Flag.meeting_id)
    )
    stats_by_meeting = {}
    for row in per_meeting_result.all():
        t = row.total or 0
        r = row.responded or 0
        stats_by_meeting[row.meeting_id] = {
            "red": row.red or 0,
            "yellow": row.yellow or 0,
            "responded": r,
            "response_rate": round((r / t * 100), 1) if t > 0 else 0.0,
        }

    # Build response ordered chronologically (oldest first for charts)
    trend_meetings = []
    for m in reversed(meetings):
        stats = stats_by_meeting.get(m.id, {"red": 0, "yellow": 0, "responded": 0, "response_rate": 0.0})
        trend_meetings.append({
            "date": str(m.meeting_date),
            "red": stats["red"],
            "yellow": stats["yellow"],
            "responded": stats["responded"],
            "response_rate": stats["response_rate"],
        })

    return {"meetings": trend_meetings}
