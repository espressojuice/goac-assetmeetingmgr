"""Tests for the standardized packet PDF generator."""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pdfplumber
import pytest
import io

from app.generators.packet_generator import StandardizedPacketGenerator, _fmt_currency


# ── Mock Objects ──────────────────────────────────────────


def _uuid():
    return uuid.uuid4()


STORE_ID = _uuid()
MEETING_ID = _uuid()


class MockStore:
    id = STORE_ID
    name = "Ashdown Classic Chevrolet"
    code = "ASH"
    brand = "Chevrolet"
    city = "Ashdown"
    state = "AR"


class MockMeeting:
    id = MEETING_ID
    store_id = STORE_ID
    meeting_date = datetime.date(2026, 2, 11)
    status = "completed"


class MockNewVehicle:
    def __init__(self, stock, year, make, model, days, fp_balance):
        self.stock_number = stock
        self.year = year
        self.make = make
        self.model = model
        self.days_in_stock = days
        self.floorplan_balance = Decimal(str(fp_balance))
        self.book_value = Decimal(str(fp_balance))
        self.vin = "1G1YY22G965100001"
        self.is_demo = False


class MockUsedVehicle:
    def __init__(self, stock, year, make, model, days, book_value, market_value=None):
        self.stock_number = stock
        self.year = year
        self.make = make
        self.model = model
        self.days_in_stock = days
        self.book_value = Decimal(str(book_value))
        self.market_value = Decimal(str(market_value)) if market_value else None
        self.floorplan_balance = None
        self.vin = "1G1YY22G965100002"


class MockServiceLoaner:
    def __init__(self, stock, year, make, model, days, book_val, curr_val, neg_equity):
        self.stock_number = stock
        self.year = year
        self.make = make
        self.model = model
        self.days_in_service = days
        self.book_value = Decimal(str(book_val))
        self.current_value = Decimal(str(curr_val))
        self.negative_equity = Decimal(str(neg_equity))
        self.vin = "1G1YY22G965100003"


class MockFloorplanRecon:
    def __init__(self, recon_type, book, floorplan, variance):
        self.reconciliation_type = MagicMock(value=recon_type)
        self.book_balance = Decimal(str(book))
        self.floorplan_balance = Decimal(str(floorplan))
        self.variance = Decimal(str(variance))
        self.unit_count_book = 10
        self.unit_count_floorplan = 10
        self.unit_count_variance = 0


class MockPartsInventory:
    def __init__(self, category_val, gl, total):
        self.category = MagicMock(value=category_val)
        self.gl_account = gl
        self.total_value = Decimal(str(total))


class MockPartsAnalysis:
    def __init__(self, month, year, turnover, obsolete, stock_order):
        self.period_month = month
        self.period_year = year
        self.true_turnover = Decimal(str(turnover)) if turnover is not None else None
        self.obsolete_value = Decimal(str(obsolete)) if obsolete is not None else None
        self.stock_order_performance = Decimal(str(stock_order)) if stock_order is not None else None
        self.cost_of_sales = Decimal("50000")
        self.average_investment = Decimal("100000")


class MockReceivable:
    def __init__(self, recv_type, current, over_30, over_60, over_90, total):
        self.receivable_type = MagicMock(value=recv_type)
        self.schedule_number = "200"
        self.current_balance = Decimal(str(current))
        self.over_30 = Decimal(str(over_30))
        self.over_60 = Decimal(str(over_60))
        self.over_90 = Decimal(str(over_90))
        self.total_balance = Decimal(str(total))


class MockFIChargeback:
    def __init__(self, account, desc, current, over_90):
        self.account_number = account
        self.account_description = desc
        self.current_balance = Decimal(str(current))
        self.over_90_balance = Decimal(str(over_90))


class MockContractInTransit:
    def __init__(self, deal, customer, sale_date, days, amount, lender):
        self.deal_number = deal
        self.customer_name = customer
        self.sale_date = sale_date
        self.days_in_transit = days
        self.amount = Decimal(str(amount))
        self.lender = lender


