"""Meeting attendance tracking endpoints."""

from __future__ import annotations

import datetime
import uuid
import zoneinfo

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    AttendanceMarkRequest,
    AttendanceResponse,
    AttendanceSummaryResponse,
)
from app.auth import get_current_user, verify_store_access
from app.database import get_db
from app.models.accountability import MeetingAttendance
from app.models.meeting import Meeting
from app.models.user import User, UserRole, UserStore

router = APIRouter()

CT = zoneinfo.ZoneInfo("US/Central")


def _validate_uuid(value: str, label: str = "ID") -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid {label} format")


async def _get_meeting_or_404(meeting_uuid: uuid.UUID, db: AsyncSession) -> Meeting:
    result = await db.execute(select(Meeting).where(Meeting.id == meeting_uuid))
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return meeting


async def _get_expected_users(store_id: uuid.UUID, db: AsyncSession) -> list[User]:
    """Get all users assigned to a store."""
    result = await db.execute(
        select(User)
        .join(UserStore, UserStore.user_id == User.id)
        .where(UserStore.store_id == store_id, User.is_active == True)
    )
    return list(result.scalars().all())


async def _get_attendance_records(meeting_id: uuid.UUID, db: AsyncSession) -> dict[uuid.UUID, MeetingAttendance]:
    """Get attendance records keyed by user_id."""
    result = await db.execute(
        select(MeetingAttendance).where(MeetingAttendance.meeting_id == meeting_id)
    )
    return {record.user_id: record for record in result.scalars().all()}


async def _build_attendance_list(
    meeting: Meeting, db: AsyncSession
) -> list[AttendanceResponse]:
    """Build full attendance list for a meeting."""
    expected_users = await _get_expected_users(meeting.store_id, db)
    records = await _get_attendance_records(meeting.id, db)

    # Also load checked_in_by names
    checker_ids = {r.checked_in_by_id for r in records.values() if r.checked_in_by_id}
    checkers = {}
    if checker_ids:
        result = await db.execute(select(User).where(User.id.in_(checker_ids)))
        checkers = {u.id: u.name for u in result.scalars().all()}

    attendance = []
    for user in expected_users:
        record = records.get(user.id)
        attendance.append(AttendanceResponse(
            user_id=str(user.id),
            user_name=user.name,
            user_role=user.role.value,
            checked_in=record.checked_in if record else False,
            checked_in_at=record.checked_in_at.isoformat() if record and record.checked_in_at else None,
            checked_in_by_name=checkers.get(record.checked_in_by_id) if record and record.checked_in_by_id else None,
        ))
    return attendance


def _require_attendance_role(user: User) -> None:
    """Corporate, GM, or Manager can mark attendance."""
    if user.role not in (UserRole.CORPORATE, UserRole.GM, UserRole.MANAGER):
        raise HTTPException(status_code=403, detail="Insufficient permissions to manage attendance")


@router.get(
    "/meetings/{meeting_id}/attendance",
    response_model=list[AttendanceResponse],
)
async def get_attendance(
    meeting_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get attendance list for a meeting."""
    meeting_uuid = _validate_uuid(meeting_id, "meeting_id")
    meeting = await _get_meeting_or_404(meeting_uuid, db)

    # Verify store access
    if current_user.role != UserRole.CORPORATE:
        from app.auth import _user_has_store_access
        if not await _user_has_store_access(current_user.id, meeting.store_id, db):
            raise HTTPException(status_code=403, detail="You do not have access to this meeting")

    return await _build_attendance_list(meeting, db)


@router.post(
    "/meetings/{meeting_id}/attendance",
    response_model=list[AttendanceResponse],
)
async def mark_attendance(
    meeting_id: str,
    body: AttendanceMarkRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark one or more users as checked in."""
    _require_attendance_role(current_user)
    meeting_uuid = _validate_uuid(meeting_id, "meeting_id")
    meeting = await _get_meeting_or_404(meeting_uuid, db)

    # Verify store access for non-corporate
    if current_user.role != UserRole.CORPORATE:
        from app.auth import _user_has_store_access
        if not await _user_has_store_access(current_user.id, meeting.store_id, db):
            raise HTTPException(status_code=403, detail="You do not have access to this meeting")

    now = datetime.datetime.now(CT)
    records = await _get_attendance_records(meeting.id, db)

    for uid in body.user_ids:
        if uid in records:
            # Update existing record
            record = records[uid]
            record.checked_in = True
            record.checked_in_at = now
            record.checked_in_by_id = current_user.id
        else:
            # Create new record
            record = MeetingAttendance(
                meeting_id=meeting.id,
                user_id=uid,
                checked_in=True,
                checked_in_at=now,
                checked_in_by_id=current_user.id,
            )
            db.add(record)

    await db.commit()
    return await _build_attendance_list(meeting, db)


@router.delete(
    "/meetings/{meeting_id}/attendance/{user_id}",
    response_model=AttendanceResponse,
)
async def unmark_attendance(
    meeting_id: str,
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Unmark a user's check-in (undo)."""
    _require_attendance_role(current_user)
    meeting_uuid = _validate_uuid(meeting_id, "meeting_id")
    user_uuid = _validate_uuid(user_id, "user_id")
    meeting = await _get_meeting_or_404(meeting_uuid, db)

    # Verify store access for non-corporate
    if current_user.role != UserRole.CORPORATE:
        from app.auth import _user_has_store_access
        if not await _user_has_store_access(current_user.id, meeting.store_id, db):
            raise HTTPException(status_code=403, detail="You do not have access to this meeting")

    # Find existing record
    result = await db.execute(
        select(MeetingAttendance).where(
            MeetingAttendance.meeting_id == meeting_uuid,
            MeetingAttendance.user_id == user_uuid,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Attendance record not found")

    record.checked_in = False
    record.checked_in_at = None
    record.checked_in_by_id = None
    await db.commit()

    # Load user for response
    user_result = await db.execute(select(User).where(User.id == user_uuid))
    user = user_result.scalar_one()

    return AttendanceResponse(
        user_id=str(user.id),
        user_name=user.name,
        user_role=user.role.value,
        checked_in=False,
        checked_in_at=None,
        checked_in_by_name=None,
    )


@router.get(
    "/meetings/{meeting_id}/attendance/summary",
    response_model=AttendanceSummaryResponse,
)
async def get_attendance_summary(
    meeting_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get attendance summary counts for a meeting."""
    meeting_uuid = _validate_uuid(meeting_id, "meeting_id")
    meeting = await _get_meeting_or_404(meeting_uuid, db)

    # Verify store access
    if current_user.role != UserRole.CORPORATE:
        from app.auth import _user_has_store_access
        if not await _user_has_store_access(current_user.id, meeting.store_id, db):
            raise HTTPException(status_code=403, detail="You do not have access to this meeting")

    expected_users = await _get_expected_users(meeting.store_id, db)
    records = await _get_attendance_records(meeting.id, db)

    total_expected = len(expected_users)
    total_present = sum(1 for u in expected_users if records.get(u.id) and records[u.id].checked_in)
    total_absent = total_expected - total_present

    return AttendanceSummaryResponse(
        total_expected=total_expected,
        total_present=total_present,
        total_absent=total_absent,
    )
