"""Meeting routes."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import MeetingResponse, MeetingDataResponse
from app.database import get_db
from app.models.meeting import Meeting
from app.models.inventory import NewVehicleInventory, UsedVehicleInventory, ServiceLoaner, FloorplanReconciliation
from app.models.parts import PartsInventory, PartsAnalysis
from app.models.financial import Receivable, FIChargeback, ContractInTransit, Prepaid, PolicyAdjustment
from app.models.operations import OpenRepairOrder, WarrantyClaim, MissingTitle, SlowToAccounting

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


@router.get("/meetings/{meeting_id}", response_model=MeetingResponse)
async def get_meeting(
    meeting_id: str, db: AsyncSession = Depends(get_db)
) -> MeetingResponse:
    """Get full meeting details."""
    try:
        meeting_uuid = uuid.UUID(meeting_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid meeting_id format")

    result = await db.execute(select(Meeting).where(Meeting.id == meeting_uuid))
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail=f"Meeting {meeting_id} not found")

    return MeetingResponse(
        id=meeting.id,
        store_id=meeting.store_id,
        meeting_date=meeting.meeting_date,
        status=meeting.status.value,
        packet_url=meeting.packet_url,
        flagged_items_url=meeting.flagged_items_url,
        packet_generated_at=meeting.packet_generated_at,
        notes=meeting.notes,
        created_at=meeting.created_at,
    )


@router.get("/meetings/{meeting_id}/data/{category}", response_model=MeetingDataResponse)
async def get_meeting_data(
    meeting_id: str,
    category: str,
    db: AsyncSession = Depends(get_db),
) -> MeetingDataResponse:
    """
    Get parsed data for a specific category.
    Categories: inventory, parts, financial, operations.
    """
    if category not in _CATEGORY_MODELS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid category: {category}. Must be one of: {', '.join(_CATEGORY_MODELS.keys())}",
        )

    try:
        meeting_uuid = uuid.UUID(meeting_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid meeting_id format")

    # Verify meeting exists
    meeting_result = await db.execute(select(Meeting).where(Meeting.id == meeting_uuid))
    if not meeting_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Meeting {meeting_id} not found")

    data = {}
    for key, model in _CATEGORY_MODELS[category].items():
        result = await db.execute(
            select(model).where(model.meeting_id == meeting_uuid)
        )
        records = list(result.scalars().all())
        data[key] = [_serialize_record(r) for r in records]

    return MeetingDataResponse(
        meeting_id=meeting_id,
        category=category,
        data=data,
    )
