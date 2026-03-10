"""Tests for flags API endpoints."""

import pytest


FLAGS_URL = "/api/v1/flags"
MEETING_ID = "22222222-2222-2222-2222-222222222222"
FAKE_MEETING = "99999999-9999-9999-9999-999999999999"


@pytest.mark.asyncio
class TestGetMeetingFlags:

    async def test_get_all_flags(self, client, sample_flags, auth_headers):
        """Get all flags for a meeting without filters."""
        response = await client.get(f"{FLAGS_URL}/{MEETING_ID}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 4

    async def test_filter_by_severity_red(self, client, sample_flags, auth_headers):
        """Filter flags by severity=red."""
        response = await client.get(f"{FLAGS_URL}/{MEETING_ID}?severity=red", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert all(f["severity"] == "red" for f in data)

    async def test_filter_by_severity_yellow(self, client, sample_flags, auth_headers):
        """Filter flags by severity=yellow."""
        response = await client.get(f"{FLAGS_URL}/{MEETING_ID}?severity=yellow", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert all(f["severity"] == "yellow" for f in data)

    async def test_filter_by_category(self, client, sample_flags, auth_headers):
        """Filter flags by category."""
        response = await client.get(f"{FLAGS_URL}/{MEETING_ID}?category=inventory", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert all(f["category"] == "inventory" for f in data)

    async def test_filter_by_status(self, client, sample_flags, auth_headers):
        """Filter flags by status."""
        response = await client.get(f"{FLAGS_URL}/{MEETING_ID}?status=responded", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["status"] == "responded"
        assert data[0]["response_text"] == "Collected on 2/15"

    async def test_combined_filters(self, client, sample_flags, auth_headers):
        """Filter flags by multiple criteria."""
        response = await client.get(
            f"{FLAGS_URL}/{MEETING_ID}?severity=red&category=inventory", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["severity"] == "red"
        assert data[0]["category"] == "inventory"

    async def test_invalid_severity_filter(self, client, sample_flags, auth_headers):
        """Invalid severity filter returns 422."""
        response = await client.get(f"{FLAGS_URL}/{MEETING_ID}?severity=orange", headers=auth_headers)
        assert response.status_code == 422

    async def test_nonexistent_meeting(self, client, sample_store, auth_headers):
        """Flags for nonexistent meeting returns 404."""
        response = await client.get(f"{FLAGS_URL}/{FAKE_MEETING}", headers=auth_headers)
        assert response.status_code == 404

    async def test_flag_response_shape(self, client, sample_flags, auth_headers):
        """Verify the shape of a flag response object."""
        response = await client.get(f"{FLAGS_URL}/{MEETING_ID}", headers=auth_headers)
        data = response.json()
        flag = data[0]
        assert "id" in flag
        assert "meeting_id" in flag
        assert "store_id" in flag
        assert "category" in flag
        assert "severity" in flag
        assert "field_name" in flag
        assert "message" in flag
        assert "status" in flag
        assert "created_at" in flag

    async def test_unauthenticated_returns_401(self, client, sample_flags):
        """Unauthenticated request returns 401."""
        response = await client.get(f"{FLAGS_URL}/{MEETING_ID}")
        assert response.status_code == 401


@pytest.mark.asyncio
class TestFlagStats:

    async def test_flag_stats(self, client, sample_flags, auth_headers):
        """Get correct flag statistics."""
        response = await client.get(f"{FLAGS_URL}/{MEETING_ID}/stats", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 4
        assert data["yellow"] == 2
        assert data["red"] == 2
        assert data["open"] == 3
        assert data["responded"] == 1
        assert data["by_category"]["inventory"] == 2
        assert data["by_category"]["financial"] == 1
        assert data["by_category"]["operations"] == 1

    async def test_stats_nonexistent_meeting(self, client, sample_store, auth_headers):
        """Stats for nonexistent meeting returns 404."""
        response = await client.get(f"{FLAGS_URL}/{FAKE_MEETING}/stats", headers=auth_headers)
        assert response.status_code == 404


@pytest.mark.asyncio
class TestRespondToFlag:

    async def test_respond_to_flag(self, client, sample_flags, auth_headers):
        """Submitting a response updates flag status and fields."""
        flag_id = str(sample_flags[0].id)
        response = await client.patch(
            f"{FLAGS_URL}/{flag_id}/respond",
            json={
                "response_text": "Vehicle sold on 2/12",
                "responded_by": "John Doe",
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "responded"
        assert data["response_text"] == "Vehicle sold on 2/12"
        assert data["responded_by"] == "John Doe"
        assert data["responded_at"] is not None

    async def test_respond_nonexistent_flag(self, client, sample_store, auth_headers):
        """Responding to nonexistent flag returns 404."""
        fake_id = "99999999-9999-9999-9999-999999999999"
        response = await client.patch(
            f"{FLAGS_URL}/{fake_id}/respond",
            json={
                "response_text": "test",
                "responded_by": "test",
            },
            headers=auth_headers,
        )
        assert response.status_code == 404

    async def test_respond_invalid_flag_id(self, client, auth_headers):
        """Invalid flag UUID returns 422."""
        response = await client.patch(
            f"{FLAGS_URL}/not-a-uuid/respond",
            json={
                "response_text": "test",
                "responded_by": "test",
            },
            headers=auth_headers,
        )
        assert response.status_code == 422

    async def test_respond_missing_fields(self, client, sample_flags, auth_headers):
        """Missing required fields returns 422."""
        flag_id = str(sample_flags[0].id)
        response = await client.patch(
            f"{FLAGS_URL}/{flag_id}/respond",
            json={"response_text": "only partial"},
            headers=auth_headers,
        )
        assert response.status_code == 422
