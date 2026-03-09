"""Tests for meetings API endpoints."""

import datetime
import uuid
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory import NewVehicleInventory, UsedVehicleInventory, ServiceLoaner, FloorplanReconciliation
from app.models.inventory import ReconciliationType
from app.models.parts import PartsAnalysis
from app.models.financial import Receivable, ContractInTransit
from app.models.financial import ReceivableType
from app.models.operations import OpenRepairOrder, MissingTitle


MEETINGS_URL = "/api/v1/meetings"
MEETING_ID = "22222222-2222-2222-2222-222222222222"
STORE_ID = "11111111-1111-1111-1111-111111111111"
FAKE_MEETING = "99999999-9999-9999-9999-999999999999"


@pytest_asyncio.fixture
async def meeting_with_data(db_session: AsyncSession, sample_meeting, sample_store):
    """Create a meeting with sample parsed data across all categories."""
    meeting_id = sample_meeting.id
    store_id = sample_store.id

    # New vehicles
    for i in range(3):
        db_session.add(NewVehicleInventory(
            meeting_id=meeting_id, store_id=store_id,
            stock_number=f"NV{i}", year=2025, make="CHEVROLET", model="TRUCK",
            days_in_stock=50 + i * 40, floorplan_balance=Decimal("45000.00"),
        ))

    # Used vehicles
    for i in range(5):
        db_session.add(UsedVehicleInventory(
            meeting_id=meeting_id, store_id=store_id,
            stock_number=f"UV{i}", year=2024, make="TOYOTA", model="CAMRY",
            days_in_stock=30 + i * 25, book_value=Decimal("20000.00"),
        ))

    # Service loaners
    db_session.add(ServiceLoaner(
        meeting_id=meeting_id, store_id=store_id,
        stock_number="SL1", year=2025, make="CHEVROLET", model="EQUINOX",
        days_in_service=120, book_value=Decimal("35000.00"),
        negative_equity=Decimal("-5000.00"),
    ))

    # Floorplan reconciliation
    db_session.add(FloorplanReconciliation(
        meeting_id=meeting_id, store_id=store_id,
        reconciliation_type=ReconciliationType.NEW_237,
        book_balance=Decimal("135000.00"), floorplan_balance=Decimal("134500.00"),
        variance=Decimal("500.00"),
    ))

    # Parts analysis
    db_session.add(PartsAnalysis(
        meeting_id=meeting_id, store_id=store_id,
        period_month=1, period_year=2026,
        true_turnover=Decimal("0.10"),
    ))

    # Open ROs
    for i in range(4):
        db_session.add(OpenRepairOrder(
            meeting_id=meeting_id, store_id=store_id,
            ro_number=f"RO{i}", open_date=datetime.date(2026, 1, 1),
            days_open=10 + i * 10,
        ))

    # Receivables
    db_session.add(Receivable(
        meeting_id=meeting_id, store_id=store_id,
        receivable_type=ReceivableType.PARTS_SERVICE_200,
        schedule_number="200", current_balance=Decimal("5000.00"),
        over_30=Decimal("100.00"), over_60=Decimal("0.00"),
        over_90=Decimal("0.00"), total_balance=Decimal("5100.00"),
    ))

    # Missing titles
    for i in range(2):
        db_session.add(MissingTitle(
            meeting_id=meeting_id, store_id=store_id,
            stock_number=f"MT{i}", days_missing=30 + i * 10,
        ))

    # Contracts in transit
    db_session.add(ContractInTransit(
        meeting_id=meeting_id, store_id=store_id,
        deal_number="D001", sale_date=datetime.date(2026, 2, 1),
        days_in_transit=10, amount=Decimal("25000.00"),
    ))

    await db_session.commit()
    return sample_meeting


