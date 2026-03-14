"""Packet retrieval routes."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    MeetingSummaryResponse,
    MeetingResponse,
    StoreResponse,
    FlagResponse,
    FlagStatsResponse,
    CondensedPacketResponse,
    CondensedSummaryResponse,
    CondensedSectionResponse,
    CondensedFlagItem,
    CondensedAttendanceResponse,
)
from app.auth import get_current_user
from app.database import get_db
from app.models.flag import Flag, FlagCategory, FlagSeverity, FlagStatus
from app.models.meeting import Meeting
from app.models.store import Store
from app.models.user import User, UserRole
from app.models.inventory import NewVehicleInventory, UsedVehicleInventory, ServiceLoaner, FloorplanReconciliation
from app.models.parts import PartsInventory, PartsAnalysis
from app.models.financial import Receivable, FIChargeback, ContractInTransit, Prepaid, PolicyAdjustment
from app.models.operations import OpenRepairOrder, WarrantyClaim, MissingTitle, SlowToAccounting
from app.models.accountability import FlagAssignment, MeetingAttendance
from app.auth import require_corporate_or_gm, get_user_store_ids

router = APIRouter()


async def _get_meeting_with_access(
    meeting_id: str, current_user: User, db: AsyncSession
) -> Meeting:
    """Fetch meeting and verify store access."""
    try:
        meeting_uuid = uuid.UUID(meeting_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid meeting_id format")

    result = await db.execute(select(Meeting).where(Meeting.id == meeting_uuid))
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail=f"Meeting {meeting_id} not found")

    if current_user.role != UserRole.CORPORATE:
        from app.auth import _user_has_store_access
        if not await _user_has_store_access(current_user.id, meeting.store_id, db):
            raise HTTPException(status_code=403, detail="You do not have access to this meeting's store")

    return meeting


@router.get("/packets/{meeting_id}")
async def get_packet(
    meeting_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the generated packet PDF for a meeting."""
    meeting = await _get_meeting_with_access(meeting_id, current_user, db)
    if not meeting.packet_url:
        raise HTTPException(status_code=404, detail="Packet not yet generated")
    return FileResponse(meeting.packet_url, media_type="application/pdf", filename="packet.pdf")


