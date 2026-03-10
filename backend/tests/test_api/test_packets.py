"""Tests for packets API endpoints."""

import pytest


PACKETS_URL = "/api/v1/packets"
MEETING_ID = "22222222-2222-2222-2222-222222222222"
FAKE_MEETING = "99999999-9999-9999-9999-999999999999"


@pytest.mark.asyncio
class TestGetMeetingSummary:

    async def test_get_summary(self, client, sample_meeting, sample_flags, auth_headers):
        """Get meeting summary with all sections."""
        response = await client.get(f"{PACKETS_URL}/{MEETING_ID}/summary", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()

        assert "meeting" in data
        assert data["meeting"]["meeting_date"] == "2026-02-11"
        assert data["meeting"]["status"] == "completed"

        assert "store" in data
        assert data["store"]["name"] == "Ashdown Classic Chevrolet"

        assert "record_counts" in data
        assert isinstance(data["record_counts"], dict)

        assert "flags" in data
        assert len(data["flags"]) == 4

        assert "flag_stats" in data
        assert data["flag_stats"]["total"] == 4
        assert data["flag_stats"]["yellow"] == 2
        assert data["flag_stats"]["red"] == 2

    async def test_summary_nonexistent_meeting(self, client, sample_store, auth_headers):
        """Summary for nonexistent meeting returns 404."""
        response = await client.get(f"{PACKETS_URL}/{FAKE_MEETING}/summary", headers=auth_headers)
        assert response.status_code == 404

    async def test_summary_flag_stats_by_category(self, client, sample_meeting, sample_flags, auth_headers):
        """Verify by_category breakdown in flag stats."""
        response = await client.get(f"{PACKETS_URL}/{MEETING_ID}/summary", headers=auth_headers)
        data = response.json()
        by_cat = data["flag_stats"]["by_category"]
        assert by_cat["inventory"] == 2
        assert by_cat["financial"] == 1
        assert by_cat["operations"] == 1
