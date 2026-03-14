"""Meeting routes."""

import datetime
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    MeetingDetailResponse,
    MeetingDataResponse,
    MeetingFlagDetailResponse,
    MeetingCloseRequest,
    MeetingCloseResponse,
)
from app.auth import get_current_user, require_corporate_or_gm, verify_store_access, get_user_store_ids
from app.database import get_db
from app.models.meeting import Meeting, MeetingStatus
from app.models.flag import Flag, FlagCategory, FlagSeverity, FlagStatus
from app.models.inventory import NewVehicleInventory, UsedVehicleInventory, ServiceLoaner, FloorplanReconciliation
from app.models.parts import PartsInventory, PartsAnalysis
from app.models.financial import Receivable, FIChargeback, ContractInTransit, Prepaid, PolicyAdjustment
from app.models.operations import OpenRepairOrder, WarrantyClaim, MissingTitle, SlowToAccounting
from app.models.user import User, UserRole, UserStore
from app.models.accountability import MeetingAttendance
from app.services.meeting_service import get_meeting_detail, get_meeting_flags
from app.services.email_service import EmailService

logger = logging.getLogger(__name__)

router = APIRouter()

# Maps category names to their models and relationship keys
_CATEGORY_MODELS = {
    "inventory": {
        "new_vehicles": NewVehicleInventory,
        "used_vehicles": UsedVehicleInventory,
        "service_loaners": ServiceLoaner,
        "floorplan_reconciliation": FloorplanReconciliation,
    },
    "parts": {
        "parts_inventory": PartsInventory,
        "parts_analysis": PartsAnalysis,
    },
    "financial": {
        "receivables": Receivable,
        "fi_chargebacks": FIChargeback,
        "contracts_in_transit": ContractInTransit,
        "prepaids": Prepaid,
        "policy_adjustments": PolicyAdjustment,
    },
    "operations": {
        "open_repair_orders": OpenRepairOrder,
        "warranty_claims": WarrantyClaim,
        "missing_titles": MissingTitle,
        "slow_to_accounting": SlowToAccounting,
    },
}

# Maps category+field_name to the model's identifying field for flag association
_FLAG_CATEGORY_MAP = {
    "inventory": ["new_vehicles", "used_vehicles", "service_loaners", "floorplan_reconciliation"],
    "parts": ["parts_inventory", "parts_analysis"],
    "financial": ["receivables", "fi_chargebacks", "contracts_in_transit", "prepaids", "policy_adjustments"],
    "operations": ["open_repair_orders", "warranty_claims", "missing_titles", "slow_to_accounting"],
}


def _serialize_record(record) -> dict:
    """Convert a SQLAlchemy model instance to a dict, handling special types."""
    from datetime import date, datetime
    from decimal import Decimal
    import enum

    result = {}
    for column in record.__table__.columns:
        val = getattr(record, column.name)
        if isinstance(val, uuid.UUID):
            val = str(val)
        elif isinstance(val, (date, datetime)):
            val = val.isoformat()
        elif isinstance(val, Decimal):
            val = float(val)
        elif isinstance(val, enum.Enum):
            val = val.value
        result[column.name] = val
    return result


