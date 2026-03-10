"""Corporate dashboard endpoint — aggregated multi-store overview."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, func, case, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user, get_user_store_ids
from app.database import get_db
from app.models.store import Store
from app.models.meeting import Meeting, MeetingStatus
from app.models.flag import Flag, FlagSeverity, FlagStatus
from app.models.user import User, UserRole

router = APIRouter()


class StoreDashboardItem(BaseModel):
    id: str
    name: str
    code: str
    last_meeting_date: Optional[str] = None
    next_meeting_date: Optional[str] = None
    flags: dict
    response_rate: float
    overdue_count: int
    recurring_issues: int


class DashboardTotals(BaseModel):
    total_stores: int
    total_open_flags: int
    total_overdue: int
    avg_response_rate: float
    meetings_this_week: int


class DashboardResponse(BaseModel):
    stores: list[StoreDashboardItem]
    totals: DashboardTotals


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DashboardResponse:
    """Return aggregated dashboard data for stores visible to the current user."""
    # Build store query scoped to user's access
    query = select(Store).where(Store.is_active == True).order_by(Store.name)

    if current_user.role != UserRole.CORPORATE:
        store_ids = await get_user_store_ids(current_user, db)
        if not store_ids:
            return DashboardResponse(
                stores=[],
                totals=DashboardTotals(
                    total_stores=0, total_open_flags=0, total_overdue=0,
                    avg_response_rate=0.0, meetings_this_week=0,
                ),
            )
        query = query.where(Store.id.in_(store_ids))

    result = await db.execute(query)
    stores = list(result.scalars().all())

    store_items = []
    total_open = 0
    total_overdue = 0
    response_rates = []

    for store in stores:
        # Get latest completed meeting for this store
        meeting_result = await db.execute(
            select(Meeting)
            .where(
                and_(
                    Meeting.store_id == store.id,
                    Meeting.status == MeetingStatus.COMPLETED,
                )
            )
            .order_by(Meeting.meeting_date.desc())
            .limit(1)
        )
        latest_meeting = meeting_result.scalar_one_or_none()

        # Get flag stats for this store (across all meetings)
        flag_result = await db.execute(
            select(
                func.count(Flag.id).label("total"),
                func.count(case((Flag.severity == FlagSeverity.RED, 1))).label("red"),
                func.count(case((Flag.severity == FlagSeverity.YELLOW, 1))).label("yellow"),
                func.count(case((Flag.status == FlagStatus.OPEN, 1))).label("open"),
                func.count(case((Flag.status == FlagStatus.RESPONDED, 1))).label("responded"),
            ).where(Flag.store_id == store.id)
        )
        stats = flag_result.one()

        flag_total = stats.total or 0
        flag_open = stats.open or 0
        flag_responded = stats.responded or 0
        flag_red = stats.red or 0
        flag_yellow = stats.yellow or 0

        rate = round((flag_responded / flag_total * 100), 1) if flag_total > 0 else 0.0
        response_rates.append(rate)
        total_open += flag_open
        # For now, overdue = open flags (we'll refine with deadline tracking later)
        total_overdue += flag_open

        store_items.append(StoreDashboardItem(
            id=str(store.id),
            name=store.name,
            code=store.code,
            last_meeting_date=str(latest_meeting.meeting_date) if latest_meeting else None,
            next_meeting_date=None,
            flags={
                "total": flag_total,
                "red": flag_red,
                "yellow": flag_yellow,
                "open": flag_open,
                "responded": flag_responded,
            },
            response_rate=rate,
            overdue_count=flag_open,
            recurring_issues=0,
        ))

    avg_rate = round(sum(response_rates) / len(response_rates), 1) if response_rates else 0.0

    return DashboardResponse(
        stores=store_items,
        totals=DashboardTotals(
            total_stores=len(stores),
            total_open_flags=total_open,
            total_overdue=total_overdue,
            avg_response_rate=avg_rate,
            meetings_this_week=0,
        ),
    )
