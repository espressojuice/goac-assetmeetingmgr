"""Processing service — orchestrates PDF extraction, parsing, database insertion, flagging, and PDF generation."""

import logging
import os
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.flag import FlagSeverity
from app.models.meeting import Meeting, MeetingStatus
from app.models.store import Store
from app.models.inventory import (
    FloorplanReconciliation,
    NewVehicleInventory,
    ReconciliationType,
    ServiceLoaner,
    UsedVehicleInventory,
)
from app.models.parts import (
    PartsAnalysis,
    PartsCategory,
    PartsInventory,
)
from app.models.financial import (
    ContractInTransit,
    FIChargeback,
    PolicyAdjustment,
    Prepaid,
    Receivable,
    ReceivableType,
)
from app.models.operations import (
    MissingTitle,
    OpenRepairOrder,
    SlowToAccounting,
    WarrantyClaim,
)
from app.flagging.engine import FlaggingEngine
from app.services.flag_service import FlagService
from app.generators.packet_generator import StandardizedPacketGenerator
from app.generators.flagged_items_report import FlaggedItemsReportGenerator
from app.parsers.pdf_extractor import PDFExtractor
from app.parsers.router import ParserRouter
from app.services.email_service import EmailService

logger = logging.getLogger(__name__)

# Maps parser result keys to SQLAlchemy model classes
_MODEL_MAP = {
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

# Fields that need enum conversion
_ENUM_FIELDS = {
    "reconciliation_type": ReconciliationType,
    "category": PartsCategory,
    "receivable_type": ReceivableType,
}


class ProcessingService:
    """Orchestrates the full PDF processing pipeline."""

    def __init__(self):
        self.extractor = PDFExtractor()
        self.router = ParserRouter()

    async def process_upload(
        self,
        file_path: str,
        store_id: str,
        meeting_id: str,
        db: AsyncSession,
        auto_assign: bool = True,
    ) -> dict:
        """
        Full processing pipeline:
        1. Extract pages from PDF
        2. Route to parsers
        3. Save parsed records to database
        4. Return summary of what was parsed
        """
        store_uuid = uuid.UUID(store_id) if isinstance(store_id, str) else store_id
        meeting_uuid = (
            uuid.UUID(meeting_id) if isinstance(meeting_id, str) else meeting_id
        )

        # Extract
        pages = self.extractor.extract(file_path)
        logger.info(f"Extracted {len(pages)} pages from {file_path}")

        # Parse
        parsed_data = self.router.route_and_parse(pages)
        unhandled_pages = parsed_data.pop("_unhandled_pages", [])

        # Save to database
        record_counts = {}
        for model_name, records in parsed_data.items():
            model_class = _MODEL_MAP.get(model_name)
            if not model_class:
                logger.warning(f"No model mapping for {model_name}, skipping")
                continue

            count = 0
            for record_data in records:
                # Inject store_id and meeting_id
                record_data["store_id"] = store_uuid
                record_data["meeting_id"] = meeting_uuid

                # Convert enum string values
                for field, enum_cls in _ENUM_FIELDS.items():
                    if field in record_data and isinstance(record_data[field], str):
                        record_data[field] = enum_cls(record_data[field])

                instance = model_class(**record_data)
                db.add(instance)
                count += 1

            record_counts[model_name] = count

        await db.flush()
        logger.info(f"Saved records: {record_counts}")

        # Load per-store flag rule overrides
        from app.models.store_flag_override import StoreFlagOverride
        override_result = await db.execute(
            select(StoreFlagOverride).where(StoreFlagOverride.store_id == store_uuid)
        )
        store_overrides = {o.rule_name: o for o in override_result.scalars().all()}

        # Run flagging engine
        engine = FlaggingEngine()
        flags = await engine.evaluate_meeting(
            str(meeting_uuid), str(store_uuid), db,
            store_overrides=store_overrides,
        )
        for flag in flags:
            db.add(flag)

        await db.flush()

        # Auto-assign and detect recurring flags
        assignment_result = None
        recurring_count = 0
        if auto_assign:
            try:
                flag_svc = FlagService()
                assignment_result = await flag_svc.auto_assign_flags(str(meeting_uuid), db)
                recurring_count = await flag_svc.detect_recurring_flags(str(meeting_uuid), db)
            except Exception:
                logger.exception("Failed to auto-assign flags or detect recurring")

        # Generate packet PDF
        packet_path = None
        flagged_items_path = None
        try:
            packet_gen = StandardizedPacketGenerator()
            packet_bytes = await packet_gen.generate(str(meeting_uuid), db)
            packet_dir = os.path.join(settings.UPLOAD_DIR, str(store_uuid), str(meeting_uuid))
            os.makedirs(packet_dir, exist_ok=True)
            packet_path = os.path.join(packet_dir, "packet.pdf")
            with open(packet_path, "wb") as f:
                f.write(packet_bytes)
            logger.info(f"Generated packet PDF: {packet_path}")
        except Exception:
            logger.exception("Failed to generate packet PDF")

        # Generate flagged items report
        try:
            flags_gen = FlaggedItemsReportGenerator()
            flags_bytes = await flags_gen.generate(str(meeting_uuid), db)
            flags_dir = os.path.join(settings.UPLOAD_DIR, str(store_uuid), str(meeting_uuid))
            os.makedirs(flags_dir, exist_ok=True)
            flagged_items_path = os.path.join(flags_dir, "flagged_items.pdf")
            with open(flagged_items_path, "wb") as f:
                f.write(flags_bytes)
            logger.info(f"Generated flagged items PDF: {flagged_items_path}")
        except Exception:
            logger.exception("Failed to generate flagged items PDF")

        # Update meeting record
        meeting_result = await db.execute(
            select(Meeting).where(Meeting.id == meeting_uuid)
        )
        meeting = meeting_result.scalar_one_or_none()
        if meeting:
            if packet_path:
                meeting.packet_url = packet_path
            if flagged_items_path:
                meeting.flagged_items_url = flagged_items_path
            meeting.packet_generated_at = datetime.now(ZoneInfo("US/Central"))
            meeting.status = MeetingStatus.COMPLETED

        await db.commit()

        red_count = sum(1 for f in flags if f.severity == FlagSeverity.RED)
        yellow_count = sum(1 for f in flags if f.severity == FlagSeverity.YELLOW)

        # Notify store users that packet is ready
        try:
            from app.models.user import User
            email_svc = EmailService()
            store_result = await db.execute(
                select(Store).where(Store.id == store_uuid)
            )
            store_obj = store_result.scalar_one_or_none()
            if store_obj and store_obj.gm_email:
                user_result = await db.execute(
                    select(User).where(User.email == store_obj.gm_email)
                )
                gm_user = user_result.scalar_one_or_none()
                if gm_user and meeting:
                    await email_svc.send_meeting_packet_ready(
                        [gm_user], meeting, store_obj,
                        red_count=red_count, yellow_count=yellow_count,
                    )
        except Exception:
            logger.warning("Failed to send packet ready notification", exc_info=True)

        result_dict = {
            "pages_extracted": len(pages),
            "records_parsed": record_counts,
            "unhandled_pages": unhandled_pages,
            "flags_generated": {
                "yellow": yellow_count,
                "red": red_count,
                "total": len(flags),
            },
            "packet_path": packet_path,
            "flagged_items_path": flagged_items_path,
        }
        if assignment_result:
            result_dict["auto_assign"] = assignment_result
            result_dict["recurring_flags"] = recurring_count

        return result_dict

    async def process_upload_from_bytes(
        self,
        file_bytes: bytes,
        store_id: str,
        meeting_id: str,
        db: AsyncSession,
    ) -> dict:
        """Process an uploaded file from bytes instead of a file path."""
        store_uuid = uuid.UUID(store_id) if isinstance(store_id, str) else store_id
        meeting_uuid = (
            uuid.UUID(meeting_id) if isinstance(meeting_id, str) else meeting_id
        )

        pages = self.extractor.extract_from_bytes(file_bytes)
        parsed_data = self.router.route_and_parse(pages)
        unhandled_pages = parsed_data.pop("_unhandled_pages", [])

        record_counts = {}
        for model_name, records in parsed_data.items():
            model_class = _MODEL_MAP.get(model_name)
            if not model_class:
                continue

            count = 0
            for record_data in records:
                record_data["store_id"] = store_uuid
                record_data["meeting_id"] = meeting_uuid

                for field, enum_cls in _ENUM_FIELDS.items():
                    if field in record_data and isinstance(record_data[field], str):
                        record_data[field] = enum_cls(record_data[field])

                instance = model_class(**record_data)
                db.add(instance)
                count += 1

            record_counts[model_name] = count

        await db.flush()

        # Load per-store flag rule overrides
        from app.models.store_flag_override import StoreFlagOverride
        override_result2 = await db.execute(
            select(StoreFlagOverride).where(StoreFlagOverride.store_id == store_uuid)
        )
        store_overrides2 = {o.rule_name: o for o in override_result2.scalars().all()}

        # Run flagging engine
        engine = FlaggingEngine()
        flags = await engine.evaluate_meeting(
            str(meeting_uuid), str(store_uuid), db,
            store_overrides=store_overrides2,
        )
        for flag in flags:
            db.add(flag)

        await db.flush()

        # Generate packet PDF
        packet_path = None
        flagged_items_path = None
        try:
            packet_gen = StandardizedPacketGenerator()
            packet_bytes = await packet_gen.generate(str(meeting_uuid), db)
            packet_dir = os.path.join(settings.UPLOAD_DIR, str(store_uuid), str(meeting_uuid))
            os.makedirs(packet_dir, exist_ok=True)
            packet_path = os.path.join(packet_dir, "packet.pdf")
            with open(packet_path, "wb") as f:
                f.write(packet_bytes)
        except Exception:
            logger.exception("Failed to generate packet PDF")

        # Generate flagged items report
        try:
            flags_gen = FlaggedItemsReportGenerator()
            flags_bytes = await flags_gen.generate(str(meeting_uuid), db)
            flags_dir = os.path.join(settings.UPLOAD_DIR, str(store_uuid), str(meeting_uuid))
            os.makedirs(flags_dir, exist_ok=True)
            flagged_items_path = os.path.join(flags_dir, "flagged_items.pdf")
            with open(flagged_items_path, "wb") as f:
                f.write(flags_bytes)
        except Exception:
            logger.exception("Failed to generate flagged items PDF")

        # Update meeting record
        meeting_result = await db.execute(
            select(Meeting).where(Meeting.id == meeting_uuid)
        )
        meeting = meeting_result.scalar_one_or_none()
        if meeting:
            if packet_path:
                meeting.packet_url = packet_path
            if flagged_items_path:
                meeting.flagged_items_url = flagged_items_path
            meeting.packet_generated_at = datetime.now(ZoneInfo("US/Central"))
            meeting.status = MeetingStatus.COMPLETED

        await db.commit()

        return {
            "pages_extracted": len(pages),
            "records_parsed": record_counts,
            "unhandled_pages": unhandled_pages,
            "flags_generated": {
                "yellow": sum(1 for f in flags if f.severity == FlagSeverity.YELLOW),
                "red": sum(1 for f in flags if f.severity == FlagSeverity.RED),
                "total": len(flags),
            },
            "packet_path": packet_path,
            "flagged_items_path": flagged_items_path,
        }