class MockOpenRO:
    def __init__(self, ro, date, days, customer, stype, amount):
        self.ro_number = ro
        self.open_date = date
        self.days_open = days
        self.customer_name = customer
        self.service_type = stype
        self.amount = Decimal(str(amount)) if amount else None


class MockMissingTitle:
    def __init__(self, stock, deal, customer, days):
        self.stock_number = stock
        self.deal_number = deal
        self.customer_name = customer
        self.days_missing = days


class MockSlowToAccounting:
    def __init__(self, deal, sale_date, days, customer, salesperson):
        self.deal_number = deal
        self.sale_date = sale_date
        self.days_to_accounting = days
        self.customer_name = customer
        self.salesperson = salesperson


class MockFlag:
    def __init__(self, severity, category, message, field_value=None, threshold=None):
        self.severity = severity
        self.category = category
        self.message = message
        self.field_name = "test_field"
        self.field_value = field_value
        self.threshold = threshold
        self.status = "open"


# ── Sample Data ───────────────────────────────────────────

from app.models.flag import FlagSeverity, FlagCategory


def _sample_data():
    """Build Ashdown-like sample data for testing."""
    return {
        "meeting": MockMeeting(),
        "store": MockStore(),
        "store_name": "Ashdown Classic Chevrolet",
        "meeting_date": datetime.date(2026, 2, 11),
        "meeting_date_str": "February 11, 2026",
        "new_vehicles": [
            MockNewVehicle("N1001", 2026, "Chevrolet", "Silverado 1500", 130, 45000),
            MockNewVehicle("N1002", 2026, "Chevrolet", "Equinox", 45, 32000),
            MockNewVehicle("N1003", 2025, "Chevrolet", "Tahoe", 95, 62000),
        ],
        "used_vehicles": [
            MockUsedVehicle("U2001", 2023, "Ford", "F-150", 95, 35000, 30000),
            MockUsedVehicle("U2002", 2024, "Toyota", "Camry", 65, 25000, 24000),
            MockUsedVehicle("U2003", 2022, "Honda", "Civic", 30, 18000, 19000),
        ],
        "service_loaners": [
            MockServiceLoaner("L3001", 2025, "Chevrolet", "Malibu", 95, 28000, 20000, 8000),
            MockServiceLoaner("L3002", 2025, "Chevrolet", "Equinox", 45, 35000, 30000, 5000),
        ],
        "floorplan_recons": [
            MockFloorplanRecon("new_237", 500000, 502000, 2000),
            MockFloorplanRecon("used_240", 300000, 300000, 0),
        ],
        "parts_inventory": [
            MockPartsInventory("parts_242", "242", 150000),
            MockPartsInventory("tires_243", "243", 25000),
            MockPartsInventory("gas_oil_grease_244", "244", 8000),
        ],
        "parts_analyses": [
            MockPartsAnalysis(1, 2026, 0.1, 45000, 82),
        ],
        "receivables": [
            MockReceivable("parts_service_200", 5000, 1200, 500, 0, 6700),
            MockReceivable("wholesale_220", 3000, 0, 0, 0, 3000),
        ],
        "fi_chargebacks": [
            MockFIChargeback("850", "Service Contract Reserve", 2500, 800),
        ],
        "contracts": [
            MockContractInTransit("D5001", "John Smith", datetime.date(2026, 1, 28), 14, 35000, "Ally Financial"),
            MockContractInTransit("D5002", "Jane Doe", datetime.date(2026, 2, 5), 6, 28000, "Chase Auto"),
        ],
        "open_ros": [
            MockOpenRO("RO9001", datetime.date(2026, 1, 10), 32, "Bob Jones", "CP", 1500),
            MockOpenRO("RO9002", datetime.date(2026, 1, 28), 14, "Alice Brown", "Warranty", 800),
        ],
        "missing_titles": [
            MockMissingTitle("U2005", "D4001", "Tom Wilson", 21),
        ],
        "slow_deals": [
            MockSlowToAccounting("D6001", datetime.date(2026, 2, 1), 10, "Mary Clark", "Jim Sales"),
        ],
        "flags": [
            MockFlag(FlagSeverity.RED, FlagCategory.INVENTORY, "Used: 2023 Ford F-150 (Stk#U2001) — 95 days in stock", "95", "90"),
            MockFlag(FlagSeverity.RED, FlagCategory.PARTS, "Parts turnover critically low at 0.1", "0.1", "1.0"),
            MockFlag(FlagSeverity.YELLOW, FlagCategory.INVENTORY, "Used: 2024 Toyota Camry (Stk#U2002) — 65 days in stock", "65", "60"),
            MockFlag(FlagSeverity.YELLOW, FlagCategory.FINANCIAL, "Receivable aging over 30 days: $1,200.00", "1200", "0"),
        ],
        "red_flags": [
            MockFlag(FlagSeverity.RED, FlagCategory.INVENTORY, "Used: 2023 Ford F-150 (Stk#U2001) — 95 days in stock", "95", "90"),
            MockFlag(FlagSeverity.RED, FlagCategory.PARTS, "Parts turnover critically low at 0.1", "0.1", "1.0"),
        ],
        "yellow_flags": [
            MockFlag(FlagSeverity.YELLOW, FlagCategory.INVENTORY, "Used: 2024 Toyota Camry (Stk#U2002) — 65 days in stock", "65", "60"),
            MockFlag(FlagSeverity.YELLOW, FlagCategory.FINANCIAL, "Receivable aging over 30 days: $1,200.00", "1200", "0"),
        ],
    }


