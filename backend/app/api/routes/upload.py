"""Upload routes — PDF upload and processing."""

from __future__ import annotations

import logging
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, Form
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import UploadResponse, BulkUploadResponse
from app.config import settings
from app.database import get_db
from app.models.meeting import Meeting, MeetingStatus
from app.models.store import Store
from app.services.processing_service import ProcessingService

logger = logging.getLogger(__name__)
router = APIRouter()


async def _validate_pdf(file: UploadFile) -> None:
    """Validate that an uploaded file is a PDF."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=422, detail="File must be a PDF (.pdf extension)")


async def _get_store(store_id: str, db: AsyncSession) -> Store:
    """Validate store exists and return it."""
    try:
        store_uuid = uuid.UUID(store_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid store_id format")

    result = await db.execute(select(Store).where(Store.id == store_uuid))
    store = result.scalar_one_or_none()
    if not store:
        raise HTTPException(status_code=404, detail=f"Store {store_id} not found")
    return store


async def _get_or_create_meeting(
    store_id: uuid.UUID, meeting_date: str, db: AsyncSession
) -> Meeting:
    """Get existing meeting or create new one for store+date combo."""
    from datetime import date as date_type

    try:
        parsed_date = date_type.fromisoformat(meeting_date)
    except ValueError:
        raise HTTPException(status_code=422, detail="meeting_date must be YYYY-MM-DD format")

    result = await db.execute(
        select(Meeting).where(
            Meeting.store_id == store_id,
            Meeting.meeting_date == parsed_date,
        )
    )
    meeting = result.scalar_one_or_none()

    if not meeting:
        meeting = Meeting(
            store_id=store_id,
            meeting_date=parsed_date,
            status=MeetingStatus.PROCESSING,
        )
        db.add(meeting)
        await db.flush()

    return meeting


@router.post("/upload", response_model=UploadResponse)
async def upload_report(
    file: UploadFile,
    store_id: str = Form(...),
    meeting_date: str = Form(...),
    db: AsyncSession = Depends(get_db),
) -> UploadResponse:
    """
    Upload an R&R report PDF for processing.

    1. Validate file is PDF
    2. Create or get Meeting record for this store + date
    3. Save uploaded file to disk
    4. Run ProcessingService.process_upload()
    5. Return processing summary
    """
    await _validate_pdf(file)
    store = await _get_store(store_id, db)
    meeting = await _get_or_create_meeting(store.id, meeting_date, db)

    # Save file to disk
    upload_dir = os.path.join(settings.UPLOAD_DIR, str(store.id), str(meeting.id))
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, file.filename)

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    # Process
    try:
        service = ProcessingService()
        result = service.process_upload(file_path, str(store.id), str(meeting.id), db)
        # Handle both sync and async
        if hasattr(result, "__await__"):
            result = await result

        return UploadResponse(
            meeting_id=str(meeting.id),
            pages_extracted=result["pages_extracted"],
            records_parsed=result["records_parsed"],
            flags_generated=result["flags_generated"],
            packet_url=result.get("packet_path"),
            flagged_items_url=result.get("flagged_items_path"),
        )
    except Exception as e:
        logger.exception("Processing failed")
        meeting.status = MeetingStatus.ERROR
        meeting.notes = str(e)
        await db.commit()
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


@router.post("/upload/bulk", response_model=BulkUploadResponse)
async def upload_bulk_reports(
    files: list[UploadFile],
    store_id: str = Form(...),
    meeting_date: str = Form(...),
    db: AsyncSession = Depends(get_db),
) -> BulkUploadResponse:
    """
    Upload multiple R&R report PDFs for the same meeting.
    Process each file and merge results.
    """
    if not files:
        raise HTTPException(status_code=422, detail="At least one file is required")

    for file in files:
        await _validate_pdf(file)

    store = await _get_store(store_id, db)
    meeting = await _get_or_create_meeting(store.id, meeting_date, db)

    upload_dir = os.path.join(settings.UPLOAD_DIR, str(store.id), str(meeting.id))
    os.makedirs(upload_dir, exist_ok=True)

    total_pages = 0
    merged_records: dict[str, int] = {}
    merged_flags = {"yellow": 0, "red": 0, "total": 0}
    last_result = None

    service = ProcessingService()

    for file in files:
        file_path = os.path.join(upload_dir, file.filename)
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        try:
            result = service.process_upload(
                file_path, str(store.id), str(meeting.id), db
            )
            if hasattr(result, "__await__"):
                result = await result

            total_pages += result["pages_extracted"]
            for model_name, count in result["records_parsed"].items():
                merged_records[model_name] = merged_records.get(model_name, 0) + count
            for key in ("yellow", "red", "total"):
                merged_flags[key] += result["flags_generated"][key]
            last_result = result

        except Exception as e:
            logger.exception(f"Processing failed for {file.filename}")
            meeting.status = MeetingStatus.ERROR
            meeting.notes = f"Failed on {file.filename}: {str(e)}"
            await db.commit()
            raise HTTPException(
                status_code=500,
                detail=f"Processing failed for {file.filename}: {str(e)}",
            )

    return BulkUploadResponse(
        meeting_id=str(meeting.id),
        files_processed=len(files),
        total_pages_extracted=total_pages,
        records_parsed=merged_records,
        flags_generated=merged_flags,
        packet_url=last_result.get("packet_path") if last_result else None,
        flagged_items_url=last_result.get("flagged_items_path") if last_result else None,
    )
