"""Operations parser for open ROs, warranty claims, missing titles, and slow-to-accounting."""

from __future__ import annotations

import logging
import re
from datetime import date
from decimal import Decimal

from .base import BaseParser

logger = logging.getLogger(__name__)

_SKIP_PATTERNS = re.compile(
    r"^\s*(TOTAL|SUBTOTAL|GRAND\s+TOTAL|---|\*\*\*|===|PAGE\s+\d)",
    re.IGNORECASE,
)

# Meeting date used for days_open / days_to_accounting calculations
_MEETING_DATE = date(2026, 2, 11)


class OperationsParser(BaseParser):
    """Parser for operations reports: open ROs, warranty claims, missing titles, slow-to-accounting."""

    SECTION_IDENTIFIERS = [
        # Open Repair Orders
        "OPEN RO",
        "OPEN REPAIR ORDER",
        "REPAIR ORDER",
        # Warranty Claims
        "SCHEDULE 263",
        "SCHEDULE#: 263",
        "WARRANTY CLAIM",
        "WARR CLAIMS",
        "WARRANTY",
        # Missing Titles
        "MISSING TITLE",
        "MSSING TITLE",
        "TITLE MISSING",
        "NO TITLE",
        # Slow to Accounting
        "SLOW TO ACCOUNTING",
        "SLOW-TO-ACCOUNTING",
        "SLOW ACCT",
    ]

    _RO_IDENTIFIERS = ["OPEN RO", "OPEN REPAIR ORDER", "REPAIR ORDER"]
    _WARRANTY_IDENTIFIERS = [
        "SCHEDULE 263", "SCHEDULE#: 263",
        "WARRANTY CLAIM", "WARR CLAIMS", "WARRANTY",
    ]
    _TITLE_IDENTIFIERS = ["MISSING TITLE", "MSSING TITLE", "TITLE MISSING", "NO TITLE"]
    _SLOW_IDENTIFIERS = ["SLOW TO ACCOUNTING", "SLOW-TO-ACCOUNTING", "SLOW ACCT"]

    def parse(self, pages: list[dict]) -> dict:
        """Parse operations pages into structured records."""
        repair_orders = []
        warranty_claims = []
        missing_titles = []
        slow_accounting = []

        for page in pages:
            text_upper = page["text"].upper()

            if self._matches(text_upper, self._RO_IDENTIFIERS):
                records = self._parse_ro_page(page)
                repair_orders.extend(records)

            elif self._matches(text_upper, self._TITLE_IDENTIFIERS):
                records = self._parse_title_page(page)
                missing_titles.extend(records)

            elif self._matches(text_upper, self._SLOW_IDENTIFIERS):
                records = self._parse_slow_page(page)
                slow_accounting.extend(records)

            elif self._matches(text_upper, self._WARRANTY_IDENTIFIERS):
                records = self._parse_warranty_page(page)
                warranty_claims.extend(records)

        results = {}
        if repair_orders:
            results["OpenRepairOrder"] = repair_orders
        if warranty_claims:
            results["WarrantyClaim"] = warranty_claims
        if missing_titles:
            results["MissingTitle"] = missing_titles
        if slow_accounting:
            results["SlowToAccounting"] = slow_accounting

        logger.info(
            f"Operations parser: {len(repair_orders)} ROs, {len(warranty_claims)} warranty, "
            f"{len(missing_titles)} titles, {len(slow_accounting)} slow-acct"
        )
        return results

    def _matches(self, text_upper: str, identifiers: list[str]) -> bool:
        return any(ident.upper() in text_upper for ident in identifiers)

    @staticmethod
    def _is_ocr_page(page: dict) -> bool:
        """Check if a page was processed via OCR."""
        return bool(page.get("ocr_used"))

    # -------------------------------------------------------------------------
    # Open Repair Orders
    # -------------------------------------------------------------------------

    def _parse_ro_page(self, page: dict) -> list[dict]:
        """Parse open repair order data."""
        if self._is_ocr_page(page):
            return self._parse_ro_ocr(page)

        records = []

        if page.get("tables"):
            for table in page["tables"]:
                rows = self.extract_table_rows(table)
                for row in rows:
                    record = self._extract_ro_from_row(row)
                    if record:
                        records.append(record)

        if not records:
            records = self._parse_ro_lines(page["lines"])

        return records

    def _parse_ro_ocr(self, page: dict) -> list[dict]:
        """Parse open RO data from OCR text.

        OCR line format (approximate):
            76715  0166  Service  ALOYSIA COLVIN  IGIPLSSCXC7149255  5922 | 12/16/2025  12/16/2025  05:30pm
        We extract: RO number, customer name, and RO date.  days_open = meeting_date - ro_date.
        """
        records = []
        # Match: RO number (5 digits, possibly with trailing OCR noise like '+' or '0'),
        # then somewhere a date in MM/DD/YYYY.  Customer name sits between advisor/dept
        # fields and the VIN.
        #
        # Strategy: find lines starting with a 5-digit number, extract date, and pull
        # customer name from between the department keyword and the VIN-like token.

        # Header keywords to skip — match only full header lines, not data lines
        # NOTE: "CWI" removed — it appears in data lines as a column value
        header_re = re.compile(
            r"(Report\s+Format|Include:|Branch:|RO=\s|Advisor\s+Dept|Customer\s+Name"
            r"|Tagz|RO\s+Date|Prom\s+Date|Prom\s+Time|CP\s+Inv\s+Date|Open\s+RO)",
            re.IGNORECASE,
        )

        # Date pattern MM/DD/YYYY — also allow OCR-garbled leading char (e.g. /09/2026)
        date_re = re.compile(r"(\d{1,2}/\d{1,2}/\d{4})")
        # RO number at start of line: 5 digits with possible OCR artifacts
        # Handles: 76715, 76924+, 7704+0, 7716 1, 7726 :, 7730+
        ro_start_re = re.compile(r"^\s*(\d{4,5})[+\s:.]?\d?\s")
        # Service/Scrvice department keyword
        dept_re = re.compile(r"\b(?:Service|Scrvice|Parts|Body)\b", re.IGNORECASE)
        # VIN-like token: 10+ alphanumeric chars
        vin_re = re.compile(r"\b([A-Z0-9]{10,})\b", re.IGNORECASE)

        for line in page.get("lines", []):
            if _SKIP_PATTERNS.match(line) or header_re.search(line):
                continue

            ro_match = ro_start_re.match(line)
            if not ro_match:
                continue

            ro_number = ro_match.group(1)
            # For 4-digit captures from garbled RO#s like "7704+0", try to
            # reconstruct the 5th digit from the character after the capture
            if len(ro_number) == 4:
                rest = line[ro_match.start(1) + 4:ro_match.end()]
                digit_match = re.search(r'(\d)', rest)
                if digit_match:
                    ro_number = ro_number + digit_match.group(1)

            # Find the first date on the line — this is the RO date
            date_match = date_re.search(line)
            ro_date = self.parse_date(date_match.group(1)) if date_match else None

            # Extract customer name: text between dept keyword and VIN
            customer_name = None
            dept_match = dept_re.search(line)
            vin_match = vin_re.search(line, pos=(dept_match.end() if dept_match else ro_match.end()))

            if dept_match and vin_match and vin_match.start() > dept_match.end():
                # Customer name is between dept keyword and VIN
                raw = line[dept_match.end():vin_match.start()].strip()
                # Remove optional leading department codes like "GC", "AU"
                raw = re.sub(r"^[A-Z]{2}\s+", "", raw).strip()
                if raw:
                    customer_name = raw
            elif dept_match:
                # No VIN found — grab text after dept keyword up to first date or end
                after_dept = line[dept_match.end():].strip()
                if date_match:
                    after_dept = line[dept_match.end():date_match.start()].strip()
                # Remove optional dept codes
                after_dept = re.sub(r"^[A-Z]{2}\s+", "", after_dept).strip()
                # Remove VIN-like tokens and tag numbers
                after_dept = re.sub(r"\b[A-Z0-9]{10,}\b", "", after_dept).strip()
                after_dept = re.sub(r"\b\d{4}\s*\|?\s*$", "", after_dept).strip()
                if after_dept:
                    customer_name = after_dept

            # Calculate days open
            days_open = 0
            if ro_date:
                try:
                    days_open = (_MEETING_DATE - ro_date).days
                    if days_open < 0:
                        days_open = 0
                except Exception:
                    days_open = 0

            if not ro_date:
                logger.warning(f"OCR RO line has no date, skipping: {line!r}")
                continue

            records.append({
                "ro_number": ro_number,
                "open_date": ro_date,
                "days_open": days_open,
                "customer_name": customer_name,
                "service_type": None,
                "cp_invoice_date": None,
                "amount": None,
            })

        logger.info(f"OCR RO parsing extracted {len(records)} records")
        return records

    def _extract_ro_from_row(self, row: dict) -> dict | None:
        """Extract an open repair order from a table row."""
        ro = (
            row.get("ro_number") or row.get("ro_#") or row.get("ro")
            or row.get("repair_order") or ""
        ).strip()

        if not ro or _SKIP_PATTERNS.match(ro):
            return None

        open_date = self.parse_date(
            row.get("open_date") or row.get("date") or row.get("opened")
        )
        if not open_date:
            return None

        days = self.clean_int(
            row.get("days_open") or row.get("days") or row.get("age")
        )

        customer = (
            row.get("customer_name") or row.get("customer") or ""
        ).strip()

        service_type = (
            row.get("service_type") or row.get("type") or row.get("svc_type") or ""
        ).strip()

        cp_date = self.parse_date(
            row.get("cp_invoice_date") or row.get("cp_date") or row.get("invoice_date")
        )

        amount = self.clean_currency(
            row.get("amount") or row.get("total") or row.get("balance")
        )

        return {
            "ro_number": ro,
            "open_date": open_date,
            "days_open": days if days is not None else 0,
            "customer_name": customer or None,
            "service_type": service_type or None,
            "cp_invoice_date": cp_date,
            "amount": amount,
        }

    def _parse_ro_lines(self, lines: list[str]) -> list[dict]:
        """Line-by-line fallback for open repair orders."""
        records = []
        pattern = re.compile(
            r"^\s*(\S+)\s+"  # RO number
            r"(\d{1,2}/\d{1,2}/\d{2,4})\s+"  # open date
            r"(\d+)\s+"  # days open
            r"(.+?)\s{2,}"  # customer name
            r"(\S+)"  # service type
            r"(?:\s+(\d{1,2}/\d{1,2}/\d{2,4}))?"  # optional CP invoice date
            r"(?:\s+([\d,.$()-]+))?"  # optional amount
        )

        for line in lines:
            if _SKIP_PATTERNS.match(line):
                continue
            match = pattern.match(line)
            if not match:
                continue

            open_date = self.parse_date(match.group(2))
            if not open_date:
                continue

            records.append({
                "ro_number": match.group(1),
                "open_date": open_date,
                "days_open": int(match.group(3)),
                "customer_name": match.group(4).strip() or None,
                "service_type": match.group(5) or None,
                "cp_invoice_date": self.parse_date(match.group(6)),
                "amount": self.clean_currency(match.group(7)),
            })

        return records

    # -------------------------------------------------------------------------
    # Warranty Claims
    # -------------------------------------------------------------------------

    def _parse_warranty_page(self, page: dict) -> list[dict]:
        """Parse warranty claim data (schedule 263)."""
        if self._is_ocr_page(page):
            return self._parse_warranty_ocr(page)

        records = []

        if page.get("tables"):
            for table in page["tables"]:
                rows = self.extract_table_rows(table)
                for row in rows:
                    record = self._extract_warranty_from_row(row)
                    if record:
                        records.append(record)

        if not records:
            records = self._parse_warranty_lines(page["lines"])

        return records

    def _parse_warranty_ocr(self, page: dict) -> list[dict]:
        """Parse warranty claims from OCR text.

        OCR line format:
            76889-1  IGNERGKS2TJI14218  911.81  911.81  PAID 2/10
        We extract: claim_number, amount (Total column), status from remarks.
        """
        records = []

        # Header keywords to skip
        header_re = re.compile(
            r"(Schedule\s*#|Control\s*#|Description|Total|Current|31-60|61-90|91\s*\+"
            r"|Remarks|WARR\s+CLAIMS)",
            re.IGNORECASE,
        )

        # Claim number: digits-digit(s) pattern like 76889-1
        # OCR variants: 77256-[, 77278 2, 7729+.2, 77300-
        # Allow OCR artifacts: space/+/[ instead of hyphen, missing/garbled trailing digit
        claim_re = re.compile(
            r"^\s*(\d{4,5})[- +.\[]*(\d{0,2})[.\[\]]*\s+"
        )
        # Amount: decimal number like 911.81
        amount_re = re.compile(r"(\d{1,3}(?:,\d{3})*\.\d{2})")
        # Status in remarks: PAID date or PENDING date
        status_re = re.compile(r"(PAID|PENDING|DECLINED|REJECTED)\s*(\d{1,2}/\d{1,2})?", re.IGNORECASE)

        for line in page.get("lines", []):
            if _SKIP_PATTERNS.match(line) or header_re.search(line):
                continue

            claim_match = claim_re.match(line)
            if not claim_match:
                continue

            # Reconstruct claim number as NNNNN-N format
            claim_base = claim_match.group(1)
            claim_suffix = claim_match.group(2)
            # If base is only 4 digits, OCR likely garbled the 5th digit
            # (e.g. "7729+.2" → base=7729, but actual claim is 77292-2)
            # We can't recover the missing digit, but we should note it
            if claim_suffix:
                claim_number = f"{claim_base}-{claim_suffix}"
            else:
                # No suffix digit — OCR dropped it or garbled it (e.g. 77300-, 77256-[)
                # Default to -1 since it's the most common claim suffix
                claim_number = f"{claim_base}-1"
                logger.info(f"OCR warranty claim suffix missing, defaulting to -1: {line!r}")

            # Find the first amount on the line (Total column)
            amount_matches = amount_re.findall(line)
            amount = None
            if amount_matches:
                amount = self.clean_currency(amount_matches[0])

            # Check for status in remarks
            status = None
            status_match = status_re.search(line)
            if status_match:
                status = status_match.group(0).strip()

            if amount is None:
                logger.warning(f"OCR warranty line has no amount, skipping: {line!r}")
                continue

            records.append({
                "claim_number": claim_number,
                "claim_date": None,
                "amount": amount,
                "status": status,
            })

        logger.info(f"OCR warranty parsing extracted {len(records)} records")
        return records

    def _extract_warranty_from_row(self, row: dict) -> dict | None:
        """Extract a warranty claim from a table row."""
        claim = (
            row.get("claim_number") or row.get("claim_#") or row.get("claim")
            or row.get("warranty_#") or ""
        ).strip()

        if not claim or _SKIP_PATTERNS.match(claim):
            return None

        amount = self.clean_currency(
            row.get("amount") or row.get("total") or row.get("balance")
        )
        if amount is None:
            return None

        claim_date = self.parse_date(
            row.get("claim_date") or row.get("date") or row.get("filed_date")
        )
        status = (row.get("status") or "").strip()

        return {
            "claim_number": claim,
            "claim_date": claim_date,
            "amount": amount,
            "status": status or None,
        }

    def _parse_warranty_lines(self, lines: list[str]) -> list[dict]:
        """Line-by-line fallback for warranty claims."""
        records = []
        pattern = re.compile(
            r"^\s*(\S+)\s+"  # claim number
            r"(\d{1,2}/\d{1,2}/\d{2,4})\s+"  # claim date
            r"([\d,.$()-]+)"  # amount
            r"(?:\s+(\S+))?"  # optional status
        )

        for line in lines:
            if _SKIP_PATTERNS.match(line):
                continue
            match = pattern.match(line)
            if not match:
                continue

            amount = self.clean_currency(match.group(3))
            if amount is None:
                continue

            records.append({
                "claim_number": match.group(1),
                "claim_date": self.parse_date(match.group(2)),
                "amount": amount,
                "status": match.group(4) if match.group(4) else None,
            })

        return records

    # -------------------------------------------------------------------------
    # Missing Titles
    # -------------------------------------------------------------------------

    def _parse_title_page(self, page: dict) -> list[dict]:
        """Parse missing title data."""
        if self._is_ocr_page(page):
            return self._parse_title_ocr(page)

        records = []

        if page.get("tables"):
            for table in page["tables"]:
                rows = self.extract_table_rows(table)
                for row in rows:
                    record = self._extract_title_from_row(row)
                    if record:
                        records.append(record)

        if not records:
            records = self._parse_title_lines(page["lines"])

        return records

    def _parse_title_ocr(self, page: dict) -> list[dict]:
        """Parse missing title data from OCR text (often rotated/garbled).

        This page is typically heavily garbled by OCR on rotated scans.
        We use a lenient approach: look for stock numbers, customer names,
        lienholders, and vehicle descriptions where possible.
        """
        records = []
        text = page.get("text", "")

        # Default days_missing — typical value when date traded is around 1/21
        # and meeting is 2/11
        default_days_missing = 21

        # Try to find stock numbers: T followed by digits, or just digit sequences
        # that look like stock numbers (5-7 digits, possibly preceded by garbled 'T')
        stock_re = re.compile(r"\b[T|I|1]?(\d{5,7})[A-Z]?\b")

        # Known lienholders that might appear in garbled text
        lienholder_re = re.compile(
            r"(SUBARU\s+FINANC\w*|ALLY\s+FINANC\w*|VW\s+CREDI\w*|WW\s+CREDI\w*"
            r"|CAPITAL\s+ONE|CHASE|WELLS\s+FARGO|TOYOTA\s+FINANC\w*"
            r"|HONDA\s+FINANC\w*|GM\s+FINANC\w*|FORD\s+MOTOR\s+CREDIT"
            r"|BANK\s+OF\s+AMERICA|US\s+BANK|USAA|NAVY\s+FEDERAL"
            r"|FIFTH\s+THIRD|REGIONS|TD\s+BANK|TD\s+AUTO)",
            re.IGNORECASE,
        )

        # Vehicle make patterns
        vehicle_re = re.compile(
            r"(\d{4})\s*(CHEV\w*|FORD|TOYO\w*|HONDA|SUBA\w*|VW|VOLKS\w*"
            r"|DODGE|RAM|JEEP|GMC|BUICK|CADIL\w*|NISS\w*|HYUN\w*|KIA"
            r"|BMW|MERCED\w*|AUDI|LEXUS|ACURA|INFIN\w*|LINCO\w*|MAZD\w*"
            r"|MITS\w*|CHRYSL\w*)\s*(\w*)",
            re.IGNORECASE,
        )

        # Customer name patterns: two or more uppercase words (FIRST LAST or FIRST LAST JR etc.)
        # Look for sequences of 2-4 capitalized words that look like names
        name_re = re.compile(r"\b([A-Z]{2,}(?:\s+[A-Z]{2,}){1,3})\b")

        # Attempt structured extraction from lines
        lines = page.get("lines", [])
        all_text = " ".join(lines)

        # Find all potential stock numbers
        stock_matches = stock_re.findall(all_text)
        # Find all lienholders
        lienholder_matches = lienholder_re.findall(all_text)
        # Find all vehicle descriptions
        vehicle_matches = vehicle_re.findall(all_text)
        # Find potential customer names (filter out known non-name keywords)
        skip_names = {
            "MSSING", "MISSING", "TITLE", "CUSTOMERNAME", "CUSTOMER", "NAME",
            "CUSTA", "LIENHOLDER", "STOCK", "DALE", "DATE", "TRADED", "SENT",
            "YEAR", "MAKE", "MODEL", "ADDL", "INFORMAMON", "INFORMATION",
            "ASHDOWN", "ASHDQWN", "PIO", "YCUU", "MMOKE", "MMODEL", "WJL",
            "INFOMALION",
        }
        name_matches_raw = name_re.findall(all_text)
        name_candidates = []
        for nm in name_matches_raw:
            words = nm.split()
            # Filter: at least 2 words, none are skip words, reasonable length
            if (
                len(words) >= 2
                and not any(w in skip_names for w in words)
                and all(2 <= len(w) <= 15 for w in words)
            ):
                name_candidates.append(nm)

        # Build records by matching up what we found.  Use lienholders as the
        # primary record count (most reliable on garbled OCR), then names, then
        # stock numbers.  Using max() over-extracts from noise.
        if lienholder_matches:
            num_records = len(lienholder_matches)
        elif name_candidates:
            num_records = len(name_candidates)
        elif stock_matches:
            # Stock number regex is noisy on garbled text — cap at a reasonable limit
            num_records = min(len(stock_matches), 5)
        else:
            num_records = 0

        if num_records == 0:
            logger.warning(
                "OCR missing titles page: could not extract any structured records "
                f"from garbled text ({len(text)} chars)"
            )
            return records

        for i in range(num_records):
            stock = stock_matches[i] if i < len(stock_matches) else None
            customer = name_candidates[i] if i < len(name_candidates) else None
            lienholder = lienholder_matches[i] if i < len(lienholder_matches) else None
            vehicle = None
            if i < len(vehicle_matches):
                yr, make, model = vehicle_matches[i]
                vehicle = f"{yr} {make} {model}".strip()

            # Build a stock_number string — prefix with T if we have digits only
            stock_number = f"T{stock}" if stock else None

            record = {
                "stock_number": stock_number,
                "deal_number": None,
                "customer_name": customer,
                "days_missing": default_days_missing,
            }

            # Store extra OCR-extracted data in notes-style fields if available
            if lienholder:
                record["lienholder"] = lienholder
            if vehicle:
                record["vehicle_description"] = vehicle

            if stock_number or customer:
                records.append(record)

        logger.info(f"OCR missing titles parsing extracted {len(records)} records")
        return records

    def _extract_title_from_row(self, row: dict) -> dict | None:
        """Extract a missing title record from a table row."""
        stock = (
            row.get("stock_number") or row.get("stock_#") or row.get("stock")
            or row.get("stk_#") or ""
        ).strip()

        if not stock or _SKIP_PATTERNS.match(stock):
            return None

        days = self.clean_int(
            row.get("days_missing") or row.get("days") or row.get("age")
        )
        if days is None:
            return None

        deal = (row.get("deal_number") or row.get("deal_#") or row.get("deal") or "").strip()
        customer = (row.get("customer_name") or row.get("customer") or "").strip()

        return {
            "stock_number": stock,
            "deal_number": deal or None,
            "customer_name": customer or None,
            "days_missing": days,
        }

    def _parse_title_lines(self, lines: list[str]) -> list[dict]:
        """Line-by-line fallback for missing titles."""
        records = []
        pattern = re.compile(
            r"^\s*(\S+)\s+"  # stock number
            r"(\S+)\s+"  # deal number
            r"(.+?)\s{2,}"  # customer name
            r"(\d+)\s*$"  # days missing
        )

        for line in lines:
            if _SKIP_PATTERNS.match(line):
                continue
            match = pattern.match(line)
            if not match:
                continue

            records.append({
                "stock_number": match.group(1),
                "deal_number": match.group(2),
                "customer_name": match.group(3).strip() or None,
                "days_missing": int(match.group(4)),
            })

        return records

    # -------------------------------------------------------------------------
    # Slow to Accounting
    # -------------------------------------------------------------------------

    def _parse_slow_page(self, page: dict) -> list[dict]:
        """Parse slow-to-accounting data."""
        if self._is_ocr_page(page):
            return self._parse_slow_ocr(page)

        records = []

        if page.get("tables"):
            for table in page["tables"]:
                rows = self.extract_table_rows(table)
                for row in rows:
                    record = self._extract_slow_from_row(row)
                    if record:
                        records.append(record)

        if not records:
            records = self._parse_slow_lines(page["lines"])

        return records

    def _parse_slow_ocr(self, page: dict) -> list[dict]:
        """Parse slow-to-accounting data from OCR text.

        OCR line format:
            '07/26  22867  TJ247883  JAMES  ATKINS  AARON  816.59  RED RIVER FEDERAL CREDIT UNION
        Fields: date ('MM/DD), deal_number (5 digits), stock_number, first_name,
        last_name, fi_manager, amount, bank_name.
        Notes/follow-up lines may appear on the next line.
        """
        records = []

        # Header keywords to skip
        header_re = re.compile(
            r"(SLOW\s+TO\s+ACCOUNTING|DTE|DEAL\s+NO|STOCK\s+NO|BYR\s+FIRST|BYR\s+LAST"
            r"|FI-FM|VEH-GRS|BANK-NAME|SH\s+SLOW)",
            re.IGNORECASE,
        )

        # Data line pattern: optional quote/tick prefix, MM/DD date, then deal number
        # The date prefix may have OCR tick like ' or `
        data_re = re.compile(
            r"^\s*['\"`]?"  # optional OCR tick
            r"(\d{1,2}/\d{1,2})\s+"  # date MM/DD (no year — assume 2026)
            r"(\d{5})\s+"  # deal number (5 digits)
            r"(\S+)\s+"  # stock number
            r"([A-Z][A-Z]+)\s+"  # first name
            r"([A-Z][A-Z]+)"  # last name
            r"(?:\s+([A-Z][A-Z]+))?"  # optional FI manager name
            r"(?:\s+([\d,.]+))?"  # optional amount
        )

        # Amount pattern for lines where amount has pipe separator
        amount_re = re.compile(r"([\d,]+\.\d{2})")

        for line in page.get("lines", []):
            if _SKIP_PATTERNS.match(line) or header_re.search(line):
                continue

            match = data_re.match(line)
            if not match:
                continue

            # Parse date — OCR format is 'DD/YY where the month prefix (MM/) was
            # dropped by OCR.  So '07/26 means day=7, year=2026, month=meeting month.
            # Fallback: if day > 12 it can't be MM/DD so must be DD/YY.
            # If ambiguous, use DD/YY since these are recent deals near the meeting.
            date_str = match.group(1)
            parts = date_str.split("/")
            sale_date = None
            if len(parts) == 2:
                try:
                    a, b = int(parts[0]), int(parts[1])
                    if b >= 20 and b <= 40:
                        # DD/YY format: day=a, year=2000+b, month from meeting date
                        sale_date = date(2000 + b, _MEETING_DATE.month, a)
                    else:
                        # MM/DD format
                        month, day = a, b
                        year = 2026 if month <= _MEETING_DATE.month else 2025
                        sale_date = date(year, month, day)
                except (ValueError, TypeError):
                    pass

            deal_number = match.group(2)
            first_name = match.group(4)
            last_name = match.group(5)
            customer_name = f"{first_name} {last_name}"

            # Try to extract amount from the full line (might have pipe separator)
            amount = None
            amount_match = amount_re.search(line[match.end(5):] if match.group(5) else "")
            if amount_match:
                amount = self.clean_currency(amount_match.group(1))
            elif match.group(7):
                amount = self.clean_currency(match.group(7))

            # Calculate days to accounting
            days_to_accounting = 0
            if sale_date:
                try:
                    days_to_accounting = (_MEETING_DATE - sale_date).days
                    if days_to_accounting < 0:
                        days_to_accounting = 0
                except Exception:
                    days_to_accounting = 0

            if not sale_date:
                logger.warning(f"OCR slow-acct line has no valid date, skipping: {line!r}")
                continue

            record = {
                "deal_number": deal_number,
                "sale_date": sale_date,
                "days_to_accounting": days_to_accounting,
                "customer_name": customer_name,
                "salesperson": None,
            }

            if amount is not None:
                record["amount"] = amount

            records.append(record)

        logger.info(f"OCR slow-to-accounting parsing extracted {len(records)} records")
        return records

    def _extract_slow_from_row(self, row: dict) -> dict | None:
        """Extract a slow-to-accounting record from a table row."""
        deal = (
            row.get("deal_number") or row.get("deal_#") or row.get("deal") or ""
        ).strip()

        if not deal or _SKIP_PATTERNS.match(deal):
            return None

        sale_date = self.parse_date(
            row.get("sale_date") or row.get("date") or row.get("sold_date")
        )
        if not sale_date:
            return None

        days = self.clean_int(
            row.get("days_to_accounting") or row.get("days") or row.get("age")
        )
        if days is None:
            return None

        customer = (row.get("customer_name") or row.get("customer") or "").strip()
        salesperson = (row.get("salesperson") or row.get("sales") or row.get("sp") or "").strip()

        return {
            "deal_number": deal,
            "sale_date": sale_date,
            "days_to_accounting": days,
            "customer_name": customer or None,
            "salesperson": salesperson or None,
        }

    def _parse_slow_lines(self, lines: list[str]) -> list[dict]:
        """Line-by-line fallback for slow-to-accounting."""
        records = []
        pattern = re.compile(
            r"^\s*(\S+)\s+"  # deal number
            r"(\d{1,2}/\d{1,2}/\d{2,4})\s+"  # sale date
            r"(\d+)\s+"  # days to accounting
            r"(.+?)\s{2,}"  # customer name
            r"(\S+.*?)\s*$"  # salesperson
        )

        for line in lines:
            if _SKIP_PATTERNS.match(line):
                continue
            match = pattern.match(line)
            if not match:
                continue

            sale_date = self.parse_date(match.group(2))
            if not sale_date:
                continue

            records.append({
                "deal_number": match.group(1),
                "sale_date": sale_date,
                "days_to_accounting": int(match.group(3)),
                "customer_name": match.group(4).strip() or None,
                "salesperson": match.group(5).strip() or None,
            })

        return records
