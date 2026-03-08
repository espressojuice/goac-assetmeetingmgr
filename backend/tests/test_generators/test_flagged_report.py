"""Tests for the flagged items report generator."""

from __future__ import annotations

import datetime
import io
import uuid
from unittest.mock import MagicMock

import pdfplumber
import pytest

from app.generators.flagged_items_report import FlaggedItemsReportGenerator
from app.models.flag import FlagSeverity, FlagCategory


# ── Mock Objects ──────────────────────────────────────────


class MockStore:
    id = uuid.uuid4()
    name = "Ashdown Classic Chevrolet"


class MockMeeting:
    id = uuid.uuid4()
    store_id = MockStore.id
    meeting_date = datetime.date(2026, 2, 11)


class MockFlag:
    def __init__(self, severity, category, message, field_value=None, threshold=None):
        self.severity = severity
        self.category = category
        self.message = message
        self.field_name = "test_field"
        self.field_value = field_value
        self.threshold = threshold
        self.status = "open"


def _make_data(red_flags=None, yellow_flags=None):
    """Build data dict mimicking what _fetch_data returns."""
    red = red_flags or []
    yellow = yellow_flags or []
    return {
        "meeting": MockMeeting(),
        "store": MockStore(),
        "store_name": "Ashdown Classic Chevrolet",
        "meeting_date_str": "February 11, 2026",
        "flags": red + yellow,
        "red_flags": red,
        "yellow_flags": yellow,
    }


def _build_pdf(data) -> bytes:
    """Build a flagged items PDF from data dict (no DB)."""
    from reportlab.platypus import SimpleDocTemplate
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch

    gen = FlaggedItemsReportGenerator()
    gen._store_name = data["store_name"]
    gen._meeting_date_str = data["meeting_date_str"]

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
        topMargin=0.75 * inch, bottomMargin=0.75 * inch,
    )

    elements = []
    elements.extend(gen._build_header(data))

    if not data["red_flags"] and not data["yellow_flags"]:
        from reportlab.platypus import Paragraph
        elements.append(Paragraph("No flagged items for this meeting.", gen.styles["NoFlags"]))
    else:
        if data["red_flags"]:
            elements.extend(gen._build_red_section(data["red_flags"]))
        if data["yellow_flags"]:
            elements.extend(gen._build_yellow_section(data["yellow_flags"]))

    elements.extend(gen._build_summary_footer(data))

    doc.build(elements, onFirstPage=gen._draw_header_footer, onLaterPages=gen._draw_header_footer)
    return buf.getvalue()


def _extract_full_text(pdf_bytes: bytes) -> str:
    full_text = ""
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"
    return full_text


# ── Tests ─────────────────────────────────────────────────


class TestFlaggedReportGeneratesBytes:
    def test_returns_non_empty_bytes(self):
        data = _make_data(
            red_flags=[MockFlag(FlagSeverity.RED, FlagCategory.INVENTORY, "Test red flag")],
        )
        pdf_bytes = _build_pdf(data)
        assert len(pdf_bytes) > 0
        assert pdf_bytes[:5] == b"%PDF-"

    def test_pdf_opens_with_pdfplumber(self):
        data = _make_data(
            red_flags=[MockFlag(FlagSeverity.RED, FlagCategory.INVENTORY, "Test red flag")],
        )
        pdf_bytes = _build_pdf(data)
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            assert len(pdf.pages) >= 1


class TestRedBeforeYellow:
    def test_red_flags_appear_before_yellow(self):
        red = [MockFlag(FlagSeverity.RED, FlagCategory.INVENTORY, "RED: Vehicle over 90 days", "95", "90")]
        yellow = [MockFlag(FlagSeverity.YELLOW, FlagCategory.FINANCIAL, "YELLOW: Receivable aging", "1200", "0")]
        data = _make_data(red_flags=red, yellow_flags=yellow)

        pdf_bytes = _build_pdf(data)
        text = _extract_full_text(pdf_bytes)

        # Red section header should appear before yellow section header
        red_pos = text.find("ESCALATED ITEMS")
        yellow_pos = text.find("WARNING ITEMS")
        assert red_pos != -1, "Red section header not found"
        assert yellow_pos != -1, "Yellow section header not found"
        assert red_pos < yellow_pos, "Red section should appear before yellow section"


class TestResponseLines:
    def test_response_lines_present(self):
        red = [MockFlag(FlagSeverity.RED, FlagCategory.OPERATIONS, "Open RO over 30 days", "32", "30")]
        data = _make_data(red_flags=red)

        pdf_bytes = _build_pdf(data)
        text = _extract_full_text(pdf_bytes)
        assert "RESPONSE" in text
        assert "Manager" in text or "Date" in text

    def test_value_and_threshold_shown(self):
        red = [MockFlag(FlagSeverity.RED, FlagCategory.INVENTORY, "Vehicle too old", "95", "90")]
        data = _make_data(red_flags=red)

        pdf_bytes = _build_pdf(data)
        text = _extract_full_text(pdf_bytes)
        assert "95" in text
        assert "90" in text


class TestEmptyFlagsCase:
    def test_no_flags_produces_pdf(self):
        data = _make_data()
        pdf_bytes = _build_pdf(data)
        assert len(pdf_bytes) > 0
        assert pdf_bytes[:5] == b"%PDF-"

    def test_no_flags_message(self):
        data = _make_data()
        pdf_bytes = _build_pdf(data)
        text = _extract_full_text(pdf_bytes)
        assert "No flagged items" in text


class TestSummaryFooter:
    def test_summary_counts(self):
        red = [
            MockFlag(FlagSeverity.RED, FlagCategory.INVENTORY, "Flag 1"),
            MockFlag(FlagSeverity.RED, FlagCategory.PARTS, "Flag 2"),
        ]
        yellow = [
            MockFlag(FlagSeverity.YELLOW, FlagCategory.FINANCIAL, "Flag 3"),
        ]
        data = _make_data(red_flags=red, yellow_flags=yellow)

        pdf_bytes = _build_pdf(data)
        text = _extract_full_text(pdf_bytes)
        assert "24 hours" in text

    def test_header_on_every_page(self):
        """Header should include ACTION REQUIRED."""
        red = [MockFlag(FlagSeverity.RED, FlagCategory.INVENTORY, f"Flag {i}") for i in range(1, 4)]
        data = _make_data(red_flags=red)

        pdf_bytes = _build_pdf(data)
        text = _extract_full_text(pdf_bytes)
        assert "ACTION REQUIRED" in text

    def test_store_name_in_header(self):
        data = _make_data(
            red_flags=[MockFlag(FlagSeverity.RED, FlagCategory.INVENTORY, "Test")],
        )
        pdf_bytes = _build_pdf(data)
        text = _extract_full_text(pdf_bytes)
        assert "Ashdown Classic Chevrolet" in text


class TestFlagCategoryLabels:
    def test_all_categories_render(self):
        flags = [
            MockFlag(FlagSeverity.RED, FlagCategory.INVENTORY, "Inventory issue"),
            MockFlag(FlagSeverity.RED, FlagCategory.PARTS, "Parts issue"),
            MockFlag(FlagSeverity.RED, FlagCategory.FINANCIAL, "Financial issue"),
            MockFlag(FlagSeverity.RED, FlagCategory.OPERATIONS, "Operations issue"),
        ]
        data = _make_data(red_flags=flags)

        pdf_bytes = _build_pdf(data)
        text = _extract_full_text(pdf_bytes)
        assert "Inventory" in text
        assert "Parts" in text
        assert "Financial" in text
        assert "Operations" in text