# ── Tests ─────────────────────────────────────────────────


class TestFormatCurrency:
    def test_positive(self):
        assert _fmt_currency(1234.56) == "$1,234.56"

    def test_negative(self):
        assert _fmt_currency(-500) == "($500.00)"

    def test_none(self):
        assert _fmt_currency(None) == "—"

    def test_zero(self):
        assert _fmt_currency(0) == "$0.00"

    def test_decimal(self):
        assert _fmt_currency(Decimal("99999.99")) == "$99,999.99"


class TestPacketGeneratorDirect:
    """Tests that exercise PDF generation by directly calling section builders."""

    def setup_method(self):
        self.gen = StandardizedPacketGenerator()
        self.gen._store_name = "Test Store"
        self.gen._meeting_date_str = "February 11, 2026"
        self.gen._generated_str = "02/11/2026 10:00 AM CT"
        self.data = _sample_data()

    def test_cover_page_elements(self):
        elements = self.gen._build_cover_page(self.data)
        assert len(elements) > 0

    def test_executive_summary_elements(self):
        elements = self.gen._build_executive_summary(self.data)
        assert len(elements) > 0

    def test_new_vehicle_section_elements(self):
        elements = self.gen._build_new_vehicle_section(self.data)
        assert len(elements) > 0

    def test_used_vehicle_section_elements(self):
        elements = self.gen._build_used_vehicle_section(self.data)
        assert len(elements) > 0

    def test_service_loaner_section_elements(self):
        elements = self.gen._build_service_loaner_section(self.data)
        assert len(elements) > 0

    def test_parts_section_elements(self):
        elements = self.gen._build_parts_section(self.data)
        assert len(elements) > 0

    def test_receivables_section_elements(self):
        elements = self.gen._build_receivables_section(self.data)
        assert len(elements) > 0

    def test_fi_chargeback_section_elements(self):
        elements = self.gen._build_fi_chargeback_section(self.data)
        assert len(elements) > 0

    def test_contracts_section_elements(self):
        elements = self.gen._build_contracts_in_transit_section(self.data)
        assert len(elements) > 0

    def test_operations_section_elements(self):
        elements = self.gen._build_operations_section(self.data)
        assert len(elements) > 0

    def test_empty_data_sections(self):
        """Sections with no data should still produce elements (with 'no data' message)."""
        empty = _sample_data()
        empty["new_vehicles"] = []
        empty["used_vehicles"] = []
        empty["service_loaners"] = []
        empty["parts_inventory"] = []
        empty["parts_analyses"] = []
        empty["receivables"] = []
        empty["fi_chargebacks"] = []
        empty["contracts"] = []
        empty["open_ros"] = []
        empty["missing_titles"] = []
        empty["slow_deals"] = []

        assert len(self.gen._build_new_vehicle_section(empty)) > 0
        assert len(self.gen._build_used_vehicle_section(empty)) > 0
        assert len(self.gen._build_service_loaner_section(empty)) > 0
        assert len(self.gen._build_parts_section(empty)) > 0
        assert len(self.gen._build_receivables_section(empty)) > 0
        assert len(self.gen._build_fi_chargeback_section(empty)) > 0
        assert len(self.gen._build_contracts_in_transit_section(empty)) > 0
        assert len(self.gen._build_operations_section(empty)) > 0


