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
    FlagVerifyRequest,
    FlagVerifyResponse,
    MyFlagResponse,
    OverdueFlagResponse,
)
from app.auth import get_current_user, require_role, require_corporate_or_gm
from app.database import get_db
from app.models.flag import Flag, FlagCategory, FlagSeverity, FlagStatus
from app.models.meeting import Meeting
from app.models.user import User, UserRole
from app.models.accountability import AssignmentStatus, FlagAssignment
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


async def _check_meeting_store_access(
    meeting_id: uuid.UUID, current_user: User, db: AsyncSession
) -> None:
    """Verify user can access the meeting's store."""
    if current_user.role == UserRole.CORPORATE:
        return
    result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    meeting = result.scalar_one_or_none()
    if not meeting:
        return
    from app.auth import _user_has_store_access
    if not await _user_has_store_access(current_user.id, meeting.store_id, db):
        raise HTTPException(status_code=403, detail="You do not have access to this meeting's store")


async def _check_flag_store_access(
    flag_id: uuid.UUID, current_user: User, db: AsyncSession
) -> Flag:
    """Verify user can access the flag's store. Returns the flag."""
    result = await db.execute(select(Flag).where(Flag.id == flag_id))
    flag = result.scalar_one_or_none()
    if not flag:
        raise HTTPException(status_code=404, detail=f"Flag {flag_id} not found")
    if current_user.role == UserRole.CORPORATE:
        return flag
    from app.auth import _user_has_store_access
    if not await _user_has_store_access(current_user.id, flag.store_id, db):
        raise HTTPException(status_code=403, detail="You do not have access to this flag's store")
    return flag


# ------------------------------------------------------------------
# Existing endpoints (now with auth)
# ------------------------------------------------------------------

