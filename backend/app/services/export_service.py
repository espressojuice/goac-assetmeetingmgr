"""CSV export service for meetings, flags, attendance, and promise tracking."""

from __future__ import annotations

import csv
import datetime
import io
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func, case, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.flag import Flag, FlagSeverity, FlagStatus
from app.models.meeting import Meeting
from app.models.store import Store
from app.models.user import User
from app.models.accountability import FlagAssignment, MeetingAttendance

# UTF-8 BOM for Excel compatibility
_BOM = "\ufeff"


def _central_str(dt: Optional[datetime.datetime]) -> str:
    """Format a datetime as Central Time string, or empty."""
    if not dt:
        return ""
    try:
        import zoneinfo
        ct = zoneinfo.ZoneInfo("US/Central")
    except ImportError:
        ct = datetime.timezone(datetime.timedelta(hours=-6))
    return dt.astimezone(ct).strftime("%Y-%m-%d %H:%M:%S CT")


def _date_str(d: Optional[datetime.date]) -> str:
    """Format a date as string, or empty."""
    return str(d) if d else ""


async def export_meetings_csv(
    db: AsyncSession,
    store_id: Optional[UUID] = None,
    date_from: Optional[datetime.date] = None,
    date_to: Optional[datetime.date] = None,
) -> str:
    """Export meetings as CSV with flag and attendance summaries."""
    query = (
        select(Meeting, Store)
        .join(Store, Meeting.store_id == Store.id)
        .order_by(Meeting.meeting_date.desc())
    )
    if store_id:
        query = query.where(Meeting.store_id == store_id)
    if date_from:
        query = query.where(Meeting.meeting_date >= date_from)
    if date_to:
        query = query.where(Meeting.meeting_date <= date_to)

    result = await db.execute(query)
    rows = result.all()

    buf = io.StringIO()
    buf.write(_BOM)
    writer = csv.writer(buf)
    writer.writerow([
        "Meeting Date", "Store Name", "Status", "Total Flags", "Red Flags",
        "Yellow Flags", "Verified", "Unresolved", "Open", "Responded",
        "Resolution Rate (%)", "Attendance (Present/Expected)",
        "Closed By", "Closed At", "Close Notes",
    ])

    for meeting, store in rows:
        # Flag stats
        flag_q = select(
            func.count(Flag.id).label("total"),
            func.count(case((Flag.severity == FlagSeverity.RED, 1))).label("red"),
            func.count(case((Flag.severity == FlagSeverity.YELLOW, 1))).label("yellow"),
            func.count(case((Flag.status == FlagStatus.VERIFIED, 1))).label("verified"),
            func.count(case((Flag.status == FlagStatus.UNRESOLVED, 1))).label("unresolved"),
            func.count(case((Flag.status == FlagStatus.OPEN, 1))).label("open"),
            func.count(case((Flag.status == FlagStatus.RESPONDED, 1))).label("responded"),
        ).where(Flag.meeting_id == meeting.id)
        fs = (await db.execute(flag_q)).one()

        resolution_rate = round(fs.verified / fs.total * 100, 1) if fs.total else 0.0

        # Attendance
        att_q = select(
            func.count(MeetingAttendance.id).label("expected"),
            func.count(case((MeetingAttendance.checked_in == True, 1))).label("present"),
        ).where(MeetingAttendance.meeting_id == meeting.id)
        att = (await db.execute(att_q)).one()
        att_str = f"{att.present}/{att.expected}" if att.expected else "0/0"

        # Closed by
        closed_by_name = ""
        if meeting.closed_by_id:
            u = (await db.execute(select(User.name).where(User.id == meeting.closed_by_id))).scalar()
            closed_by_name = u or ""

        writer.writerow([
            str(meeting.meeting_date), store.name, meeting.status.value,
            fs.total, fs.red, fs.yellow, fs.verified, fs.unresolved,
            fs.open, fs.responded, resolution_rate, att_str,
            closed_by_name, _central_str(meeting.closed_at), meeting.close_notes or "",
        ])

    return buf.getvalue()


async def export_flags_csv(
    db: AsyncSession,
    store_id: Optional[UUID] = None,
    date_from: Optional[datetime.date] = None,
    date_to: Optional[datetime.date] = None,
    status: Optional[str] = None,
) -> str:
    """Export flags as CSV with priority scores."""
    from app.services.metrics_service import get_top_priority_items

    query = (
        select(Flag, Meeting, Store)
        .join(Meeting, Flag.meeting_id == Meeting.id)
        .join(Store, Flag.store_id == Store.id)
        .order_by(Meeting.meeting_date.desc())
    )
    if store_id:
        query = query.where(Flag.store_id == store_id)
    if date_from:
        query = query.where(Meeting.meeting_date >= date_from)
    if date_to:
        query = query.where(Meeting.meeting_date <= date_to)
    if status:
        query = query.where(Flag.status == status)

    result = await db.execute(query)
    rows = result.all()

    # Get priority scores for non-verified flags (reuse MetricsService)
    priority_items = await get_top_priority_items(
        db, store_id=store_id, limit=99999
    )
    score_map = {item["flag_id"]: item["priority_score"] for item in priority_items}

    today = datetime.date.today()

    buf = io.StringIO()
    buf.write(_BOM)
    writer = csv.writer(buf)
    writer.writerow([
        "Meeting Date", "Store Name", "Rule Name", "Severity", "Status",
        "Description", "Assigned To", "Response", "Responded At",
        "Verified By", "Verified At", "Verification Notes",
        "Expected Resolution Date", "Days Outstanding",
        "Escalation Level", "Priority Score",
    ])

    for flag, meeting, store in rows:
        # Get latest assignment
        assign_q = (
            select(FlagAssignment)
            .where(FlagAssignment.flag_id == flag.id)
            .order_by(FlagAssignment.created_at.desc())
            .limit(1)
        )
        assignment = (await db.execute(assign_q)).scalar_one_or_none()

        assigned_to = ""
        if assignment:
            u = (await db.execute(select(User.name).where(User.id == assignment.assigned_to_id))).scalar()
            assigned_to = u or ""

        verified_by = ""
        if flag.verified_by_id:
            u = (await db.execute(select(User.name).where(User.id == flag.verified_by_id))).scalar()
            verified_by = u or ""

        days_outstanding = (today - flag.created_at.date()).days if flag.created_at else 0
        priority_score = score_map.get(str(flag.id), 0)

        writer.writerow([
            str(meeting.meeting_date), store.name, flag.field_name,
            flag.severity.value, flag.status.value, flag.message,
            assigned_to, flag.response_text or "", _central_str(flag.responded_at),
            verified_by, _central_str(flag.verified_at), flag.verification_notes or "",
            _date_str(flag.expected_resolution_date), days_outstanding,
            flag.escalation_level, priority_score,
        ])

    return buf.getvalue()