async def _validate_meeting(meeting_id: str, db: AsyncSession) -> uuid.UUID:
    """Validate and return meeting UUID, raising HTTPException on errors."""
    try:
        meeting_uuid = uuid.UUID(meeting_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid meeting_id format")

    result = await db.execute(select(Meeting).where(Meeting.id == meeting_uuid))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Meeting {meeting_id} not found")
    return meeting_uuid


async def _get_meeting_with_access_check(
    meeting_id: str, current_user: User, db: AsyncSession
) -> Meeting:
    """Fetch meeting and verify user has access to its store."""
    try:
        meeting_uuid = uuid.UUID(meeting_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid meeting_id format")

    result = await db.execute(select(Meeting).where(Meeting.id == meeting_uuid))
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail=f"Meeting {meeting_id} not found")

    # Corporate can access any meeting
    if current_user.role != UserRole.CORPORATE:
        from app.auth import _user_has_store_access
        if not await _user_has_store_access(current_user.id, meeting.store_id, db):
            raise HTTPException(status_code=403, detail="You do not have access to this meeting's store")

    return meeting


@router.get("/meetings/{meeting_id}", response_model=MeetingDetailResponse)
async def get_meeting(
    meeting_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MeetingDetailResponse:
    """Get comprehensive meeting details with executive summary and flag stats."""
    meeting = await _get_meeting_with_access_check(meeting_id, current_user, db)

    detail = await get_meeting_detail(meeting.id, db)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Meeting {meeting_id} not found")

    return detail


@router.get("/meetings/{meeting_id}/data/{category}", response_model=MeetingDataResponse)
async def get_meeting_data(
    meeting_id: str,
    category: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MeetingDataResponse:
    """Get parsed data for a specific category with associated flags.

    Categories: inventory, parts, financial, operations.
    """
    if category not in _CATEGORY_MODELS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid category: {category}. Must be one of: {', '.join(_CATEGORY_MODELS.keys())}",
        )

    meeting = await _get_meeting_with_access_check(meeting_id, current_user, db)
    meeting_uuid = meeting.id

    # Load flags for this meeting+category to attach to records
    flag_result = await db.execute(
        select(Flag)
        .where(Flag.meeting_id == meeting_uuid)
        .where(Flag.category == FlagCategory(category))
    )
    flags = list(flag_result.scalars().all())

    # Index flags by field_value for matching to records
    flags_by_value: dict[str, dict] = {}
    for f in flags:
        if f.field_value:
            key = f.field_value.strip()
            flags_by_value[key] = {
                "severity": f.severity.value,
                "status": f.status.value,
                "message": f.message,
                "field_name": f.field_name,
            }

    data = {}
    for key, model in _CATEGORY_MODELS[category].items():
        result = await db.execute(
            select(model).where(model.meeting_id == meeting_uuid)
        )
        records = list(result.scalars().all())
        serialized = []
        for r in records:
            rec = _serialize_record(r)
            # Try to attach flag info based on common identifying fields
            rec["flag"] = None
            for id_field in ["stock_number", "ro_number", "deal_number", "claim_number",
                             "account_number", "gl_account", "schedule_number"]:
                if id_field in rec and rec[id_field]:
                    # Check if any flag references this record's value
                    for fv, flag_info in flags_by_value.items():
                        if str(rec[id_field]) in fv or fv in str(rec.get(flag_info.get("field_name", ""), "")):
                            rec["flag"] = flag_info
                            break
                if rec["flag"]:
                    break
            # Also check by field_value matching days_in_stock, days_open, etc.
            if not rec["flag"]:
                for fv, flag_info in flags_by_value.items():
                    fname = flag_info.get("field_name", "")
                    if fname in rec and str(rec.get(fname)) == fv:
                        rec["flag"] = flag_info
                        break
            serialized.append(rec)
        data[key] = serialized

    return MeetingDataResponse(
        meeting_id=meeting_id,
        category=category,
        data=data,
    )


@router.get("/meetings/{meeting_id}/flags", response_model=list[MeetingFlagDetailResponse])
async def get_meeting_flags_endpoint(
    meeting_id: str,
    severity: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    sort_by: str = "severity",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MeetingFlagDetailResponse]:
    """Get all flags for a meeting with full detail including assignment and response info."""
    meeting = await _get_meeting_with_access_check(meeting_id, current_user, db)

    # Validate filter values
    if severity:
        try:
            FlagSeverity(severity)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid severity: {severity}")
    if category:
        try:
            FlagCategory(category)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid category: {category}")
    if status:
        try:
            FlagStatus(status)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid status: {status}")
    if sort_by not in ("severity", "category", "created_at", "status"):
        raise HTTPException(status_code=422, detail=f"Invalid sort_by: {sort_by}")

    flags = await get_meeting_flags(
        meeting.id, db,
        severity=severity, category=category, status=status, sort_by=sort_by,
    )
    return flags


@router.post("/meetings/{meeting_id}/close", response_model=MeetingCloseResponse)
async def close_meeting(
    meeting_id: str,
    body: MeetingCloseRequest,
    current_user: User = Depends(require_corporate_or_gm),
    db: AsyncSession = Depends(get_db),
) -> MeetingCloseResponse:
    """Close a meeting: set status to CLOSED, auto-unresolve open flags, build recap."""
    meeting = await _get_meeting_with_access_check(meeting_id, current_user, db)

    # Cannot close an already-closed meeting
    if meeting.status == MeetingStatus.CLOSED:
        raise HTTPException(status_code=409, detail="Meeting is already closed")

    # --- 1. Close the meeting ---
    now = datetime.datetime.now(datetime.timezone.utc)
    meeting.status = MeetingStatus.CLOSED
    meeting.closed_at = now
    meeting.closed_by_id = current_user.id
    meeting.close_notes = body.close_notes

    # --- 2. Auto-unresolve OPEN flags ---
    flag_result = await db.execute(
        select(Flag).where(Flag.meeting_id == meeting.id)
    )
    flags = list(flag_result.scalars().all())

    open_count = 0
    responded_count = 0
    verified_count = 0
    unresolved_count = 0
    auto_unresolved = 0

    for flag in flags:
        if flag.status == FlagStatus.OPEN:
            flag.status = FlagStatus.UNRESOLVED
            auto_unresolved += 1
            unresolved_count += 1
        elif flag.status == FlagStatus.RESPONDED:
            responded_count += 1
        elif flag.status == FlagStatus.VERIFIED:
            verified_count += 1
        elif flag.status == FlagStatus.UNRESOLVED:
            unresolved_count += 1
        elif flag.status == FlagStatus.ESCALATED:
            # Escalated flags also get auto-unresolved on close
            flag.status = FlagStatus.UNRESOLVED
            auto_unresolved += 1
            unresolved_count += 1

    # --- 3. Attendance summary ---
    attendance_result = await db.execute(
        select(MeetingAttendance).where(MeetingAttendance.meeting_id == meeting.id)
    )
    attendance_records = list(attendance_result.scalars().all())

    # If no attendance records exist, count users associated with the store
    if attendance_records:
        total_expected = len(attendance_records)
        total_present = sum(1 for a in attendance_records if a.checked_in)
    else:
        user_count_result = await db.execute(
            select(func.count(UserStore.id)).where(UserStore.store_id == meeting.store_id)
        )
        total_expected = user_count_result.scalar() or 0
        total_present = 0
    total_absent = total_expected - total_present

    await db.commit()

    # --- 4. Send recap email (fire-and-forget) ---
    try:
        await _send_meeting_recap(
            meeting, current_user, flags, attendance_records, total_expected, total_present, db
        )
    except Exception:
        logger.exception("Failed to send meeting recap email for meeting %s", meeting_id)

    return MeetingCloseResponse(
        meeting_id=str(meeting.id),
        status="closed",
        closed_at=now.isoformat(),
        closed_by_name=current_user.name,
        close_notes=body.close_notes,
        flags_summary={
            "total": len(flags),
            "open": open_count,
            "responded": responded_count,
            "verified": verified_count,
            "unresolved": unresolved_count,
            "auto_unresolved": auto_unresolved,
        },
        attendance_summary={
            "total_expected": total_expected,
            "total_present": total_present,
            "total_absent": total_absent,
        },
    )


async def _send_meeting_recap(
    meeting: Meeting,
    closed_by: User,
    flags: list[Flag],
    attendance_records: list[MeetingAttendance],
    total_expected: int,
    total_present: int,
    db: AsyncSession,
) -> None:
    """Build and send the meeting recap email to corporate users."""
    from app.services.email_service import _wrap_html, _severity_badge

    # Fetch store
    from app.models.store import Store
    store_result = await db.execute(select(Store).where(Store.id == meeting.store_id))
    store = store_result.scalar_one()

    # Fetch corporate users
    corporate_result = await db.execute(
        select(User).where(User.role == UserRole.CORPORATE, User.is_active == True)
    )
    corporate_users = list(corporate_result.scalars().all())
    if not corporate_users:
        logger.info("No corporate users to send recap email to")
        return

    # Build attendance section
    attendance_html = ""
    if attendance_records:
        # Load user names for attendance
        user_ids = [a.user_id for a in attendance_records]
        users_result = await db.execute(select(User).where(User.id.in_(user_ids)))
        users_by_id = {u.id: u for u in users_result.scalars().all()}

        attendance_rows = ""
        for a in attendance_records:
            user = users_by_id.get(a.user_id)
            name = user.name if user else "Unknown"
            status_icon = "&#9989;" if a.checked_in else "&#10060;"  # check / cross
            attendance_rows += f'<tr><td style="padding:6px 10px;border-bottom:1px solid #eee;">{name}</td><td style="padding:6px 10px;border-bottom:1px solid #eee;text-align:center;">{status_icon}</td></tr>'

        attendance_html = f"""
<h3>Attendance ({total_present}/{total_expected})</h3>
<table style="width:100%;border-collapse:collapse;margin:15px 0;">
<tr style="background:#003366;color:#fff;"><th style="padding:8px;text-align:left;">Name</th><th style="padding:8px;text-align:center;">Present</th></tr>
{attendance_rows}
</table>"""
    else:
        attendance_html = f"<h3>Attendance</h3><p>No attendance records ({total_expected} users expected)</p>"

    # Build flags section grouped by status
    verified_flags = [f for f in flags if f.status == FlagStatus.VERIFIED]
    responded_flags = [f for f in flags if f.status == FlagStatus.RESPONDED]
    unresolved_flags = [f for f in flags if f.status == FlagStatus.UNRESOLVED]

    def _flag_rows(flag_list: list[Flag]) -> str:
        if not flag_list:
            return "<p><em>None</em></p>"
        rows = ""
        for f in flag_list:
            rows += (
                f'<tr><td style="padding:6px 10px;border-bottom:1px solid #eee;">{_severity_badge(f.severity.value)}</td>'
                f'<td style="padding:6px 10px;border-bottom:1px solid #eee;">{f.category.value.upper()}</td>'
                f'<td style="padding:6px 10px;border-bottom:1px solid #eee;">{f.message[:80]}</td></tr>'
            )
        return f"""<table style="width:100%;border-collapse:collapse;margin:10px 0;">
<tr style="background:#f0f0f0;"><th style="padding:6px 10px;text-align:left;">Severity</th><th style="padding:6px 10px;text-align:left;">Category</th><th style="padding:6px 10px;text-align:left;">Issue</th></tr>
{rows}</table>"""

    flags_html = f"""
<h3>Flags Summary ({len(flags)} total)</h3>
<p><strong>Verified:</strong> {len(verified_flags)} &bull; <strong>Responded:</strong> {len(responded_flags)} &bull; <strong>Unresolved:</strong> {len(unresolved_flags)}</p>
"""
    if unresolved_flags:
        flags_html += f"<h4 style='color:#dc2626;'>Unresolved ({len(unresolved_flags)})</h4>{_flag_rows(unresolved_flags)}"
    if responded_flags:
        flags_html += f"<h4>Responded ({len(responded_flags)})</h4>{_flag_rows(responded_flags)}"
    if verified_flags:
        flags_html += f"<h4 style='color:#16a34a;'>Verified ({len(verified_flags)})</h4>{_flag_rows(verified_flags)}"

    close_notes_html = ""
    if meeting.close_notes:
        close_notes_html = f'<h3>Close Notes</h3><p style="background:#f8f8f8;padding:12px;border-left:3px solid #003366;">{meeting.close_notes}</p>'

    subject = f"Meeting Closed — {store.name} {meeting.meeting_date}"
    body = f"""
<h2>Meeting Recap: {store.name}</h2>
<table class="detail-table">
<tr><td>Store</td><td>{store.name}</td></tr>
<tr><td>Meeting Date</td><td>{meeting.meeting_date}</td></tr>
<tr><td>Closed By</td><td>{closed_by.name}</td></tr>
<tr><td>Closed At</td><td>{meeting.closed_at.strftime('%Y-%m-%d %I:%M %p')} CT</td></tr>
</table>
{close_notes_html}
{attendance_html}
{flags_html}
"""
    html = _wrap_html(body)

    email_service = EmailService()
    for user in corporate_users:
        await email_service.send_email(user.email, subject, html)
