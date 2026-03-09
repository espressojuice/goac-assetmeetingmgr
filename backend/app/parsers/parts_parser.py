"""Parts parser for GL 242-244 inventory and monthly analysis reports."""

from __future__ import annotations

import logging
import re
from decimal import Decimal

from .base import BaseParser

logger = logging.getLogger(__name__)

# GL account to category mapping
_GL_CATEGORY_MAP = {
    "242": "parts_242",
    "243": "tires_243",
    "244": "gas_oil_grease_244",
}

# Regex to collapse OCR-introduced spaces inside numbers.
# Matches digits separated by spaces around a dot, e.g. "64 . 2 8" -> "64.28"
# Also handles "29 , 941 . 28" -> "29,941.28" and plain "1 2 3" -> "123"
_OCR_SPACED_NUMBER = re.compile(r"(?<=\d)\s+(?=[.,])|(?<=[.,])\s+(?=\d)|(?<=\d)\s+(?=\d)")


def _clean_ocr_number(text: str) -> str:
    """Remove OCR-induced spaces inside a number string.

    Examples:
        "64 . 2 8"   -> "64.28"
        "29 , 941.28" -> "29,941.28"
        "110 720 . 14" -> "110720.14"
        "4 . 3"       -> "4.3"
    """
    return _OCR_SPACED_NUMBER.sub("", text)


def _clean_ocr_line(line: str) -> str:
    """Aggressively clean an OCR line by collapsing spaced-out numbers.

    Scans the line for number-like token sequences and collapses them while
    leaving other text untouched.
    """
    # Find runs that look like spaced numbers: digits/dots/commas separated by spaces
    # e.g. "29 , 941 . 28" or "110 720 . 14"
    pattern = re.compile(
        r"""
        \$?\s*                         # optional dollar sign
        (?:\d[\d\s]*[\s]*[.,][\s]*)*   # groups of digits + separator
        \d[\d\s]*\d                    # at least two digits with possible spaces
        """,
        re.VERBOSE,
    )

    def _collapse(m: re.Match) -> str:
        return _clean_ocr_number(m.group(0))

    return pattern.sub(_collapse, line)