@router.get("/packets/{meeting_id}/flagged-items")
async def get_flagged_items(
    meeting_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the flagged items report PDF for a meeting."""
    meeting = await _get_meeting_with_access(meeting_id, current_user, db)
    if not meeting.flagged_items_url:
        raise HTTPException(status_code=404, detail="Flagged items report not yet generated")
    return FileResponse(
        meeting.flagged_items_url, media_type="application/pdf", filename="flagged_items.pdf"
    )


@router.get("/packets/{meeting_id}/summary", response_model=MeetingSummaryResponse)
async def get_meeting_summary(
    meeting_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MeetingSummaryResponse:
    """
    Return JSON summary of a meeting's parsed data and flags.
    Used by the frontend to render the web view.
    """
    meeting = await _get_meeting_with_access(meeting_id, current_user, db)

    # Get store
    store_result = await db.execute(select(Store).where(Store.id == meeting.store_id))
    store = store_result.scalar_one()

    # Count records per category
    meeting_uuid = meeting.id
    record_counts = {}

    model_map = {
        "NewVehicleInventory": NewVehicleInventory,
        "UsedVehicleInventory": UsedVehicleInventory,
        "ServiceLoaner": ServiceLoaner,
        "FloorplanReconciliation": FloorplanReconciliation,
        "PartsInventory": PartsInventory,
        "PartsAnalysis": PartsAnalysis,
        "Receivable": Receivable,
        "FIChargeback": FIChargeback,
        "ContractInTransit": ContractInTransit,
        "Prepaid": Prepaid,
        "PolicyAdjustment": PolicyAdjustment,
        "OpenRepairOrder": OpenRepairOrder,
        "WarrantyClaim": WarrantyClaim,
        "MissingTitle": MissingTitle,
        "SlowToAccounting": SlowToAccounting,
    }

    for name, model in model_map.items():
        count_result = await db.execute(
            select(func.count()).select_from(model).where(model.meeting_id == meeting_uuid)
        )
        count = count_result.scalar()
        if count > 0:
            record_counts[name] = count

    # Get flags
    flags_result = await db.execute(
        select(Flag).where(Flag.meeting_id == meeting_uuid).order_by(Flag.created_at)
    )
    flags = list(flags_result.scalars().all())

    # Build flag stats
    yellow_count = sum(1 for f in flags if f.severity == FlagSeverity.YELLOW)
    red_count = sum(1 for f in flags if f.severity == FlagSeverity.RED)
    open_count = sum(1 for f in flags if f.status == FlagStatus.OPEN)
    responded_count = sum(1 for f in flags if f.status == FlagStatus.RESPONDED)

    by_category = {}
    for cat in FlagCategory:
        cat_count = sum(1 for f in flags if f.category == cat)
        if cat_count > 0:
            by_category[cat.value] = cat_count

    return MeetingSummaryResponse(
        meeting=MeetingResponse(
            id=meeting.id,
            store_id=meeting.store_id,
            meeting_date=meeting.meeting_date,
            status=meeting.status.value,
            packet_url=meeting.packet_url,
            flagged_items_url=meeting.flagged_items_url,
            packet_generated_at=meeting.packet_generated_at,
            notes=meeting.notes,
            created_at=meeting.created_at,
        ),
        store=StoreResponse(
            id=store.id,
            name=store.name,
            code=store.code,
            brand=store.brand,
            city=store.city,
            state=store.state,
            timezone=store.timezone,
            meeting_cadence=store.meeting_cadence,
            gm_name=store.gm_name,
            gm_email=store.gm_email,
            is_active=store.is_active,
            created_at=store.created_at,
        ),
        record_counts=record_counts,
        flags=[
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
        ],
        flag_stats=FlagStatsResponse(
            total=len(flags),
            yellow=yellow_count,
            red=red_count,
            open=open_count,
            responded=responded_count,
            by_category=by_category,
        ),
    )


# Category titles and key metric builders
_CATEGORY_TITLES = {
    FlagCategory.INVENTORY: "Vehicle Inventory",
    FlagCategory.PARTS: "Parts & Service",
    FlagCategory.FINANCIAL: "Financial",
    FlagCategory.OPERATIONS: "Operations",
}


async def _build_key_metrics(category: FlagCategory, meeting_id, db: AsyncSession) -> dict:
    """Build key summary metrics for a category based on parsed data."""
    mid = meeting_id
    metrics = {}

    if category == FlagCategory.INVENTORY:
        new_count = (await db.execute(
            select(func.count()).select_from(NewVehicleInventory).where(NewVehicleInventory.meeting_id == mid)
        )).scalar() or 0
        used_count = (await db.execute(
            select(func.count()).select_from(UsedVehicleInventory).where(UsedVehicleInventory.meeting_id == mid)
        )).scalar() or 0
        used_over_60 = (await db.execute(
            select(func.count()).select_from(UsedVehicleInventory).where(
                UsedVehicleInventory.meeting_id == mid,
                UsedVehicleInventory.days_in_stock > 60,
            )
        )).scalar() or 0
        loaner_count = (await db.execute(
            select(func.count()).select_from(ServiceLoaner).where(ServiceLoaner.meeting_id == mid)
        )).scalar() or 0
        metrics = {
            "new_vehicle_count": new_count,
            "used_vehicle_count": used_count,
            "used_over_60_days": used_over_60,
            "service_loaner_count": loaner_count,
        }

    elif category == FlagCategory.PARTS:
        parts_count = (await db.execute(
            select(func.count()).select_from(PartsAnalysis).where(PartsAnalysis.meeting_id == mid)
        )).scalar() or 0
        metrics = {"parts_analysis_records": parts_count}

    elif category == FlagCategory.FINANCIAL:
        recv_count = (await db.execute(
            select(func.count()).select_from(Receivable).where(Receivable.meeting_id == mid)
        )).scalar() or 0
        cit_count = (await db.execute(
            select(func.count()).select_from(ContractInTransit).where(ContractInTransit.meeting_id == mid)
        )).scalar() or 0
        chargeback_count = (await db.execute(
            select(func.count()).select_from(FIChargeback).where(FIChargeback.meeting_id == mid)
        )).scalar() or 0
        metrics = {
            "receivables_count": recv_count,
            "contracts_in_transit_count": cit_count,
            "chargebacks_count": chargeback_count,
        }

    elif category == FlagCategory.OPERATIONS:
        ro_count = (await db.execute(
            select(func.count()).select_from(OpenRepairOrder).where(OpenRepairOrder.meeting_id == mid)
        )).scalar() or 0
        warranty_count = (await db.execute(
            select(func.count()).select_from(WarrantyClaim).where(WarrantyClaim.meeting_id == mid)
        )).scalar() or 0
        missing_title_count = (await db.execute(
            select(func.count()).select_from(MissingTitle).where(MissingTitle.meeting_id == mid)
        )).scalar() or 0
        metrics = {
            "open_ro_count": ro_count,
            "warranty_claims_count": warranty_count,
            "missing_titles_count": missing_title_count,
        }

    return metrics


@router.get("/packets/{meeting_id}/condensed", response_model=CondensedPacketResponse)
async def get_condensed_packet(
    meeting_id: str,
    current_user: User = Depends(require_corporate_or_gm),
    db: AsyncSession = Depends(get_db),
) -> CondensedPacketResponse:
    """Condensed packet JSON — only flagged/important items, not 30 pages of raw data."""
    meeting = await _get_meeting_with_access(meeting_id, current_user, db)

    # Get store
    store_result = await db.execute(select(Store).where(Store.id == meeting.store_id))
    store = store_result.scalar_one()

    # Get all flags for this meeting
    flags_result = await db.execute(
        select(Flag).where(Flag.meeting_id == meeting.id).order_by(Flag.category, Flag.severity.desc())
    )
    flags = list(flags_result.scalars().all())

    # Summary counts
    total_flags = len(flags)
    red = sum(1 for f in flags if f.severity == FlagSeverity.RED)
    yellow = sum(1 for f in flags if f.severity == FlagSeverity.YELLOW)
    verified = sum(1 for f in flags if f.status == FlagStatus.VERIFIED)
    unresolved = sum(1 for f in flags if f.status == FlagStatus.UNRESOLVED)
    open_count = sum(1 for f in flags if f.status == FlagStatus.OPEN)

    # Group flags by category — only include sections with flags
    sections = []
    for category in FlagCategory:
        cat_flags = [f for f in flags if f.category == category]
        if not cat_flags:
            continue

        # Get assigned_to names for each flag
        flag_items = []
        for f in cat_flags:
            # Get latest assignment
            assign_result = await db.execute(
                select(FlagAssignment)
                .where(FlagAssignment.flag_id == f.id)
                .order_by(FlagAssignment.created_at.desc())
                .limit(1)
            )
            assignment = assign_result.scalar_one_or_none()
            assigned_to_name = None
            if assignment:
                user_result = await db.execute(
                    select(User.name).where(User.id == assignment.assigned_to_id)
                )
                assigned_to_name = user_result.scalar_one_or_none()

            flag_items.append(CondensedFlagItem(
                id=str(f.id),
                severity=f.severity.value,
                status=f.status.value,
                field_name=f.field_name,
                field_value=f.field_value,
                message=f.message,
                assigned_to=assigned_to_name,
                response_text=f.response_text,
            ))

        key_metrics = await _build_key_metrics(category, meeting.id, db)

        sections.append(CondensedSectionResponse(
            category=category.value,
            title=_CATEGORY_TITLES.get(category, category.value),
            flag_count=len(cat_flags),
            flags=flag_items,
            key_metrics=key_metrics,
        ))

    # Attendance summary
    att_result = await db.execute(
        select(MeetingAttendance, User)
        .join(User, MeetingAttendance.user_id == User.id)
        .where(MeetingAttendance.meeting_id == meeting.id)
    )
    att_rows = att_result.all()
    present = sum(1 for a, u in att_rows if a.checked_in)
    expected = len(att_rows)
    absent_names = [u.name for a, u in att_rows if not a.checked_in]

    return CondensedPacketResponse(
        meeting_date=str(meeting.meeting_date),
        store_name=store.name,
        summary=CondensedSummaryResponse(
            total_flags=total_flags,
            red=red,
            yellow=yellow,
            verified=verified,
            unresolved=unresolved,
            open=open_count,
        ),
        sections=sections,
        attendance=CondensedAttendanceResponse(
            present=present,
            expected=expected,
            absent=absent_names,
        ),
    )
