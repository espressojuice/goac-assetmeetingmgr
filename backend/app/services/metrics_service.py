"""Accountability metrics service — manager resolution rates, store comparison, priority items, resolution trends."""

from __future__ import annotations

import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func, case, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.flag import Flag, FlagSeverity, FlagStatus
from app.models.meeting import Meeting, MeetingStatus
from app.models.store import Store
from app.models.user import User
from app.models.accountability import FlagAssignment, MeetingAttendance


async def get_manager_resolution_rates(
    db: AsyncSession,
    store_id: Optional[UUID] = None,
    date_from: Optional[datetime.date] = None,
    date_to: Optional[datetime.date] = None,
) -> list[dict]:
    """Per-manager flag resolution metrics.

    Returns list sorted by resolution_rate ascending (worst first).
    """
    # Base: join FlagAssignment → Flag → Meeting, group by assigned_to_id
    query = (
        select(
            FlagAssignment.assigned_to_id,
            func.count(FlagAssignment.id).label("total_assigned"),
            func.count(case((Flag.status == FlagStatus.VERIFIED, 1))).label("total_resolved"),
            func.count(case((Flag.status == FlagStatus.UNRESOLVED, 1))).label("total_unresolved"),
            func.count(case((Flag.status == FlagStatus.RESPONDED, 1))).label("total_responded"),
            func.count(case((Flag.status == FlagStatus.OPEN, 1))).label("total_open"),
            func.count(
                case((
                    and_(
                        FlagAssignment.deadline < func.current_date(),
                        Flag.status.in_([FlagStatus.OPEN, FlagStatus.RESPONDED]),
                    ),
                    1,
                ))
            ).label("total_overdue"),
        )
        .select_from(FlagAssignment)
        .join(Flag, FlagAssignment.flag_id == Flag.id)
        .join(Meeting, Flag.meeting_id == Meeting.id)
        .group_by(FlagAssignment.assigned_to_id)
    )

    if store_id:
        query = query.where(Flag.store_id == store_id)
    if date_from:
        query = query.where(Meeting.meeting_date >= date_from)
    if date_to:
        query = query.where(Meeting.meeting_date <= date_to)

    result = await db.execute(query)
    rows = result.all()

    # Fetch user info and store names for each manager
    metrics = []
    for row in rows:
        user_result = await db.execute(
            select(User).where(User.id == row.assigned_to_id)
        )
        user = user_result.scalar_one_or_none()
        if not user:
            continue

        # Get store names for this user
        from app.models.user import UserStore
        store_result = await db.execute(
            select(Store.name)
            .join(UserStore, Store.id == UserStore.store_id)
            .where(UserStore.user_id == user.id)
        )
        store_names = [s for s in store_result.scalars().all()]

        total_assigned = row.total_assigned or 0
        total_resolved = row.total_resolved or 0
        resolution_rate = round(total_resolved / total_assigned * 100, 1) if total_assigned > 0 else 0.0

        # Avg response time: average hours between assignment.created_at and flag.responded_at
        avg_q = (
            select(
                func.avg(
                    func.julianday(Flag.responded_at) - func.julianday(FlagAssignment.created_at)
                )
            )
            .select_from(FlagAssignment)
            .join(Flag, FlagAssignment.flag_id == Flag.id)
            .where(
                FlagAssignment.assigned_to_id == row.assigned_to_id,
                Flag.responded_at.isnot(None),
            )
        )
        avg_result = await db.execute(avg_q)
        avg_days = avg_result.scalar()
        avg_response_time_hours = round(avg_days * 24, 1) if avg_days else None

        metrics.append({
            "user_id": str(user.id),
            "user_name": user.name,
            "user_role": user.role.value,
            "store_names": store_names,
            "total_assigned": total_assigned,
            "total_resolved": total_resolved,
            "total_unresolved": row.total_unresolved or 0,
            "total_responded": row.total_responded or 0,
            "total_open": row.total_open or 0,
            "total_overdue": row.total_overdue or 0,
            "resolution_rate": resolution_rate,
            "avg_response_time_hours": avg_response_time_hours,
        })

    # Sort worst first
    metrics.sort(key=lambda m: m["resolution_rate"])
    return metrics