@pytest.mark.asyncio
class TestGetMeetingDetail:

    async def test_get_meeting_detail_structure(self, client, meeting_with_data):
        """Meeting detail returns meeting, executive_summary, and flags_summary."""
        response = await client.get(f"{MEETINGS_URL}/{MEETING_ID}")
        assert response.status_code == 200
        data = response.json()
        assert "meeting" in data
        assert "executive_summary" in data
        assert "flags_summary" in data

    async def test_meeting_info(self, client, meeting_with_data):
        """Meeting info includes store_name and all expected fields."""
        data = (await client.get(f"{MEETINGS_URL}/{MEETING_ID}")).json()
        meeting = data["meeting"]
        assert meeting["id"] == MEETING_ID
        assert meeting["store_id"] == STORE_ID
        assert meeting["store_name"] == "Ashdown Classic Chevrolet"
        assert meeting["meeting_date"] == "2026-02-11"
        assert meeting["status"] == "completed"

    async def test_executive_summary_structure(self, client, meeting_with_data):
        """Executive summary has all expected fields."""
        data = (await client.get(f"{MEETINGS_URL}/{MEETING_ID}")).json()
        es = data["executive_summary"]
        expected_keys = [
            "new_vehicle_count", "new_vehicle_floorplan_total",
            "used_vehicle_count", "used_over_60_days", "used_over_90_days",
            "used_over_90_exposure", "service_loaner_count",
            "service_loaner_neg_equity_total", "parts_turnover",
            "open_ro_count", "receivables_over_30_total",
            "missing_titles_count", "contracts_in_transit_count",
            "floorplan_variance",
        ]
        for key in expected_keys:
            assert key in es, f"Missing key: {key}"

    async def test_executive_summary_values(self, client, meeting_with_data):
        """Executive summary aggregates are computed correctly from parsed data."""
        data = (await client.get(f"{MEETINGS_URL}/{MEETING_ID}")).json()
        es = data["executive_summary"]
        assert es["new_vehicle_count"] == 3
        assert es["new_vehicle_floorplan_total"] == 135000.00  # 3 * 45000
        assert es["used_vehicle_count"] == 5
        # days_in_stock: 30, 55, 80, 105, 130 → over 60: 3 (80,105,130), over 90: 2 (105,130)
        assert es["used_over_60_days"] == 3
        assert es["used_over_90_days"] == 2
        assert es["used_over_90_exposure"] == 40000.00  # 2 * 20000
        assert es["service_loaner_count"] == 1
        assert es["service_loaner_neg_equity_total"] == -5000.00
        assert es["parts_turnover"] == 0.10
        assert es["open_ro_count"] == 4
        assert es["receivables_over_30_total"] == 100.00
        assert es["missing_titles_count"] == 2
        assert es["contracts_in_transit_count"] == 1
        assert es["floorplan_variance"] == 500.00

    async def test_flags_summary_structure(self, client, sample_meeting, sample_flags):
        """Flags summary has correct structure with by_category breakdown."""
        data = (await client.get(f"{MEETINGS_URL}/{MEETING_ID}")).json()
        fs = data["flags_summary"]
        assert "total" in fs
        assert "red" in fs
        assert "yellow" in fs
        assert "open" in fs
        assert "responded" in fs
        assert "overdue" in fs
        assert "by_category" in fs

    async def test_flags_summary_values(self, client, sample_meeting, sample_flags):
        """Flags summary values match sample flags (2 red, 2 yellow, 3 open, 1 responded)."""
        data = (await client.get(f"{MEETINGS_URL}/{MEETING_ID}")).json()
        fs = data["flags_summary"]
        assert fs["total"] == 4
        assert fs["red"] == 2
        assert fs["yellow"] == 2
        assert fs["open"] == 3
        assert fs["responded"] == 1

    async def test_flags_summary_by_category(self, client, sample_meeting, sample_flags):
        """By-category breakdown shows correct severity counts per category."""
        data = (await client.get(f"{MEETINGS_URL}/{MEETING_ID}")).json()
        by_cat = data["flags_summary"]["by_category"]
        # sample_flags: inventory (1 red, 1 yellow), financial (1 red), operations (1 yellow)
        assert "inventory" in by_cat
        assert by_cat["inventory"]["red"] == 1
        assert by_cat["inventory"]["yellow"] == 1
        assert by_cat["financial"]["red"] == 1
        assert by_cat["operations"]["yellow"] == 1

    async def test_meeting_not_found(self, client, sample_store):
        """Nonexistent meeting returns 404."""
        response = await client.get(f"{MEETINGS_URL}/{FAKE_MEETING}")
        assert response.status_code == 404

    async def test_invalid_meeting_id(self, client):
        """Invalid UUID returns 422."""
        response = await client.get(f"{MEETINGS_URL}/not-a-uuid")
        assert response.status_code == 422

    async def test_empty_meeting_executive_summary(self, client, sample_meeting):
        """Meeting with no parsed data returns zeroed executive summary."""
        data = (await client.get(f"{MEETINGS_URL}/{MEETING_ID}")).json()
        es = data["executive_summary"]
        assert es["new_vehicle_count"] == 0
        assert es["used_vehicle_count"] == 0
        assert es["open_ro_count"] == 0
        assert es["parts_turnover"] is None


