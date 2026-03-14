"""Tests for meeting close endpoint."""

import uuid

import pytest

from tests.test_api.conftest import auth_header

MEETING_ID = "22222222-2222-2222-2222-222222222222"
CLOSE_URL = f"/api/v1/meetings/{MEETING_ID}/close"
FAKE_MEETING = "99999999-9999-9999-9999-999999999999"


@pytest.mark.asyncio
class TestCloseMeeting:

    async def test_close_meeting_sets_status(self, client, sample_meeting, auth_headers):
        """POST close sets status to CLOSED with closed_at and closed_by."""
        response = await client.post(CLOSE_URL, json={}, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "closed"
        assert data["closed_at"] is not None
        assert data["closed_by_name"] == "Corporate Admin"
        assert data["meeting_id"] == MEETING_ID

    async def test_close_meeting_with_notes(self, client, sample_meeting, auth_headers):
        """POST close with close_notes stores them."""
        response = await client.post(
            CLOSE_URL,
            json={"close_notes": "Good meeting, follow up on parts next month."},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["close_notes"] == "Good meeting, follow up on parts next month."

    async def test_close_auto_unresolves_open_flags(
        self, client, sample_meeting, sample_flags, auth_headers
    ):
        """POST close changes OPEN flags to UNRESOLVED."""
        response = await client.post(CLOSE_URL, json={}, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        # sample_flags has 3 OPEN flags and 1 RESPONDED
        assert data["flags_summary"]["auto_unresolved"] == 3
        assert data["flags_summary"]["unresolved"] == 3

    async def test_close_leaves_responded_flags(
        self, client, sample_meeting, sample_flags, auth_headers
    ):
        """POST close does not change RESPONDED flags."""
        response = await client.post(CLOSE_URL, json={}, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["flags_summary"]["responded"] == 1

    async def test_close_leaves_verified_flags(
        self, client, sample_meeting, sample_flags, db_session, auth_headers
    ):
        """POST close does not change VERIFIED flags."""
        from app.models.flag import Flag, FlagStatus
        from sqlalchemy import select, update

        # Mark first flag as verified
        flag = sample_flags[0]
        flag.status = FlagStatus.VERIFIED
        await db_session.commit()

        response = await client.post(CLOSE_URL, json={}, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["flags_summary"]["verified"] == 1
        # Only 2 OPEN flags remain (one was set to verified above)
        assert data["flags_summary"]["auto_unresolved"] == 2

    async def test_close_returns_correct_summary(
        self, client, sample_meeting, sample_flags, auth_headers
    ):
        """POST close returns correct total flag counts."""
        response = await client.post(CLOSE_URL, json={}, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["flags_summary"]["total"] == 4

    async def test_close_returns_attendance_summary(
        self, client, sample_meeting, gm_user, manager_user, auth_headers
    ):
        """POST close returns attendance summary."""
        # Mark one user present
        await client.post(
            f"/api/v1/meetings/{MEETING_ID}/attendance",
            json={"user_ids": [str(gm_user.id)]},
            headers=auth_headers,
        )

        response = await client.post(CLOSE_URL, json={}, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["attendance_summary"]["total_expected"] == 1
        assert data["attendance_summary"]["total_present"] == 1
        assert data["attendance_summary"]["total_absent"] == 0

    async def test_cannot_close_already_closed(
        self, client, sample_meeting, auth_headers
    ):
        """POST close on already-closed meeting returns 409."""
        # Close once
        response = await client.post(CLOSE_URL, json={}, headers=auth_headers)
        assert response.status_code == 200

        # Try to close again
        response = await client.post(CLOSE_URL, json={}, headers=auth_headers)
        assert response.status_code == 409
        assert "already closed" in response.json()["detail"].lower()

    async def test_non_gm_non_corporate_cannot_close(
        self, client, sample_meeting, manager_user
    ):
        """POST close by a MANAGER returns 403."""
        headers = auth_header(manager_user)
        response = await client.post(CLOSE_URL, json={}, headers=headers)
        assert response.status_code == 403

    async def test_gm_can_close(self, client, sample_meeting, gm_user):
        """POST close by a GM with store access succeeds."""
        headers = auth_header(gm_user)
        response = await client.post(CLOSE_URL, json={}, headers=headers)
        assert response.status_code == 200
        assert response.json()["closed_by_name"] == "GM User"

    async def test_meeting_not_found(self, client, auth_headers):
        """POST close for nonexistent meeting returns 404."""
        response = await client.post(
            f"/api/v1/meetings/{FAKE_MEETING}/close",
            json={},
            headers=auth_headers,
        )
        assert response.status_code == 404

    async def test_unauthenticated_blocked(self, client, sample_meeting):
        """POST close without auth returns 401."""
        response = await client.post(CLOSE_URL, json={})
        assert response.status_code == 401
