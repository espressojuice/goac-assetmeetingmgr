"""Flag management routes."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    AutoAssignResponse,
    FlagAssignRequest,
    FlagEscalateRequest,
    FlagRespondRequest,
    FlagRespondWorkflowRequest,
    FlagResponse,
    FlagStatsResponse,
    MyFlagResponse,
    OverdueFlagResponse,
)
from app.auth import get_current_user, require_role
from app.database import get_db
from app.models.flag import Flag, FlagCategory, FlagSeverity, FlagStatus
from app.models.meeting import Meeting
from app.models.user import User, UserRole
from app.models.accountability import FlagAssignment
from app.services.flag_service import FlagService

router = APIRouter()
_flag_service = FlagService()


async def _validate_meeting(meeting_id: str, db: AsyncSession) -> uuid.UUID:
    try:
        meeting_uuid = uuid.UUID(meeting_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid meeting_id format")

    result = await db.execute(select(Meeting).where(Meeting.id == meeting_uuid))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Meeting {meeting_id} not found")
    return meeting_uuid


def _validate_uuid(value: str, name: str = "id") -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid {name} format")


# ------------------------------------------------------------------
# Existing endpoints (unchanged)
# ------------------------------------------------------------------

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
async def respond_to_flag_legacy(
    flag_id: str,
    body: FlagRespondRequest,
    db: AsyncSession = Depends(get_db),
) -> FlagResponse:
    """Submit a response to a flagged item (legacy endpoint, no auth required)."""
    flag_uuid = _validate_uuid(flag_id, "flag_id")

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


# ------------------------------------------------------------------
# New workflow endpoints
# ------------------------------------------------------------------

@router.get("/flags/my/assigned", response_model=list[MyFlagResponse])
async def get_my_flags(
    status: Optional[str] = None,
    store_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all flags assigned to the current user."""
    flags = await _flag_service.get_my_flags(
        str(current_user.id), db, status=status, store_id=store_id
    )
    return flags


@router.get("/flags/overdue/all", response_model=list[OverdueFlagResponse])
async def get_overdue_flags(
    store_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all overdue flags. Corporate sees all, GM sees their stores."""
    # GMs can only see overdue flags for stores they manage
    effective_store_id = store_id
    if current_user.role not in (UserRole.CORPORATE,):
        # Non-corporate users see only their own assigned overdue flags
        flags = await _flag_service.get_my_flags(
            str(current_user.id), db, status="overdue", store_id=store_id
        )
        return [
            OverdueFlagResponse(
                id=f["id"],
                assignment_id=f["assignment_id"],
                category=f["category"],
                severity=f["severity"],
                message=f["message"],
                status=f["status"],
                store_name=f["store_name"],
                meeting_date=f["meeting_date"],
                deadline=f["deadline"],
                days_overdue=f["days_overdue"],
                assigned_to_name="You",
                assigned_to_email="",
            )
            for f in flags
        ]

    overdue = await _flag_service.check_overdue_flags(db, store_id=effective_store_id)
    return overdue


@router.post("/flags/{flag_id}/assign")
async def assign_flag(
    flag_id: str,
    body: FlagAssignRequest,
    current_user: User = Depends(require_role(UserRole.CORPORATE, UserRole.GM)),
    db: AsyncSession = Depends(get_db),
):
    """Assign a flag to a user. Requires corporate or GM role."""
    _validate_uuid(flag_id, "flag_id")
    try:
        assignment = await _flag_service.assign_flag(
            flag_id=flag_id,
            assigned_to_id=body.assigned_to_id,
            assigned_by_id=str(current_user.id),
            db=db,
        )
        await db.commit()
        return {
            "id": str(assignment.id),
            "flag_id": str(assignment.flag_id),
            "assigned_to_id": str(assignment.assigned_to_id),
            "deadline": str(assignment.deadline),
            "status": assignment.status.value,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/flags/{flag_id}/respond-workflow")
async def respond_to_flag_workflow(
    flag_id: str,
    body: FlagRespondWorkflowRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Submit a response to an assigned flag.

    Only the assigned user or a corporate user can respond.
    Response must be at least 10 characters.
    """
    flag_uuid = _validate_uuid(flag_id, "flag_id")

    # Check permission: must be assigned user or corporate
    assignment_result = await db.execute(
        select(FlagAssignment).where(FlagAssignment.flag_id == flag_uuid)
    )
    assignment = assignment_result.scalar_one_or_none()

    if current_user.role != UserRole.CORPORATE:
        if not assignment or assignment.assigned_to_id != current_user.id:
            raise HTTPException(
                status_code=403,
                detail="Only the assigned user or a corporate user can respond to this flag",
            )

    try:
        record = await _flag_service.submit_response(
            flag_id=flag_id,
            responder_id=str(current_user.id),
            response_text=body.response_text,
            db=db,
        )
        await db.commit()
        return {
            "id": str(record.id),
            "flag_id": str(record.flag_id),
            "response_text": record.response_text,
            "created_at": record.created_at.isoformat() if record.created_at else None,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/flags/{flag_id}/escalate")
async def escalate_flag(
    flag_id: str,
    body: FlagEscalateRequest = FlagEscalateRequest(),
    current_user: User = Depends(require_role(UserRole.CORPORATE, UserRole.GM)),
    db: AsyncSession = Depends(get_db),
):
    """Manually escalate a flag. Changes status to escalated, increments escalation_level."""
    _validate_uuid(flag_id, "flag_id")
    try:
        flag = await _flag_service.escalate_flag(
            flag_id=flag_id, db=db, reason=body.reason
        )
        await db.commit()
        return {
            "id": str(flag.id),
            "status": flag.status.value,
            "escalation_level": flag.escalation_level,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "/meetings/{meeting_id}/auto-assign",
    response_model=AutoAssignResponse,
)
async def auto_assign_meeting_flags(
    meeting_id: str,
    current_user: User = Depends(require_role(UserRole.CORPORATE, UserRole.GM)),
    db: AsyncSession = Depends(get_db),
):
    """Auto-assign all unassigned flags for a meeting based on category-to-role mapping."""
    await _validate_meeting(meeting_id, db)
    result = await _flag_service.auto_assign_flags(
        meeting_id=meeting_id,
        db=db,
        assigned_by_id=str(current_user.id),
    )
    await db.commit()
    return result
