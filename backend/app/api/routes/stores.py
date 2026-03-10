"""Store management routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    StoreResponse,
    StoreCreateRequest,
    StoreDetailResponse,
    MeetingBriefResponse,
    RichStoreDetailResponse,
    FlagTrendsResponse,
)
from app.auth import (
    get_current_user,
    require_corporate,
    verify_store_access,
    get_user_store_ids,
)
from app.database import get_db
from app.models.meeting import Meeting
from app.models.store import Store
from app.models.user import User, UserRole
from app.services.store_service import get_store_detail, get_flag_trends

router = APIRouter()


def _parse_store_id(store_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(store_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid store_id format")


@router.get("/stores", response_model=list[StoreResponse])
async def list_stores(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[StoreResponse]:
    """List active stores visible to the current user."""
    query = select(Store).where(Store.is_active == True).order_by(Store.name)

    # Non-corporate users only see their assigned stores
    if current_user.role != UserRole.CORPORATE:
        store_ids = await get_user_store_ids(current_user, db)
        if not store_ids:
            return []
        query = query.where(Store.id.in_(store_ids))

    result = await db.execute(query)
    stores = list(result.scalars().all())

    return [
        StoreResponse(
            id=s.id,
            name=s.name,
            code=s.code,
            brand=s.brand,
            city=s.city,
            state=s.state,
            timezone=s.timezone,
            meeting_cadence=s.meeting_cadence,
            gm_name=s.gm_name,
            gm_email=s.gm_email,
            is_active=s.is_active,
            created_at=s.created_at,
        )
        for s in stores
    ]


@router.get("/stores/{store_id}", response_model=RichStoreDetailResponse)
async def get_store(
    store_id: str,
    current_user: User = Depends(verify_store_access),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get rich store details with stats, meetings, and users."""
    store_uuid = _parse_store_id(store_id)
    detail = await get_store_detail(store_uuid, db)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Store {store_id} not found")
    return detail


@router.get("/stores/{store_id}/flag-trends", response_model=FlagTrendsResponse)
async def get_store_flag_trends(
    store_id: str,
    current_user: User = Depends(verify_store_access),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get flag trend data over the last 6 meetings for charts."""
    store_uuid = _parse_store_id(store_id)
    trends = await get_flag_trends(store_uuid, db)
    if trends is None:
        raise HTTPException(status_code=404, detail=f"Store {store_id} not found")
    return trends


@router.post("/stores", response_model=StoreResponse, status_code=201)
async def create_store(
    body: StoreCreateRequest,
    current_user: User = Depends(require_corporate),
    db: AsyncSession = Depends(get_db),
) -> StoreResponse:
    """Create a new store. Corporate only."""
    # Check for duplicate code
    existing = await db.execute(select(Store).where(Store.code == body.code))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Store with code '{body.code}' already exists")

    store = Store(
        name=body.name,
        code=body.code,
        city=body.city,
        state=body.state,
        brand=body.brand,
        meeting_cadence=body.meeting_cadence,
        gm_name=body.gm_name,
        gm_email=body.gm_email,
    )
    db.add(store)
    await db.commit()
    await db.refresh(store)

    return StoreResponse(
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
    )


@router.get("/stores/{store_id}/meetings", response_model=list[MeetingBriefResponse])
async def get_store_meetings(
    store_id: str,
    limit: int = 10,
    current_user: User = Depends(verify_store_access),
    db: AsyncSession = Depends(get_db),
) -> list[MeetingBriefResponse]:
    """Get recent meetings for a store, ordered by date descending."""
    store_uuid = _parse_store_id(store_id)

    # Verify store exists
    store_result = await db.execute(select(Store).where(Store.id == store_uuid))
    if not store_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Store {store_id} not found")

    result = await db.execute(
        select(Meeting)
        .where(Meeting.store_id == store_uuid)
        .order_by(Meeting.meeting_date.desc())
        .limit(limit)
    )
    meetings = list(result.scalars().all())

    return [
        MeetingBriefResponse(
            id=m.id,
            meeting_date=m.meeting_date,
            status=m.status.value,
            packet_url=m.packet_url,
            flagged_items_url=m.flagged_items_url,
            created_at=m.created_at,
        )
        for m in meetings
    ]
