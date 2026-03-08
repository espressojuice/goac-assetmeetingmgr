"""Base parser framework for R&R DMS report sections."""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Optional

logger = logging.getLogger(__name__)


class BaseParser(ABC):
    """Base class for all R&R report section parsers."""

    # Each subclass defines which schedule/report identifiers it handles
    SECTION_IDENTIFIERS: list[str] = []

    @abstractmethod
    def parse(self, pages: list[dict]) -> dict:
        """
        Parse extracted page data into structured records.

        Args:
            pages: List of dicts with keys:
                - page_number (int)
                - text (str) — full text of the page
                - lines (list[str]) — text split by newlines
                - tables (list[list[list[str]]]) — pdfplumber table extractions

        Returns:
            Dict with model name as key and list of record dicts as values.
            Example: {"NewVehicleInventory": [{"stock_number": "1234", ...}]}
        """
        pass

    @classmethod
    def can_handle(cls, page_text: str) -> bool:
        """Check if this parser handles the given page based on section identifiers."""
        text_upper = page_text.upper()
        return any(
            identifier.upper() in text_upper
            for identifier in cls.SECTION_IDENTIFIERS
        )

    @staticmethod
    def clean_currency(value: str | None) -> Decimal | None:
        """Parse currency strings like '$1,234.56' or '(1,234.56)' into Decimal."""
        if value is None:
            return None

        cleaned = str(value).strip()
        if not cleaned or cleaned in ("-", "--", "—", "N/A", "n/a"):
            return None

        negative = False
        if cleaned.startswith("(") and cleaned.endswith(")"):
            negative = True
            cleaned = cleaned[1:-1]

        cleaned = cleaned.replace("$", "").replace(",", "").strip()

        if not cleaned:
            return None

        try:
            result = Decimal(cleaned)
            return -result if negative else result
        except InvalidOperation:
            logger.warning(f"Could not parse currency value: {value!r}")
            return None

    @staticmethod
    def clean_int(value: str | None) -> int | None:
        """Parse integer strings, handling commas and whitespace."""
        if value is None:
            return None

        cleaned = str(value).strip().replace(",", "")
        if not cleaned or cleaned in ("-", "--", "—", "N/A", "n/a"):
            return None

        try:
            return int(cleaned)
        except ValueError:
            # Try parsing as float first (e.g. "123.0")
            try:
                return int(float(cleaned))
            except (ValueError, OverflowError):
                logger.warning(f"Could not parse integer value: {value!r}")
                return None

    @staticmethod
    def parse_date(value: str | None) -> date | None:
        """Parse date strings in common R&R formats (MM/DD/YY, MM/DD/YYYY, etc.)."""
        if value is None:
            return None

        cleaned = str(value).strip()
        if not cleaned:
            return None

        # Try MM/DD/YYYY
        match = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", cleaned)
        if match:
            month, day, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
            try:
                return date(year, month, day)
            except ValueError:
                pass

        # Try MM/DD/YY
        match = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{2})$", cleaned)
        if match:
            month, day, year_short = int(match.group(1)), int(match.group(2)), int(match.group(3))
            year = 2000 + year_short if year_short < 80 else 1900 + year_short
            try:
                return date(year, month, day)
            except ValueError:
                pass

        # Try MM-DD-YYYY and MM-DD-YY
        match = re.match(r"^(\d{1,2})-(\d{1,2})-(\d{2,4})$", cleaned)
        if match:
            month, day = int(match.group(1)), int(match.group(2))
            year_str = match.group(3)
            year = int(year_str)
            if len(year_str) == 2:
                year = 2000 + year if year < 80 else 1900 + year
            try:
                return date(year, month, day)
            except ValueError:
                pass

        logger.warning(f"Could not parse date value: {value!r}")
        return None

    @staticmethod
    def extract_table_rows(
        table: list[list[str | None]], header_row_index: int = 0
    ) -> list[dict[str, str]]:
        """
        Convert a pdfplumber table into a list of dicts.

        Uses the specified row as headers and maps subsequent rows to those headers.
        Skips rows that are entirely empty.
        """
        if not table or len(table) <= header_row_index + 1:
            return []

        headers = [
            (h or "").strip().lower().replace(" ", "_").replace("\n", "_")
            for h in table[header_row_index]
        ]

        rows = []
        for row in table[header_row_index + 1 :]:
            # Skip entirely empty rows
            if all(not (cell or "").strip() for cell in row):
                continue
            row_dict = {}
            for i, header in enumerate(headers):
                if i < len(row) and header:
                    row_dict[header] = (row[i] or "").strip()
            rows.append(row_dict)

        return rows

    @staticmethod
    def find_section_in_pages(
        pages: list[dict],
        start_identifier: str,
        end_identifier: str | None = None,
    ) -> list[dict]:
        """
        Return subset of pages between two section markers.

        Finds pages containing start_identifier (inclusive) and continues
        until a page containing end_identifier is found (exclusive), or
        until all remaining pages are consumed.
        """
        result = []
        capturing = False
        start_upper = start_identifier.upper()
        end_upper = end_identifier.upper() if end_identifier else None

        for page in pages:
            text_upper = page["text"].upper()

            if not capturing:
                if start_upper in text_upper:
                    capturing = True
                    result.append(page)
            else:
                if end_upper and end_upper in text_upper:
                    break
                result.append(page)

        return result
