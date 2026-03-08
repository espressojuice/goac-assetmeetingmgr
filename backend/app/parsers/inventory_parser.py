"""Inventory parser for R&R schedules 237, 240, and 277."""

from __future__ import annotations

import logging
import re
from decimal import Decimal

from .base import BaseParser

logger = logging.getLogger(__name__)

# Patterns to skip totals/subtotals/header lines
_SKIP_PATTERNS = re.compile(
    r"^\s*(TOTAL|SUBTOTAL|GRAND\s+TOTAL|---|\*\*\*|===|PAGE\s+\d|SCHEDULE\s+\d)",
    re.IGNORECASE,
)


class InventoryParser(BaseParser):
    """Parser for inventory schedules: 237 (new), 240 (used), 277 (loaners)."""

    SECTION_IDENTIFIERS = [
        # Schedule 237
        "SCHEDULE 237",
        "NEW VEHICLE INVENTORY",
        "NEW VEH INV",
        # Schedule 240
        "SCHEDULE 240",
        "USED VEHICLE INVENTORY",
        "USED VEH INV",
        # Schedule 277
        "SCHEDULE 277",
        "SERVICE LOANER",
        "LOANER VEHICLE",
    ]

    # Sub-identifiers for routing pages to specific schedule handlers
    _NEW_IDENTIFIERS = ["SCHEDULE 237", "NEW VEHICLE INVENTORY", "NEW VEH INV"]
    _USED_IDENTIFIERS = ["SCHEDULE 240", "USED VEHICLE INVENTORY", "USED VEH INV"]
    _LOANER_IDENTIFIERS = ["SCHEDULE 277", "SERVICE LOANER", "LOANER VEHICLE"]

    def parse(self, pages: list[dict]) -> dict:
        """Parse inventory pages into structured records."""
        new_vehicles = []
        used_vehicles = []
        service_loaners = []

        # Totals for floorplan reconciliation
        new_total_book = Decimal("0")
        new_total_floorplan = Decimal("0")
        used_total_book = Decimal("0")
        used_total_floorplan = Decimal("0")
        new_count = 0
        used_count = 0

        for page in pages:
            text_upper = page["text"].upper()

            if self._matches(text_upper, self._NEW_IDENTIFIERS):
                vehicles, totals = self._parse_vehicle_page(
                    page, schedule_type="new"
                )
                new_vehicles.extend(vehicles)
                if totals:
                    new_total_book = totals.get("book_total", new_total_book)
                    new_total_floorplan = totals.get(
                        "floorplan_total", new_total_floorplan
                    )

            elif self._matches(text_upper, self._USED_IDENTIFIERS):
                vehicles, totals = self._parse_vehicle_page(
                    page, schedule_type="used"
                )
                used_vehicles.extend(vehicles)
                if totals:
                    used_total_book = totals.get("book_total", used_total_book)
                    used_total_floorplan = totals.get(
                        "floorplan_total", used_total_floorplan
                    )

            elif self._matches(text_upper, self._LOANER_IDENTIFIERS):
                loaners = self._parse_loaner_page(page)
                service_loaners.extend(loaners)

        new_count = len(new_vehicles)
        used_count = len(used_vehicles)

        # Compute running totals from parsed records if schedule totals weren't found
        if new_total_book == 0 and new_vehicles:
            new_total_book = sum(
                v.get("book_value") or Decimal("0") for v in new_vehicles
            )
        if new_total_floorplan == 0 and new_vehicles:
            new_total_floorplan = sum(
                v.get("floorplan_balance") or Decimal("0") for v in new_vehicles
            )
        if used_total_book == 0 and used_vehicles:
            used_total_book = sum(
                v.get("book_value") or Decimal("0") for v in used_vehicles
            )
        if used_total_floorplan == 0 and used_vehicles:
            used_total_floorplan = sum(
                v.get("floorplan_balance") or Decimal("0") for v in used_vehicles
            )

        # Build floorplan reconciliation records
        reconciliations = []
        if new_vehicles:
            reconciliations.append(
                {
                    "reconciliation_type": "new_237",
                    "book_balance": new_total_book,
                    "floorplan_balance": new_total_floorplan,
                    "variance": new_total_book - new_total_floorplan,
                    "unit_count_book": new_count,
                }
            )
        if used_vehicles:
            reconciliations.append(
                {
                    "reconciliation_type": "used_240",
                    "book_balance": used_total_book,
                    "floorplan_balance": used_total_floorplan,
                    "variance": used_total_book - used_total_floorplan,
                    "unit_count_book": used_count,
                }
            )

        results = {}
        if new_vehicles:
            results["NewVehicleInventory"] = new_vehicles
        if used_vehicles:
            results["UsedVehicleInventory"] = used_vehicles
        if service_loaners:
            results["ServiceLoaner"] = service_loaners
        if reconciliations:
            results["FloorplanReconciliation"] = reconciliations

        logger.info(
            f"Inventory parser: {len(new_vehicles)} new, {len(used_vehicles)} used, "
            f"{len(service_loaners)} loaners"
        )
        return results

    def _matches(self, text_upper: str, identifiers: list[str]) -> bool:
        """Check if text contains any of the given identifiers."""
        return any(ident.upper() in text_upper for ident in identifiers)

    def _parse_vehicle_page(
        self, page: dict, schedule_type: str
    ) -> tuple[list[dict], dict | None]:
        """
        Parse a new or used vehicle inventory page.

        Tries table extraction first, falls back to line-by-line parsing.
        Returns (list of vehicle dicts, totals dict or None).
        """
        vehicles = []
        totals = None

        # Try table-based extraction first
        if page.get("tables"):
            for table in page["tables"]:
                rows = self.extract_table_rows(table)
                for row in rows:
                    vehicle = self._extract_vehicle_from_row(row, schedule_type)
                    if vehicle:
                        vehicles.append(vehicle)
                    total = self._extract_totals_from_row(row, schedule_type)
                    if total:
                        totals = total

        # Fall back to line-by-line parsing if no table results
        if not vehicles:
            vehicles, totals = self._parse_vehicle_lines(page["lines"], schedule_type)

        return vehicles, totals

    def _extract_vehicle_from_row(
        self, row: dict, schedule_type: str
    ) -> dict | None:
        """Extract a vehicle record from a table row dict."""
        # Look for stock number — the anchor field
        stock = (
            row.get("stock_number")
            or row.get("stock_#")
            or row.get("stock")
            or row.get("stk_#")
            or row.get("stk")
        )
        if not stock or _SKIP_PATTERNS.match(stock):
            return None

        stock = stock.strip()
        if not stock:
            return None

        year = self.clean_int(
            row.get("year") or row.get("yr") or row.get("model_year")
        )
        make = (row.get("make") or "").strip()
        model = (
            row.get("model") or row.get("description") or row.get("desc") or ""
        ).strip()

        if not year or not make:
            # Try to parse year/make/model from a combined description field
            desc = (
                row.get("description")
                or row.get("vehicle")
                or row.get("vehicle_description")
                or ""
            )
            parsed = self._parse_year_make_model(desc)
            if parsed:
                year = year or parsed[0]
                make = make or parsed[1]
                model = model or parsed[2]

        if not year or not make:
            logger.warning(f"Skipping row with insufficient vehicle data: {row}")
            return None

        vehicle: dict = {
            "stock_number": stock,
            "year": year,
            "make": make,
            "model": model or "UNKNOWN",
        }

        # VIN
        vin = (row.get("vin") or row.get("serial") or row.get("serial_number") or "").strip()
        if vin and len(vin) >= 6:
            vehicle["vin"] = vin[:17]

        # Days in stock
        days = self.clean_int(
            row.get("days") or row.get("days_in_stock") or row.get("age")
        )
        if days is not None:
            vehicle["days_in_stock"] = days
        else:
            vehicle["days_in_stock"] = 0

        # Monetary fields
        if schedule_type == "new":
            vehicle["floorplan_balance"] = self.clean_currency(
                row.get("floorplan")
                or row.get("floorplan_balance")
                or row.get("floor")
                or row.get("flr_plan")
            ) or Decimal("0")
            vehicle["book_value"] = self.clean_currency(
                row.get("book_value")
                or row.get("book")
                or row.get("cost")
                or row.get("total_cost")
            )
        elif schedule_type == "used":
            vehicle["book_value"] = self.clean_currency(
                row.get("book_value")
                or row.get("book")
                or row.get("cost")
                or row.get("total_cost")
            ) or Decimal("0")
            vehicle["market_value"] = self.clean_currency(
                row.get("market_value")
                or row.get("market")
                or row.get("acv")
            )
            vehicle["floorplan_balance"] = self.clean_currency(
                row.get("floorplan")
                or row.get("floorplan_balance")
                or row.get("floor")
                or row.get("flr_plan")
            )

        return vehicle

    def _extract_totals_from_row(
        self, row: dict, schedule_type: str
    ) -> dict | None:
        """Check if a row contains totals and extract them."""
        # Check for totals indicators
        first_val = next(iter(row.values()), "")
        if not first_val or not re.match(
            r"^\s*(TOTAL|GRAND\s+TOTAL)", str(first_val), re.IGNORECASE
        ):
            return None

        totals = {}
        book = self.clean_currency(
            row.get("book_value")
            or row.get("book")
            or row.get("cost")
            or row.get("total_cost")
        )
        if book is not None:
            totals["book_total"] = book

        floorplan = self.clean_currency(
            row.get("floorplan")
            or row.get("floorplan_balance")
            or row.get("floor")
            or row.get("flr_plan")
        )
        if floorplan is not None:
            totals["floorplan_total"] = floorplan

        return totals if totals else None

    def _parse_vehicle_lines(
        self, lines: list[str], schedule_type: str
    ) -> tuple[list[dict], dict | None]:
        """
        Line-by-line fallback parser for vehicle inventory.

        Handles cases where pdfplumber can't extract clean tables.
        Looks for lines matching patterns like:
            STOCK#  YEAR MAKE MODEL  DAYS  COST  FLOORPLAN
        """
        vehicles = []
        totals = None

        # Pattern: stock_number followed by year (4 digits), then text, then numbers
        vehicle_pattern = re.compile(
            r"^\s*(\S+)\s+"  # stock number
            r"(\d{4})\s+"  # year
            r"(\S+)\s+"  # make
            r"(.+?)\s{2,}"  # model (followed by 2+ spaces)
            r"(\d+)\s+"  # days in stock
            r"([\d,.$()-]+)"  # first dollar amount
            r"(?:\s+([\d,.$()-]+))?"  # optional second dollar amount
        )

        totals_pattern = re.compile(
            r"^\s*(?:TOTAL|GRAND\s+TOTAL).*?"
            r"([\d,.$()-]+)"  # first total
            r"(?:\s+([\d,.$()-]+))?",  # optional second total
            re.IGNORECASE,
        )

        for line in lines:
            if _SKIP_PATTERNS.match(line):
                # Check for totals
                tmatch = totals_pattern.match(line)
                if tmatch:
                    totals = {}
                    val1 = self.clean_currency(tmatch.group(1))
                    val2 = self.clean_currency(tmatch.group(2))
                    if val1 is not None:
                        totals["book_total"] = val1
                    if val2 is not None:
                        totals["floorplan_total"] = val2
                continue

            match = vehicle_pattern.match(line)
            if not match:
                continue

            stock = match.group(1)
            year = int(match.group(2))
            make = match.group(3)
            model = match.group(4).strip()
            days = int(match.group(5))
            amount1 = self.clean_currency(match.group(6))
            amount2 = self.clean_currency(match.group(7))

            vehicle: dict = {
                "stock_number": stock,
                "year": year,
                "make": make,
                "model": model or "UNKNOWN",
                "days_in_stock": days,
            }

            if schedule_type == "new":
                vehicle["book_value"] = amount1
                vehicle["floorplan_balance"] = amount2 or Decimal("0")
            elif schedule_type == "used":
                vehicle["book_value"] = amount1 or Decimal("0")
                vehicle["market_value"] = amount2

            vehicles.append(vehicle)

        return vehicles, totals

    def _parse_loaner_page(self, page: dict) -> list[dict]:
        """Parse a service loaner (schedule 277) page."""
        loaners = []

        # Try table extraction first
        if page.get("tables"):
            for table in page["tables"]:
                rows = self.extract_table_rows(table)
                for row in rows:
                    loaner = self._extract_loaner_from_row(row)
                    if loaner:
                        loaners.append(loaner)

        # Fall back to line parsing
        if not loaners:
            loaners = self._parse_loaner_lines(page["lines"])

        return loaners

    def _extract_loaner_from_row(self, row: dict) -> dict | None:
        """Extract a service loaner record from a table row."""
        stock = (
            row.get("stock_number")
            or row.get("stock_#")
            or row.get("stock")
            or row.get("stk_#")
            or row.get("stk")
        )
        if not stock or _SKIP_PATTERNS.match(stock):
            return None

        stock = stock.strip()
        if not stock:
            return None

        year = self.clean_int(
            row.get("year") or row.get("yr") or row.get("model_year")
        )
        make = (row.get("make") or "").strip()
        model = (
            row.get("model") or row.get("description") or row.get("desc") or ""
        ).strip()

        if not year or not make:
            desc = (
                row.get("description")
                or row.get("vehicle")
                or row.get("vehicle_description")
                or ""
            )
            parsed = self._parse_year_make_model(desc)
            if parsed:
                year = year or parsed[0]
                make = make or parsed[1]
                model = model or parsed[2]

        if not year or not make:
            logger.warning(f"Skipping loaner row with insufficient data: {row}")
            return None

        loaner: dict = {
            "stock_number": stock,
            "year": year,
            "make": make,
            "model": model or "UNKNOWN",
        }

        vin = (row.get("vin") or row.get("serial") or "").strip()
        if vin and len(vin) >= 6:
            loaner["vin"] = vin[:17]

        days = self.clean_int(
            row.get("days")
            or row.get("days_in_service")
            or row.get("days_in_svc")
            or row.get("age")
        )
        loaner["days_in_service"] = days if days is not None else 0

        loaner["book_value"] = self.clean_currency(
            row.get("book_value") or row.get("book") or row.get("cost")
        ) or Decimal("0")

        loaner["current_value"] = self.clean_currency(
            row.get("current_value")
            or row.get("current")
            or row.get("acv")
            or row.get("market_value")
        )

        neg_equity = self.clean_currency(
            row.get("negative_equity")
            or row.get("neg_equity")
            or row.get("equity")
            or row.get("loss")
        )
        loaner["negative_equity"] = neg_equity if neg_equity is not None else Decimal("0")

        return loaner

    def _parse_loaner_lines(self, lines: list[str]) -> list[dict]:
        """Line-by-line fallback parser for service loaners."""
        loaners = []

        loaner_pattern = re.compile(
            r"^\s*(\S+)\s+"  # stock number
            r"(\d{4})\s+"  # year
            r"(\S+)\s+"  # make
            r"(.+?)\s{2,}"  # model
            r"(\d+)\s+"  # days in service
            r"([\d,.$()-]+)"  # book value
            r"(?:\s+([\d,.$()-]+))?"  # current value
            r"(?:\s+([\d,.$()-]+))?"  # negative equity
        )

        for line in lines:
            if _SKIP_PATTERNS.match(line):
                continue

            match = loaner_pattern.match(line)
            if not match:
                continue

            loaners.append(
                {
                    "stock_number": match.group(1),
                    "year": int(match.group(2)),
                    "make": match.group(3),
                    "model": match.group(4).strip() or "UNKNOWN",
                    "days_in_service": int(match.group(5)),
                    "book_value": self.clean_currency(match.group(6)) or Decimal("0"),
                    "current_value": self.clean_currency(match.group(7)),
                    "negative_equity": self.clean_currency(match.group(8))
                    or Decimal("0"),
                }
            )

        return loaners

    @staticmethod
    def _parse_year_make_model(
        description: str,
    ) -> tuple[int, str, str] | None:
        """Try to extract year, make, model from a combined description string."""
        if not description:
            return None

        match = re.match(
            r"^\s*(\d{4})\s+(\S+)\s*(.*)", description.strip()
        )
        if match:
            return (
                int(match.group(1)),
                match.group(2).strip(),
                match.group(3).strip() or "UNKNOWN",
            )
        return None
