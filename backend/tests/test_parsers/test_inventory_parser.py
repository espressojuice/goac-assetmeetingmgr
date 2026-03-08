"""Tests for the inventory parser (schedules 237, 240, 277)."""

from decimal import Decimal

import pytest

from app.parsers.inventory_parser import InventoryParser


@pytest.fixture
def parser():
    return InventoryParser()


def _make_page(num, text, tables=None):
    return {
        "page_number": num,
        "text": text,
        "lines": text.split("\n"),
        "tables": tables or [],
    }


class TestCanHandle:
    def test_schedule_237(self, parser):
        assert parser.can_handle("SCHEDULE 237 - NEW VEHICLE INVENTORY")

    def test_new_vehicle_inventory(self, parser):
        assert parser.can_handle("Report: New Vehicle Inventory")

    def test_schedule_240(self, parser):
        assert parser.can_handle("SCHEDULE 240 - USED VEHICLE INVENTORY")

    def test_schedule_277(self, parser):
        assert parser.can_handle("SCHEDULE 277 - SERVICE LOANER")

    def test_unrelated_text(self, parser):
        assert not parser.can_handle("SCHEDULE 200 - RECEIVABLES AGING")

    def test_empty_text(self, parser):
        assert not parser.can_handle("")

    def test_case_insensitive(self, parser):
        assert parser.can_handle("schedule 237 new veh inv")


class TestParseNewVehicleTable:
    def test_parse_from_table(self, parser):
        table = [
            ["Stock #", "Year", "Make", "Model", "Days", "Book Value", "Floorplan"],
            ["N1234", "2025", "CHEVROLET", "SILVERADO 1500", "45", "$52,340.00", "$51,000.00"],
            ["N5678", "2025", "CHEVROLET", "EQUINOX", "12", "$32,100.00", "$31,500.00"],
        ]
        page = _make_page(
            1,
            "SCHEDULE 237 - NEW VEHICLE INVENTORY\nSome header text",
            tables=[table],
        )
        result = parser.parse([page])

        assert "NewVehicleInventory" in result
        vehicles = result["NewVehicleInventory"]
        assert len(vehicles) == 2

        v1 = vehicles[0]
        assert v1["stock_number"] == "N1234"
        assert v1["year"] == 2025
        assert v1["make"] == "CHEVROLET"
        assert v1["model"] == "SILVERADO 1500"
        assert v1["days_in_stock"] == 45
        assert v1["book_value"] == Decimal("52340.00")
        assert v1["floorplan_balance"] == Decimal("51000.00")

    def test_creates_reconciliation(self, parser):
        table = [
            ["Stock #", "Year", "Make", "Model", "Days", "Book Value", "Floorplan"],
            ["N1234", "2025", "CHEVROLET", "SILVERADO", "45", "$50,000.00", "$48,000.00"],
        ]
        page = _make_page(1, "SCHEDULE 237 - NEW VEHICLE INVENTORY", tables=[table])
        result = parser.parse([page])

        assert "FloorplanReconciliation" in result
        recon = result["FloorplanReconciliation"][0]
        assert recon["reconciliation_type"] == "new_237"
        assert recon["book_balance"] == Decimal("50000.00")
        assert recon["floorplan_balance"] == Decimal("48000.00")
        assert recon["variance"] == Decimal("2000.00")


class TestParseUsedVehicleTable:
    def test_parse_from_table(self, parser):
        table = [
            ["Stock #", "Year", "Make", "Model", "Days", "Book Value", "Market Value"],
            ["U9999", "2022", "FORD", "F-150", "30", "$28,500.00", "$29,000.00"],
        ]
        page = _make_page(1, "SCHEDULE 240 - USED VEHICLE INVENTORY", tables=[table])
        result = parser.parse([page])

        assert "UsedVehicleInventory" in result
        vehicles = result["UsedVehicleInventory"]
        assert len(vehicles) == 1
        assert vehicles[0]["stock_number"] == "U9999"
        assert vehicles[0]["book_value"] == Decimal("28500.00")
        assert vehicles[0]["market_value"] == Decimal("29000.00")


class TestParseLoanerTable:
    def test_parse_from_table(self, parser):
        table = [
            ["Stock #", "Year", "Make", "Model", "Days In Service", "Book Value", "Current Value", "Negative Equity"],
            ["L100", "2024", "CHEVROLET", "MALIBU", "180", "$25,000.00", "$20,000.00", "($5,000.00)"],
        ]
        page = _make_page(1, "SCHEDULE 277 - SERVICE LOANER VEHICLES", tables=[table])
        result = parser.parse([page])

        assert "ServiceLoaner" in result
        loaners = result["ServiceLoaner"]
        assert len(loaners) == 1
        assert loaners[0]["stock_number"] == "L100"
        assert loaners[0]["days_in_service"] == 180
        assert loaners[0]["book_value"] == Decimal("25000.00")
        assert loaners[0]["current_value"] == Decimal("20000.00")
        assert loaners[0]["negative_equity"] == Decimal("-5000.00")


class TestParseNewVehicleLines:
    def test_line_based_parsing(self, parser):
        text = """SCHEDULE 237 - NEW VEHICLE INVENTORY
ASHDOWN CLASSIC CHEVROLET               02/11/2026

Stock#  Year Make       Model              Days  Cost        Floorplan
N1234   2025 CHEVROLET  SILVERADO 1500     45    $52,340.00  $51,000.00
N5678   2025 CHEVROLET  EQUINOX            12    $32,100.00  $31,500.00

TOTAL                                           $84,440.00  $82,500.00"""
        page = _make_page(1, text)
        result = parser.parse([page])

        assert "NewVehicleInventory" in result
        assert len(result["NewVehicleInventory"]) == 2


class TestSkipsTotalsRows:
    def test_totals_not_treated_as_vehicles(self, parser):
        table = [
            ["Stock #", "Year", "Make", "Model", "Days", "Book Value", "Floorplan"],
            ["N1234", "2025", "CHEVROLET", "SILVERADO", "45", "$50,000.00", "$48,000.00"],
            ["TOTAL", "", "", "", "", "$50,000.00", "$48,000.00"],
        ]
        page = _make_page(1, "SCHEDULE 237 - NEW VEHICLE INVENTORY", tables=[table])
        result = parser.parse([page])

        vehicles = result["NewVehicleInventory"]
        assert len(vehicles) == 1
        assert vehicles[0]["stock_number"] == "N1234"


class TestMultiPageParsing:
    def test_multi_page_new_vehicles(self, parser):
        table1 = [
            ["Stock #", "Year", "Make", "Model", "Days", "Book Value", "Floorplan"],
            ["N001", "2025", "CHEVROLET", "SILVERADO", "10", "$50,000.00", "$48,000.00"],
        ]
        table2 = [
            ["Stock #", "Year", "Make", "Model", "Days", "Book Value", "Floorplan"],
            ["N002", "2025", "CHEVROLET", "EQUINOX", "20", "$35,000.00", "$34,000.00"],
        ]
        pages = [
            _make_page(1, "SCHEDULE 237 - NEW VEHICLE INVENTORY", tables=[table1]),
            _make_page(2, "SCHEDULE 237 - NEW VEHICLE INVENTORY (cont)", tables=[table2]),
        ]
        result = parser.parse(pages)

        assert len(result["NewVehicleInventory"]) == 2


class TestEmptyResults:
    def test_no_vehicles_found(self, parser):
        page = _make_page(1, "SCHEDULE 237 - NEW VEHICLE INVENTORY\nNo data available")
        result = parser.parse([page])
        # No vehicle keys if nothing parsed
        assert "NewVehicleInventory" not in result