class PartsParser(BaseParser):
    """Parser for parts inventory (GL 242-244) and parts monthly analysis."""

    SECTION_IDENTIFIERS = [
        # Parts Inventory
        "GL 242",
        "GL 243",
        "GL 244",
        "PARTS INVENTORY",
        "TIRES",
        "GAS OIL GREASE",
        "GAS, OIL",
        # Parts Monthly Analysis
        "PARTS MONTHLY",
        "PARTS ANALYSIS",
        "PARTS ACTIVITY",
        "MONTHLY ANALYSIS",
        "TURNOVER",
        "STOCK ORDER",
    ]

    _INVENTORY_IDENTIFIERS = [
        "GL 242", "GL 243", "GL 244",
        "PARTS INVENTORY", "TIRES", "GAS OIL GREASE", "GAS, OIL",
    ]
    _ANALYSIS_IDENTIFIERS = [
        "PARTS MONTHLY", "PARTS ANALYSIS", "PARTS ACTIVITY",
        "MONTHLY ANALYSIS", "TURNOVER", "STOCK ORDER",
    ]

    def parse(self, pages: list[dict]) -> dict:
        """Parse parts pages into structured records."""
        inventory_records = []
        analysis_records = []

        for page in pages:
            text_upper = page["text"].upper()

            if self._matches(text_upper, self._INVENTORY_IDENTIFIERS):
                records = self._parse_inventory_page(page)
                inventory_records.extend(records)

            if self._matches(text_upper, self._ANALYSIS_IDENTIFIERS):
                record = self._parse_analysis_page(page)
                if record:
                    analysis_records.append(record)

        results = {}
        if inventory_records:
            results["PartsInventory"] = inventory_records
        if analysis_records:
            results["PartsAnalysis"] = analysis_records

        logger.info(
            f"Parts parser: {len(inventory_records)} inventory, "
            f"{len(analysis_records)} analysis records"
        )
        return results

    def _matches(self, text_upper: str, identifiers: list[str]) -> bool:
        """Check if text contains any of the given identifiers."""
        return any(ident.upper() in text_upper for ident in identifiers)

    def _parse_inventory_page(self, page: dict) -> list[dict]:
        """Parse parts inventory summary lines for GL 242/243/244."""
        records = []
        text_upper = page["text"].upper()

        for gl_num, category in _GL_CATEGORY_MAP.items():
            gl_key = f"GL {gl_num}"
            if gl_key not in text_upper:
                continue

            # Try to find the total value from table rows
            total = self._find_gl_total_from_tables(page, gl_num)

            # Fall back to line-by-line search
            if total is None:
                total = self._find_gl_total_from_lines(page["lines"], gl_num)

            if total is not None:
                records.append({
                    "category": category,
                    "gl_account": gl_num,
                    "total_value": total,
                })
            else:
                logger.warning(f"Found GL {gl_num} identifier but could not extract total value")

        return records

    def _find_gl_total_from_tables(self, page: dict, gl_num: str) -> Decimal | None:
        """Try to extract GL total from table data."""
        if not page.get("tables"):
            return None

        for table in page["tables"]:
            rows = self.extract_table_rows(table)
            for row in rows:
                # Check if any cell references this GL account
                row_text = " ".join(str(v) for v in row.values()).upper()
                if gl_num in row_text or f"GL {gl_num}" in row_text:
                    # Look for a total/balance/amount column
                    amount = self.clean_currency(
                        row.get("total")
                        or row.get("total_value")
                        or row.get("balance")
                        or row.get("amount")
                        or row.get("value")
                    )
                    if amount is not None:
                        return amount

        return None

    def _find_gl_total_from_lines(self, lines: list[str], gl_num: str) -> Decimal | None:
        """Extract GL total from text lines using regex."""
        # Pattern: line containing GL number followed by a dollar amount
        gl_pattern = re.compile(
            rf"(?:GL\s*{gl_num}|ACCOUNT\s*{gl_num})"
            r".*?([\d,.$()-]+)\s*$",
            re.IGNORECASE,
        )
        # Also try: amount appears on the same line as the GL account
        amount_pattern = re.compile(
            r"\$?\s*([\d,]+\.?\d*)\s*$"
        )

        for line in lines:
            if gl_num not in line.upper().replace(" ", ""):
                continue
            # Try specific GL pattern
            match = gl_pattern.search(line)
            if match:
                val = self.clean_currency(match.group(1))
                if val is not None:
                    return val
            # Try generic trailing amount
            match = amount_pattern.search(line)
            if match:
                val = self.clean_currency(match.group(0))
                if val is not None:
                    return val

        return None

    def _parse_analysis_page(self, page: dict) -> dict | None:
        """Parse parts monthly analysis data."""
        record: dict = {}
        is_ocr = page.get("ocr_used", False)

        # Try table extraction first — but skip for OCR pages since tables
        # are unreliable from OCR output.
        if not is_ocr and page.get("tables"):
            for table in page["tables"]:
                rows = self.extract_table_rows(table)
                for row in rows:
                    self._extract_analysis_fields(row, record)

        # Fall back to (or always use for OCR) line parsing
        if not record or is_ocr:
            self._extract_analysis_from_lines(page["lines"], record, is_ocr=is_ocr)

        if not record:
            return None

        # Extract period from page header or default
        period = self._extract_period(page["lines"])
        record.setdefault("period_month", period[0])
        record.setdefault("period_year", period[1])

        return record

    def _extract_analysis_fields(self, row: dict, record: dict) -> None:
        """Extract analysis fields from a table row dict."""
        field_mappings = {
            "cost_of_sales": ["cost_of_sales", "cost_sales", "cos"],
            "average_investment": ["average_investment", "avg_investment", "avg_inv"],
            "true_turnover": ["true_turnover", "turnover", "true_turn"],
            "months_no_sale": ["months_no_sale", "no_sale", "months_no_activity"],
            "obsolete_value": ["obsolete_value", "obsolete", "obsolescence"],
            "stock_order_performance": [
                "stock_order_performance", "stock_order_perf",
                "stock_order_%", "stock_order",
            ],
            "outstanding_orders_value": [
                "outstanding_orders_value", "outstanding_orders",
                "outstanding", "open_orders",
            ],
            "processed_orders_value": [
                "processed_orders_value", "processed_orders", "processed",
            ],
            "receipts_value": ["receipts_value", "receipts", "receipt"],
        }

        for target_field, source_keys in field_mappings.items():
            if target_field in record:
                continue
            for key in source_keys:
                raw = row.get(key)
                if raw:
                    val = self._parse_analysis_value(raw, target_field)
                    if val is not None:
                        record[target_field] = val
                        break

    def _extract_analysis_from_lines(
        self, lines: list[str], record: dict, *, is_ocr: bool = False
    ) -> None:
        """Extract analysis fields from text lines using pattern matching.

        For OCR text, numbers may have embedded spaces (e.g. "64 . 2 8").
        We pre-clean each line to collapse those before applying patterns.
        We also do a two-pass approach: first try the current line, then try
        combining the label line with the next line (value on separate line).
        """
        # Build pattern list — order matters (first match wins per field).
        # Patterns are applied to OCR-cleaned lines.
        line_patterns = [
            ("cost_of_sales", re.compile(
                r"TOTAL\s+COST\s+(?:OF\s+)?SALES.*?([\d,]+\.\d{2})", re.IGNORECASE
            )),
            ("cost_of_sales", re.compile(
                r"TOTAL\s+COST\s+(?:OF\s+)?SALES.*?([\d,.$()-]+)\s*$", re.IGNORECASE
            )),
            ("cost_of_sales", re.compile(
                r"COST\s+(?:OF\s+)?SALES\s+[\$]?\s*([\d,.$()-]+)\s*$", re.IGNORECASE
            )),
            ("average_investment", re.compile(
                r"(?:TOTAL\s+)?INVESTMENT.*?([\d,.$()-]+)\s*$", re.IGNORECASE
            )),
            ("average_investment", re.compile(
                r"AVE?RAGE?\s+INV.*?([\d,.$()-]+)\s*$", re.IGNORECASE
            )),
            ("true_turnover", re.compile(
                r"TRUE\s+TURN(?:OVER)?(?:\s+RATE)?.*?([\d,.]+)\s*[%$]?\s*$", re.IGNORECASE
            )),
            ("months_no_sale", re.compile(
                r"MONTHS?\s+NO\s+SALE.*?([\d,.$()-]+)\s*$", re.IGNORECASE
            )),
            ("obsolete_value", re.compile(
                r"OBSOLETE?.*?([\d,.$()-]+)\s*$", re.IGNORECASE
            )),
            ("obsolete_value", re.compile(
                r"\bOB\b.*?([\d,.$()-]+)\s*$", re.IGNORECASE
            )),
            ("stock_order_performance", re.compile(
                r"STOCK\s+ORDER(?:\s+PERF(?:ORMANCE)?)?\s*.*?([\d,.]+)\s*[%$]?\s*$",
                re.IGNORECASE,
            )),
            ("outstanding_orders_value", re.compile(
                r"OUTSTANDING.*?ORDER.*?([\d,.$()-]+)\s*$", re.IGNORECASE
            )),
            ("processed_orders_value", re.compile(
                r"PROCESSED.*?ORDER.*?([\d,.$()-]+)\s*$", re.IGNORECASE
            )),
            ("receipts_value", re.compile(
                r"RECEIPTS?\s+.*?([\d,.$()-]+)\s*$", re.IGNORECASE
            )),
            ("level_of_service", re.compile(
                r"LEVEL\s+OF\s+SERVICE.*?([\d,.]+)\s*[%$]?\s*$", re.IGNORECASE
            )),
            ("gross_turnover", re.compile(
                r"GROSS\s+TURN(?:OVER)?(?:\s+RATE)?.*?([\d,.]+)\s*[%$]?\s*$", re.IGNORECASE
            )),
        ]

        # For OCR: two-pass approach.
        # Pass 1: match on raw lines (handles values without spaces like "29941.28").
        # Pass 2: match on OCR-cleaned lines but SKIP lines starting with TOTAL
        #         to avoid collapsing separate column values (e.g. "274 100 691 29941.28").
        num_lines = len(lines)

        # Pass 1: raw lines
        for i, line in enumerate(lines):
            for field, pattern in line_patterns:
                if field in record:
                    continue

                match = pattern.search(line)
                if match:
                    raw = match.group(1)
                    if is_ocr:
                        raw = _clean_ocr_number(raw)
                        raw = raw.rstrip("$")
                    val = self._parse_analysis_value(raw, field)
                    if val is not None:
                        record[field] = val
                    continue

                # Try combining with next line (value on separate line)
                if is_ocr and i + 1 < num_lines:
                    combined = line.rstrip() + "  " + lines[i + 1].lstrip()
                    match = pattern.search(combined)
                    if match:
                        raw = _clean_ocr_number(match.group(1))
                        raw = raw.rstrip("$")
                        val = self._parse_analysis_value(raw, field)
                        if val is not None:
                            record[field] = val

        # Pass 2: OCR-cleaned lines for fields not yet captured.
        # Skip TOTAL lines to avoid collapsing separate column values.
        if is_ocr:
            for i, line in enumerate(lines):
                # Skip lines that start with TOTAL — cleaning merges columns
                if re.match(r"\s*TOTAL\b", line, re.IGNORECASE):
                    continue

                cleaned = _clean_ocr_line(line)
                for field, pattern in line_patterns:
                    if field in record:
                        continue

                    match = pattern.search(cleaned)
                    if match:
                        raw = _clean_ocr_number(match.group(1))
                        raw = raw.rstrip("$")
                        val = self._parse_analysis_value(raw, field)
                        if val is not None:
                            record[field] = val

    def _parse_analysis_value(self, raw: str, field: str) -> Decimal | None:
        """Parse a value, handling percentages and small decimals."""
        cleaned = raw.strip().rstrip("%").rstrip("$")
        if field in (
            "true_turnover", "stock_order_performance",
            "level_of_service", "gross_turnover",
        ):
            # These are small decimal/percentage values, not currency
            cleaned = cleaned.replace("$", "").replace(",", "").strip()
            if not cleaned:
                return None
            try:
                return Decimal(cleaned)
            except Exception:
                logger.warning(f"Could not parse {field} value: {raw!r}")
                return None
        return self.clean_currency(raw)

    def _extract_period(self, lines: list[str]) -> tuple[int, int]:
        """Extract period month/year from header lines, defaulting to current date.

        Handles formats:
        - Full date: MM/DD/YYYY or MM/DD/YY
        - Month name: JANUARY 2026
        - MM/YY period shorthand (common in OCR headers like "MM/Yx 02/26")
        """
        import datetime

        # Full date: MM/DD/YYYY or MM/DD/YY
        date_pattern = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{2,4})")
        # MM/YY shorthand (without day), e.g. "02/26" not followed by another /digit
        mmyy_pattern = re.compile(r"(?<!\d/)(\d{2})/(\d{2})(?!/|\d)")
        month_names = {
            "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
            "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
        }
        month_pattern = re.compile(
            r"(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\w*\s+(\d{4})",
            re.IGNORECASE,
        )

        for line in lines[:10]:
            # Try month name + year (e.g. "JANUARY 2026")
            match = month_pattern.search(line)
            if match:
                month = month_names.get(match.group(1).upper()[:3], 0)
                year = int(match.group(2))
                if month and 2000 <= year <= 2100:
                    return (month, year)

            # Try full date format MM/DD/YYYY or MM/DD/YY
            match = date_pattern.search(line)
            if match:
                month = int(match.group(1))
                year_raw = int(match.group(3))
                year = year_raw if year_raw > 100 else 2000 + year_raw
                if 1 <= month <= 12:
                    return (month, year)

        # Second pass: look for MM/YY shorthand in headers (OCR often has this)
        for line in lines[:10]:
            line_upper = line.upper()
            # Only match if line looks like a header (has keywords or is near top)
            if any(kw in line_upper for kw in (
                "MM/Y", "PAGE", "SUMMARY", "ANALYSIS", "BRANCH", "STORE",
            )):
                for match in mmyy_pattern.finditer(line):
                    month = int(match.group(1))
                    year_short = int(match.group(2))
                    year = 2000 + year_short if year_short < 80 else 1900 + year_short
                    if 1 <= month <= 12 and 2000 <= year <= 2100:
                        return (month, year)

        # Default to current date
        today = datetime.date.today()
        return (today.month, today.year)
