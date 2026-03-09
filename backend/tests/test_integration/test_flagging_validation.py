"""Flagging validation test — runs FlaggingEngine against parsed Ashdown data without DB.

Tests that the flagging rules correctly identify expected flags from the
Ashdown reference packet (02/11/2026).
"""

import os
import sys
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.parsers.pdf_extractor import PDFExtractor
from app.parsers.router import ParserRouter
from app.flagging.engine import FlaggingEngine
from app.flagging.rules import DEFAULT_RULES, FlagRule
from app.models.flag import FlagCategory, FlagSeverity

PDF_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "data", "samples", "ashdown_2026-02-11.pdf"
)

pytestmark = pytest.mark.skipif(
    not os.path.exists(PDF_PATH),
    reason="Ashdown sample PDF not found",
)


class MockRecord:
    """Simple mock that wraps a dict so getattr() works."""

    def __init__(self, data: dict):
        for k, v in data.items():
            setattr(self, k, v)


@pytest.fixture(scope="module")
def parsed_results():
    extractor = PDFExtractor(enable_ocr=True)
    pages = extractor.extract(PDF_PATH)
    router = ParserRouter()
    return router.route_and_parse(pages)


@pytest.fixture(scope="module")
def flag_results(parsed_results):
    """Run FlaggingEngine._evaluate_record against all parsed records."""
    engine = FlaggingEngine()
    flags = []

    for rule in engine.rules:
        if not rule.enabled:
            continue
        model_name = rule.model
        records = parsed_results.get(model_name, [])
        for record_dict in records:
            mock = MockRecord(record_dict)
            severity = engine._evaluate_record(mock, rule)
            if severity:
                flags.append({
                    "rule_name": rule.name,
                    "category": rule.category,
                    "severity": severity,
                    "field": rule.field,
                    "value": getattr(mock, rule.field, None),
                    "stock_number": record_dict.get("stock_number"),
                    "record": record_dict,
                })

    return flags


class TestFlagCounts:
    """Verify overall flag counts."""

    def test_has_red_flags(self, flag_results):
        red = [f for f in flag_results if f["severity"] == FlagSeverity.RED]
        assert len(red) >= 10, f"Expected >=10 red flags, got {len(red)}"

    def test_has_yellow_flags(self, flag_results):
        yellow = [f for f in flag_results if f["severity"] == FlagSeverity.YELLOW]
        assert len(yellow) >= 5, f"Expected >=5 yellow flags, got {len(yellow)}"

    def test_total_flags(self, flag_results):
        assert len(flag_results) >= 15, f"Expected >=15 total flags, got {len(flag_results)}"


class TestUsedVehicleFlags:
    """Verify used vehicle age flags."""

    def _used_flags(self, flag_results):
        return [f for f in flag_results if f["rule_name"] == "Used Vehicle Age"]

    def test_used_over_90_days_red(self, flag_results):
        """Units >90 days in stock should be red: A247632, A420479, T130976, 7059534, etc."""
        red = [f for f in self._used_flags(flag_results) if f["severity"] == FlagSeverity.RED]
        assert len(red) >= 11, f"Expected >=11 used red flags, got {len(red)}"

    def test_used_60_to_90_yellow(self, flag_results):
        """Units 61-90 days in stock should be yellow."""
        yellow = [f for f in self._used_flags(flag_results) if f["severity"] == FlagSeverity.YELLOW]
        assert len(yellow) >= 2, f"Expected >=2 used yellow flags, got {len(yellow)}"


class TestNewVehicleFlags:
    """Verify new vehicle age flags."""

    def _new_flags(self, flag_results):
        return [f for f in flag_results if f["rule_name"] == "New Vehicle Age"]

    def test_new_over_120_days_red(self, flag_results):
        """SS265520 (161d), T1144978 (131d), etc. should be red."""
        red = [f for f in self._new_flags(flag_results) if f["severity"] == FlagSeverity.RED]
        assert len(red) >= 2, f"Expected >=2 new red flags, got {len(red)}"

    def test_new_90_to_120_yellow(self, flag_results):
        """Units 91-120 days in stock should be yellow."""
        yellow = [f for f in self._new_flags(flag_results) if f["severity"] == FlagSeverity.YELLOW]
        assert len(yellow) >= 2, f"Expected >=2 new yellow flags, got {len(yellow)}"