@pytest.mark.asyncio
class TestGetMeetingData:

    async def test_get_inventory_data(self, client, meeting_with_data):
        """Get inventory category data for a meeting."""
        response = await client.get(f"{MEETINGS_URL}/{MEETING_ID}/data/inventory")
        assert response.status_code == 200
        data = response.json()
        assert data["category"] == "inventory"
        assert "new_vehicles" in data["data"]
        assert "used_vehicles" in data["data"]
        assert "service_loaners" in data["data"]
        assert "floorplan_reconciliation" in data["data"]
        assert len(data["data"]["new_vehicles"]) == 3
        assert len(data["data"]["used_vehicles"]) == 5

    async def test_get_parts_data(self, client, sample_meeting):
        """Get parts category data."""
        response = await client.get(f"{MEETINGS_URL}/{MEETING_ID}/data/parts")
        assert response.status_code == 200
        data = response.json()
        assert data["category"] == "parts"
        assert "parts_inventory" in data["data"]
        assert "parts_analysis" in data["data"]

    async def test_get_financial_data(self, client, sample_meeting):
        """Get financial category data."""
        response = await client.get(f"{MEETINGS_URL}/{MEETING_ID}/data/financial")
        assert response.status_code == 200
        data = response.json()
        assert data["category"] == "financial"
        assert "receivables" in data["data"]
        assert "fi_chargebacks" in data["data"]
        assert "contracts_in_transit" in data["data"]
        assert "prepaids" in data["data"]
        assert "policy_adjustments" in data["data"]

    async def test_get_operations_data(self, client, sample_meeting):
        """Get operations category data."""
        response = await client.get(f"{MEETINGS_URL}/{MEETING_ID}/data/operations")
        assert response.status_code == 200
        data = response.json()
        assert data["category"] == "operations"
        assert "open_repair_orders" in data["data"]
        assert "warranty_claims" in data["data"]
        assert "missing_titles" in data["data"]
        assert "slow_to_accounting" in data["data"]

    async def test_data_records_include_flag_field(self, client, meeting_with_data):
        """Each record includes a flag field (null or object)."""
        response = await client.get(f"{MEETINGS_URL}/{MEETING_ID}/data/inventory")
        data = response.json()
        for rec in data["data"]["new_vehicles"]:
            assert "flag" in rec

    async def test_invalid_category(self, client, sample_meeting):
        """Invalid category returns 422."""
        response = await client.get(f"{MEETINGS_URL}/{MEETING_ID}/data/nonexistent")
        assert response.status_code == 422
        assert "Invalid category" in response.json()["detail"]

    async def test_meeting_not_found(self, client, sample_store):
        """Data for nonexistent meeting returns 404."""
        response = await client.get(f"{MEETINGS_URL}/{FAKE_MEETING}/data/inventory")
        assert response.status_code == 404


