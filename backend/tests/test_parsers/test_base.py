"""Tests for the base parser framework."""

from datetime import date
from decimal import Decimal

import pytest

from app.parsers.base import BaseParser


class TestCleanCurrency:
    def test_basic_dollar(self):
        assert BaseParser.clean_currency("$1,234.56") == Decimal("1234.56")

    def test_no_dollar_sign(self):
        assert BaseParser.clean_currency("1234.56") == Decimal("1234.56")

    def test_negative_parentheses(self):
        assert BaseParser.clean_currency("(500.00)") == Decimal("-500.00")

    def test_negative_parentheses_with_dollar(self):
        assert BaseParser.clean_currency("($1,500.00)") == Decimal("-1500.00")

    def test_dash_returns_none(self):
        assert BaseParser.clean_currency("-") is None

    def test_double_dash_returns_none(self):
        assert BaseParser.clean_currency("--") is None

    def test_empty_string_returns_none(self):
        assert BaseParser.clean_currency("") is None

    def test_none_returns_none(self):
        assert BaseParser.clean_currency(None) is None

    def test_na_returns_none(self):
        assert BaseParser.clean_currency("N/A") is None

    def test_whitespace(self):
        assert BaseParser.clean_currency("  $1,234.56  ") == Decimal("1234.56")

    def test_zero(self):
        assert BaseParser.clean_currency("$0.00") == Decimal("0.00")

    def test_large_number(self):
        assert BaseParser.clean_currency("$1,234,567.89") == Decimal("1234567.89")


class TestCleanInt:
    def test_basic(self):
        assert BaseParser.clean_int("1234") == 1234

    def test_with_commas(self):
        assert BaseParser.clean_int("1,234") == 1234

    def test_empty_returns_none(self):
        assert BaseParser.clean_int("") is None

    def test_none_returns_none(self):
        assert BaseParser.clean_int(None) is None

    def test_dash_returns_none(self):
        assert BaseParser.clean_int("-") is None

    def test_whitespace(self):
        assert BaseParser.clean_int("  42  ") == 42

    def test_float_string(self):
        assert BaseParser.clean_int("123.0") == 123

    def test_na_returns_none(self):
        assert BaseParser.clean_int("N/A") is None


class TestParseDate:
    def test_mm_dd_yy(self):
        assert BaseParser.parse_date("02/11/26") == date(2026, 2, 11)

    def test_mm_dd_yyyy(self):
        assert BaseParser.parse_date("02/11/2026") == date(2026, 2, 11)

    def test_single_digit_month_day(self):
        assert BaseParser.parse_date("2/1/26") == date(2026, 2, 1)

    def test_old_date_yy(self):
        assert BaseParser.parse_date("06/15/95") == date(1995, 6, 15)

    def test_dash_format(self):
        assert BaseParser.parse_date("02-11-2026") == date(2026, 2, 11)

    def test_empty_returns_none(self):
        assert BaseParser.parse_date("") is None

    def test_none_returns_none(self):
        assert BaseParser.parse_date(None) is None

    def test_invalid_returns_none(self):
        assert BaseParser.parse_date("not a date") is None


class TestExtractTableRows:
    def test_basic_table(self):
        table = [
            ["Stock #", "Year", "Make"],
            ["1234", "2024", "Chevrolet"],
            ["5678", "2025", "Ford"],
        ]
        rows = BaseParser.extract_table_rows(table)
        assert len(rows) == 2
        assert rows[0] == {"stock_#": "1234", "year": "2024", "make": "Chevrolet"}
        assert rows[1] == {"stock_#": "5678", "year": "2025", "make": "Ford"}

    def test_skips_empty_rows(self):
        table = [
            ["Stock", "Year"],
            ["1234", "2024"],
            ["", ""],
            ["5678", "2025"],
        ]
        rows = BaseParser.extract_table_rows(table)
        assert len(rows) == 2

    def test_handles_none_cells(self):
        table = [
            ["Stock", "Year"],
            ["1234", None],
        ]
        rows = BaseParser.extract_table_rows(table)
        assert rows[0] == {"stock": "1234", "year": ""}

    def test_empty_table(self):
        assert BaseParser.extract_table_rows([]) == []

    def test_header_only(self):
        assert BaseParser.extract_table_rows([["A", "B"]]) == []


class TestFindSectionInPages:
    def _make_page(self, num, text):
        return {"page_number": num, "text": text, "lines": text.split("\n"), "tables": []}

    def test_finds_section(self):
        pages = [
            self._make_page(1, "SCHEDULE 200 - RECEIVABLES"),
            self._make_page(2, "SCHEDULE 237 - NEW VEHICLE INVENTORY"),
            self._make_page(3, "Continued vehicle list"),
            self._make_page(4, "SCHEDULE 240 - USED VEHICLE INVENTORY"),
        ]
        result = BaseParser.find_section_in_pages(pages, "SCHEDULE 237", "SCHEDULE 240")
        assert len(result) == 2
        assert result[0]["page_number"] == 2
        assert result[1]["page_number"] == 3

    def test_no_end_marker(self):
        pages = [
            self._make_page(1, "OTHER STUFF"),
            self._make_page(2, "SCHEDULE 237 - NEW"),
            self._make_page(3, "More vehicles"),
        ]
        result = BaseParser.find_section_in_pages(pages, "SCHEDULE 237")
        assert len(result) == 2

    def test_not_found(self):
        pages = [self._make_page(1, "SCHEDULE 200")]
        result = BaseParser.find_section_in_pages(pages, "SCHEDULE 237")
        assert result == []