class TestServiceLoanerFlags:
    """Verify service loaner flags."""

    def test_loaner_days_red(self, flag_results):
        """Colorado (110d) and Silverado (140d) should be red."""
        red = [
            f for f in flag_results
            if f["rule_name"] == "Service Loaner Days" and f["severity"] == FlagSeverity.RED
        ]
        assert len(red) >= 2, f"Expected >=2 loaner days red flags, got {len(red)}"

    def test_loaner_neg_equity_red(self, flag_results):
        """Loaners with >$50K negative equity should be red."""
        red = [
            f for f in flag_results
            if f["rule_name"] == "Service Loaner Neg Equity" and f["severity"] == FlagSeverity.RED
        ]
        assert len(red) >= 2, f"Expected >=2 loaner neg equity red flags, got {len(red)}"

    def test_loaner_neg_equity_yellow(self, flag_results):
        """Colorado at $43K negative equity should be yellow."""
        yellow = [
            f for f in flag_results
            if f["rule_name"] == "Service Loaner Neg Equity" and f["severity"] == FlagSeverity.YELLOW
        ]
        assert len(yellow) >= 1, f"Expected >=1 loaner neg equity yellow flag, got {len(yellow)}"


class TestFinancialFlags:
    """Verify F&I and receivable flags."""

    def test_fi_chargeback_over_90_red(self, flag_results):
        """850A ($1,543.86) and 851A ($3,715.39) should be red."""
        red = [
            f for f in flag_results
            if f["rule_name"] == "F&I Chargeback Over 90" and f["severity"] == FlagSeverity.RED
        ]
        assert len(red) >= 2, f"Expected >=2 F&I over-90 red flags, got {len(red)}"


class TestOperationsFlags:
    """Verify operations flags."""

    def test_open_ro_flags(self, flag_results):
        """Most ROs should be >14 days open."""
        ro_flags = [f for f in flag_results if f["rule_name"] == "Open RO Age"]
        assert len(ro_flags) >= 5, f"Expected >=5 open RO flags, got {len(ro_flags)}"

    def test_missing_title_flags(self, flag_results):
        """All 3 missing titles should be flagged (immediately, >=0 days)."""
        title_flags = [f for f in flag_results if f["rule_name"] == "Missing Title"]
        assert len(title_flags) == 3, f"Expected 3 missing title flags, got {len(title_flags)}"


class TestPartsFlags:
    """Verify parts flags."""

    def test_parts_turnover_not_extracted(self, flag_results):
        """True turnover value is cut off in OCR (line has label but no value).
        Gross turnover (1.3) is captured but true_turnover field is empty.
        This verifies the engine correctly skips None values."""
        turnover_flags = [f for f in flag_results if f["rule_name"] == "Parts True Turnover"]
        # true_turnover is not in the parsed data (OCR truncation), so no flags expected
        assert len(turnover_flags) == 0, f"Expected 0 parts turnover flags (field not extracted)"


class TestFlagReport:
    """Print a full flag report sorted by severity and category."""

    def test_print_flag_report(self, flag_results):
        """Print all flags for visual inspection (always passes)."""
        # Sort: red first, then by category
        severity_order = {FlagSeverity.RED: 0, FlagSeverity.YELLOW: 1}
        sorted_flags = sorted(
            flag_results,
            key=lambda f: (severity_order.get(f["severity"], 9), f["category"].value, f["rule_name"]),
        )

        red_count = sum(1 for f in flag_results if f["severity"] == FlagSeverity.RED)
        yellow_count = sum(1 for f in flag_results if f["severity"] == FlagSeverity.YELLOW)
        print(f"\n{'='*80}")
        print(f"FLAG REPORT: {len(flag_results)} total ({red_count} RED, {yellow_count} YELLOW)")
        print(f"{'='*80}")

        current_severity = None
        for f in sorted_flags:
            if f["severity"] != current_severity:
                current_severity = f["severity"]
                label = "RED FLAGS" if current_severity == FlagSeverity.RED else "YELLOW FLAGS"
                print(f"\n--- {label} ---")

            stock = f.get("stock_number", "")
            print(
                f"  [{f['category'].value:10s}] {f['rule_name']:30s} | "
                f"{f['field']}={f['value']} | {stock}"
            )

        print(f"\n{'='*80}\n")
        assert True  # Always passes — this is for visual inspection