class TestPacketGeneratorPDF:
    """Tests that generate an actual PDF and validate via pdfplumber."""

    @pytest.fixture
    def sample_data(self):
        return _sample_data()

    def _build_pdf(self, data) -> bytes:
        """Build a PDF from section builders (without DB)."""
        from reportlab.platypus import SimpleDocTemplate, PageBreak
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.units import inch

        gen = StandardizedPacketGenerator()
        gen._store_name = data["store_name"]
        gen._meeting_date_str = data["meeting_date_str"]
        gen._generated_str = "02/11/2026 10:00 AM CT"

        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf, pagesize=letter,
            leftMargin=0.75 * inch, rightMargin=0.75 * inch,
            topMargin=0.75 * inch, bottomMargin=0.75 * inch,
        )

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

        doc.build(elements, onFirstPage=gen._draw_footer, onLaterPages=gen._draw_footer)
        return buf.getvalue()

    def test_generates_non_empty_bytes(self, sample_data):
        pdf_bytes = self._build_pdf(sample_data)
        assert len(pdf_bytes) > 0
        assert pdf_bytes[:5] == b"%PDF-"

    def test_cover_page_includes_store_name(self, sample_data):
        pdf_bytes = self._build_pdf(sample_data)
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            first_page_text = pdf.pages[0].extract_text()
            assert "Ashdown Classic Chevrolet" in first_page_text

    def test_cover_page_includes_meeting_date(self, sample_data):
        pdf_bytes = self._build_pdf(sample_data)
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            first_page_text = pdf.pages[0].extract_text()
            assert "February 11, 2026" in first_page_text

    def test_pdf_has_multiple_pages(self, sample_data):
        pdf_bytes = self._build_pdf(sample_data)
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            assert len(pdf.pages) >= 10  # Cover + 9 sections

    def test_red_flagged_vehicle_in_output(self, sample_data):
        """The 95-day Ford F-150 should appear in the used vehicle section."""
        pdf_bytes = self._build_pdf(sample_data)
        full_text = ""
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    full_text += text + "\n"
        assert "U2001" in full_text
        assert "F-150" in full_text

    def test_floorplan_reconciliation_present(self, sample_data):
        """Floorplan reconciliation should be in the executive summary."""
        pdf_bytes = self._build_pdf(sample_data)
        full_text = ""
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    full_text += text + "\n"
        assert "Floorplan Reconciliation" in full_text

    def test_all_section_headers_present(self, sample_data):
        """All 9 sections should have headers in the PDF."""
        pdf_bytes = self._build_pdf(sample_data)
        full_text = ""
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    full_text += text + "\n"

        expected_sections = [
            "Executive Summary",
            "New Vehicle Inventory",
            "Used Vehicle Inventory",
            "Service Loaners",
            "Parts",
            "Receivables",
            "Chargebacks",
            "Contracts in Transit",
            "Operations",
        ]
        for section in expected_sections:
            assert section in full_text, f"Missing section: {section}"

    def test_footer_on_pages(self, sample_data):
        """Footer should contain store name and CONFIDENTIAL."""
        pdf_bytes = self._build_pdf(sample_data)
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            # Check a later page (page 2+) for footer text
            if len(pdf.pages) > 1:
                text = pdf.pages[1].extract_text()
                assert "CONFIDENTIAL" in text
