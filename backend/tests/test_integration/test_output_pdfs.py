"""Generate output PDFs from parsed Ashdown data using mock data objects.

Bypasses the async DB layer by creating mock record objects from parsed dicts
and calling section builder methods directly.
"""

import io
import os
import sys
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.parsers.pdf_extractor import PDFExtractor
from app.parsers.router import ParserRouter
from app.flagging.engine import FlaggingEngine
from app.flagging.rules import DEFAULT_RULES
from app.models.flag import FlagCategory, FlagSeverity

PDF_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "data", "samples", "ashdown_2026-02-11.pdf"
)
OUTPUT_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "data", "samples"
)

pytestmark = pytest.mark.skipif(
    not os.path.exists(PDF_PATH),
    reason="Ashdown sample PDF not found",
)


class _EnumLike:
    """Wraps a string to provide .value attribute like an enum."""

    def __init__(self, v):
        self.value = v

    def __str__(self):
        return str(self.value)

    def __repr__(self):
        return f"_EnumLike({self.value!r})"

    def __eq__(self, other):
        if isinstance(other, _EnumLike):
            return self.value == other.value
        return self.value == other or self.value == getattr(other, "value", None)

    def __hash__(self):
        return hash(self.value)


class MockObj:
    """Wraps a dict so attribute access works (for ReportLab section builders).

    Returns None for missing attributes instead of raising AttributeError,
    matching SQLAlchemy model behavior where nullable columns return None.
    String fields that represent enums are wrapped in _EnumLike so .value works.
    """

    _ENUM_FIELDS = {
        "reconciliation_type", "category", "severity", "status",
        "receivable_type", "chargeback_type",
    }

    def __init__(self, data: dict):
        for k, v in data.items():
            if k in self._ENUM_FIELDS and isinstance(v, str):
                setattr(self, k, _EnumLike(v))
            else:
                # Keep enums and other types as-is
                setattr(self, k, v)
        # Also ensure receivable records have 'receivable_type' as _EnumLike
        # The parser uses 'schedule_number' but generator expects 'receivable_type'
        if "schedule_number" in data and not hasattr(self, "receivable_type"):
            self.receivable_type = _EnumLike(f"schedule_{data['schedule_number']}")

    def __getattr__(self, name):
        # Return None for any attribute not explicitly set
        return None

    def __repr__(self):
        return f"MockObj({self.__dict__})"


def _to_mock_list(records: list[dict]) -> list[MockObj]:
    return [MockObj(r) for r in records]


def _generate_flags(parsed_results: dict) -> tuple[list[MockObj], list[MockObj]]:
    """Run the flagging engine on parsed data, return (red_flags, yellow_flags)."""
    engine = FlaggingEngine()
    red_flags = []
    yellow_flags = []

    for rule in engine.rules:
        if not rule.enabled:
            continue
        records = parsed_results.get(rule.model, [])
        for record_dict in records:
            mock = MockObj(record_dict)
            severity = engine._evaluate_record(mock, rule)
            if severity:
                value = getattr(mock, rule.field, None)
                threshold = rule.red_threshold if severity == FlagSeverity.RED else rule.yellow_threshold
                try:
                    context = {k: v for k, v in record_dict.items()}
                    message = rule.message_template.format(**context)
                except (KeyError, ValueError, TypeError):
                    message = f"{rule.name}: {rule.field}={value}"

                flag_obj = MockObj({
                    "category": rule.category,
                    "severity": severity,
                    "field_name": rule.field,
                    "field_value": str(value) if value is not None else None,
                    "threshold": str(threshold) if threshold is not None else None,
                    "message": message,
                })
                if severity == FlagSeverity.RED:
                    red_flags.append(flag_obj)
                else:
                    yellow_flags.append(flag_obj)

    return red_flags, yellow_flags


@pytest.fixture(scope="module")
def parsed_results():
    extractor = PDFExtractor(enable_ocr=True)
    pages = extractor.extract(PDF_PATH)
    router = ParserRouter()
    return router.route_and_parse(pages)


