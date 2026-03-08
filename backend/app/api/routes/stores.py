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
)
from app.database import get_db
from app.models.meeting import Meeting
from app.models.store import Store

router = APIRouter()


@router.get("/stores", response_model=list[StoreResponse])
async def list_stores(db: AsyncSession = Depends(get_db)) -> list[StoreResponse]:
    """List all active stores."""
    result = await db.execute(
        select(Store).where(Store.is_active == True).order_by(Store.name)
    )
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


@router.get("/stores/{store_id}", response_model=StoreDetailResponse)
async def get_store(
    store_id: str, db: AsyncSession = Depends(get_db)
) -> StoreDetailResponse:
    """Get store details including recent meetings."""
    try:
        store_uuid = uuid.UUID(store_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid store_id format")

    result = await db.execute(select(Store).where(Store.id == store_uuid))
    store = result.scalar_one_or_none()
    if not store:
        raise HTTPException(status_code=404, detail=f"Store {store_id} not found")

    # Get recent meetings
    meetings_result = await db.execute(
        select(Meeting)
        .where(Meeting.store_id == store_uuid)
        .order_by(Meeting.meeting_date.desc())
        .limit(10)
    )
    meetings = list(meetings_result.scalars().all())

    return StoreDetailResponse(
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
        recent_meetings=[
            MeetingBriefResponse(
                id=m.id,
                meeting_date=m.meeting_date,
                status=m.status.value,
                packet_url=m.packet_url,
                flagged_items_url=m.flagged_items_url,
                created_at=m.created_at,
            )
            for m in meetings
        ],
    )


@router.post("/stores", response_model=StoreResponse, status_code=201)
async def create_store(
    body: StoreCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> StoreResponse:
    """Create a new store."""
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
    db: AsyncSession = Depends(get_db),
) -> list[MeetingBriefResponse]:
    """Get recent meetings for a store, ordered by date descending."""
    try:
        store_uuid = uuid.UUID(store_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid store_id format")

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
