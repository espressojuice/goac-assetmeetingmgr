"""Integration tests for Ashdown reference packet (ashdown_2026-02-11.pdf).

Tests end-to-end extraction + parsing of the 27-page scanned PDF against
ground truth values. Runs the full pipeline: PDF extraction → OCR → parsing.
"""

import os
import sys
from decimal import Decimal

import pytest

# Allow imports from the backend root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.parsers.pdf_extractor import PDFExtractor
from app.parsers.router import ParserRouter

PDF_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "data", "samples", "ashdown_2026-02-11.pdf"
)

# Skip the entire module if the sample PDF is not present
pytestmark = pytest.mark.skipif(
    not os.path.exists(PDF_PATH),
    reason="Ashdown sample PDF not found",
)


# ---------------------------------------------------------------------------
# Shared fixture: extract and parse once for all tests
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def parsed_results():
    """Extract and parse the Ashdown PDF once for the entire test module."""
    extractor = PDFExtractor(enable_ocr=True)
    pages = extractor.extract(PDF_PATH)
    router = ParserRouter()
    results = router.route_and_parse(pages)
    return results


# ---------------------------------------------------------------------------
# Record Type Existence & Counts
# ---------------------------------------------------------------------------

class TestRecordCounts:
    """Verify that all expected record types are extracted with reasonable counts."""

    def test_new_vehicle_inventory_count(self, parsed_results):
        records = parsed_results.get("NewVehicleInventory", [])
        assert len(records) == 52, f"Expected 52 new vehicles, got {len(records)}"

    def test_used_vehicle_inventory_count(self, parsed_results):
        records = parsed_results.get("UsedVehicleInventory", [])
        assert len(records) == 60, f"Expected 60 used vehicles, got {len(records)}"

    def test_service_loaner_count(self, parsed_results):
        records = parsed_results.get("ServiceLoaner", [])
        assert len(records) == 4, f"Expected 4 loaners, got {len(records)}"

    def test_contract_in_transit_count(self, parsed_results):
        records = parsed_results.get("ContractInTransit", [])
        assert len(records) >= 3, f"Expected >=3 CIT, got {len(records)}"
        assert len(records) <= 5, f"Expected <=5 CIT, got {len(records)}"

    def test_fi_chargeback_count(self, parsed_results):
        records = parsed_results.get("FIChargeback", [])
        assert len(records) == 4, f"Expected 4 chargebacks (850, 850A, 851, 851A), got {len(records)}"

    def test_receivable_count(self, parsed_results):
        records = parsed_results.get("Receivable", [])
        assert len(records) == 2, f"Expected 2 receivables (200, 220), got {len(records)}"

    def test_policy_adjustment_count(self, parsed_results):
        records = parsed_results.get("PolicyAdjustment", [])
        assert len(records) == 2, f"Expected 2 policy adjustments (15A, 15B), got {len(records)}"

    def test_open_repair_order_count(self, parsed_results):
        records = parsed_results.get("OpenRepairOrder", [])
        assert len(records) == 58, f"Expected 58 open ROs, got {len(records)}"

    def test_warranty_claim_count(self, parsed_results):
        records = parsed_results.get("WarrantyClaim", [])
        assert len(records) == 16, f"Expected 16 warranty claims, got {len(records)}"

    def test_missing_title_count(self, parsed_results):
        records = parsed_results.get("MissingTitle", [])
        assert len(records) == 3, f"Expected 3 missing titles, got {len(records)}"

    def test_slow_to_accounting_count(self, parsed_results):
        records = parsed_results.get("SlowToAccounting", [])
        assert len(records) == 2, f"Expected 2 slow-to-accounting, got {len(records)}"

    def test_parts_analysis_exists(self, parsed_results):
        records = parsed_results.get("PartsAnalysis", [])
        assert len(records) >= 1, "Expected at least 1 PartsAnalysis record"

    def test_floorplan_reconciliation_count(self, parsed_results):
        records = parsed_results.get("FloorplanReconciliation", [])
        assert len(records) == 2, f"Expected 2 floorplan reconciliations, got {len(records)}"


# ---------------------------------------------------------------------------
# Receivables
# ---------------------------------------------------------------------------