async def export_attendance_csv(
    db: AsyncSession,
    store_id: Optional[UUID] = None,
    date_from: Optional[datetime.date] = None,
    date_to: Optional[datetime.date] = None,
) -> str:
    """Export meeting attendance as CSV."""
    query = (
        select(MeetingAttendance, Meeting, Store, User)
        .join(Meeting, MeetingAttendance.meeting_id == Meeting.id)
        .join(Store, Meeting.store_id == Store.id)
        .join(User, MeetingAttendance.user_id == User.id)
        .order_by(Meeting.meeting_date.desc(), Store.name, User.name)
    )
    if store_id:
        query = query.where(Meeting.store_id == store_id)
    if date_from:
        query = query.where(Meeting.meeting_date >= date_from)
    if date_to:
        query = query.where(Meeting.meeting_date <= date_to)

    result = await db.execute(query)
    rows = result.all()

    buf = io.StringIO()
    buf.write(_BOM)
    writer = csv.writer(buf)
    writer.writerow([
        "Meeting Date", "Store Name", "User Name", "User Role",
        "Checked In", "Checked In At", "Checked In By",
    ])

    for att, meeting, store, user in rows:
        checked_in_by = ""
        if att.checked_in_by_id:
            u = (await db.execute(select(User.name).where(User.id == att.checked_in_by_id))).scalar()
            checked_in_by = u or ""

        writer.writerow([
            str(meeting.meeting_date), store.name, user.name,
            user.role.value, "Yes" if att.checked_in else "No",
            _central_str(att.checked_in_at), checked_in_by,
        ])

    return buf.getvalue()


async def export_promise_tracking_csv(
    db: AsyncSession,
    store_id: Optional[UUID] = None,
    date_from: Optional[datetime.date] = None,
    date_to: Optional[datetime.date] = None,
) -> str:
    """Export promise date tracking — flags with expected_resolution_date."""
    query = (
        select(Flag, Meeting, Store)
        .join(Meeting, Flag.meeting_id == Meeting.id)
        .join(Store, Flag.store_id == Store.id)
        .where(Flag.expected_resolution_date.isnot(None))
    )
    if store_id:
        query = query.where(Flag.store_id == store_id)
    if date_from:
        query = query.where(Meeting.meeting_date >= date_from)
    if date_to:
        query = query.where(Meeting.meeting_date <= date_to)

    result = await db.execute(query)
    rows = result.all()

    today = datetime.date.today()

    buf = io.StringIO()
    buf.write(_BOM)
    writer = csv.writer(buf)
    writer.writerow([
        "Meeting Date", "Store Name", "Rule Name", "Assigned To",
        "Expected Resolution Date", "Actual Resolution Date", "Status",
        "Days Late", "Promise Kept",
    ])

    # Build list for sorting
    export_rows = []
    for flag, meeting, store in rows:
        # Get assigned user
        assign_q = (
            select(FlagAssignment)
            .where(FlagAssignment.flag_id == flag.id)
            .order_by(FlagAssignment.created_at.desc())
            .limit(1)
        )
        assignment = (await db.execute(assign_q)).scalar_one_or_none()

        assigned_to = ""
        if assignment:
            u = (await db.execute(select(User.name).where(User.id == assignment.assigned_to_id))).scalar()
            assigned_to = u or ""

        actual_resolution = flag.verified_at.date() if flag.verified_at else None

        # Calculate days_late and promise_kept
        expected = flag.expected_resolution_date
        if flag.status == FlagStatus.VERIFIED and actual_resolution:
            days_late = max(0, (actual_resolution - expected).days)
            promise_kept = "Yes" if actual_resolution <= expected else "No"
        elif expected < today and flag.status != FlagStatus.VERIFIED:
            days_late = (today - expected).days
            promise_kept = "No"
        else:
            days_late = 0
            promise_kept = "Pending"

        export_rows.append((
            days_late,
            [
                str(meeting.meeting_date), store.name, flag.field_name,
                assigned_to, _date_str(expected),
                _date_str(actual_resolution), flag.status.value,
                days_late, promise_kept,
            ],
        ))

    # Sort by days_late descending (worst offenders first)
    export_rows.sort(key=lambda r: r[0], reverse=True)
    for _, row in export_rows:
        writer.writerow(row)

    return buf.getvalue()