class TestPacketPDF:
    """Generate the standardized packet PDF."""

    def test_generate_packet_pdf(self, parsed_results):
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, PageBreak

        from app.generators.packet_generator import StandardizedPacketGenerator

        gen = StandardizedPacketGenerator()
        gen._store_name = "Ashdown Classic Chevrolet"
        gen._meeting_date_str = "February 11, 2026"
        gen._generated_str = "03/09/2026 12:00 PM CT"

        red_flags, yellow_flags = _generate_flags(parsed_results)

        # Build data dict matching what section builders expect
        data = {
            "store_name": "Ashdown Classic Chevrolet",
            "meeting_date": date(2026, 2, 11),
            "meeting_date_str": "February 11, 2026",
            "new_vehicles": _to_mock_list(parsed_results.get("NewVehicleInventory", [])),
            "used_vehicles": _to_mock_list(parsed_results.get("UsedVehicleInventory", [])),
            "service_loaners": _to_mock_list(parsed_results.get("ServiceLoaner", [])),
            "floorplan_recons": _to_mock_list(parsed_results.get("FloorplanReconciliation", [])),
            "parts_inventory": [],
            "parts_analyses": _to_mock_list(parsed_results.get("PartsAnalysis", [])),
            "receivables": _to_mock_list(parsed_results.get("Receivable", [])),
            "fi_chargebacks": _to_mock_list(parsed_results.get("FIChargeback", [])),
            "contracts": _to_mock_list(parsed_results.get("ContractInTransit", [])),
            "open_ros": _to_mock_list(parsed_results.get("OpenRepairOrder", [])),
            "missing_titles": _to_mock_list(parsed_results.get("MissingTitle", [])),
            "slow_deals": _to_mock_list(parsed_results.get("SlowToAccounting", [])),
            "flags": red_flags + yellow_flags,
            "red_flags": red_flags,
            "yellow_flags": yellow_flags,
        }

        # Build PDF elements
        elements = []
        elements.extend(gen._build_cover_page(data))
        elements.append(PageBreak())
        elements.extend(gen._build_executive_summary(data))
        elements.append(PageBreak())
        elements.extend(gen._build_new_vehicle_section(data))
        elements.append(PageBreak())
        elements.extend(gen._build_used_vehicle_section(data))
        elements.append(PageBreak())
        elements.extend(gen._build_service_loaner_section(data))
        elements.append(PageBreak())
        elements.extend(gen._build_parts_section(data))
        elements.append(PageBreak())
        elements.extend(gen._build_receivables_section(data))
        elements.append(PageBreak())
        elements.extend(gen._build_fi_chargeback_section(data))
        elements.append(PageBreak())
        elements.extend(gen._build_contracts_in_transit_section(data))
        elements.append(PageBreak())
        elements.extend(gen._build_operations_section(data))

        # Generate PDF
        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=letter,
            leftMargin=gen.margin,
            rightMargin=gen.margin,
            topMargin=gen.margin,
            bottomMargin=gen.margin,
        )
        doc.build(elements, onFirstPage=gen._draw_footer, onLaterPages=gen._draw_footer)
        pdf_bytes = buf.getvalue()

        # Write to file
        output_path = os.path.join(OUTPUT_DIR, "ashdown_2026-02-11_packet_OUTPUT.pdf")
        with open(output_path, "wb") as f:
            f.write(pdf_bytes)

        # Verify
        assert len(pdf_bytes) > 1000, f"PDF too small: {len(pdf_bytes)} bytes"
        assert pdf_bytes[:5] == b"%PDF-", "Not a valid PDF"
        print(f"\nPacket PDF generated: {output_path} ({len(pdf_bytes):,} bytes)")


class TestFlaggedItemsPDF:
    """Generate the flagged items report PDF."""

    def test_generate_flagged_pdf(self, parsed_results):
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.platypus import (
            SimpleDocTemplate,
            Table,
            TableStyle,
            Paragraph,
            Spacer,
            PageBreak,
            HRFlowable,
        )

        from app.generators.flagged_items_report import FlaggedItemsReportGenerator

        gen = FlaggedItemsReportGenerator()
        red_flags, yellow_flags = _generate_flags(parsed_results)

        data = {
            "store_name": "Ashdown Classic Chevrolet",
            "meeting_date_str": "February 11, 2026",
            "flags": red_flags + yellow_flags,
            "red_flags": red_flags,
            "yellow_flags": yellow_flags,
        }

        # Build elements
        elements = []
        elements.extend(gen._build_header(data))
        if red_flags:
            elements.extend(gen._build_red_section(red_flags))
        if yellow_flags:
            elements.extend(gen._build_yellow_section(yellow_flags))
        elements.extend(gen._build_summary_footer(data))

        # Generate PDF
        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=letter,
            leftMargin=gen.margin,
            rightMargin=gen.margin,
            topMargin=gen.margin,
            bottomMargin=gen.margin,
        )
        doc.build(
            elements,
            onFirstPage=gen._draw_header_footer,
            onLaterPages=gen._draw_header_footer,
        )
        pdf_bytes = buf.getvalue()

        # Write to file
        output_path = os.path.join(OUTPUT_DIR, "ashdown_2026-02-11_flagged_OUTPUT.pdf")
        with open(output_path, "wb") as f:
            f.write(pdf_bytes)

        # Verify
        assert len(pdf_bytes) > 1000, f"PDF too small: {len(pdf_bytes)} bytes"
        assert pdf_bytes[:5] == b"%PDF-", "Not a valid PDF"
        print(f"\nFlagged items PDF generated: {output_path} ({len(pdf_bytes):,} bytes)")