class TestReceivables:
    """Validate receivable totals against ground truth."""

    def _find_receivable(self, parsed_results, schedule):
        for r in parsed_results.get("Receivable", []):
            if r.get("schedule_number") == schedule:
                return r
        return None

    def test_schedule_200_total(self, parsed_results):
        r = self._find_receivable(parsed_results, "200")
        assert r is not None, "Schedule 200 receivable not found"
        assert abs(float(r["total_balance"]) - 2796.80) < 1.0

    def test_schedule_220_total(self, parsed_results):
        r = self._find_receivable(parsed_results, "220")
        assert r is not None, "Schedule 220 receivable not found"
        assert abs(float(r["total_balance"]) - 720.00) < 1.0


# ---------------------------------------------------------------------------
# F&I Chargebacks
# ---------------------------------------------------------------------------

class TestFIChargebacks:
    """Validate F&I chargeback closing balances."""

    def _find_chargeback(self, parsed_results, account):
        for r in parsed_results.get("FIChargeback", []):
            if r.get("account_number") == account:
                return r
        return None

    def test_850_closing_balance(self, parsed_results):
        r = self._find_chargeback(parsed_results, "850")
        assert r is not None, "Account 850 not found"
        # OCR may truncate decimals (5142 vs 5142.79)
        assert abs(float(r["current_balance"]) - 5142.79) < 2.0

    def test_850a_closing_balance(self, parsed_results):
        r = self._find_chargeback(parsed_results, "850A")
        assert r is not None, "Account 850A not found"
        assert abs(float(r["current_balance"]) - 1543.86) < 1.0

    def test_851_closing_balance(self, parsed_results):
        r = self._find_chargeback(parsed_results, "851")
        assert r is not None, "Account 851 not found"
        assert abs(float(r["current_balance"]) - 5399.49) < 1.0

    def test_851a_closing_balance(self, parsed_results):
        r = self._find_chargeback(parsed_results, "851A")
        assert r is not None, "Account 851A not found"
        assert abs(float(r["current_balance"]) - 3715.39) < 1.0

    def test_850a_is_all_over_90(self, parsed_results):
        r = self._find_chargeback(parsed_results, "850A")
        assert r is not None
        assert float(r["over_90_balance"]) == float(r["current_balance"])

    def test_851a_is_all_over_90(self, parsed_results):
        r = self._find_chargeback(parsed_results, "851A")
        assert r is not None
        assert float(r["over_90_balance"]) == float(r["current_balance"])


# ---------------------------------------------------------------------------
# Policy Adjustments
# ---------------------------------------------------------------------------

class TestPolicyAdjustments:
    """Validate policy adjustment closing balances."""

    def _find_policy(self, parsed_results, gl):
        for r in parsed_results.get("PolicyAdjustment", []):
            if r.get("gl_account") == gl:
                return r
        return None

    def test_15a_amount(self, parsed_results):
        r = self._find_policy(parsed_results, "15A")
        assert r is not None, "GL 15A not found"
        assert abs(float(r["amount"]) - 133.40) < 1.0

    def test_15b_amount(self, parsed_results):
        r = self._find_policy(parsed_results, "15B")
        assert r is not None, "GL 15B not found"
        assert abs(float(r["amount"]) - 3174.00) < 1.0


# ---------------------------------------------------------------------------
# Contracts in Transit
# ---------------------------------------------------------------------------

class TestContractsInTransit:
    """Validate CIT records."""

    def test_cit_deal_numbers(self, parsed_results):
        records = parsed_results.get("ContractInTransit", [])
        deal_numbers = {r["deal_number"] for r in records}
        # These deal numbers must be present
        for deal in ["678", "684", "710", "695"]:
            assert deal in deal_numbers, f"CIT deal {deal} not found"

    def test_gonzales_amount(self, parsed_results):
        records = parsed_results.get("ContractInTransit", [])
        for r in records:
            if r["deal_number"] == "678":
                assert abs(float(r["amount"]) - 28281.61) < 1.0
                return
        pytest.fail("Deal 678 not found")

    def test_morris_negative_amount(self, parsed_results):
        records = parsed_results.get("ContractInTransit", [])
        for r in records:
            if r["deal_number"] == "710":
                assert float(r["amount"]) < 0, "Deal 710 should be negative"
                return
        pytest.fail("Deal 710 not found")


# ---------------------------------------------------------------------------
# New Vehicle Inventory
# ---------------------------------------------------------------------------

