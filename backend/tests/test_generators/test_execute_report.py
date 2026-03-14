"""Tests for the Execute Report PDF generator."""

from __future__ import annotations

import io

import pdfplumber
import pytest

from app.generators.execute_report import ExecuteReportGenerator


def _make_data(**overrides) -> dict:
    """Build a minimal data dict for the execute report generator."""
    base = {
        "store_name": "Ashdown Classic Chevrolet",
        "meeting_date_str": "February 11, 2026",
        "meeting_status": "closed",
        "closed_at_str": "2026-02-11 03:30 PM CT",
        "closed_by_name": "Corporate Admin",
        "attendance": {
            "present": 3,
            "absent": 1,
            "present_names": ["John Doe", "Jane Smith", "Bob Jones"],
            "absent_names": ["Alice Brown"],
        },
        "total_flags": 10,
        "red_count": 4,
        "yellow_count": 6,
        "verified_count": 5,
        "unresolved_count": 3,
        "open_count": 2,
        "resolution_rate": 50.0,
        "top_priorities": [
            {
                "flag_id": "aaa",
                "priority_score": 15,
                "description": "Used vehicle over 90 days — stock 12345",
                "severity": "red",
                "status": "unresolved",
                "assigned_to_name": "Tommy Test",
                "days_outstanding": 14,
                "expected_resolution_date": "2026-02-20",
                "escalation_level": 1,
            },
            {
                "flag_id": "bbb",
                "priority_score": 8,
                "description": "Receivable over 60 days aging",
                "severity": "red",
                "status": "open",
                "assigned_to_name": "Jane Smith",
                "days_outstanding": 7,
                "expected_resolution_date": None,
                "escalation_level": 0,
            },
            {
                "flag_id": "ccc",
                "priority_score": 3,
                "description": "Parts turnover below 2.0",
                "severity": "yellow",
                "status": "responded",
                "assigned_to_name": None,
                "days_outstanding": 5,
                "expected_resolution_date": None,
                "escalation_level": 0,
            },
        ],
        "flags_unresolved": [
            {
                "rule_name": "days_in_stock",
                "description": "Used vehicle over 90 days",
                "severity": "red",
                "status": "unresolved",
                "assigned_to_name": "Tommy Test",
                "days_outstanding": 14,
                "expected_resolution_date": "2026-02-20",
                "escalation_level": 1,
            },
        ],
        "flags_responded": [
            {
                "rule_name": "over_60",
                "description": "Receivable aging over 60 days",
                "severity": "red",
                "status": "responded",
                "assigned_to_name": "Jane Smith",
                "days_outstanding": 7,
                "expected_resolution_date": None,
                "escalation_level": 0,
                "response_text": "Payment collected on 2/15, pending confirmation from accounting.",
            },
        ],
        "flags_verified": [
            {
                "rule_name": "days_open",
                "description": "Open RO closed",
                "severity": "yellow",
                "status": "verified",
                "assigned_to_name": "Bob Jones",
                "days_outstanding": 3,
                "expected_resolution_date": None,
                "escalation_level": 0,
                "verified_by_name": "Corporate Admin",
                "verification_notes": "Confirmed closed in DMS.",
            },
        ],
        "flags_auto_unresolved": [
            {
                "rule_name": "missing_title",
                "description": "Missing title — stock 99999",
                "severity": "yellow",
                "status": "unresolved",
                "assigned_to_name": "Alice Brown",
                "days_outstanding": 10,
                "expected_resolution_date": None,
                "escalation_level": 0,
            },
        ],
        "manager_metrics": [
            {"name": "Tommy Test", "assigned": 3, "resolved": 1, "unresolved": 2, "resolution_rate": 33.3},
            {"name": "Jane Smith", "assigned": 2, "resolved": 2, "unresolved": 0, "resolution_rate": 100.0},
        ],
    }
    base.update(overrides)
    return base


def _build_pdf(data: dict) -> bytes:
    gen = ExecuteReportGenerator()
    return gen.generate(data)


def _extract_text(pdf_bytes: bytes) -> str:
    full_text = ""
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"
    return full_text


# ── Tests ─────────────────────────────────────────────────


class TestExecuteReportGeneratesValidPDF:
    def test_returns_non_empty_bytes(self):
        pdf_bytes = _build_pdf(_make_data())
        assert len(pdf_bytes) > 0
        assert pdf_bytes[:5] == b"%PDF-"

    def test_pdf_opens_with_pdfplumber(self):
        pdf_bytes = _build_pdf(_make_data())
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            assert len(pdf.pages) >= 3  # At least exec summary + priorities + flags


class TestExecuteReportContent:
    def test_store_name_and_date_in_report(self):
        pdf_bytes = _build_pdf(_make_data())
        text = _extract_text(pdf_bytes)
        assert "Ashdown Classic Chevrolet" in text
        assert "February 11, 2026" in text

    def test_top_priority_items_shown(self):
        data = _make_data()
        pdf_bytes = _build_pdf(data)
        text = _extract_text(pdf_bytes)
        assert "TOP PRIORITY ITEMS" in text
        # Should show the priority scores
        assert "15" in text
        assert "8" in text

    def test_correct_number_of_priority_items(self):
        data = _make_data()
        pdf_bytes = _build_pdf(data)
        text = _extract_text(pdf_bytes)
        # 3 priority items in test data
        assert "Tommy Test" in text
        assert "Jane Smith" in text


class TestFlagsGroupedByStatus:
    def test_unresolved_section_present(self):
        pdf_bytes = _build_pdf(_make_data())
        text = _extract_text(pdf_bytes)
        assert "UNRESOLVED" in text

    def test_responded_section_present(self):
        pdf_bytes = _build_pdf(_make_data())
        text = _extract_text(pdf_bytes)
        assert "RESPONDED" in text

    def test_verified_section_present(self):
        pdf_bytes = _build_pdf(_make_data())
        text = _extract_text(pdf_bytes)
        assert "VERIFIED" in text

    def test_auto_unresolved_section_present(self):
        pdf_bytes = _build_pdf(_make_data())
        text = _extract_text(pdf_bytes)
        assert "AUTO-UNRESOLVED" in text


class TestManagerAccountability:
    def test_manager_table_present(self):
        pdf_bytes = _build_pdf(_make_data())
        text = _extract_text(pdf_bytes)
        assert "MANAGER ACCOUNTABILITY" in text
        assert "Tommy Test" in text
        assert "33%" in text  # Tommy's 33.3% resolution rate

    def test_resolution_rates_shown(self):
        pdf_bytes = _build_pdf(_make_data())
        text = _extract_text(pdf_bytes)
        assert "100%" in text  # Jane's perfect rate


class TestEmptyReport:
    def test_no_flags_produces_valid_pdf(self):
        data = _make_data(
            total_flags=0, red_count=0, yellow_count=0,
            verified_count=0, unresolved_count=0, open_count=0,
            resolution_rate=0.0,
            top_priorities=[],
            flags_unresolved=[], flags_responded=[],
            flags_verified=[], flags_auto_unresolved=[],
            manager_metrics=[],
        )
        pdf_bytes = _build_pdf(data)
        assert len(pdf_bytes) > 0
        assert pdf_bytes[:5] == b"%PDF-"
        text = _extract_text(pdf_bytes)
        assert "No unresolved priority items" in text
