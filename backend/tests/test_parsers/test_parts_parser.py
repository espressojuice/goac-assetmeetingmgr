"""Tests for the parts parser (GL 242-244, monthly analysis)."""

from decimal import Decimal

import pytest

from app.parsers.parts_parser import PartsParser


@pytest.fixture
def parser():
    return PartsParser()


def _make_page(num, text, tables=None):
    return {
        "page_number": num,
        "text": text,
        "lines": text.split("\n"),
        "tables": tables or [],
    }


class TestCanHandle:
    def test_gl_242(self, parser):
        assert parser.can_handle("GL 242 - PARTS INVENTORY")

    def test_gl_243(self, parser):
        assert parser.can_handle("GL 243 - TIRES")

    def test_gl_244(self, parser):
        assert parser.can_handle("GL 244 - GAS OIL GREASE")

    def test_parts_inventory(self, parser):
        assert parser.can_handle("PARTS INVENTORY SUMMARY")

    def test_parts_monthly_analysis(self, parser):
        assert parser.can_handle("PARTS MONTHLY ANALYSIS REPORT")

    def test_turnover(self, parser):
        assert parser.can_handle("TRUE TURNOVER REPORT")

    def test_stock_order(self, parser):
        assert parser.can_handle("STOCK ORDER PERFORMANCE")

    def test_unrelated_text(self, parser):
        assert not parser.can_handle("SCHEDULE 237 - NEW VEHICLE INVENTORY")

    def test_case_insensitive(self, parser):
        assert parser.can_handle("gl 242 parts inventory")


class TestParsePartsInventory:
    def test_parse_gl242_summary_from_lines(self, parser):
        text = """GL 242 - PARTS INVENTORY
ASHDOWN CLASSIC CHEVROLET               02/11/2026

Account   Description              Total
GL 242    Parts Inventory          $125,432.50
"""
        page = _make_page(1, text)
        result = parser.parse([page])

        assert "PartsInventory" in result
        records = result["PartsInventory"]
        assert len(records) == 1
        assert records[0]["category"] == "parts_242"
        assert records[0]["gl_account"] == "242"
        assert records[0]["total_value"] == Decimal("125432.50")

    def test_parse_multiple_gl_accounts(self, parser):
        text = """PARTS INVENTORY SUMMARY
GL 242    Parts               $125,000.00
GL 243    Tires               $45,000.00
GL 244    Gas, Oil & Grease   $12,500.00
"""
        page = _make_page(1, text)
        result = parser.parse([page])

        records = result["PartsInventory"]
        assert len(records) == 3

        categories = {r["category"] for r in records}
        assert categories == {"parts_242", "tires_243", "gas_oil_grease_244"}

    def test_parse_from_table(self, parser):
        table = [
            ["Account", "Description", "Total"],
            ["GL 242", "Parts Inventory", "$98,765.43"],
        ]
        text = "GL 242 - PARTS INVENTORY\nSummary report"
        page = _make_page(1, text, tables=[table])
        result = parser.parse([page])

        assert "PartsInventory" in result
        assert result["PartsInventory"][0]["total_value"] == Decimal("98765.43")


class TestParsePartsAnalysis:
    def test_parse_turnover_zero_point_one(self, parser):
        """Ashdown had true turnover of 0.1 — must not round to 0."""
        text = """PARTS MONTHLY ANALYSIS
ASHDOWN CLASSIC CHEVROLET               02/11/2026

Cost of Sales                $8,500.00
Average Investment           $85,000.00
True Turnover                0.1
Months No Sale               $15,200.00
Obsolete                     $3,400.00
Stock Order Performance      0.0%
Outstanding Orders           $2,100.00
Processed Orders             $1,800.00
Receipts                     $5,600.00
"""
        page = _make_page(1, text)
        result = parser.parse([page])

        assert "PartsAnalysis" in result
        analysis = result["PartsAnalysis"][0]
        assert analysis["true_turnover"] == Decimal("0.1")
        assert analysis["stock_order_performance"] == Decimal("0.0")
        assert analysis["cost_of_sales"] == Decimal("8500.00")
        assert analysis["average_investment"] == Decimal("85000.00")
        assert analysis["months_no_sale"] == Decimal("15200.00")
        assert analysis["obsolete_value"] == Decimal("3400.00")
        assert analysis["outstanding_orders_value"] == Decimal("2100.00")
        assert analysis["processed_orders_value"] == Decimal("1800.00")
        assert analysis["receipts_value"] == Decimal("5600.00")

    def test_parse_zero_stock_order_performance(self, parser):
        """0.0% stock order performance must parse correctly."""
        text = """PARTS ANALYSIS
Stock Order Performance      0.0%
"""
        page = _make_page(1, text)
        result = parser.parse([page])

        assert "PartsAnalysis" in result
        assert result["PartsAnalysis"][0]["stock_order_performance"] == Decimal("0.0")

    def test_period_extraction(self, parser):
        text = """PARTS MONTHLY ANALYSIS
ASHDOWN CLASSIC CHEVROLET               02/11/2026

True Turnover                1.5
"""
        page = _make_page(1, text)
        result = parser.parse([page])

        analysis = result["PartsAnalysis"][0]
        assert analysis["period_month"] == 2
        assert analysis["period_year"] == 2026

    def test_empty_analysis_page(self, parser):
        text = "PARTS ANALYSIS\nNo data available"
        page = _make_page(1, text)
        result = parser.parse([page])
        assert "PartsAnalysis" not in result