@router.get("/flags/{meeting_id}", response_model=list[FlagResponse])
async def get_meeting_flags(
    meeting_id: str,
    severity: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[FlagResponse]:
    """Get all flags for a meeting with optional filters."""
    meeting_uuid = await _validate_meeting(meeting_id, db)

    # Check store access
    await _check_meeting_store_access(meeting_uuid, current_user, db)

    query = select(Flag).where(Flag.meeting_id == meeting_uuid)

    # Manager: only see flags assigned to them
    if current_user.role == UserRole.MANAGER:
        query = query.where(
            Flag.id.in_(
                select(FlagAssignment.flag_id).where(
                    FlagAssignment.assigned_to_id == current_user.id
                )
            )
        )

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
    meeting_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FlagStatsResponse:
    """Get flag statistics for a meeting."""
    meeting_uuid = await _validate_meeting(meeting_id, db)
    await _check_meeting_store_access(meeting_uuid, current_user, db)

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
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FlagResponse:
    """Submit a response to a flagged item (legacy endpoint)."""
    flag_uuid = _validate_uuid(flag_id, "flag_id")

    result = await db.execute(select(Flag).where(Flag.id == flag_uuid))
    flag = result.scalar_one_or_none()
    if not flag:
        raise HTTPException(status_code=404, detail=f"Flag {flag_id} not found")

    # Check store access
    if current_user.role != UserRole.CORPORATE:
        from app.auth import _user_has_store_access
        if not await _user_has_store_access(current_user.id, flag.store_id, db):
            raise HTTPException(status_code=403, detail="You do not have access to this flag's store")

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
    """Get all overdue flags. Corporate sees all, GM sees their stores, Manager sees own."""
    if current_user.role == UserRole.MANAGER:
        # Managers only see their own assigned overdue flags
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

    if current_user.role == UserRole.GM:
        # GMs see overdue flags for their stores only
        from app.auth import get_user_store_ids
        user_store_ids = await get_user_store_ids(current_user, db)
        # If store_id is provided, verify it's one of theirs
        if store_id:
            sid = _validate_uuid(store_id, "store_id")
            if sid not in user_store_ids:
                raise HTTPException(status_code=403, detail="You do not have access to this store")
        # Filter to their stores
        overdue = await _flag_service.check_overdue_flags(db, store_id=store_id)
        if user_store_ids:
            overdue = [f for f in overdue if any(
                str(sid) in (f.store_name if hasattr(f, 'store_name') else '')
                for sid in user_store_ids
            )]
            # Better approach: filter by store_id from the flag's meeting
            # For now, use the service's store_id filter
            if not store_id and user_store_ids:
                # Re-query for each store
                all_overdue = []
                for sid in user_store_ids:
                    store_overdue = await _flag_service.check_overdue_flags(db, store_id=str(sid))
                    all_overdue.extend(store_overdue)
                overdue = all_overdue
        return overdue

    # Corporate sees all
    overdue = await _flag_service.check_overdue_flags(db, store_id=store_id)
    return overdue


@router.post("/flags/{flag_id}/assign")
async def assign_flag(
    flag_id: str,
    body: FlagAssignRequest,
    current_user: User = Depends(require_role(UserRole.CORPORATE, UserRole.GM)),
    db: AsyncSession = Depends(get_db),
):
    """Assign a flag to a user. Requires corporate or GM role."""
    flag_uuid = _validate_uuid(flag_id, "flag_id")

    # GM: verify they have access to the flag's store
    if current_user.role == UserRole.GM:
        await _check_flag_store_access(flag_uuid, current_user, db)

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
    flag_uuid = _validate_uuid(flag_id, "flag_id")

    # GM: verify store access
    if current_user.role == UserRole.GM:
        await _check_flag_store_access(flag_uuid, current_user, db)

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
    meeting_uuid = await _validate_meeting(meeting_id, db)

    # GM: verify store access
    if current_user.role == UserRole.GM:
        await _check_meeting_store_access(meeting_uuid, current_user, db)

    result = await _flag_service.auto_assign_flags(
        meeting_id=meeting_id,
        db=db,
        assigned_by_id=str(current_user.id),
    )
    await db.commit()
    return result


# ------------------------------------------------------------------
# Flag verification (during/after meeting)
# ------------------------------------------------------------------

@router.post("/flags/{flag_id}/verify", response_model=FlagVerifyResponse)
async def verify_flag(
    flag_id: str,
    body: FlagVerifyRequest,
    current_user: User = Depends(require_role(UserRole.CORPORATE, UserRole.GM)),
    db: AsyncSession = Depends(get_db),
):
    """Mark a responded flag as verified or unresolved. Corporate/GM only."""
    flag_uuid = _validate_uuid(flag_id, "flag_id")
    flag = await _check_flag_store_access(flag_uuid, current_user, db)

    if flag.status != FlagStatus.RESPONDED:
        raise HTTPException(
            status_code=422,
            detail=f"Flag must be in 'responded' status to verify (current: {flag.status.value})",
        )

    new_status = FlagStatus.VERIFIED if body.status == "verified" else FlagStatus.UNRESOLVED
    now = datetime.now(ZoneInfo("US/Central"))

    flag.status = new_status
    flag.verified_by_id = current_user.id
    flag.verified_at = now
    if body.verification_notes is not None:
        flag.verification_notes = body.verification_notes
    if body.expected_resolution_date is not None:
        flag.expected_resolution_date = body.expected_resolution_date
        # Also propagate to active FlagAssignment
        assignment_result = await db.execute(
            select(FlagAssignment).where(
                FlagAssignment.flag_id == flag.id,
                FlagAssignment.status.in_([
                    AssignmentStatus.PENDING,
                    AssignmentStatus.ACKNOWLEDGED,
                    AssignmentStatus.RESPONDED,
                ]),
            )
        )
        for assignment in assignment_result.scalars().all():
            assignment.expected_resolution_date = body.expected_resolution_date

    await db.commit()
    await db.refresh(flag)

    return FlagVerifyResponse(
        id=str(flag.id),
        status=flag.status.value,
        verified_by_id=str(flag.verified_by_id),
        verified_at=flag.verified_at.isoformat(),
        verification_notes=flag.verification_notes,
        expected_resolution_date=str(flag.expected_resolution_date) if flag.expected_resolution_date else None,
    )
