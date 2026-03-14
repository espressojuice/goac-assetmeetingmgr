"""CSV export endpoints — corporate only."""

from __future__ import annotations

import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_corporate
from app.database import get_db
from app.models.user import User
from app.services import export_service

router = APIRouter()


def _csv_response(csv_data: str, filename: str) -> StreamingResponse:
    """Wrap CSV string in a StreamingResponse with proper headers."""
    return StreamingResponse(
        iter([csv_data]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _filename(prefix: str) -> str:
    """Generate a timestamped CSV filename."""
    return f"{prefix}_{datetime.date.today().isoformat()}.csv"


@router.get("/exports/meetings")
async def export_meetings(
    store_id: Optional[str] = Query(None),
    date_from: Optional[datetime.date] = Query(None),
    date_to: Optional[datetime.date] = Query(None),
    current_user: User = Depends(require_corporate),
    db: AsyncSession = Depends(get_db),
):
    """Export meetings CSV with flag and attendance summaries."""
    csv_data = await export_service.export_meetings_csv(
        db, store_id=store_id, date_from=date_from, date_to=date_to,
    )
    return _csv_response(csv_data, _filename("meetings_export"))


@router.get("/exports/flags")
async def export_flags(
    store_id: Optional[str] = Query(None),
    date_from: Optional[datetime.date] = Query(None),
    date_to: Optional[datetime.date] = Query(None),
    status: Optional[str] = Query(None),
    current_user: User = Depends(require_corporate),
    db: AsyncSession = Depends(get_db),
):
    """Export flags CSV with priority scores."""
    csv_data = await export_service.export_flags_csv(
        db, store_id=store_id, date_from=date_from, date_to=date_to, status=status,
    )
    return _csv_response(csv_data, _filename("flags_export"))


@router.get("/exports/attendance")
async def export_attendance(
    store_id: Optional[str] = Query(None),
    date_from: Optional[datetime.date] = Query(None),
    date_to: Optional[datetime.date] = Query(None),
    current_user: User = Depends(require_corporate),
    db: AsyncSession = Depends(get_db),
):
    """Export attendance CSV."""
    csv_data = await export_service.export_attendance_csv(
        db, store_id=store_id, date_from=date_from, date_to=date_to,
    )
    return _csv_response(csv_data, _filename("attendance_export"))


@router.get("/exports/promise-tracking")
async def export_promise_tracking(
    store_id: Optional[str] = Query(None),
    date_from: Optional[datetime.date] = Query(None),
    date_to: Optional[datetime.date] = Query(None),
    current_user: User = Depends(require_corporate),
    db: AsyncSession = Depends(get_db),
):
    """Export promise date tracking CSV."""
    csv_data = await export_service.export_promise_tracking_csv(
        db, store_id=store_id, date_from=date_from, date_to=date_to,
    )
    return _csv_response(csv_data, _filename("promise_tracking_export"))
