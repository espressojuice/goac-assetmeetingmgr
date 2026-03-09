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

# OCR line pattern for Schedule Summary format:
# Control#  Description  Total  Sch_balance  Other_balance  Days  VIN  Days_in_Stock
# Example: T1144978  26 CHEVROLET TRUCK C _.  2,448.49  44,312.71  441,864.22  126  1GCPTEEKTT1144978  131
_OCR_VEHICLE_PATTERN = re.compile(
    r"^\s*([A-Z0-9][A-Z0-9]{3,})\s+"  # control# (min 4 chars, starts with letter/digit)
    r"(\d{2})\s+"  # 2-digit year
    r"(\S+)\s+"  # make
    r"(.+?)\s{2,}"  # model (until 2+ spaces)
    r"([\d,.~$()-]+)"  # first amount (Total)
    r"(?:\s+([\d,.~$()-]+))?"  # schedule balance
    r"(?:\s+([\d,.~$()-]+))?"  # other balance (231/311)
    r"(?:\s+(\d{1,3}(?:\s*\|\s*\S+)?))?",  # days (maybe with "| VIN" glued)
    re.IGNORECASE,
)

# OCR loaner pattern:
# Year  VIN  Description  Control#  277_balance  312_balance  Days  Remarks
# Example: 2026  IGCPTEEK6TA25634  26 CHEVROLET TRUCK COLORADO  11125631  45,724.68  443,143.27  110  5188
_OCR_LOANER_PATTERN = re.compile(
    r"^\s*(\d{4})\s+"  # 4-digit year
    r"([A-Z0-9]{10,})\s+"  # VIN (10+ alphanumeric)
    r"\d{2}\s+"  # 2-digit year in description (skip)
    r"(\S+)\s+"  # make
    r"(.+?)\s{2,}"  # model
    r"([A-Z0-9]{4,})\s+"  # control#
    r"([\d,.~$()-]+)\s+"  # 277 balance
    r"([\d,.~$()-]+)"  # 312 balance
    r"(?:\s+(\d{1,3}(?:\s*\|\s*\S+)?))?"  # days (maybe with "| stock#")
)


