"""Flag management routes."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import FlagResponse, FlagStatsResponse, FlagRespondRequest
from app.database import get_db
from app.models.flag import Flag, FlagCategory, FlagSeverity, FlagStatus
from app.models.meeting import Meeting

router = APIRouter()


async def _validate_meeting(meeting_id: str, db: AsyncSession) -> uuid.UUID:
    try:
        meeting_uuid = uuid.UUID(meeting_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid meeting_id format")

    result = await db.execute(select(Meeting).where(Meeting.id == meeting_uuid))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Meeting {meeting_id} not found")
    return meeting_uuid


@router.get("/flags/{meeting_id}", response_model=list[FlagResponse])
async def get_meeting_flags(
    meeting_id: str,
    severity: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
) -> list[FlagResponse]:
    """Get all flags for a meeting with optional filters."""
    meeting_uuid = await _validate_meeting(meeting_id, db)

    query = select(Flag).where(Flag.meeting_id == meeting_uuid)

    if severity:
        try:
            sev_enum = FlagSeverity(severity)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid severity: {severity}")
        query = query.where(Flag.severity == sev_enum)

    if category:
        try:
            cat_enum = FlagCategory(category)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid category: {category}")
        query = query.where(Flag.category == cat_enum)

    if status:
        try:
            stat_enum = FlagStatus(status)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid status: {status}")
        query = query.where(Flag.status == stat_enum)

    query = query.order_by(Flag.created_at)
    result = await db.execute(query)
    flags = list(result.scalars().all())

    return [
        FlagResponse(
            id=f.id,
            meeting_id=f.meeting_id,
            store_id=f.store_id,
            category=f.category.value,
            severity=f.severity.value,
            field_name=f.field_name,
            field_value=f.field_value,
            threshold=f.threshold,
            message=f.message,
            status=f.status.value,
            response_text=f.response_text,
            responded_by=f.responded_by,
            responded_at=f.responded_at,
            created_at=f.created_at,
        )
        for f in flags
    ]


@router.get("/flags/{meeting_id}/stats", response_model=FlagStatsResponse)
async def get_flag_stats(
    meeting_id: str, db: AsyncSession = Depends(get_db)
) -> FlagStatsResponse:
    """Get flag statistics for a meeting."""
    meeting_uuid = await _validate_meeting(meeting_id, db)

    result = await db.execute(
        select(Flag).where(Flag.meeting_id == meeting_uuid)
    )
    flags = list(result.scalars().all())

    by_category = {}
    for cat in FlagCategory:
        count = sum(1 for f in flags if f.category == cat)
        if count > 0:
            by_category[cat.value] = count

    return FlagStatsResponse(
        total=len(flags),
        yellow=sum(1 for f in flags if f.severity == FlagSeverity.YELLOW),
        red=sum(1 for f in flags if f.severity == FlagSeverity.RED),
        open=sum(1 for f in flags if f.status == FlagStatus.OPEN),
        responded=sum(1 for f in flags if f.status == FlagStatus.RESPONDED),
        by_category=by_category,
    )


@router.patch("/flags/{flag_id}/respond", response_model=FlagResponse)
async def respond_to_flag(
    flag_id: str,
    body: FlagRespondRequest,
    db: AsyncSession = Depends(get_db),
) -> FlagResponse:
    """Submit a response to a flagged item."""
    try:
        flag_uuid = uuid.UUID(flag_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid flag_id format")

    result = await db.execute(select(Flag).where(Flag.id == flag_uuid))
    flag = result.scalar_one_or_none()
    if not flag:
        raise HTTPException(status_code=404, detail=f"Flag {flag_id} not found")

    flag.response_text = body.response_text
    flag.responded_by = body.responded_by
    flag.responded_at = datetime.now(ZoneInfo("US/Central"))
    flag.status = FlagStatus.RESPONDED

    await db.commit()
    await db.refresh(flag)

    return FlagResponse(
        id=flag.id,
        meeting_id=flag.meeting_id,
        store_id=flag.store_id,
        category=flag.category.value,
        severity=flag.severity.value,
        field_name=flag.field_name,
        field_value=flag.field_value,
        threshold=flag.threshold,
        message=flag.message,
        status=flag.status.value,
        response_text=flag.response_text,
        responded_by=flag.responded_by,
        responded_at=flag.responded_at,
        created_at=flag.created_at,
    )