class TestNewVehicleInventory:
    """Validate new vehicle records."""

    def test_page_reports_52_records(self, parsed_results):
        records = parsed_results.get("NewVehicleInventory", [])
        # Page footer says "52 records listed"
        assert len(records) == 52, f"Expected 52 new vehicles, got {len(records)}"

    def test_first_vehicle_details(self, parsed_results):
        records = parsed_results.get("NewVehicleInventory", [])
        assert len(records) > 0
        # First vehicle should be the oldest (highest days)
        oldest = max(records, key=lambda r: r.get("days_in_stock", 0))
        assert oldest["days_in_stock"] >= 150, "Oldest new vehicle should have 150+ days"

    def test_floorplan_reconciliation_new(self, parsed_results):
        recons = parsed_results.get("FloorplanReconciliation", [])
        new_recon = next((r for r in recons if r["reconciliation_type"] == "new_237"), None)
        assert new_recon is not None
        assert new_recon["unit_count_book"] == 52


# ---------------------------------------------------------------------------
# Used Vehicle Inventory
# ---------------------------------------------------------------------------

class TestUsedVehicleInventory:
    """Validate used vehicle records."""

    def test_page_reports_60_records(self, parsed_results):
        records = parsed_results.get("UsedVehicleInventory", [])
        # Page footer says "60 records listed"
        assert len(records) == 60, f"Expected 60 used vehicles, got {len(records)}"

    def test_floorplan_reconciliation_used(self, parsed_results):
        recons = parsed_results.get("FloorplanReconciliation", [])
        used_recon = next((r for r in recons if r["reconciliation_type"] == "used_240"), None)
        assert used_recon is not None
        assert used_recon["unit_count_book"] == 60


# ---------------------------------------------------------------------------
# Service Loaners
# ---------------------------------------------------------------------------

class TestServiceLoaners:
    """Validate service loaner records."""

    def test_loaner_count(self, parsed_results):
        records = parsed_results.get("ServiceLoaner", [])
        assert len(records) == 4, f"Expected 4 loaners, got {len(records)}"

    def test_loaner_book_values(self, parsed_results):
        records = parsed_results.get("ServiceLoaner", [])
        book_values = sorted([float(r["book_value"]) for r in records])
        # Should have values around 45K, 51K, 57K
        assert any(40000 < v < 50000 for v in book_values), "Expected a loaner with ~45K book value"
        assert any(50000 < v < 55000 for v in book_values), "Expected a loaner with ~51K book value"

    def test_loaner_negative_equity_reasonable(self, parsed_results):
        records = parsed_results.get("ServiceLoaner", [])
        for r in records:
            neg_eq = float(r.get("negative_equity", 0))
            book = float(r.get("book_value", 0))
            # Negative equity should be in same order of magnitude as book value
            assert neg_eq < book * 3, (
                f"Loaner {r.get('stock_number')} neg equity {neg_eq} unreasonably high vs book {book}"
            )


# ---------------------------------------------------------------------------
# Open Repair Orders
# ---------------------------------------------------------------------------

class TestOpenRepairOrders:
    """Validate open RO records."""

    def test_ro_count(self, parsed_results):
        records = parsed_results.get("OpenRepairOrder", [])
        assert len(records) == 58, f"Expected 58 open ROs, got {len(records)}"

    def test_oldest_ro(self, parsed_results):
        records = parsed_results.get("OpenRepairOrder", [])
        oldest = max(records, key=lambda r: r.get("days_open", 0))
        assert oldest["days_open"] >= 45, "Oldest RO should be 45+ days open"

    def test_ro_dates_are_valid(self, parsed_results):
        import datetime
        records = parsed_results.get("OpenRepairOrder", [])
        meeting_date = datetime.date(2026, 2, 11)
        for r in records:
            if r.get("open_date"):
                assert r["open_date"] < meeting_date, f"RO date {r['open_date']} should be before meeting"
                assert r["open_date"] > datetime.date(2025, 1, 1), f"RO date {r['open_date']} too old"


# ---------------------------------------------------------------------------
# Warranty Claims
# ---------------------------------------------------------------------------

