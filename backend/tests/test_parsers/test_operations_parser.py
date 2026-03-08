"""Tests for the operations parser (open ROs, warranty, missing titles, slow-to-accounting)."""

from datetime import date
from decimal import Decimal

import pytest

from app.parsers.operations_parser import OperationsParser


@pytest.fixture
def parser():
    return OperationsParser()


def _make_page(num, text, tables=None):
    return {
        "page_number": num,
        "text": text,
        "lines": text.split("\n"),
        "tables": tables or [],
    }


class TestCanHandle:
    def test_open_ro(self, parser):
        assert parser.can_handle("OPEN RO REPORT")

    def test_open_repair_order(self, parser):
        assert parser.can_handle("OPEN REPAIR ORDER AGING")

    def test_schedule_263(self, parser):
        assert parser.can_handle("SCHEDULE 263 - WARRANTY CLAIMS")

    def test_warranty(self, parser):
        assert parser.can_handle("WARRANTY CLAIM REPORT")

    def test_missing_title(self, parser):
        assert parser.can_handle("MISSING TITLE REPORT")

    def test_no_title(self, parser):
        assert parser.can_handle("VEHICLES WITH NO TITLE")

    def test_slow_to_accounting(self, parser):
        assert parser.can_handle("SLOW TO ACCOUNTING REPORT")

    def test_slow_acct(self, parser):
        assert parser.can_handle("SLOW ACCT DEALS")

    def test_unrelated_text(self, parser):
        assert not parser.can_handle("SCHEDULE 237 - NEW VEHICLE INVENTORY")


class TestOpenRepairOrderParsing:
    def test_parse_ro_from_table(self, parser):
        table = [
            ["RO #", "Open Date", "Days Open", "Customer Name", "Type", "CP Invoice Date", "Amount"],
            ["RO12345", "12/15/2025", "58", "SMITH, JOHN", "CP", "01/05/2026", "$1,250.00"],
            ["RO12346", "12/20/2025", "53", "JONES, MARY", "WARRANTY", None, "$800.00"],
        ]
        page = _make_page(1, "OPEN REPAIR ORDER AGING REPORT", tables=[table])
        result = parser.parse([page])

        assert "OpenRepairOrder" in result
        ros = result["OpenRepairOrder"]
        assert len(ros) == 2

        ro1 = ros[0]
        assert ro1["ro_number"] == "RO12345"
        assert ro1["open_date"] == date(2025, 12, 15)
        assert ro1["days_open"] == 58
        assert ro1["customer_name"] == "SMITH, JOHN"
        assert ro1["service_type"] == "CP"
        assert ro1["cp_invoice_date"] == date(2026, 1, 5)
        assert ro1["amount"] == Decimal("1250.00")

    def test_ro_without_cp_invoice_date(self, parser):
        """Warranty/internal ROs often have no CP invoice date."""
        table = [
            ["RO #", "Open Date", "Days Open", "Customer Name", "Type", "CP Invoice Date", "Amount"],
            ["RO99999", "01/10/2026", "32", "INTERNAL", "INTERNAL", "", "$450.00"],
        ]
        page = _make_page(1, "OPEN RO REPORT", tables=[table])
        result = parser.parse([page])

        ro = result["OpenRepairOrder"][0]
        assert ro["cp_invoice_date"] is None
        assert ro["service_type"] == "INTERNAL"

    def test_parse_ro_from_lines(self, parser):
        text = """OPEN REPAIR ORDER AGING
RO12345  12/15/2025  58  SMITH, JOHN          CP
RO12346  12/20/2025  53  JONES, MARY          WARRANTY
"""
        page = _make_page(1, text)
        result = parser.parse([page])

        assert "OpenRepairOrder" in result
        assert len(result["OpenRepairOrder"]) == 2


class TestWarrantyClaimParsing:
    def test_parse_warranty_from_table(self, parser):
        table = [
            ["Claim #", "Date", "Amount", "Status"],
            ["WC001", "01/05/2026", "$2,500.00", "PENDING"],
            ["WC002", "01/10/2026", "$1,800.00", "APPROVED"],
        ]
        page = _make_page(1, "SCHEDULE 263 - WARRANTY CLAIMS", tables=[table])
        result = parser.parse([page])

        assert "WarrantyClaim" in result
        claims = result["WarrantyClaim"]
        assert len(claims) == 2
        assert claims[0]["claim_number"] == "WC001"
        assert claims[0]["amount"] == Decimal("2500.00")
        assert claims[0]["status"] == "PENDING"


class TestMissingTitleParsing:
    def test_parse_missing_titles_from_table(self, parser):
        """Ashdown had 3 missing titles."""
        table = [
            ["Stock #", "Deal #", "Customer Name", "Days Missing"],
            ["U1001", "D5001", "WILLIAMS, BOB", "45"],
            ["U1002", "D5002", "DAVIS, ANN", "30"],
            ["U1003", "D5003", "CLARK, TOM", "15"],
        ]
        page = _make_page(1, "MISSING TITLE REPORT", tables=[table])
        result = parser.parse([page])

        assert "MissingTitle" in result
        titles = result["MissingTitle"]
        assert len(titles) == 3

        assert titles[0]["stock_number"] == "U1001"
        assert titles[0]["deal_number"] == "D5001"
        assert titles[0]["customer_name"] == "WILLIAMS, BOB"
        assert titles[0]["days_missing"] == 45

    def test_parse_missing_titles_from_lines(self, parser):
        text = """MISSING TITLE REPORT
U1001  D5001  WILLIAMS, BOB          45
U1002  D5002  DAVIS, ANN             30
"""
        page = _make_page(1, text)
        result = parser.parse([page])

        assert "MissingTitle" in result
        assert len(result["MissingTitle"]) == 2


class TestSlowToAccountingParsing:
    def test_parse_slow_from_table(self, parser):
        table = [
            ["Deal #", "Sale Date", "Days", "Customer Name", "Salesperson"],
            ["D9001", "01/28/2026", "14", "BROWN, MIKE", "JOHNSON"],
            ["D9002", "01/25/2026", "17", "GREEN, SUE", "WILLIAMS"],
        ]
        page = _make_page(1, "SLOW TO ACCOUNTING REPORT", tables=[table])
        result = parser.parse([page])

        assert "SlowToAccounting" in result
        slow = result["SlowToAccounting"]
        assert len(slow) == 2

        assert slow[0]["deal_number"] == "D9001"
        assert slow[0]["sale_date"] == date(2026, 1, 28)
        assert slow[0]["days_to_accounting"] == 14
        assert slow[0]["customer_name"] == "BROWN, MIKE"
        assert slow[0]["salesperson"] == "JOHNSON"

    def test_parse_slow_from_lines(self, parser):
        text = """SLOW TO ACCOUNTING
D9001  01/28/2026  14  BROWN, MIKE          JOHNSON
"""
        page = _make_page(1, text)
        result = parser.parse([page])

        assert "SlowToAccounting" in result
        assert result["SlowToAccounting"][0]["days_to_accounting"] == 14
