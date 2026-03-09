"""Service layer for meeting detail and flag queries."""

from __future__ import annotations

import datetime as _dt
import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, func, case, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.meeting import Meeting, MeetingStatus
from app.models.store import Store
from app.models.flag import Flag, FlagCategory, FlagSeverity, FlagStatus
from app.models.inventory import (
    NewVehicleInventory, UsedVehicleInventory, ServiceLoaner, FloorplanReconciliation,
)
from app.models.parts import PartsInventory, PartsAnalysis
from app.models.financial import Receivable, ContractInTransit
from app.models.operations import OpenRepairOrder, MissingTitle
from app.models.accountability import FlagAssignment
from app.models.user import User


def _dec(val) -> float:
    """Convert Decimal/None to float."""
    if val is None:
        return 0.0
    return float(val)


async def get_meeting_detail(meeting_id: uuid.UUID, db: AsyncSession) -> Optional[dict]:
    """Assemble comprehensive meeting detail with executive summary and flag stats.

    Returns None if the meeting doesn't exist.
    """
    # Fetch meeting + store
    result = await db.execute(
        select(Meeting, Store)
        .join(Store, Meeting.store_id == Store.id)
        .where(Meeting.id == meeting_id)
    )
    row = result.first()
    if not row:
        return None

    meeting, store = row[0], row[1]

    # --- Executive Summary (computed from parsed data) ---

    # New vehicles
    nv_result = await db.execute(
        select(
            func.count(NewVehicleInventory.id).label("count"),
            func.coalesce(func.sum(NewVehicleInventory.floorplan_balance), 0).label("floorplan_total"),
        ).where(NewVehicleInventory.meeting_id == meeting_id)
    )
    nv = nv_result.one()

    # Used vehicles
    uv_result = await db.execute(
        select(
            func.count(UsedVehicleInventory.id).label("count"),
            func.count(case((UsedVehicleInventory.days_in_stock > 60, 1))).label("over_60"),
            func.count(case((UsedVehicleInventory.days_in_stock > 90, 1))).label("over_90"),
        ).where(UsedVehicleInventory.meeting_id == meeting_id)
    )
    uv = uv_result.one()

    # Used over 90 exposure (sum of book_value for >90 days)
    uv_exposure_result = await db.execute(
        select(
            func.coalesce(func.sum(UsedVehicleInventory.book_value), 0),
        ).where(
            and_(
                UsedVehicleInventory.meeting_id == meeting_id,
                UsedVehicleInventory.days_in_stock > 90,
            )
        )
    )
    uv_over_90_exposure = _dec(uv_exposure_result.scalar())

    # Service loaners
    sl_result = await db.execute(
        select(
            func.count(ServiceLoaner.id).label("count"),
            func.coalesce(func.sum(ServiceLoaner.negative_equity), 0).label("neg_equity_total"),
        ).where(ServiceLoaner.meeting_id == meeting_id)
    )
    sl = sl_result.one()

    # Parts turnover (most recent analysis period)
    pt_result = await db.execute(
        select(PartsAnalysis.true_turnover)
        .where(PartsAnalysis.meeting_id == meeting_id)
        .order_by(PartsAnalysis.period_year.desc(), PartsAnalysis.period_month.desc())
        .limit(1)
    )
    parts_turnover = pt_result.scalar()

    # Open ROs
    ro_result = await db.execute(
        select(func.count(OpenRepairOrder.id))
        .where(OpenRepairOrder.meeting_id == meeting_id)
    )
    open_ro_count = ro_result.scalar() or 0

    # Receivables over 30
    recv_result = await db.execute(
        select(
            func.coalesce(func.sum(Receivable.over_30), 0),
        ).where(Receivable.meeting_id == meeting_id)
    )
    receivables_over_30 = _dec(recv_result.scalar())

    # Missing titles
    mt_result = await db.execute(
        select(func.count(MissingTitle.id))
        .where(MissingTitle.meeting_id == meeting_id)
    )
    missing_titles_count = mt_result.scalar() or 0

    # Contracts in transit
    cit_result = await db.execute(
        select(func.count(ContractInTransit.id))
        .where(ContractInTransit.meeting_id == meeting_id)
    )
    contracts_in_transit_count = cit_result.scalar() or 0

    # Floorplan variance
    fp_result = await db.execute(
        select(func.coalesce(func.sum(FloorplanReconciliation.variance), 0))
        .where(FloorplanReconciliation.meeting_id == meeting_id)
    )
    floorplan_variance = _dec(fp_result.scalar())

    executive_summary = {
        "new_vehicle_count": nv.count or 0,
        "new_vehicle_floorplan_total": _dec(nv.floorplan_total),
        "used_vehicle_count": uv.count or 0,
        "used_over_60_days": uv.over_60 or 0,
        "used_over_90_days": uv.over_90 or 0,
        "used_over_90_exposure": uv_over_90_exposure,
        "service_loaner_count": sl.count or 0,
        "service_loaner_neg_equity_total": _dec(sl.neg_equity_total),
        "parts_turnover": _dec(parts_turnover) if parts_turnover is not None else None,
        "open_ro_count": open_ro_count,
        "receivables_over_30_total": receivables_over_30,
        "missing_titles_count": missing_titles_count,
        "contracts_in_transit_count": contracts_in_transit_count,
        "floorplan_variance": floorplan_variance,
    }

    # --- Flags Summary ---
    flags_result = await db.execute(
        select(
            func.count(Flag.id).label("total"),
            func.count(case((Flag.severity == FlagSeverity.RED, 1))).label("red"),
            func.count(case((Flag.severity == FlagSeverity.YELLOW, 1))).label("yellow"),
            func.count(case((Flag.status == FlagStatus.OPEN, 1))).label("open"),
            func.count(case((Flag.status == FlagStatus.RESPONDED, 1))).label("responded"),
        ).where(Flag.meeting_id == meeting_id)
    )
    fs = flags_result.one()

    # Overdue = open (until deadline tracking is refined)
    overdue = fs.open or 0

    # By category with severity breakdown
    cat_result = await db.execute(
        select(
            Flag.category,
            Flag.severity,
            func.count(Flag.id).label("cnt"),
        )
        .where(Flag.meeting_id == meeting_id)
        .group_by(Flag.category, Flag.severity)
    )
    by_category: dict = {}
    for row in cat_result.all():
        cat_key = row.category.value if hasattr(row.category, "value") else str(row.category)
        if cat_key not in by_category:
            by_category[cat_key] = {"red": 0, "yellow": 0}
        sev_key = row.severity.value if hasattr(row.severity, "value") else str(row.severity)
        by_category[cat_key][sev_key] = row.cnt or 0

    flags_summary = {
        "total": fs.total or 0,
        "red": fs.red or 0,
        "yellow": fs.yellow or 0,
        "open": fs.open or 0,
        "responded": fs.responded or 0,
        "overdue": overdue,
        "by_category": by_category,
    }

    return {
        "meeting": {
            "id": str(meeting.id),
            "store_id": str(meeting.store_id),
            "store_name": store.name,
            "meeting_date": str(meeting.meeting_date),
            "status": meeting.status.value,
            "packet_generated_at": meeting.packet_generated_at.isoformat() if meeting.packet_generated_at else None,
            "packet_url": meeting.packet_url,
            "flagged_items_url": meeting.flagged_items_url,
            "notes": meeting.notes,
        },
        "executive_summary": executive_summary,
        "flags_summary": flags_summary,
    }


