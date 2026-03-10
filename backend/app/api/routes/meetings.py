"""Meeting routes."""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    MeetingDetailResponse,
    MeetingDataResponse,
    MeetingFlagDetailResponse,
)
from app.auth import get_current_user, verify_store_access, get_user_store_ids
from app.database import get_db
from app.models.meeting import Meeting
from app.models.flag import Flag, FlagCategory, FlagSeverity, FlagStatus
from app.models.inventory import NewVehicleInventory, UsedVehicleInventory, ServiceLoaner, FloorplanReconciliation
from app.models.parts import PartsInventory, PartsAnalysis
from app.models.financial import Receivable, FIChargeback, ContractInTransit, Prepaid, PolicyAdjustment
from app.models.operations import OpenRepairOrder, WarrantyClaim, MissingTitle, SlowToAccounting
from app.models.user import User, UserRole
from app.services.meeting_service import get_meeting_detail, get_meeting_flags

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