async def get_store_comparison(
    db: AsyncSession,
    store_ids: Optional[list[UUID]] = None,
    date_from: Optional[datetime.date] = None,
    date_to: Optional[datetime.date] = None,
) -> list[dict]:
    """Side-by-side store metrics for corporate dashboard."""
    store_query = select(Store).where(Store.is_active == True).order_by(Store.name)
    if store_ids:
        store_query = store_query.where(Store.id.in_(store_ids))

    result = await db.execute(store_query)
    stores = list(result.scalars().all())

    comparisons = []
    for store in stores:
        # Meeting count
        meeting_q = select(func.count(Meeting.id)).where(Meeting.store_id == store.id)
        if date_from:
            meeting_q = meeting_q.where(Meeting.meeting_date >= date_from)
        if date_to:
            meeting_q = meeting_q.where(Meeting.meeting_date <= date_to)
        meeting_count = (await db.execute(meeting_q)).scalar() or 0

        # Flag stats
        flag_q = (
            select(
                func.count(Flag.id).label("total"),
                func.count(case((Flag.status == FlagStatus.VERIFIED, 1))).label("verified"),
                func.count(case((Flag.status == FlagStatus.UNRESOLVED, 1))).label("unresolved"),
                func.count(case((Flag.status == FlagStatus.OPEN, 1))).label("open"),
            )
            .join(Meeting, Flag.meeting_id == Meeting.id)
            .where(Flag.store_id == store.id)
        )
        if date_from:
            flag_q = flag_q.where(Meeting.meeting_date >= date_from)
        if date_to:
            flag_q = flag_q.where(Meeting.meeting_date <= date_to)

        flag_result = await db.execute(flag_q)
        fs = flag_result.one()

        total_flags = fs.total or 0
        total_verified = fs.verified or 0
        resolution_rate = round(total_verified / total_flags * 100, 1) if total_flags > 0 else 0.0
        avg_flags = round(total_flags / meeting_count, 1) if meeting_count > 0 else 0.0

        # Attendance rate
        att_q = (
            select(
                func.count(MeetingAttendance.id).label("total"),
                func.count(case((MeetingAttendance.checked_in == True, 1))).label("present"),
            )
            .join(Meeting, MeetingAttendance.meeting_id == Meeting.id)
            .where(Meeting.store_id == store.id)
        )
        if date_from:
            att_q = att_q.where(Meeting.meeting_date >= date_from)
        if date_to:
            att_q = att_q.where(Meeting.meeting_date <= date_to)

        att_result = await db.execute(att_q)
        att = att_result.one()
        att_total = att.total or 0
        att_present = att.present or 0
        attendance_rate = round(att_present / att_total * 100, 1) if att_total > 0 else 0.0

        # meetings_on_schedule: simple check — at least 2 meetings in date range
        meetings_on_schedule = meeting_count >= 2

        comparisons.append({
            "store_id": str(store.id),
            "store_name": store.name,
            "total_meetings": meeting_count,
            "total_flags": total_flags,
            "total_verified": total_verified,
            "total_unresolved": fs.unresolved or 0,
            "total_open": fs.open or 0,
            "resolution_rate": resolution_rate,
            "avg_flags_per_meeting": avg_flags,
            "attendance_rate": attendance_rate,
            "meetings_on_schedule": meetings_on_schedule,
        })

    # Sort worst resolution first
    comparisons.sort(key=lambda c: c["resolution_rate"])
    return comparisons


