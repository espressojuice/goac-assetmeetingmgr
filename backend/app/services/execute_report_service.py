"""Execute Report service — generate and send the condensed meeting summary PDF."""

from __future__ import annotations

import base64
import logging
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.generators.execute_report import ExecuteReportGenerator
from app.models.flag import Flag, FlagSeverity, FlagStatus
from app.models.meeting import Meeting
from app.models.store import Store
from app.models.user import User, UserRole, UserStore
from app.models.accountability import FlagAssignment, MeetingAttendance
from app.services.metrics_service import get_top_priority_items

logger = logging.getLogger(__name__)


async def generate_execute_report(
    meeting_id: UUID,
    db: AsyncSession,
    top_n: int = 10,
) -> bytes:
    """Generate the Execute Report PDF for a meeting.

    Returns PDF bytes.
    """
    data = await _load_report_data(meeting_id, db, top_n)
    generator = ExecuteReportGenerator()
    return generator.generate(data)


async def send_execute_report(
    meeting_id: UUID,
    db: AsyncSession,
    recipient_ids: Optional[list[UUID]] = None,
) -> int:
    """Generate and email the Execute Report.

    Returns the number of recipients sent to.
    """
    from app.services.email_service import EmailService, _wrap_html

    # Generate PDF
    pdf_bytes = await generate_execute_report(meeting_id, db)

    # Load meeting + store for email subject/body
    meeting_result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    meeting = meeting_result.scalar_one()
    store_result = await db.execute(select(Store).where(Store.id == meeting.store_id))
    store = store_result.scalar_one()

    # Determine recipients
    if recipient_ids:
        users_result = await db.execute(
            select(User).where(User.id.in_(recipient_ids), User.is_active == True)
        )
    else:
        # Default: all corporate users
        users_result = await db.execute(
            select(User).where(User.role == UserRole.CORPORATE, User.is_active == True)
        )
    recipients = list(users_result.scalars().all())

    if not recipients:
        logger.info("No recipients for execute report (meeting %s)", meeting_id)
        return 0

    # Count flags for email body
    flag_result = await db.execute(
        select(func.count(Flag.id)).where(Flag.meeting_id == meeting_id)
    )
    total_flags = flag_result.scalar() or 0

    verified_result = await db.execute(
        select(func.count(Flag.id)).where(
            Flag.meeting_id == meeting_id,
            Flag.status == FlagStatus.VERIFIED,
        )
    )
    verified = verified_result.scalar() or 0

    unresolved_result = await db.execute(
        select(func.count(Flag.id)).where(
            Flag.meeting_id == meeting_id,
            Flag.status == FlagStatus.UNRESOLVED,
        )
    )
    unresolved = unresolved_result.scalar() or 0

    subject = f"Execute Report — {store.name} — {meeting.meeting_date}"
    body = f"""
<h2>Execute Report: {store.name}</h2>
<p>Attached is the execute report for the <strong>{store.name}</strong> asset meeting on <strong>{meeting.meeting_date}</strong>.</p>
<p><strong>{total_flags}</strong> flags reviewed, <strong>{verified}</strong> verified, <strong>{unresolved}</strong> unresolved.</p>
"""
    html = _wrap_html(body)

    # Send with PDF attachment
    email_service = EmailService()
    sent_count = 0
    filename = f"Execute_Report_{store.code}_{meeting.meeting_date}.pdf"

    for user in recipients:
        success = await email_service.send_email_with_attachment(
            to_email=user.email,
            subject=subject,
            html_content=html,
            attachment_bytes=pdf_bytes,
            attachment_filename=filename,
            attachment_type="application/pdf",
        )
        if success:
            sent_count += 1

    return sent_count