class InventoryParser(BaseParser):
    """Parser for inventory schedules: 237 (new), 240 (used), 277 (loaners)."""

    SECTION_IDENTIFIERS = [
        # Schedule 237
        "SCHEDULE 237",
        "SCHEDULE#: 237",
        "NEW VEHICLE INVENTORY",
        "NEW VEH INV",
        # Schedule 240
        "SCHEDULE 240",
        "SCHEDULE#: 240",
        "USED VEHICLE INVENTORY",
        "USED VEH INV",
        # Schedule 277
        "SCHEDULE 277",
        "SCHEDULE#: 277",
        "SERVICE LOANER",
        "LOANER VEHICLE",
        "LOANERS",
    ]

    # Sub-identifiers for routing pages to specific schedule handlers
    _NEW_IDENTIFIERS = ["SCHEDULE 237", "SCHEDULE#: 237", "NEW VEHICLE INVENTORY", "NEW VEH INV"]
    _USED_IDENTIFIERS = ["SCHEDULE 240", "SCHEDULE#: 240", "USED VEHICLE INVENTORY", "USED VEH INV"]
    _LOANER_IDENTIFIERS = ["SCHEDULE 277", "SCHEDULE#: 277", "SERVICE LOANER", "LOANER VEHICLE", "LOANERS"]

    @classmethod
    def can_handle(cls, page_text: str) -> bool:
        """Override to detect continuation pages with schedule numbers in column headers."""
        text_upper = page_text.upper()
        if any(ident.upper() in text_upper for ident in cls.SECTION_IDENTIFIERS):
            return True
        # Continuation pages: "Schedule Summary" + column header with 237/240/277
        if "SCHEDULE SUMMARY" in text_upper and "DESCRIPTION" in text_upper:
            if re.search(r"\b237\b", text_upper):
                return True
            if re.search(r"\b240\b", text_upper):
                return True
            if re.search(r"\b277\b", text_upper):
                return True
        return False

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

        for page in pages:
            text_upper = page["text"].upper()

            if self._matches(text_upper, self._LOANER_IDENTIFIERS):
                loaners = self._parse_loaner_page(page)
                service_loaners.extend(loaners)

            elif self._matches(text_upper, self._NEW_IDENTIFIERS):
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

            else:
                # Continuation pages: detect schedule type from column headers
                schedule_type = self._detect_continuation_schedule(text_upper)
                if schedule_type == "new":
                    vehicles, totals = self._parse_vehicle_page(
                        page, schedule_type="new"
                    )
                    new_vehicles.extend(vehicles)
                elif schedule_type == "used":
                    vehicles, totals = self._parse_vehicle_page(
                        page, schedule_type="used"
                    )
                    used_vehicles.extend(vehicles)

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
            "Inventory parser: %d new, %d used, %d loaners",
            len(new_vehicles), len(used_vehicles), len(service_loaners),
        )
        return results

    def _matches(self, text_upper: str, identifiers: list[str]) -> bool:
        """Check if text contains any of the given identifiers."""
        return any(ident.upper() in text_upper for ident in identifiers)

    def _detect_continuation_schedule(self, text_upper: str) -> str | None:
        """Detect schedule type from column headers on continuation pages.

        Continuation pages have 'Schedule Summary' and column headers containing
        schedule numbers (237, 240, 277) but no explicit schedule identifier.
        """
        if "SCHEDULE SUMMARY" not in text_upper:
            return None
        # Look for schedule number in column header lines (first ~5 lines)
        lines = text_upper.split("\n")[:5]
        for line in lines:
            # Column header line typically has DESCRIPTION, TOTAL, and a schedule number
            if "DESCRIPTION" in line or "TOTAL" in line:
                if re.search(r"\b237\b", line):
                    return "new"
                if re.search(r"\b240\b", line):
                    return "used"
        return None

    def _parse_vehicle_page(
        self, page: dict, schedule_type: str
    ) -> tuple[list[dict], dict | None]:
        """Parse a new or used vehicle inventory page.

        Tries table extraction first, falls back to line-by-line parsing.
        """
        vehicles = []
        totals = None

        # Try table-based extraction first (works for native PDFs)
        if page.get("tables") and not page.get("ocr_used"):
            for table in page["tables"]:
                rows = self.extract_table_rows(table)
                for row in rows:
                    vehicle = self._extract_vehicle_from_row(row, schedule_type)
                    if vehicle:
                        vehicles.append(vehicle)
                    total = self._extract_totals_from_row(row, schedule_type)
                    if total:
                        totals = total

        # Fall back to line-by-line parsing (works for OCR and native)
        if not vehicles:
            vehicles, totals = self._parse_vehicle_lines(page["lines"], schedule_type)

        return vehicles, totals

    def _extract_vehicle_from_row(
        self, row: dict, schedule_type: str
    ) -> dict | None:
        """Extract a vehicle record from a table row dict."""
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
            logger.warning("Skipping row with insufficient vehicle data: %s", row)
            return None

        vehicle: dict = {
            "stock_number": stock,
            "year": year,
            "make": make,
            "model": model or "UNKNOWN",
        }

        vin = (row.get("vin") or row.get("serial") or row.get("serial_number") or "").strip()
        if vin and len(vin) >= 6:
            vehicle["vin"] = vin[:17]

        days = self.clean_int(
            row.get("days") or row.get("days_in_stock") or row.get("age")
        )
        vehicle["days_in_stock"] = days if days is not None else 0

        if schedule_type == "new":
            vehicle["floorplan_balance"] = self.clean_currency(
                row.get("floorplan") or row.get("floorplan_balance")
                or row.get("floor") or row.get("flr_plan")
            ) or Decimal("0")
            vehicle["book_value"] = self.clean_currency(
                row.get("book_value") or row.get("book")
                or row.get("cost") or row.get("total_cost")
            )
        elif schedule_type == "used":
            vehicle["book_value"] = self.clean_currency(
                row.get("book_value") or row.get("book")
                or row.get("cost") or row.get("total_cost")
            ) or Decimal("0")
            vehicle["market_value"] = self.clean_currency(
                row.get("market_value") or row.get("market") or row.get("acv")
            )
            vehicle["floorplan_balance"] = self.clean_currency(
                row.get("floorplan") or row.get("floorplan_balance")
                or row.get("floor") or row.get("flr_plan")
            )

        return vehicle

    def _extract_totals_from_row(
        self, row: dict, schedule_type: str
    ) -> dict | None:
        """Check if a row contains totals and extract them."""
        first_val = next(iter(row.values()), "")
        if not first_val or not re.match(
            r"^\s*(TOTAL|GRAND\s+TOTAL)", str(first_val), re.IGNORECASE
        ):
            return None

        totals = {}
        book = self.clean_currency(
            row.get("book_value") or row.get("book")
            or row.get("cost") or row.get("total_cost")
        )
        if book is not None:
            totals["book_total"] = book

        floorplan = self.clean_currency(
            row.get("floorplan") or row.get("floorplan_balance")
            or row.get("floor") or row.get("flr_plan")
        )
        if floorplan is not None:
            totals["floorplan_total"] = floorplan

        return totals if totals else None

    def _parse_vehicle_lines(
        self, lines: list[str], schedule_type: str
    ) -> tuple[list[dict], dict | None]:
        """Line-by-line parser for vehicle inventory (native PDF and OCR formats)."""
        vehicles = []
        totals = None

        # Pattern for native PDF format:
        # STOCK#  YEAR MAKE MODEL  DAYS  COST  FLOORPLAN
        native_pattern = re.compile(
            r"^\s*(\S+)\s+"  # stock number
            r"(\d{4})\s+"  # year
            r"(\S+)\s+"  # make
            r"(.+?)\s{2,}"  # model (followed by 2+ spaces)
            r"(\d+)\s+"  # days in stock
            r"([\d,.$()-]+)"  # first dollar amount
            r"(?:\s+([\d,.$()-]+))?"  # optional second dollar amount
        )

        # OCR Schedule Summary format:
        # Control#  "YY MAKE MODEL..."  amounts  days  VIN  days_in_stock
        # OCR may add lowercase letters (v suffix), + artifacts, etc.
        ocr_pattern = re.compile(
            r"^\s*([A-Z0-9][A-Z0-9+]{3,}[A-Z0-9v+]*)\s+"  # control# with OCR artifacts
            r"(\d{2})\s+"  # 2-digit year
            r"(\S+)\s+"  # make
            r"(.+?)\s{2,}"  # model
            r"([\d,.~$()'-]+)"  # first amount (allow ' from OCR)
            , re.IGNORECASE,
        )

        totals_pattern = re.compile(
            r"^\s*(?:TOTAL|GRAND\s+TOTAL|Report\s+Total|Report).*?"
            r"([\d,.$()-]+)"
            r"(?:\s+([\d,.$()-]+))?",
            re.IGNORECASE,
        )

        # Track if this is a header/metadata section (skip those lines)
        past_header = False

        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue

            # Skip header lines
            if re.match(r"^(Schedule\s+Summary|Schedule#:|Cutoff|Days:|Control#\(|Include)", line_stripped, re.IGNORECASE):
                past_header = True
                continue

            # Skip column header line
            if re.match(r"^Control#\s+Description", line_stripped, re.IGNORECASE):
                past_header = True
                continue

            if _SKIP_PATTERNS.match(line_stripped):
                continue

            # Check for totals
            tmatch = totals_pattern.match(line_stripped)
            if tmatch:
                totals = {}
                val1 = self.clean_currency(tmatch.group(1))
                val2 = self.clean_currency(tmatch.group(2))
                if val1 is not None:
                    totals["book_total"] = val1
                if val2 is not None:
                    totals["floorplan_total"] = val2
                continue

            # Skip footer lines
            if re.match(r"^(Store:|Branch:|Page|\d+ records)", line_stripped, re.IGNORECASE):
                continue

            # Try native format first
            match = native_pattern.match(line_stripped)
            if match:
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
                continue

            # Try OCR short format: stock# then amounts and VIN only (no description)
            # e.g. "T168339  390.46  390.46  1GNSKBKCSKR168339"
            ocr_short = re.match(
                r"^\s*([A-Z0-9][A-Z0-9+]{3,}[A-Z0-9v+]*)\s+"
                r"([\d,.~$()'-]+)\s+"
                r"([\d,.~$()'-]+)\s+"
                r"([A-Z0-9]{10,})\s*$",
                line_stripped, re.IGNORECASE,
            )
            if ocr_short:
                stock = ocr_short.group(1).rstrip("vV+")
                amount1 = self.clean_currency(ocr_short.group(2))
                amount2 = self.clean_currency(ocr_short.group(3))
                vin_candidate = ocr_short.group(4)
                vehicle = {
                    "stock_number": stock,
                    "year": 0,
                    "make": "UNKNOWN",
                    "model": "UNKNOWN",
                    "days_in_stock": 0,
                }
                if schedule_type == "new":
                    vehicle["book_value"] = amount1
                    vehicle["floorplan_balance"] = amount2 or Decimal("0")
                elif schedule_type == "used":
                    vehicle["book_value"] = amount1 or Decimal("0")
                    vehicle["floorplan_balance"] = amount2
                if vin_candidate and len(vin_candidate) >= 10:
                    vehicle["vin"] = vin_candidate[:17]
                vehicles.append(vehicle)
                continue

            # Try OCR format
            match = ocr_pattern.match(line_stripped)
            if match:
                stock = re.sub(r'[vV+]+$', '', match.group(1))  # clean OCR suffix
                year_2d = int(match.group(2))
                year = 2000 + year_2d if year_2d < 80 else 1900 + year_2d
                make = match.group(3)
                model = match.group(4).strip()
                # Clean model — remove trailing OCR artifacts
                model = re.sub(r'[._:]+$', '', model).strip() or "UNKNOWN"

                # Extract remaining amounts from the rest of the line
                rest = line_stripped[match.end():]
                # OCR uses " and ' as negative signs
                rest = rest.replace('"', '-').replace("'", "-")
                amounts = re.findall(r'[\d,.~$()-]+', rest)
                # Filter out small numbers that might be noise
                parsed_amounts = []
                for a in amounts:
                    val = self.clean_currency(a.replace("~", "-"))
                    if val is not None:
                        parsed_amounts.append(val)

                # Try to extract days_in_stock from the end of the line
                days_match = re.search(r'\b(\d{1,3})\s*$', line_stripped)
                days = int(days_match.group(1)) if days_match else 0

                # Also look for days embedded with "| VIN" pattern
                days_vin_match = re.search(r'(\d{1,3})\s*\|\s*\S+', line_stripped)
                if days_vin_match and not days_match:
                    days = int(days_vin_match.group(1))

                vehicle = {
                    "stock_number": stock,
                    "year": year,
                    "make": make,
                    "model": model,
                    "days_in_stock": days,
                }

                if schedule_type == "new":
                    # For new: Total, 237_balance, 231_balance
                    raw_amount = match.group(5).replace("~", "-").replace('"', '-').replace("'", "-")
                    book_val = self.clean_currency(raw_amount)
                    vehicle["book_value"] = book_val
                    if parsed_amounts:
                        vehicle["floorplan_balance"] = parsed_amounts[0]
                        if len(parsed_amounts) > 1:
                            vehicle["schedule_237_balance"] = parsed_amounts[0]
                    else:
                        vehicle["floorplan_balance"] = Decimal("0")
                elif schedule_type == "used":
                    raw_amount = match.group(5).replace("~", "-").replace('"', '-').replace("'", "-")
                    book_val = self.clean_currency(raw_amount)
                    vehicle["book_value"] = book_val or Decimal("0")
                    if parsed_amounts:
                        vehicle["floorplan_balance"] = parsed_amounts[0]

                # Try to extract VIN from the line
                vin_match = re.search(r'\b([A-Z0-9]{17})\b', line_stripped)
                if not vin_match:
                    # OCR may garble VINs — look for long alphanumeric sequences
                    vin_match = re.search(r'\b([A-Z0-9]{14,17})\b', line_stripped)
                if vin_match:
                    vin_candidate = vin_match.group(1)
                    # Don't use the stock number as VIN
                    if vin_candidate != stock and len(vin_candidate) >= 10:
                        vehicle["vin"] = vin_candidate[:17]

                vehicles.append(vehicle)

        return vehicles, totals

    def _parse_loaner_page(self, page: dict) -> list[dict]:
        """Parse a service loaner (schedule 277) page."""
        loaners = []

        # Try table extraction first (native PDF only)
        if page.get("tables") and not page.get("ocr_used"):
            for table in page["tables"]:
                rows = self.extract_table_rows(table)
                for row in rows:
                    loaner = self._extract_loaner_from_row(row)
                    if loaner:
                        loaners.append(loaner)

        # Fall back to line parsing (OCR and native)
        if not loaners:
            loaners = self._parse_loaner_lines(page["lines"])

        return loaners

    def _extract_loaner_from_row(self, row: dict) -> dict | None:
        """Extract a service loaner record from a table row."""
        stock = (
            row.get("stock_number") or row.get("stock_#") or row.get("stock")
            or row.get("stk_#") or row.get("stk")
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
                row.get("description") or row.get("vehicle")
                or row.get("vehicle_description") or ""
            )
            parsed = self._parse_year_make_model(desc)
            if parsed:
                year = year or parsed[0]
                make = make or parsed[1]
                model = model or parsed[2]

        if not year or not make:
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
            row.get("days") or row.get("days_in_service")
            or row.get("days_in_svc") or row.get("age")
        )
        loaner["days_in_service"] = days if days is not None else 0

        loaner["book_value"] = self.clean_currency(
            row.get("book_value") or row.get("book") or row.get("cost")
        ) or Decimal("0")

        loaner["current_value"] = self.clean_currency(
            row.get("current_value") or row.get("current")
            or row.get("acv") or row.get("market_value")
        )

        neg_equity = self.clean_currency(
            row.get("negative_equity") or row.get("neg_equity")
            or row.get("equity") or row.get("loss")
        )
        loaner["negative_equity"] = neg_equity if neg_equity is not None else Decimal("0")

        return loaner

    def _parse_loaner_lines(self, lines: list[str]) -> list[dict]:
        """Line-by-line parser for service loaners (native PDF and OCR formats)."""
        loaners = []

        # Native format: STOCK  YEAR MAKE MODEL  DAYS  BOOK  CURRENT  NEG_EQUITY
        native_pattern = re.compile(
            r"^\s*(\S+)\s+"  # stock number
            r"(\d{4})\s+"  # year
            r"(\S+)\s+"  # make
            r"(.+?)\s{2,}"  # model
            r"(\d+)\s+"  # days in service
            r"([\d,.$()-]+)"  # book value
            r"(?:\s+([\d,.$()-]+))?"  # current value
            r"(?:\s+([\d,.$()-]+))?"  # negative equity
        )

        # OCR Schedule 277 format:
        # YEAR  VIN  "YY MAKE MODEL"  Control#  277_balance  312_balance  Days  Remarks
        # Allow + and other OCR artifacts in VIN and control#
        ocr_pattern = re.compile(
            r"^\s*(\d{4})\s+"  # 4-digit year
            r"([A-Z0-9+]{10,})\s+"  # VIN (allow + OCR artifact)
            r"\d{2}\s+"  # 2-digit year in description (skip)
            r"(\S+)\s+"  # make
            r"(.+?)\s{2,}"  # model
            r"([A-Z0-9+]{3,})\s+"  # control# (allow + and shorter OCR-garbled)
            r"([\d,.~$()-]+)\s+"  # 277 balance (book value)
            r"([\d,.~$()-]+)"  # 312 balance (negative equity)
        )

        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue

            # Skip headers, footers
            if re.match(r"^(Schedule|Cutoff|Days:|Control#\(|Include|Vehicle\s+VIN|Store:|Branch:|Page|\d+ records|Report)", line_stripped, re.IGNORECASE):
                continue

            if _SKIP_PATTERNS.match(line_stripped):
                continue

            # Try native format
            match = native_pattern.match(line_stripped)
            if match:
                loaners.append({
                    "stock_number": match.group(1),
                    "year": int(match.group(2)),
                    "make": match.group(3),
                    "model": match.group(4).strip() or "UNKNOWN",
                    "days_in_service": int(match.group(5)),
                    "book_value": self.clean_currency(match.group(6)) or Decimal("0"),
                    "current_value": self.clean_currency(match.group(7)),
                    "negative_equity": self.clean_currency(match.group(8)) or Decimal("0"),
                })
                continue

            # Try OCR format
            match = ocr_pattern.match(line_stripped)
            if match:
                year = int(match.group(1))
                vin = match.group(2)
                make = match.group(3)
                model = match.group(4).strip()
                model = re.sub(r'[._:]+$', '', model).strip() or "UNKNOWN"
                stock = match.group(5)
                book_val = self.clean_currency(match.group(6)) or Decimal("0")
                neg_equity_raw = match.group(7).replace("~", "-")
                neg_equity = self.clean_currency(neg_equity_raw) or Decimal("0")
                # 312 is negative equity (current_value - book_value), reported as negative
                # Make it positive for our model
                if neg_equity > 0:
                    neg_equity = neg_equity  # OCR sometimes drops the negative sign

                # Extract days from rest of line
                rest = line_stripped[match.end():]
                days_match = re.search(r'(\d{1,3})', rest)
                days = int(days_match.group(1)) if days_match else 0

                # Also check for "days | stock" pattern before rest
                days_pipe_match = re.search(r'(\d{1,3})\s*\|', rest)
                if days_pipe_match:
                    days = int(days_pipe_match.group(1))

                neg_equity_abs = abs(neg_equity)
                # OCR column-bleed fix: if the 312 value starts with the same
                # leading digit as an extra (e.g. 443,143.27 vs 43,143.27),
                # try stripping the leading digit when the value is unreasonably
                # large compared to the book value.
                if neg_equity_abs > book_val * Decimal("2") and len(str(neg_equity_abs).replace(".", "")) > 6:
                    stripped = str(neg_equity_abs)[1:]  # remove first digit
                    try:
                        stripped_val = Decimal(stripped)
                        if stripped_val < book_val * Decimal("2"):
                            neg_equity_abs = stripped_val
                    except Exception:
                        pass

                loaners.append({
                    "stock_number": stock,
                    "year": year,
                    "make": make,
                    "model": model,
                    "vin": vin[:17] if len(vin) >= 10 else None,
                    "days_in_service": days,
                    "book_value": book_val,
                    "negative_equity": neg_equity_abs,
                })
                continue

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