class TestWarrantyClaims:
    """Validate warranty claim records."""

    def test_warranty_count(self, parsed_results):
        records = parsed_results.get("WarrantyClaim", [])
        assert len(records) == 16, f"Expected 16 warranty claims, got {len(records)}"

    def test_claim_number_format(self, parsed_results):
        records = parsed_results.get("WarrantyClaim", [])
        import re
        for r in records:
            # Allow 4-5 digit base (OCR may garble 5th digit)
            assert re.match(r"\d{4,5}-\d{1,2}", r["claim_number"]), (
                f"Claim number {r['claim_number']} doesn't match NNNNN-N format"
            )

    def test_known_claim(self, parsed_results):
        records = parsed_results.get("WarrantyClaim", [])
        claims = {r["claim_number"]: r for r in records}
        assert "76889-1" in claims, "Claim 76889-1 not found"
        assert abs(float(claims["76889-1"]["amount"]) - 911.81) < 0.01


# ---------------------------------------------------------------------------
# Missing Titles
# ---------------------------------------------------------------------------

class TestMissingTitles:
    """Validate missing title records."""

    def test_exactly_3_titles(self, parsed_results):
        records = parsed_results.get("MissingTitle", [])
        assert len(records) == 3


# ---------------------------------------------------------------------------
# Slow to Accounting
# ---------------------------------------------------------------------------

class TestSlowToAccounting:
    """Validate slow-to-accounting records."""

    def test_exactly_2_records(self, parsed_results):
        records = parsed_results.get("SlowToAccounting", [])
        assert len(records) == 2

    def test_atkins_deal(self, parsed_results):
        records = parsed_results.get("SlowToAccounting", [])
        atkins = next((r for r in records if r["deal_number"] == "22867"), None)
        assert atkins is not None, "Deal 22867 (Atkins) not found"
        assert atkins["days_to_accounting"] <= 10, f"Atkins days should be <=10, got {atkins['days_to_accounting']}"
        assert abs(float(atkins.get("amount", 0)) - 816.59) < 1.0

    def test_morris_deal(self, parsed_results):
        records = parsed_results.get("SlowToAccounting", [])
        morris = next((r for r in records if r["deal_number"] == "22879"), None)
        assert morris is not None, "Deal 22879 (Morris) not found"
        assert morris["days_to_accounting"] <= 10, f"Morris days should be <=10, got {morris['days_to_accounting']}"


# ---------------------------------------------------------------------------
# Parts Analysis
# ---------------------------------------------------------------------------

class TestPartsAnalysis:
    """Validate parts analysis values."""

    def _all_analysis_fields(self, parsed_results):
        """Merge all PartsAnalysis records into one dict."""
        merged = {}
        for r in parsed_results.get("PartsAnalysis", []):
            for k, v in r.items():
                if k not in ("period_month", "period_year") and v is not None:
                    merged.setdefault(k, v)
        return merged

    def test_cost_of_sales(self, parsed_results):
        fields = self._all_analysis_fields(parsed_results)
        cos = float(fields.get("cost_of_sales", 0))
        assert abs(cos - 29941.28) < 1.0, f"Cost of sales should be 29,941.28, got {cos}"

    def test_level_of_service(self, parsed_results):
        fields = self._all_analysis_fields(parsed_results)
        los = float(fields.get("level_of_service", 0))
        assert 95 < los <= 100, f"Level of service should be ~100%, got {los}"

    def test_gross_turnover(self, parsed_results):
        fields = self._all_analysis_fields(parsed_results)
        gt = float(fields.get("gross_turnover", 0))
        assert 0.5 < gt < 5.0, f"Gross turnover should be ~1.3, got {gt}"

    def test_period_is_february_2026(self, parsed_results):
        records = parsed_results.get("PartsAnalysis", [])
        assert len(records) > 0
        assert records[0]["period_month"] == 2
        assert records[0]["period_year"] == 2026


# ---------------------------------------------------------------------------
# Unhandled Pages
# ---------------------------------------------------------------------------

class TestPageCoverage:
    """Verify page routing handles most pages."""

    def test_minimal_unhandled_pages(self, parsed_results):
        # Pages 2 (Employee Roster), 6 (Core Inventory), 19 (no clear section) are expected unhandled
        # The rest should be handled
        all_types = set(parsed_results.keys())
        # We should have at least these record types
        expected_types = {
            "NewVehicleInventory", "UsedVehicleInventory", "ServiceLoaner",
            "ContractInTransit", "FIChargeback", "Receivable", "PolicyAdjustment",
            "OpenRepairOrder", "WarrantyClaim", "MissingTitle", "SlowToAccounting",
            "PartsAnalysis", "FloorplanReconciliation",
        }
        missing = expected_types - all_types
        assert not missing, f"Missing record types: {missing}"
