"""Upload routes — PDF upload (validate-only) and approve (process)."""

from __future__ import annotations

import logging
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, Form
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    ApproveResponse,
    ValidationUploadResponse,
)
from app.auth import (
    _user_has_store_access,
    get_current_user,
    require_corporate_or_gm,
    verify_store_access,
)
from app.config import settings
from app.database import get_db
from app.models.meeting import Meeting, MeetingStatus
from app.models.store import Store
from app.models.user import User, UserRole
from app.services.packet_validator import PacketValidator
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
            status=MeetingStatus.PENDING,
        )
        db.add(meeting)
        await db.flush()

    return meeting


async def _check_store_access(current_user: User, store_id: str, db: AsyncSession) -> None:
    """Verify non-corporate users have access to the store."""
    if current_user.role != UserRole.CORPORATE:
        try:
            store_uuid = uuid.UUID(store_id)
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid store_id format")
        if not await _user_has_store_access(current_user.id, store_uuid, db):
            raise HTTPException(status_code=403, detail="You do not have access to this store")


@router.post("/upload", response_model=ValidationUploadResponse)
async def upload_report(
    file: UploadFile,
    store_id: str = Form(...),
    meeting_date: str = Form(...),
    current_user: User = Depends(require_corporate_or_gm),
    db: AsyncSession = Depends(get_db),
) -> ValidationUploadResponse:
    """
    Upload an R&R report PDF for validation review.
    Saves the file and runs packet validation only — does NOT process.
    Call POST /upload/{meeting_id}/approve to trigger processing after review.
    """
    await _check_store_access(current_user, store_id, db)
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

    # Run validation only (no processing)
    try:
        validator = PacketValidator()
        validation = validator.validate_detailed(file_path)
    except Exception as e:
        logger.exception("Packet validation failed")
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")

    # Keep meeting in PENDING status until approved
    meeting.status = MeetingStatus.PENDING
    await db.commit()

    return ValidationUploadResponse(
        meeting_id=str(meeting.id),
        store_id=str(store.id),
        total_pages=validation.total_pages,
        validation=validation,
    )


@router.post("/upload/bulk", response_model=ValidationUploadResponse)
async def upload_bulk_reports(
    files: list[UploadFile],
    store_id: str = Form(...),
    meeting_date: str = Form(...),
    current_user: User = Depends(require_corporate_or_gm),
    db: AsyncSession = Depends(get_db),
) -> ValidationUploadResponse:
    """
    Upload multiple R&R report PDFs for the same meeting.
    Saves files and runs validation only — does NOT process.
    Call POST /upload/{meeting_id}/approve to trigger processing after review.
    """
    await _check_store_access(current_user, store_id, db)

    if not files:
        raise HTTPException(status_code=422, detail="At least one file is required")

    for file in files:
        await _validate_pdf(file)

    store = await _get_store(store_id, db)
    meeting = await _get_or_create_meeting(store.id, meeting_date, db)

    upload_dir = os.path.join(settings.UPLOAD_DIR, str(store.id), str(meeting.id))
    os.makedirs(upload_dir, exist_ok=True)

    last_file_path = None
    for file in files:
        file_path = os.path.join(upload_dir, file.filename)
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
        last_file_path = file_path

    # Validate the last uploaded file (primary packet)
    try:
        validator = PacketValidator()
        validation = validator.validate_detailed(last_file_path)
    except Exception as e:
        logger.exception("Packet validation failed for bulk upload")
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")

    meeting.status = MeetingStatus.PENDING
    await db.commit()

    return ValidationUploadResponse(
        meeting_id=str(meeting.id),
        store_id=str(store.id),
        total_pages=validation.total_pages,
        validation=validation,
    )


@router.post("/upload/{meeting_id}/approve", response_model=ApproveResponse)
async def approve_upload(
    meeting_id: str,
    current_user: User = Depends(require_corporate_or_gm),
    db: AsyncSession = Depends(get_db),
) -> ApproveResponse:
    """
    Approve a previously uploaded packet and trigger the full processing pipeline.
    Runs parsing, flagging, PDF generation, and email notification.
    """
    try:
        meeting_uuid = uuid.UUID(meeting_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid meeting_id format")

    result = await db.execute(select(Meeting).where(Meeting.id == meeting_uuid))
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail=f"Meeting {meeting_id} not found")

    # Check store access
    await _check_store_access(current_user, str(meeting.store_id), db)

    # Find uploaded PDFs in the meeting directory
    upload_dir = os.path.join(settings.UPLOAD_DIR, str(meeting.store_id), str(meeting.id))
    if not os.path.isdir(upload_dir):
        raise HTTPException(status_code=404, detail="No uploaded files found for this meeting")

    pdf_files = sorted(
        [f for f in os.listdir(upload_dir) if f.lower().endswith(".pdf")
         and f not in ("packet.pdf", "flagged_items.pdf")]
    )
    if not pdf_files:
        raise HTTPException(status_code=404, detail="No uploaded PDF files found")

    # Process all uploaded PDFs
    meeting.status = MeetingStatus.PROCESSING
    await db.flush()

    service = ProcessingService()
    total_pages = 0
    merged_records: dict[str, int] = {}
    merged_flags = {"yellow": 0, "red": 0, "total": 0}
    last_result = None

    for pdf_name in pdf_files:
        file_path = os.path.join(upload_dir, pdf_name)
        try:
            proc_result = service.process_upload(
                file_path, str(meeting.store_id), str(meeting.id), db
            )
            if hasattr(proc_result, "__await__"):
                proc_result = await proc_result

            total_pages += proc_result["pages_extracted"]
            for model_name, count in proc_result["records_parsed"].items():
                merged_records[model_name] = merged_records.get(model_name, 0) + count
            for key in ("yellow", "red", "total"):
                merged_flags[key] += proc_result["flags_generated"][key]
            last_result = proc_result

        except Exception as e:
            logger.exception(f"Processing failed for {pdf_name}")
            meeting.status = MeetingStatus.ERROR
            meeting.notes = f"Failed on {pdf_name}: {str(e)}"
            await db.commit()
            raise HTTPException(
                status_code=500,
                detail=f"Processing failed for {pdf_name}: {str(e)}",
            )

    return ApproveResponse(
        meeting_id=str(meeting.id),
        pages_extracted=total_pages,
        records_parsed=merged_records,
        flags_generated=merged_flags,
        packet_url=last_result.get("packet_path") if last_result else None,
        flagged_items_url=last_result.get("flagged_items_path") if last_result else None,
    )