async def get_meeting_flags(
    meeting_id: uuid.UUID,
    db: AsyncSession,
    severity: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    sort_by: str = "severity",
) -> list[dict]:
    """Return all flags for a meeting with assignment and response details."""
    query = select(Flag).where(Flag.meeting_id == meeting_id)

    if severity:
        query = query.where(Flag.severity == FlagSeverity(severity))
    if category:
        query = query.where(Flag.category == FlagCategory(category))
    if status:
        query = query.where(Flag.status == FlagStatus(status))

    # Sort
    sort_map = {
        "severity": [Flag.severity, Flag.created_at],
        "category": [Flag.category, Flag.created_at],
        "created_at": [Flag.created_at],
        "status": [Flag.status, Flag.created_at],
    }
    for col in sort_map.get(sort_by, [Flag.severity, Flag.created_at]):
        query = query.order_by(col)

    result = await db.execute(query)
    flags = list(result.scalars().all())

    if not flags:
        return []

    # Batch-load assignments for these flags
    flag_ids = [f.id for f in flags]
    assign_result = await db.execute(
        select(FlagAssignment, User)
        .join(User, FlagAssignment.assigned_to_id == User.id)
        .where(FlagAssignment.flag_id.in_(flag_ids))
    )
    assignments_by_flag: dict = {}
    for row in assign_result.all():
        assignment, user = row[0], row[1]
        assignments_by_flag[assignment.flag_id] = {
            "id": str(user.id),
            "name": user.name,
            "email": user.email,
            "deadline": str(assignment.deadline) if assignment.deadline else None,
            "assignment_status": assignment.status.value,
        }

    output = []
    for f in flags:
        assignment_info = assignments_by_flag.get(f.id)
        response = None
        if f.response_text:
            response = {
                "text": f.response_text,
                "submitted_at": f.responded_at.isoformat() if f.responded_at else None,
                "responder": f.responded_by,
            }

        output.append({
            "id": str(f.id),
            "category": f.category.value,
            "severity": f.severity.value,
            "message": f.message,
            "field_name": f.field_name,
            "field_value": f.field_value,
            "threshold": f.threshold,
            "status": f.status.value,
            "assigned_to": assignment_info,
            "response": response,
            "deadline": assignment_info["deadline"] if assignment_info else None,
            "is_overdue": (
                f.status == FlagStatus.OPEN
                and assignment_info is not None
                and assignment_info.get("deadline") is not None
                and assignment_info["deadline"] < str(_dt.date.today())
            ),
            "escalation_level": f.escalation_level,
            "created_at": f.created_at.isoformat() if f.created_at else None,
        })

    return output
