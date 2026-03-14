"""Meeting scheduling and cadence enforcement endpoints."""

from __future__ import annotations

import datetime
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    AutoCreateResponse,
    CadenceComplianceResponse,
    MeetingScheduleRequest,
    MeetingScheduleResponse,
    OverdueMeetingResponse,
)
from app.auth import get_current_user, require_corporate, require_corporate_or_gm
from app.database import get_db
from app.models.meeting_schedule import MeetingCadence
from app.models.store import Store
from app.models.user import User, UserRole
from app.services import scheduling_service

router = APIRouter()


def _validate_uuid(value: str, label: str = "ID") -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid {label} format")


async def _get_store_or_404(store_id: uuid.UUID, db: AsyncSession) -> Store:
    result = await db.execute(select(Store).where(Store.id == store_id))
    store = result.scalar_one_or_none()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    return store


async def _build_schedule_response(
    schedule, store_name: str, db: AsyncSession
) -> MeetingScheduleResponse:
    upcoming = scheduling_service.get_upcoming_meetings(
        schedule.cadence,
        schedule.preferred_day_of_week,
        months_ahead=1,
    )

    # Resolve attendee names from UUIDs
    attendee_names = []
    if schedule.default_attendee_ids:
        from app.models.user import User as UserModel
        for uid_str in schedule.default_attendee_ids:
            try:
                uid = uuid.UUID(uid_str) if isinstance(uid_str, str) else uid_str
                user_result = await db.execute(
                    select(UserModel.name).where(UserModel.id == uid)
                )
                name = user_result.scalar_one_or_none()
                if name:
                    attendee_names.append(name)
            except (ValueError, TypeError):
                continue

    return MeetingScheduleResponse(
        id=str(schedule.id),
        store_id=str(schedule.store_id),
        store_name=store_name,
        cadence=schedule.cadence.value,
        preferred_day_of_week=schedule.preferred_day_of_week,
        preferred_time=schedule.preferred_time.strftime("%H:%M") if schedule.preferred_time else None,
        minimum_per_month=schedule.minimum_per_month,
        is_active=schedule.is_active,
        notes=schedule.notes,
        upcoming_dates=upcoming,
        template_name=schedule.template_name,
        default_attendee_ids=schedule.default_attendee_ids or [],
        default_attendee_names=attendee_names,
        auto_create_meetings=schedule.auto_create_meetings,
        reminder_days_before=schedule.reminder_days_before,
    )


@router.get(
    "/stores/{store_id}/schedule",
    response_model=MeetingScheduleResponse,
)
async def get_store_schedule(
    store_id: str,
    current_user: User = Depends(require_corporate_or_gm),
    db: AsyncSession = Depends(get_db),
):
    """Get a store's meeting schedule."""
    store_uuid = _validate_uuid(store_id, "store_id")
    store = await _get_store_or_404(store_uuid, db)

    # GM store access check
    if current_user.role == UserRole.GM:
        from app.auth import _user_has_store_access
        if not await _user_has_store_access(current_user.id, store.id, db):
            raise HTTPException(status_code=403, detail="You do not have access to this store")

    schedule = await scheduling_service.get_store_schedule(db, store.id)
    if not schedule:
        raise HTTPException(status_code=404, detail="No schedule set for this store")

    return await _build_schedule_response(schedule, store.name, db)


@router.put(
    "/stores/{store_id}/schedule",
    response_model=MeetingScheduleResponse,
)
async def set_store_schedule(
    store_id: str,
    body: MeetingScheduleRequest,
    current_user: User = Depends(require_corporate_or_gm),
    db: AsyncSession = Depends(get_db),
):
    """Set or update a store's meeting schedule."""
    store_uuid = _validate_uuid(store_id, "store_id")
    store = await _get_store_or_404(store_uuid, db)

    # GM store access check
    if current_user.role == UserRole.GM:
        from app.auth import _user_has_store_access
        if not await _user_has_store_access(current_user.id, store.id, db):
            raise HTTPException(status_code=403, detail="You do not have access to this store")

    # Parse preferred_time
    preferred_time = None
    if body.preferred_time:
        try:
            parts = body.preferred_time.split(":")
            preferred_time = datetime.time(int(parts[0]), int(parts[1]))
        except (ValueError, IndexError):
            raise HTTPException(status_code=422, detail="Invalid time format, use HH:MM")

    cadence = MeetingCadence(body.cadence)

    # Convert attendee UUIDs to string list for JSON storage
    attendee_id_strs = None
    if body.default_attendee_ids is not None:
        attendee_id_strs = [str(uid) for uid in body.default_attendee_ids]

    schedule = await scheduling_service.upsert_store_schedule(
        db=db,
        store_id=store.id,
        cadence=cadence,
        preferred_day=body.preferred_day_of_week,
        preferred_time=preferred_time,
        minimum_per_month=body.minimum_per_month,
        notes=body.notes,
        created_by_id=current_user.id,
        template_name=body.template_name,
        default_attendee_ids=attendee_id_strs,
        auto_create_meetings=body.auto_create_meetings,
        reminder_days_before=body.reminder_days_before,
    )

    return await _build_schedule_response(schedule, store.name, db)


@router.get(
    "/schedules/compliance",
    response_model=list[CadenceComplianceResponse],
)
async def get_compliance(
    month: Optional[int] = Query(None, ge=1, le=12),
    year: Optional[int] = Query(None, ge=2020, le=2100),
    current_user: User = Depends(require_corporate),
    db: AsyncSession = Depends(get_db),
):
    """Cadence compliance across all stores — corporate only."""
    results = await scheduling_service.get_cadence_compliance(
        db, month=month, year=year
    )
    return [CadenceComplianceResponse(**r) for r in results]


@router.get(
    "/schedules/overdue",
    response_model=list[OverdueMeetingResponse],
)
async def get_overdue(
    current_user: User = Depends(require_corporate),
    db: AsyncSession = Depends(get_db),
):
    """Stores behind on meeting cadence — corporate only."""
    results = await scheduling_service.check_overdue_meetings(db)
    return [OverdueMeetingResponse(**r) for r in results]


@router.post(
    "/schedules/auto-create",
    response_model=AutoCreateResponse,
)
async def auto_create_meetings(
    current_user: User = Depends(require_corporate),
    db: AsyncSession = Depends(get_db),
):
    """Trigger auto-creation of upcoming meetings — corporate only.

    Creates Meeting records for the next 30 days based on schedules
    with auto_create_meetings=True. Idempotent — skips existing meetings.
    """
    created = await scheduling_service.auto_create_upcoming_meetings(db)
    return AutoCreateResponse(
        created=len(created),
        meetings=created,
    )