async def get_top_priority_items(
    db: AsyncSession,
    store_id: Optional[UUID] = None,
    store_ids: Optional[list[UUID]] = None,
    limit: int = 10,
) -> list[dict]:
    """Joel's top N list of items requiring immediate attention.

    Priority score is additive across multiple criteria.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    today = now.date()

    # Load non-verified flags with related data
    query = (
        select(Flag, Meeting, Store)
        .join(Meeting, Flag.meeting_id == Meeting.id)
        .join(Store, Flag.store_id == Store.id)
        .where(Flag.status != FlagStatus.VERIFIED)
    )

    if store_id:
        query = query.where(Flag.store_id == store_id)
    elif store_ids:
        query = query.where(Flag.store_id.in_(store_ids))

    result = await db.execute(query)
    rows = result.all()

    items = []
    for flag, meeting, store in rows:
        score = 0

        # Status-based scoring
        if flag.status == FlagStatus.UNRESOLVED:
            score += 10
        if flag.status == FlagStatus.ESCALATED:
            score += 8

        # Deadline-based scoring (need to check assignment)
        assignment_result = await db.execute(
            select(FlagAssignment)
            .where(FlagAssignment.flag_id == flag.id)
            .order_by(FlagAssignment.created_at.desc())
            .limit(1)
        )
        assignment = assignment_result.scalar_one_or_none()

        if flag.status == FlagStatus.OPEN and assignment and assignment.deadline:
            if assignment.deadline < today:
                score += 5  # past deadline
            elif (assignment.deadline - today).days <= 2:
                score += 3  # within 48 hours

        # Severity scoring
        if flag.severity == FlagSeverity.RED:
            score += 3
        elif flag.severity == FlagSeverity.YELLOW:
            score += 1

        # Broken promise: expected_resolution_date is past
        if flag.expected_resolution_date and flag.expected_resolution_date < today:
            score += 5

        # Recurring flag
        if flag.escalation_level > 0:
            score += 2

        # Previous meeting also had this flag unresolved
        if flag.previous_flag_id:
            score += 2

        days_outstanding = (today - flag.created_at.date()).days if flag.created_at else 0

        # Get assigned_to name
        assigned_to_name = None
        if assignment:
            user_result = await db.execute(
                select(User.name).where(User.id == assignment.assigned_to_id)
            )
            assigned_to_name = user_result.scalar_one_or_none()

        items.append({
            "flag_id": str(flag.id),
            "priority_score": score,
            "store_name": store.name,
            "rule_name": flag.field_name,
            "description": flag.message,
            "severity": flag.severity.value,
            "status": flag.status.value,
            "assigned_to_name": assigned_to_name,
            "days_outstanding": days_outstanding,
            "expected_resolution_date": str(flag.expected_resolution_date) if flag.expected_resolution_date else None,
            "escalation_level": flag.escalation_level,
            "meeting_date": str(meeting.meeting_date),
        })

    # Sort by priority score descending, take top N
    items.sort(key=lambda i: i["priority_score"], reverse=True)
    return items[:limit]


async def get_resolution_trends(
    db: AsyncSession,
    store_id: Optional[UUID] = None,
    last_n_meetings: int = 6,
) -> list[dict]:
    """Per-meeting resolution trend data for charting.

    Returns list sorted by meeting_date ascending (oldest first).
    """
    # Get the last N meetings (completed or closed)
    meeting_query = (
        select(Meeting, Store)
        .join(Store, Meeting.store_id == Store.id)
        .where(Meeting.status.in_([MeetingStatus.COMPLETED, MeetingStatus.CLOSED]))
        .order_by(Meeting.meeting_date.desc())
        .limit(last_n_meetings)
    )
    if store_id:
        meeting_query = meeting_query.where(Meeting.store_id == store_id)

    result = await db.execute(meeting_query)
    meeting_rows = result.all()

    trends = []
    today = datetime.date.today()

    for meeting, store in meeting_rows:
        # Flag counts by status
        flag_q = (
            select(
                func.count(Flag.id).label("total"),
                func.count(case((Flag.status == FlagStatus.VERIFIED, 1))).label("verified"),
                func.count(case((Flag.status == FlagStatus.UNRESOLVED, 1))).label("unresolved"),
                func.count(case((Flag.status == FlagStatus.RESPONDED, 1))).label("responded"),
                func.count(case((Flag.status == FlagStatus.OPEN, 1))).label("open"),
            )
            .where(Flag.meeting_id == meeting.id)
        )
        flag_result = await db.execute(flag_q)
        fs = flag_result.one()

        total = fs.total or 0
        verified = fs.verified or 0
        resolution_rate = round(verified / total * 100, 1) if total > 0 else 0.0

        # Promise tracking for this meeting's flags
        promises_kept_q = (
            select(func.count(Flag.id))
            .where(
                Flag.meeting_id == meeting.id,
                Flag.expected_resolution_date.isnot(None),
                Flag.status == FlagStatus.VERIFIED,
                Flag.verified_at.isnot(None),
            )
        )
        promises_kept = (await db.execute(promises_kept_q)).scalar() or 0

        promises_broken_q = (
            select(func.count(Flag.id))
            .where(
                Flag.meeting_id == meeting.id,
                Flag.expected_resolution_date.isnot(None),
                Flag.expected_resolution_date < today,
                Flag.status != FlagStatus.VERIFIED,
            )
        )
        promises_broken = (await db.execute(promises_broken_q)).scalar() or 0

        # Attendance rate
        att_q = (
            select(
                func.count(MeetingAttendance.id).label("total"),
                func.count(case((MeetingAttendance.checked_in == True, 1))).label("present"),
            )
            .where(MeetingAttendance.meeting_id == meeting.id)
        )
        att_result = await db.execute(att_q)
        att = att_result.one()
        att_total = att.total or 0
        att_present = att.present or 0
        attendance_rate = round(att_present / att_total * 100, 1) if att_total > 0 else 0.0

        trends.append({
            "meeting_id": str(meeting.id),
            "meeting_date": str(meeting.meeting_date),
            "store_name": store.name,
            "total_flags": total,
            "verified": verified,
            "unresolved": fs.unresolved or 0,
            "responded": fs.responded or 0,
            "open": fs.open or 0,
            "resolution_rate": resolution_rate,
            "promises_kept": promises_kept,
            "promises_broken": promises_broken,
            "attendance_rate": attendance_rate,
        })

    # Sort ascending by meeting_date for chart plotting
    trends.sort(key=lambda t: t["meeting_date"])
    return trends


async def get_promise_tracking_summary(
    db: AsyncSession,
    store_id: Optional[UUID] = None,
) -> dict:
    """Aggregate promise date tracking across active (non-verified) flags."""
    today = datetime.date.today()

    # Base filter: flags with expected_resolution_date set
    base_filter = [Flag.expected_resolution_date.isnot(None)]
    if store_id:
        base_filter.append(Flag.store_id == store_id)

    # Total promises
    total_q = select(func.count(Flag.id)).where(*base_filter)
    total_promises = (await db.execute(total_q)).scalar() or 0

    # Kept: verified on or before expected date
    kept_q = select(func.count(Flag.id)).where(
        *base_filter,
        Flag.status == FlagStatus.VERIFIED,
        Flag.verified_at.isnot(None),
    )
    promises_kept = (await db.execute(kept_q)).scalar() or 0

    # Broken: past expected date and not verified
    broken_q = select(func.count(Flag.id)).where(
        *base_filter,
        Flag.expected_resolution_date < today,
        Flag.status != FlagStatus.VERIFIED,
    )
    promises_broken = (await db.execute(broken_q)).scalar() or 0

    # Pending: expected date in the future, not yet verified
    pending_q = select(func.count(Flag.id)).where(
        *base_filter,
        Flag.expected_resolution_date >= today,
        Flag.status != FlagStatus.VERIFIED,
    )
    promises_pending = (await db.execute(pending_q)).scalar() or 0

    # Avg days late for broken promises
    broken_flags_q = select(Flag).where(
        *base_filter,
        Flag.expected_resolution_date < today,
        Flag.status != FlagStatus.VERIFIED,
    )
    broken_result = await db.execute(broken_flags_q)
    broken_flags = list(broken_result.scalars().all())

    avg_days_late = None
    if broken_flags:
        total_days = sum(
            (today - f.expected_resolution_date).days
            for f in broken_flags
        )
        avg_days_late = round(total_days / len(broken_flags), 1)

    # Worst offenders: top 5 managers by broken promise count
    # Join flags → assignments to get assigned_to_id
    offender_q = (
        select(
            FlagAssignment.assigned_to_id,
            func.count(Flag.id).label("broken_count"),
        )
        .select_from(Flag)
        .join(FlagAssignment, FlagAssignment.flag_id == Flag.id)
        .where(
            Flag.expected_resolution_date.isnot(None),
            Flag.expected_resolution_date < today,
            Flag.status != FlagStatus.VERIFIED,
        )
        .group_by(FlagAssignment.assigned_to_id)
        .order_by(func.count(Flag.id).desc())
        .limit(5)
    )
    if store_id:
        offender_q = offender_q.where(Flag.store_id == store_id)

    offender_result = await db.execute(offender_q)
    offender_rows = offender_result.all()

    worst_offenders = []
    for row in offender_rows:
        user_result = await db.execute(
            select(User.name).where(User.id == row.assigned_to_id)
        )
        user_name = user_result.scalar_one_or_none() or "Unknown"

        # Total promises for this user
        total_user_q = (
            select(func.count(Flag.id))
            .select_from(Flag)
            .join(FlagAssignment, FlagAssignment.flag_id == Flag.id)
            .where(
                Flag.expected_resolution_date.isnot(None),
                FlagAssignment.assigned_to_id == row.assigned_to_id,
            )
        )
        if store_id:
            total_user_q = total_user_q.where(Flag.store_id == store_id)
        total_user = (await db.execute(total_user_q)).scalar() or 0

        worst_offenders.append({
            "user_name": user_name,
            "broken_count": row.broken_count,
            "total_promises": total_user,
        })

    return {
        "total_promises": total_promises,
        "promises_kept": promises_kept,
        "promises_broken": promises_broken,
        "promises_pending": promises_pending,
        "avg_days_late": avg_days_late,
        "worst_offenders": worst_offenders,
    }