@pytest.mark.asyncio
class TestGetMeetingFlags:

    async def test_get_flags(self, client, sample_meeting, sample_flags):
        """Get all flags for a meeting."""
        response = await client.get(f"{MEETINGS_URL}/{MEETING_ID}/flags")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 4

    async def test_flag_detail_structure(self, client, sample_meeting, sample_flags):
        """Each flag has full detail fields."""
        data = (await client.get(f"{MEETINGS_URL}/{MEETING_ID}/flags")).json()
        flag = data[0]
        expected_keys = [
            "id", "category", "severity", "message", "field_name",
            "field_value", "threshold", "status", "assigned_to",
            "response", "deadline", "is_overdue", "escalation_level",
            "created_at",
        ]
        for key in expected_keys:
            assert key in flag, f"Missing key: {key}"

    async def test_filter_by_severity(self, client, sample_meeting, sample_flags):
        """Filter flags by severity."""
        response = await client.get(f"{MEETINGS_URL}/{MEETING_ID}/flags?severity=red")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert all(f["severity"] == "red" for f in data)

    async def test_filter_by_category(self, client, sample_meeting, sample_flags):
        """Filter flags by category."""
        response = await client.get(f"{MEETINGS_URL}/{MEETING_ID}/flags?category=inventory")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert all(f["category"] == "inventory" for f in data)

    async def test_filter_by_status(self, client, sample_meeting, sample_flags):
        """Filter flags by status."""
        response = await client.get(f"{MEETINGS_URL}/{MEETING_ID}/flags?status=responded")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["status"] == "responded"

    async def test_responded_flag_has_response(self, client, sample_meeting, sample_flags):
        """Responded flag includes response details."""
        data = (await client.get(f"{MEETINGS_URL}/{MEETING_ID}/flags?status=responded")).json()
        assert len(data) == 1
        flag = data[0]
        assert flag["response"] is not None
        assert flag["response"]["text"] == "Collected on 2/15"
        assert flag["response"]["responder"] == "Jane Smith"

    async def test_open_flags_no_response(self, client, sample_meeting, sample_flags):
        """Open flags have null response."""
        data = (await client.get(f"{MEETINGS_URL}/{MEETING_ID}/flags?status=open")).json()
        assert all(f["response"] is None for f in data)

    async def test_invalid_severity_filter(self, client, sample_meeting, sample_flags):
        """Invalid severity returns 422."""
        response = await client.get(f"{MEETINGS_URL}/{MEETING_ID}/flags?severity=purple")
        assert response.status_code == 422

    async def test_invalid_category_filter(self, client, sample_meeting, sample_flags):
        """Invalid category returns 422."""
        response = await client.get(f"{MEETINGS_URL}/{MEETING_ID}/flags?category=bogus")
        assert response.status_code == 422

    async def test_invalid_status_filter(self, client, sample_meeting, sample_flags):
        """Invalid status returns 422."""
        response = await client.get(f"{MEETINGS_URL}/{MEETING_ID}/flags?status=bogus")
        assert response.status_code == 422

    async def test_invalid_sort_by(self, client, sample_meeting, sample_flags):
        """Invalid sort_by returns 422."""
        response = await client.get(f"{MEETINGS_URL}/{MEETING_ID}/flags?sort_by=bogus")
        assert response.status_code == 422

    async def test_meeting_not_found(self, client, sample_store):
        """Flags for nonexistent meeting returns 404."""
        response = await client.get(f"{MEETINGS_URL}/{FAKE_MEETING}/flags")
        assert response.status_code == 404

    async def test_combined_filters(self, client, sample_meeting, sample_flags):
        """Multiple filters work together."""
        response = await client.get(
            f"{MEETINGS_URL}/{MEETING_ID}/flags?severity=red&category=financial"
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["severity"] == "red"
        assert data[0]["category"] == "financial"

    async def test_sort_by_category(self, client, sample_meeting, sample_flags):
        """Sort by category groups flags by category."""
        response = await client.get(f"{MEETINGS_URL}/{MEETING_ID}/flags?sort_by=category")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 4
        categories = [f["category"] for f in data]
        assert categories == sorted(categories)

    async def test_empty_result(self, client, sample_meeting):
        """Meeting with no flags returns empty list."""
        response = await client.get(f"{MEETINGS_URL}/{MEETING_ID}/flags")
        assert response.status_code == 200
        assert response.json() == []
