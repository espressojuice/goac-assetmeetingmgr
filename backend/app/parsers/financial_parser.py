"""Financial parser for receivables, F&I chargebacks, CIT, prepaids, and policy adjustments."""

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

# Schedule/GL to receivable type mapping
_RECEIVABLE_TYPE_MAP = {
    "200": "parts_service_200",
    "220": "wholesale_220",
    "2612": "factory_2612",
}


class FinancialParser(BaseParser):
    """Parser for financial reports: receivables, F&I chargebacks, CIT, prepaids, policy adjustments."""

    SECTION_IDENTIFIERS = [
        # Receivables
        "SCHEDULE 200",
        "SCHEDULE 220",
        "GL 2612",
        "P&S RECEIVABLE",
        "PARTS & SERVICE RECEIVABLE",
        "WHOLESALE RECEIVABLE",
        "FACTORY RECEIVABLE",
        # F&I Chargebacks
        "CHARGEBACK",
        "F&I CHARGE",
        "FINANCE CHARGE",
        # Contracts in Transit
        "SCHEDULE 205",
        "CONTRACT IN TRANSIT",
        "CONTRACTS IN TRANSIT",
        "CIT",
        # Prepaids
        "GL 2741",
        "PREPAID",
        # Policy Adjustments
        "GL 15A",
        "GL 15B",
        "POLICY ADJUST",
    ]

    _RECEIVABLE_IDENTIFIERS = [
        "SCHEDULE 200", "SCHEDULE 220", "GL 2612",
        "P&S RECEIVABLE", "PARTS & SERVICE RECEIVABLE",
        "WHOLESALE RECEIVABLE", "FACTORY RECEIVABLE",
    ]
    _CHARGEBACK_IDENTIFIERS = ["CHARGEBACK", "F&I CHARGE", "FINANCE CHARGE"]
    _CIT_IDENTIFIERS = [
        "SCHEDULE 205", "CONTRACT IN TRANSIT", "CONTRACTS IN TRANSIT", "CIT",
    ]
    _PREPAID_IDENTIFIERS = ["GL 2741", "PREPAID"]
    _POLICY_IDENTIFIERS = ["GL 15A", "GL 15B", "POLICY ADJUST"]

    @classmethod
    def can_handle(cls, page_text: str) -> bool:
        """Override can_handle to add context-aware matching for short identifiers.

        "850" and "851" are too short for simple substring matching — they could
        appear in addresses, amounts, etc. We require "CHARGEBACK" or "F&I" context.
        """
        text_upper = page_text.upper()

        # Check non-chargeback identifiers normally
        non_chargeback = [
            ident for ident in cls.SECTION_IDENTIFIERS
            if ident not in cls._CHARGEBACK_IDENTIFIERS
        ]
        if any(ident.upper() in text_upper for ident in non_chargeback):
            return True

        # For chargebacks, require explicit context words
        if any(ident.upper() in text_upper for ident in cls._CHARGEBACK_IDENTIFIERS):
            return True

        # Also check for account 850/851 but only with F&I/chargeback context
        has_850_851 = bool(re.search(r"\b85[01]A?\b", text_upper))
        has_context = "CHARGEBACK" in text_upper or "F&I" in text_upper or "F & I" in text_upper
        if has_850_851 and has_context:
            return True

        return False

    def parse(self, pages: list[dict]) -> dict:
        """Parse financial pages into structured records."""
        receivables = []
        chargebacks = []
        cit_records = []
        prepaids = []
        adjustments = []

        for page in pages:
            text_upper = page["text"].upper()

            if self._matches(text_upper, self._RECEIVABLE_IDENTIFIERS):
                records = self._parse_receivable_page(page)
                receivables.extend(records)

            if self._has_chargeback_context(text_upper):
                records = self._parse_chargeback_page(page)
                chargebacks.extend(records)

            if self._matches(text_upper, self._CIT_IDENTIFIERS):
                records = self._parse_cit_page(page)
                cit_records.extend(records)

            if self._matches(text_upper, self._PREPAID_IDENTIFIERS):
                records = self._parse_prepaid_page(page)
                prepaids.extend(records)

            if self._matches(text_upper, self._POLICY_IDENTIFIERS):
                records = self._parse_policy_page(page)
                adjustments.extend(records)

        results = {}
        if receivables:
            results["Receivable"] = receivables
        if chargebacks:
            results["FIChargeback"] = chargebacks
        if cit_records:
            results["ContractInTransit"] = cit_records
        if prepaids:
            results["Prepaid"] = prepaids
        if adjustments:
            results["PolicyAdjustment"] = adjustments

        logger.info(
            f"Financial parser: {len(receivables)} receivables, {len(chargebacks)} chargebacks, "
            f"{len(cit_records)} CIT, {len(prepaids)} prepaids, {len(adjustments)} adjustments"
        )
        return results

    def _matches(self, text_upper: str, identifiers: list[str]) -> bool:
        return any(ident.upper() in text_upper for ident in identifiers)

    def _has_chargeback_context(self, text_upper: str) -> bool:
        """Check for chargeback section with context awareness."""
        if any(ident.upper() in text_upper for ident in self._CHARGEBACK_IDENTIFIERS):
            return True
        has_850_851 = bool(re.search(r"\b85[01]A?\b", text_upper))
        has_context = "CHARGEBACK" in text_upper or "F&I" in text_upper or "F & I" in text_upper
        return has_850_851 and has_context

    # --- Receivables ---

    def _parse_receivable_page(self, page: dict) -> list[dict]:
        """Parse receivable aging data for schedules 200, 220, GL 2612."""
        records = []
        text_upper = page["text"].upper()

        # Determine which receivable type(s) are on this page
        for schedule_num, recv_type in _RECEIVABLE_TYPE_MAP.items():
            key = f"SCHEDULE {schedule_num}" if schedule_num != "2612" else f"GL {schedule_num}"
            if key not in text_upper:
                # Also check for descriptive names
                name_checks = {
                    "200": ["P&S RECEIVABLE", "PARTS & SERVICE RECEIVABLE"],
                    "220": ["WHOLESALE RECEIVABLE"],
                    "2612": ["FACTORY RECEIVABLE"],
                }
                if not any(name in text_upper for name in name_checks.get(schedule_num, [])):
                    continue

            record = self._extract_receivable(page, schedule_num, recv_type)
            if record:
                records.append(record)

        return records

    def _extract_receivable(self, page: dict, schedule_num: str, recv_type: str) -> dict | None:
        """Extract aging bucket data for a receivable type."""
        aging = {"current_balance": None, "over_30": None, "over_60": None, "over_90": None, "total_balance": None}

        # Try table extraction
        if page.get("tables"):
            for table in page["tables"]:
                rows = self.extract_table_rows(table)
                for row in rows:
                    self._extract_aging_from_row(row, aging)

        # Fall back to line parsing
        if aging["total_balance"] is None:
            self._extract_aging_from_lines(page["lines"], aging)

        # Need at least a total to create a record
        if aging["total_balance"] is None and aging["current_balance"] is None:
            return None

        return {
            "receivable_type": recv_type,
            "schedule_number": schedule_num,
            "current_balance": aging["current_balance"] or Decimal("0"),
            "over_30": aging["over_30"] or Decimal("0"),
            "over_60": aging["over_60"] or Decimal("0"),
            "over_90": aging["over_90"] or Decimal("0"),
            "total_balance": aging["total_balance"] or (aging["current_balance"] or Decimal("0")),
        }

    def _extract_aging_from_row(self, row: dict, aging: dict) -> None:
        """Extract aging bucket values from a table row."""
        current = self.clean_currency(
            row.get("current") or row.get("current_balance") or row.get("0-30")
        )
        if current is not None:
            aging["current_balance"] = current

        over_30 = self.clean_currency(
            row.get("over_30") or row.get("31-60") or row.get("30+") or row.get("31_60")
        )
        if over_30 is not None:
            aging["over_30"] = over_30

        over_60 = self.clean_currency(
            row.get("over_60") or row.get("61-90") or row.get("60+") or row.get("61_90")
        )
        if over_60 is not None:
            aging["over_60"] = over_60

        over_90 = self.clean_currency(
            row.get("over_90") or row.get("90+") or row.get("91+") or row.get("over_90_balance")
        )
        if over_90 is not None:
            aging["over_90"] = over_90

        total = self.clean_currency(
            row.get("total") or row.get("total_balance") or row.get("balance")
        )
        if total is not None:
            aging["total_balance"] = total

    def _extract_aging_from_lines(self, lines: list[str], aging: dict) -> None:
        """Extract aging data from text lines."""
        patterns = [
            ("current_balance", re.compile(r"CURRENT.*?([\d,.$()-]+)\s*$", re.IGNORECASE)),
            ("over_30", re.compile(r"(?:OVER\s+30|31[-\s]60|30\+).*?([\d,.$()-]+)\s*$", re.IGNORECASE)),
            ("over_60", re.compile(r"(?:OVER\s+60|61[-\s]90|60\+).*?([\d,.$()-]+)\s*$", re.IGNORECASE)),
            ("over_90", re.compile(r"(?:OVER\s+90|91\+|90\+).*?([\d,.$()-]+)\s*$", re.IGNORECASE)),
            ("total_balance", re.compile(r"TOTAL.*?([\d,.$()-]+)\s*$", re.IGNORECASE)),
        ]
        for line in lines:
            for field, pattern in patterns:
                if aging[field] is not None:
                    continue
                match = pattern.search(line)
                if match:
                    val = self.clean_currency(match.group(1))
                    if val is not None:
                        aging[field] = val

    # --- F&I Chargebacks ---

    def _parse_chargeback_page(self, page: dict) -> list[dict]:
        """Parse F&I chargeback data (accounts 850, 850A, 851, 851A)."""
        records = []

        # Try table extraction
        if page.get("tables"):
            for table in page["tables"]:
                rows = self.extract_table_rows(table)
                for row in rows:
                    record = self._extract_chargeback_from_row(row)
                    if record:
                        records.append(record)

        # Fall back to line parsing
        if not records:
            records = self._parse_chargeback_lines(page["lines"])

        return records

    def _extract_chargeback_from_row(self, row: dict) -> dict | None:
        """Extract a chargeback record from a table row."""
        account = (
            row.get("account_number") or row.get("account") or row.get("acct")
            or row.get("account_#") or row.get("acct_#") or ""
        ).strip()

        if not account:
            # Check if any cell contains an 850/851 pattern
            for val in row.values():
                if re.match(r"^\s*85[01]A?\s*$", str(val)):
                    account = str(val).strip()
                    break

        if not account or not re.match(r"85[01]A?", account):
            return None

        description = (
            row.get("account_description") or row.get("description")
            or row.get("desc") or ""
        ).strip()

        current = self.clean_currency(
            row.get("current_balance") or row.get("current") or row.get("balance")
        )
        over_90 = self.clean_currency(
            row.get("over_90_balance") or row.get("over_90") or row.get("90+")
        )

        if current is None and over_90 is None:
            return None

        return {
            "account_number": account,
            "account_description": description or None,
            "current_balance": current or Decimal("0"),
            "over_90_balance": over_90 or Decimal("0"),
        }

    def _parse_chargeback_lines(self, lines: list[str]) -> list[dict]:
        """Parse chargeback data from text lines."""
        records = []
        pattern = re.compile(
            r"^\s*(85[01]A?)\s+"  # account number
            r"(.*?)\s{2,}"  # description
            r"([\d,.$()-]+)"  # current balance
            r"(?:\s+([\d,.$()-]+))?"  # optional over-90 balance
        )

        for line in lines:
            match = pattern.match(line)
            if not match:
                continue

            current = self.clean_currency(match.group(3))
            over_90 = self.clean_currency(match.group(4))

            records.append({
                "account_number": match.group(1),
                "account_description": match.group(2).strip() or None,
                "current_balance": current or Decimal("0"),
                "over_90_balance": over_90 or Decimal("0"),
            })

        return records

    # --- Contracts in Transit ---

    def _parse_cit_page(self, page: dict) -> list[dict]:
        """Parse contracts in transit (schedule 205)."""
        records = []

        if page.get("tables"):
            for table in page["tables"]:
                rows = self.extract_table_rows(table)
                for row in rows:
                    record = self._extract_cit_from_row(row)
                    if record:
                        records.append(record)

        if not records:
            records = self._parse_cit_lines(page["lines"])

        return records

    def _extract_cit_from_row(self, row: dict) -> dict | None:
        """Extract a contract in transit from a table row."""
        deal = (
            row.get("deal_number") or row.get("deal_#") or row.get("deal")
            or row.get("contract_#") or ""
        ).strip()

        if not deal or _SKIP_PATTERNS.match(deal):
            return None

        sale_date = self.parse_date(
            row.get("sale_date") or row.get("date") or row.get("sold_date")
        )
        if not sale_date:
            return None

        days = self.clean_int(
            row.get("days_in_transit") or row.get("days") or row.get("age")
        )
        amount = self.clean_currency(
            row.get("amount") or row.get("balance") or row.get("contract_amount")
        )

        if amount is None:
            return None

        return {
            "deal_number": deal,
            "customer_name": (row.get("customer_name") or row.get("customer") or "").strip() or None,
            "sale_date": sale_date,
            "days_in_transit": days if days is not None else 0,
            "amount": amount,
            "lender": (row.get("lender") or row.get("bank") or row.get("finance_source") or "").strip() or None,
        }

    def _parse_cit_lines(self, lines: list[str]) -> list[dict]:
        """Line-by-line fallback for contracts in transit."""
        records = []
        pattern = re.compile(
            r"^\s*(\S+)\s+"  # deal number
            r"(.+?)\s{2,}"  # customer name
            r"(\d{1,2}/\d{1,2}/\d{2,4})\s+"  # sale date
            r"(\d+)\s+"  # days
            r"([\d,.$()-]+)"  # amount
            r"(?:\s+(.+))?"  # optional lender
        )

        for line in lines:
            if _SKIP_PATTERNS.match(line):
                continue
            match = pattern.match(line)
            if not match:
                continue

            sale_date = self.parse_date(match.group(3))
            amount = self.clean_currency(match.group(5))
            if not sale_date or amount is None:
                continue

            records.append({
                "deal_number": match.group(1),
                "customer_name": match.group(2).strip() or None,
                "sale_date": sale_date,
                "days_in_transit": int(match.group(4)),
                "amount": amount,
                "lender": match.group(6).strip() if match.group(6) else None,
            })

        return records

    # --- Prepaids ---

    def _parse_prepaid_page(self, page: dict) -> list[dict]:
        """Parse prepaid line items (GL 2741)."""
        records = []

        if page.get("tables"):
            for table in page["tables"]:
                rows = self.extract_table_rows(table)
                for row in rows:
                    record = self._extract_prepaid_from_row(row)
                    if record:
                        records.append(record)

        if not records:
            records = self._parse_prepaid_lines(page["lines"])

        return records

    def _extract_prepaid_from_row(self, row: dict) -> dict | None:
        """Extract a prepaid from a table row."""
        gl = (row.get("gl_account") or row.get("gl") or row.get("account") or "").strip()
        description = (row.get("description") or row.get("desc") or "").strip()
        amount = self.clean_currency(
            row.get("amount") or row.get("balance") or row.get("value")
        )

        if amount is None:
            return None
        if not description:
            return None

        return {
            "gl_account": gl or "2741",
            "description": description,
            "amount": amount,
        }

    def _parse_prepaid_lines(self, lines: list[str]) -> list[dict]:
        """Line-by-line fallback for prepaids."""
        records = []
        pattern = re.compile(
            r"^\s*(\S+)\s+"  # GL account
            r"(.+?)\s{2,}"  # description
            r"([\d,.$()-]+)\s*$"  # amount
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
                "gl_account": match.group(1),
                "description": match.group(2).strip(),
                "amount": amount,
            })

        return records

    # --- Policy Adjustments ---

    def _parse_policy_page(self, page: dict) -> list[dict]:
        """Parse policy adjustments (GL 15A/15B)."""
        records = []

        if page.get("tables"):
            for table in page["tables"]:
                rows = self.extract_table_rows(table)
                for row in rows:
                    record = self._extract_policy_from_row(row)
                    if record:
                        records.append(record)

        if not records:
            records = self._parse_policy_lines(page["lines"])

        return records

    def _extract_policy_from_row(self, row: dict) -> dict | None:
        """Extract a policy adjustment from a table row."""
        gl = (row.get("gl_account") or row.get("gl") or row.get("account") or "").strip()
        description = (row.get("description") or row.get("desc") or "").strip()
        amount = self.clean_currency(
            row.get("amount") or row.get("balance") or row.get("adjustment")
        )
        adj_date = self.parse_date(
            row.get("adjustment_date") or row.get("date") or row.get("adj_date")
        )

        if amount is None:
            return None

        return {
            "gl_account": gl or "15",
            "description": description or None,
            "amount": amount,
            "adjustment_date": adj_date,
        }

    def _parse_policy_lines(self, lines: list[str]) -> list[dict]:
        """Line-by-line fallback for policy adjustments."""
        records = []
        pattern = re.compile(
            r"^\s*(\S+)\s+"  # GL account
            r"(.+?)\s{2,}"  # description
            r"([\d,.$()-]+)"  # amount
            r"(?:\s+(\d{1,2}/\d{1,2}/\d{2,4}))?"  # optional date
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
                "gl_account": match.group(1),
                "description": match.group(2).strip() or None,
                "amount": amount,
                "adjustment_date": self.parse_date(match.group(4)),
            })

        return records
