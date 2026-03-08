"""Processing service — orchestrates PDF extraction, parsing, database insertion, and flagging."""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.flag import FlagSeverity
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
from app.parsers.pdf_extractor import PDFExtractor
from app.parsers.router import ParserRouter

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

        # Run flagging engine
        engine = FlaggingEngine()
        flags = await engine.evaluate_meeting(str(meeting_uuid), str(store_uuid), db)
        for flag in flags:
            db.add(flag)

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
        }

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

        # Run flagging engine
        engine = FlaggingEngine()
        flags = await engine.evaluate_meeting(str(meeting_uuid), str(store_uuid), db)
        for flag in flags:
            db.add(flag)

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
        }