async def _load_report_data(
    meeting_id: UUID,
    db: AsyncSession,
    top_n: int = 10,
) -> dict:
    """Load all data needed for the execute report."""
    # Meeting + Store
    meeting_result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    meeting = meeting_result.scalar_one()

    store_result = await db.execute(select(Store).where(Store.id == meeting.store_id))
    store = store_result.scalar_one()

    # Flags
    flag_result = await db.execute(select(Flag).where(Flag.meeting_id == meeting_id))
    flags = list(flag_result.scalars().all())

    red_flags = [f for f in flags if f.severity == FlagSeverity.RED]
    yellow_flags = [f for f in flags if f.severity == FlagSeverity.YELLOW]
    verified_flags = [f for f in flags if f.status == FlagStatus.VERIFIED]
    unresolved_flags = [f for f in flags if f.status == FlagStatus.UNRESOLVED]
    responded_flags = [f for f in flags if f.status == FlagStatus.RESPONDED]
    open_flags = [f for f in flags if f.status == FlagStatus.OPEN]

    total = len(flags)
    verified_count = len(verified_flags)
    resolution_rate = round(verified_count / total * 100, 1) if total > 0 else 0.0

    # Attendance
    att_result = await db.execute(
        select(MeetingAttendance).where(MeetingAttendance.meeting_id == meeting_id)
    )
    attendance_records = list(att_result.scalars().all())

    present_names = []
    absent_names = []
    if attendance_records:
        user_ids = [a.user_id for a in attendance_records]
        users_result = await db.execute(select(User).where(User.id.in_(user_ids)))
        users_by_id = {u.id: u for u in users_result.scalars().all()}

        for a in attendance_records:
            user = users_by_id.get(a.user_id)
            name = user.name if user else "Unknown"
            if a.checked_in:
                present_names.append(name)
            else:
                absent_names.append(name)

    # Top priorities — reuse MetricsService logic
    top_priorities = await get_top_priority_items(
        db, store_id=store.id, limit=top_n,
    )

    # Build flag detail dicts with assignment/response info
    flags_unresolved = await _enrich_flags(unresolved_flags, db)
    flags_responded = await _enrich_flags(responded_flags, db, include_response=True)
    flags_verified = await _enrich_flags(verified_flags, db, include_verification=True)

    # Auto-unresolved: flags that were OPEN when meeting was closed (now UNRESOLVED)
    # Identify by: UNRESOLVED status + no response_text (never answered)
    auto_unresolved = [
        f for f in unresolved_flags
        if not f.response_text and not f.responded_at
    ]
    flags_auto_unresolved = await _enrich_flags(auto_unresolved, db)

    # Remove auto-unresolved from the main unresolved list to avoid double-counting
    auto_ids = {f.id for f in auto_unresolved}
    manual_unresolved = [f for f in unresolved_flags if f.id not in auto_ids]
    flags_unresolved = await _enrich_flags(manual_unresolved, db)

    # Manager accountability for this meeting
    manager_metrics = await _get_meeting_manager_metrics(flags, db)

    # Meeting status info
    closed_at_str = "N/A"
    closed_by_name = "N/A"
    if meeting.closed_at:
        closed_at_str = meeting.closed_at.strftime("%Y-%m-%d %I:%M %p CT")
    if meeting.closed_by_id:
        closer_result = await db.execute(select(User).where(User.id == meeting.closed_by_id))
        closer = closer_result.scalar_one_or_none()
        if closer:
            closed_by_name = closer.name

    return {
        "store_name": store.name,
        "meeting_date_str": meeting.meeting_date.strftime("%B %d, %Y"),
        "meeting_status": meeting.status.value,
        "closed_at_str": closed_at_str,
        "closed_by_name": closed_by_name,
        "attendance": {
            "present": len(present_names),
            "absent": len(absent_names),
            "present_names": present_names,
            "absent_names": absent_names,
        },
        "total_flags": total,
        "red_count": len(red_flags),
        "yellow_count": len(yellow_flags),
        "verified_count": verified_count,
        "unresolved_count": len(unresolved_flags),
        "open_count": len(open_flags),
        "resolution_rate": resolution_rate,
        "top_priorities": top_priorities,
        "flags_unresolved": flags_unresolved,
        "flags_responded": flags_responded,
        "flags_verified": flags_verified,
        "flags_auto_unresolved": flags_auto_unresolved,
        "manager_metrics": manager_metrics,
    }


async def _enrich_flags(
    flags: list[Flag],
    db: AsyncSession,
    include_response: bool = False,
    include_verification: bool = False,
) -> list[dict]:
    """Convert Flag objects to dicts with assignment/response detail."""
    enriched = []
    today = __import__("datetime").date.today()

    for flag in flags:
        # Get latest assignment
        assignment_result = await db.execute(
            select(FlagAssignment)
            .where(FlagAssignment.flag_id == flag.id)
            .order_by(FlagAssignment.created_at.desc())
            .limit(1)
        )
        assignment = assignment_result.scalar_one_or_none()

        assigned_to_name = None
        if assignment:
            user_result = await db.execute(
                select(User.name).where(User.id == assignment.assigned_to_id)
            )
            assigned_to_name = user_result.scalar_one_or_none()

        days = (today - flag.created_at.date()).days if flag.created_at else 0

        item = {
            "rule_name": flag.field_name,
            "description": flag.message,
            "severity": flag.severity.value,
            "status": flag.status.value,
            "assigned_to_name": assigned_to_name,
            "days_outstanding": days,
            "expected_resolution_date": str(flag.expected_resolution_date) if flag.expected_resolution_date else None,
            "escalation_level": flag.escalation_level,
        }

        if include_response:
            item["response_text"] = flag.response_text

        if include_verification:
            item["verification_notes"] = flag.verification_notes
            verified_by_name = None
            if flag.verified_by_id:
                vr = await db.execute(select(User.name).where(User.id == flag.verified_by_id))
                verified_by_name = vr.scalar_one_or_none()
            item["verified_by_name"] = verified_by_name

        enriched.append(item)

    return enriched


async def _get_meeting_manager_metrics(flags: list[Flag], db: AsyncSession) -> list[dict]:
    """Get per-manager resolution stats for flags in this meeting only."""
    # Get all assignments for these flags
    flag_ids = [f.id for f in flags]
    if not flag_ids:
        return []

    assignment_result = await db.execute(
        select(FlagAssignment).where(FlagAssignment.flag_id.in_(flag_ids))
    )
    assignments = list(assignment_result.scalars().all())

    # Group by assigned_to_id
    by_manager: dict[UUID, list] = {}
    for a in assignments:
        by_manager.setdefault(a.assigned_to_id, []).append(a)

    # Build flag lookup
    flag_by_id = {f.id: f for f in flags}

    metrics = []
    for manager_id, manager_assignments in by_manager.items():
        user_result = await db.execute(select(User).where(User.id == manager_id))
        user = user_result.scalar_one_or_none()
        if not user:
            continue

        total_assigned = len(manager_assignments)
        resolved = 0
        unresolved = 0
        for a in manager_assignments:
            flag = flag_by_id.get(a.flag_id)
            if flag:
                if flag.status == FlagStatus.VERIFIED:
                    resolved += 1
                elif flag.status == FlagStatus.UNRESOLVED:
                    unresolved += 1

        rate = round(resolved / total_assigned * 100, 1) if total_assigned > 0 else 0.0

        metrics.append({
            "name": user.name,
            "assigned": total_assigned,
            "resolved": resolved,
            "unresolved": unresolved,
            "resolution_rate": rate,
        })

    # Sort worst-first
    metrics.sort(key=lambda m: m["resolution_rate"])
    return metrics
