"""Tests for meetings API endpoints."""

import pytest


MEETINGS_URL = "/api/v1/meetings"
MEETING_ID = "22222222-2222-2222-2222-222222222222"
FAKE_MEETING = "99999999-9999-9999-9999-999999999999"


@pytest.mark.asyncio
class TestGetMeeting:

    async def test_get_meeting(self, client, sample_meeting):
        """Get meeting details."""
        response = await client.get(f"{MEETINGS_URL}/{MEETING_ID}")
        assert response.status_code == 200
        data = response.json()
        assert data["meeting_date"] == "2026-02-11"
        assert data["status"] == "completed"
        assert data["packet_url"] is not None

    async def test_meeting_not_found(self, client, sample_store):
        """Nonexistent meeting returns 404."""
        response = await client.get(f"{MEETINGS_URL}/{FAKE_MEETING}")
        assert response.status_code == 404

    async def test_invalid_meeting_id(self, client):
        """Invalid UUID returns 422."""
        response = await client.get(f"{MEETINGS_URL}/not-a-uuid")
        assert response.status_code == 422

    async def test_meeting_response_shape(self, client, sample_meeting):
        """Verify meeting response includes all expected fields."""
        response = await client.get(f"{MEETINGS_URL}/{MEETING_ID}")
        data = response.json()
        assert "id" in data
        assert "store_id" in data
        assert "meeting_date" in data
        assert "status" in data
        assert "packet_url" in data
        assert "flagged_items_url" in data
        assert "created_at" in data


@pytest.mark.asyncio
class TestGetMeetingData:

    async def test_get_inventory_data(self, client, sample_meeting):
        """Get inventory category data for a meeting."""
        response = await client.get(f"{MEETINGS_URL}/{MEETING_ID}/data/inventory")
        assert response.status_code == 200
        data = response.json()
        assert data["category"] == "inventory"
        assert "new_vehicles" in data["data"]
        assert "used_vehicles" in data["data"]
        assert "service_loaners" in data["data"]
        assert "floorplan_reconciliation" in data["data"]

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

    async def test_invalid_category(self, client, sample_meeting):
        """Invalid category returns 422."""
        response = await client.get(f"{MEETINGS_URL}/{MEETING_ID}/data/nonexistent")
        assert response.status_code == 422
        assert "Invalid category" in response.json()["detail"]

    async def test_meeting_not_found(self, client, sample_store):
        """Data for nonexistent meeting returns 404."""
        response = await client.get(f"{MEETINGS_URL}/{FAKE_MEETING}/data/inventory")
        assert response.status_code == 404
