"""Tests for the financial parser (receivables, F&I, CIT, prepaids, policy adjustments)."""

from datetime import date
from decimal import Decimal

import pytest

from app.parsers.financial_parser import FinancialParser


@pytest.fixture
def parser():
    return FinancialParser()


def _make_page(num, text, tables=None):
    return {
        "page_number": num,
        "text": text,
        "lines": text.split("\n"),
        "tables": tables or [],
    }


class TestCanHandle:
    def test_schedule_200(self, parser):
        assert parser.can_handle("SCHEDULE 200 - P&S RECEIVABLE AGING")

    def test_schedule_220(self, parser):
        assert parser.can_handle("SCHEDULE 220 - WHOLESALE RECEIVABLE")

    def test_gl_2612(self, parser):
        assert parser.can_handle("GL 2612 - FACTORY RECEIVABLE")

    def test_chargeback(self, parser):
        assert parser.can_handle("F&I CHARGEBACK REPORT - ACCOUNTS 850/851")

    def test_schedule_205(self, parser):
        assert parser.can_handle("SCHEDULE 205 - CONTRACTS IN TRANSIT")

    def test_prepaid(self, parser):
        assert parser.can_handle("GL 2741 - PREPAID EXPENSES")

    def test_policy_adjust(self, parser):
        assert parser.can_handle("GL 15A - POLICY ADJUSTMENT")

    def test_unrelated_text(self, parser):
        assert not parser.can_handle("SCHEDULE 237 - NEW VEHICLE INVENTORY")

    def test_850_without_context_does_not_match(self, parser):
        """'850' in an address or amount should NOT trigger the parser."""
        assert not parser.can_handle("Located at 850 Main Street, Suite 200")

    def test_850_with_fi_context_matches(self, parser):
        """'850' with F&I context should match."""
        assert parser.can_handle("F&I RESERVE ACCOUNT 850 BALANCE REPORT")

    def test_850_with_chargeback_context_matches(self, parser):
        """'850' with CHARGEBACK context should match."""
        assert parser.can_handle("ACCOUNT 850 CHARGEBACK AGING")


class TestReceivableParsing:
    def test_parse_aging_buckets_from_table(self, parser):
        table = [
            ["Current", "Over 30", "Over 60", "Over 90", "Total"],
            ["$5,000.00", "$2,500.00", "$1,200.00", "$800.00", "$9,500.00"],
        ]
        page = _make_page(
            1,
            "SCHEDULE 200 - P&S RECEIVABLE AGING\nAshdown Classic Chevrolet",
            tables=[table],
        )
        result = parser.parse([page])

        assert "Receivable" in result
        recv = result["Receivable"][0]
        assert recv["receivable_type"] == "parts_service_200"
        assert recv["current_balance"] == Decimal("5000.00")
        assert recv["over_30"] == Decimal("2500.00")
        assert recv["over_60"] == Decimal("1200.00")
        assert recv["over_90"] == Decimal("800.00")
        assert recv["total_balance"] == Decimal("9500.00")

    def test_parse_aging_from_lines(self, parser):
        text = """SCHEDULE 220 - WHOLESALE RECEIVABLE
Current              $3,000.00
Over 30              $1,500.00
Over 60              $750.00
Over 90              $250.00
Total                $5,500.00
"""
        page = _make_page(1, text)
        result = parser.parse([page])

        assert "Receivable" in result
        recv = result["Receivable"][0]
        assert recv["receivable_type"] == "wholesale_220"
        assert recv["total_balance"] == Decimal("5500.00")


class TestFIChargebackParsing:
    def test_parse_chargeback_from_table(self, parser):
        table = [
            ["Account #", "Description", "Current Balance", "Over 90 Balance"],
            ["850", "F&I Reserve - New", "$4,250.00", "$1,543.86"],
            ["851", "F&I Reserve - Used", "$2,100.00", "$0.00"],
        ]
        page = _make_page(
            1,
            "F&I CHARGEBACK REPORT\nAccounts 850 / 851",
            tables=[table],
        )
        result = parser.parse([page])

        assert "FIChargeback" in result
        chargebacks = result["FIChargeback"]
        assert len(chargebacks) == 2

        cb850 = chargebacks[0]
        assert cb850["account_number"] == "850"
        assert cb850["current_balance"] == Decimal("4250.00")
        assert cb850["over_90_balance"] == Decimal("1543.86")

    def test_parse_chargeback_from_lines(self, parser):
        text = """F&I CHARGEBACK AGING
850   F&I Reserve New       $4,250.00  $1,543.86
851   F&I Reserve Used      $2,100.00  $0.00
"""
        page = _make_page(1, text)
        result = parser.parse([page])

        assert "FIChargeback" in result
        assert result["FIChargeback"][0]["over_90_balance"] == Decimal("1543.86")

    def test_over_90_ashdown_reference(self, parser):
        """Ashdown had over-90 balance of $1,543.86."""
        table = [
            ["Account #", "Description", "Current Balance", "Over 90 Balance"],
            ["850", "F&I Reserve", "$4,250.00", "$1,543.86"],
        ]
        page = _make_page(1, "F&I CHARGEBACK REPORT", tables=[table])
        result = parser.parse([page])

        assert result["FIChargeback"][0]["over_90_balance"] == Decimal("1543.86")


class TestContractInTransit:
    def test_parse_cit_from_table(self, parser):
        table = [
            ["Deal #", "Customer Name", "Sale Date", "Days", "Amount", "Lender"],
            ["D12345", "SMITH, JOHN", "01/15/2026", "27", "$35,000.00", "ALLY FINANCIAL"],
        ]
        page = _make_page(1, "SCHEDULE 205 - CONTRACTS IN TRANSIT", tables=[table])
        result = parser.parse([page])

        assert "ContractInTransit" in result
        cit = result["ContractInTransit"][0]
        assert cit["deal_number"] == "D12345"
        assert cit["sale_date"] == date(2026, 1, 15)
        assert cit["days_in_transit"] == 27
        assert cit["amount"] == Decimal("35000.00")
        assert cit["lender"] == "ALLY FINANCIAL"

    def test_parse_cit_from_lines(self, parser):
        text = """CONTRACTS IN TRANSIT
D12345  SMITH, JOHN          01/15/2026  27  $35,000.00  ALLY FINANCIAL
"""
        page = _make_page(1, text)
        result = parser.parse([page])

        assert "ContractInTransit" in result
        assert result["ContractInTransit"][0]["days_in_transit"] == 27


class TestPrepaid:
    def test_parse_prepaid_from_table(self, parser):
        table = [
            ["GL Account", "Description", "Amount"],
            ["2741", "Insurance Prepaid", "$12,500.00"],
            ["2741", "Ad Prepaid", "$3,200.00"],
        ]
        page = _make_page(1, "GL 2741 - PREPAID EXPENSES", tables=[table])
        result = parser.parse([page])

        assert "Prepaid" in result
        assert len(result["Prepaid"]) == 2
        assert result["Prepaid"][0]["amount"] == Decimal("12500.00")


class TestPolicyAdjustment:
    def test_parse_policy_from_table(self, parser):
        table = [
            ["GL Account", "Description", "Amount", "Date"],
            ["15A", "Goodwill - Service", "$500.00", "01/20/2026"],
        ]
        page = _make_page(1, "GL 15A - POLICY ADJUSTMENT", tables=[table])
        result = parser.parse([page])

        assert "PolicyAdjustment" in result
        adj = result["PolicyAdjustment"][0]
        assert adj["gl_account"] == "15A"
        assert adj["amount"] == Decimal("500.00")
        assert adj["adjustment_date"] == date(2026, 1, 20)
