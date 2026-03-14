"""Corporate dashboard endpoint — aggregated multi-store overview."""

from __future__ import annotations

import datetime
import uuid as uuid_mod
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, func, case, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user, get_user_store_ids, require_corporate, require_corporate_or_gm
from app.database import get_db
from app.models.store import Store
from app.models.meeting import Meeting, MeetingStatus
from app.models.flag import Flag, FlagSeverity, FlagStatus
from app.models.user import User, UserRole
from app.api.schemas import (
    ManagerMetricsResponse, StoreComparisonResponse, PriorityItemResponse,
    MeetingTrendResponse, PromiseSummaryResponse, PromiseOffenderResponse,
)
from app.services import metrics_service

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
    top_priority_count: int = 0
    worst_resolution_rate: Optional[float] = None


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

    # Enhanced metrics: top priority count and worst resolution rate
    top_priority_count = 0
    worst_resolution_rate = None
    try:
        priority_items = await metrics_service.get_top_priority_items(db)
        top_priority_count = sum(1 for item in priority_items if item["priority_score"] >= 10)

        manager_metrics = await metrics_service.get_manager_resolution_rates(db)
        if manager_metrics:
            worst_resolution_rate = manager_metrics[0]["resolution_rate"]  # already sorted asc
    except Exception:
        pass  # Don't break the dashboard if metrics fail

    return DashboardResponse(
        stores=store_items,
        totals=DashboardTotals(
            total_stores=len(stores),
            total_open_flags=total_open,
            total_overdue=total_overdue,
            avg_response_rate=avg_rate,
            meetings_this_week=0,
            top_priority_count=top_priority_count,
            worst_resolution_rate=worst_resolution_rate,
        ),
    )


# ── New dashboard metrics endpoints ──────────────────────────────────


@router.get("/dashboard/manager-metrics", response_model=list[ManagerMetricsResponse])
async def get_manager_metrics(
    store_id: Optional[str] = Query(None),
    date_from: Optional[datetime.date] = Query(None),
    date_to: Optional[datetime.date] = Query(None),
    current_user: User = Depends(require_corporate),
    db: AsyncSession = Depends(get_db),
) -> list[ManagerMetricsResponse]:
    """Per-manager resolution rates — corporate only."""
    sid = uuid_mod.UUID(store_id) if store_id else None
    results = await metrics_service.get_manager_resolution_rates(
        db, store_id=sid, date_from=date_from, date_to=date_to,
    )
    return [ManagerMetricsResponse(**r) for r in results]


@router.get("/dashboard/store-comparison", response_model=list[StoreComparisonResponse])
async def get_store_comparison(
    date_from: Optional[datetime.date] = Query(None),
    date_to: Optional[datetime.date] = Query(None),
    current_user: User = Depends(require_corporate),
    db: AsyncSession = Depends(get_db),
) -> list[StoreComparisonResponse]:
    """Side-by-side store metrics — corporate only."""
    results = await metrics_service.get_store_comparison(
        db, date_from=date_from, date_to=date_to,
    )
    return [StoreComparisonResponse(**r) for r in results]


@router.get("/dashboard/top-priorities", response_model=list[PriorityItemResponse])
async def get_top_priorities(
    store_id: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=100),
    current_user: User = Depends(require_corporate_or_gm),
    db: AsyncSession = Depends(get_db),
) -> list[PriorityItemResponse]:
    """Joel's top N list of items requiring immediate attention.

    Corporate sees all stores; GMs see only their stores.
    """
    sid = uuid_mod.UUID(store_id) if store_id else None

    # GMs can only see their own stores
    gm_store_ids = None
    if current_user.role == UserRole.GM:
        gm_store_ids = await get_user_store_ids(current_user, db)
        if not gm_store_ids:
            return []

    results = await metrics_service.get_top_priority_items(
        db, store_id=sid, store_ids=gm_store_ids, limit=limit,
    )
    return [PriorityItemResponse(**r) for r in results]


@router.get("/dashboard/resolution-trends", response_model=list[MeetingTrendResponse])
async def get_resolution_trends(
    store_id: Optional[str] = Query(None),
    last_n_meetings: int = Query(6, ge=1, le=50),
    current_user: User = Depends(require_corporate_or_gm),
    db: AsyncSession = Depends(get_db),
) -> list[MeetingTrendResponse]:
    """Resolution trend data for charts — corporate sees all, GM is store-scoped."""
    sid = uuid_mod.UUID(store_id) if store_id else None

    # GMs can only see their own stores
    if current_user.role == UserRole.GM:
        gm_store_ids = await get_user_store_ids(current_user, db)
        if not gm_store_ids:
            return []
        # If no store_id specified, use first GM store; if specified, verify access
        if sid and sid not in gm_store_ids:
            return []
        if not sid and len(gm_store_ids) == 1:
            sid = gm_store_ids[0]

    results = await metrics_service.get_resolution_trends(
        db, store_id=sid, last_n_meetings=last_n_meetings,
    )
    return [MeetingTrendResponse(**r) for r in results]


@router.get("/dashboard/promise-tracking", response_model=PromiseSummaryResponse)
async def get_promise_tracking(
    store_id: Optional[str] = Query(None),
    current_user: User = Depends(require_corporate),
    db: AsyncSession = Depends(get_db),
) -> PromiseSummaryResponse:
    """Promise date tracking summary — corporate only."""
    sid = uuid_mod.UUID(store_id) if store_id else None
    result = await metrics_service.get_promise_tracking_summary(db, store_id=sid)
    return PromiseSummaryResponse(
        total_promises=result["total_promises"],
        promises_kept=result["promises_kept"],
        promises_broken=result["promises_broken"],
        promises_pending=result["promises_pending"],
        avg_days_late=result["avg_days_late"],
        worst_offenders=[PromiseOffenderResponse(**o) for o in result["worst_offenders"]],
    )
