"""Operations parser for open ROs, warranty claims, missing titles, and slow-to-accounting."""

from __future__ import annotations

import logging
import re
from decimal import Decimal

from .base import BaseParser

logger = logging.getLogger(__name__)

_SKIP_PATTERNS = re.compile(
    r"^\s*(TOTAL|SUBTOTAL|GRAND\s+TOTAL|---|\*\*\*|===|PAGE\s+\d)",
    re.IGNORECASE,
)


class OperationsParser(BaseParser):
    """Parser for operations reports: open ROs, warranty claims, missing titles, slow-to-accounting."""

    SECTION_IDENTIFIERS = [
        # Open Repair Orders
        "OPEN RO",
        "OPEN REPAIR ORDER",
        "REPAIR ORDER",
        # Warranty Claims
        "SCHEDULE 263",
        "WARRANTY CLAIM",
        "WARRANTY",
        # Missing Titles
        "MISSING TITLE",
        "TITLE MISSING",
        "NO TITLE",
        # Slow to Accounting
        "SLOW TO ACCOUNTING",
        "SLOW-TO-ACCOUNTING",
        "SLOW ACCT",
    ]

    _RO_IDENTIFIERS = ["OPEN RO", "OPEN REPAIR ORDER", "REPAIR ORDER"]
    _WARRANTY_IDENTIFIERS = ["SCHEDULE 263", "WARRANTY CLAIM", "WARRANTY"]
    _TITLE_IDENTIFIERS = ["MISSING TITLE", "TITLE MISSING", "NO TITLE"]
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

    # --- Open Repair Orders ---

    def _parse_ro_page(self, page: dict) -> list[dict]:
        """Parse open repair order data."""
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

    # --- Warranty Claims ---

    def _parse_warranty_page(self, page: dict) -> list[dict]:
        """Parse warranty claim data (schedule 263)."""
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

    # --- Missing Titles ---

    def _parse_title_page(self, page: dict) -> list[dict]:
        """Parse missing title data."""
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

    # --- Slow to Accounting ---

    def _parse_slow_page(self, page: dict) -> list[dict]:
        """Parse slow-to-accounting data."""
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
