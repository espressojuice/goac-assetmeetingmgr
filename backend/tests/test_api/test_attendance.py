"""Tests for meeting attendance tracking API endpoints."""

import pytest

from tests.test_api.conftest import auth_header

MEETING_ID = "22222222-2222-2222-2222-222222222222"
BASE_URL = f"/api/v1/meetings/{MEETING_ID}/attendance"
FAKE_MEETING = "99999999-9999-9999-9999-999999999999"


@pytest.mark.asyncio
class TestGetAttendance:

    async def test_returns_expected_users(self, client, sample_meeting, gm_user, manager_user, auth_headers):
        """GET returns all users assigned to the meeting's store."""
        response = await client.get(BASE_URL, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        # gm_user and manager_user are assigned to sample_store
        assert len(data) == 2
        user_ids = {item["user_id"] for item in data}
        assert str(gm_user.id) in user_ids
        assert str(manager_user.id) in user_ids
        # All should be unchecked initially
        assert all(item["checked_in"] is False for item in data)

    async def test_meeting_not_found(self, client, auth_headers):
        """GET for nonexistent meeting returns 404."""
        response = await client.get(
            f"/api/v1/meetings/{FAKE_MEETING}/attendance", headers=auth_headers
        )
        assert response.status_code == 404

    async def test_unauthenticated_blocked(self, client, sample_meeting):
        """GET without auth returns 401."""
        response = await client.get(BASE_URL)
        assert response.status_code == 401


@pytest.mark.asyncio
class TestMarkAttendance:

    async def test_mark_users_checked_in(self, client, sample_meeting, gm_user, manager_user, auth_headers):
        """POST marks specified users as checked in."""
        response = await client.post(
            BASE_URL,
            json={"user_ids": [str(gm_user.id)]},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        gm_entry = next(item for item in data if item["user_id"] == str(gm_user.id))
        assert gm_entry["checked_in"] is True
        assert gm_entry["checked_in_at"] is not None
        assert gm_entry["checked_in_by_name"] == "Corporate Admin"
        # Manager should still be unchecked
        mgr_entry = next(item for item in data if item["user_id"] == str(manager_user.id))
        assert mgr_entry["checked_in"] is False

    async def test_mark_already_checked_in_updates_timestamp(self, client, sample_meeting, gm_user, manager_user, auth_headers):
        """POST on already checked-in user updates the timestamp."""
        # First check-in
        await client.post(
            BASE_URL,
            json={"user_ids": [str(gm_user.id)]},
            headers=auth_headers,
        )
        # Second check-in
        response = await client.post(
            BASE_URL,
            json={"user_ids": [str(gm_user.id)]},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        gm_entry = next(item for item in data if item["user_id"] == str(gm_user.id))
        assert gm_entry["checked_in"] is True

    async def test_gm_can_mark_attendance(self, client, sample_meeting, gm_user, manager_user):
        """GM with store access can mark attendance."""
        headers = auth_header(gm_user)
        response = await client.post(
            BASE_URL,
            json={"user_ids": [str(manager_user.id)]},
            headers=headers,
        )
        assert response.status_code == 200

    async def test_manager_can_mark_attendance(self, client, sample_meeting, gm_user, manager_user):
        """Manager (office manager) with store access can mark attendance."""
        headers = auth_header(manager_user)
        response = await client.post(
            BASE_URL,
            json={"user_ids": [str(gm_user.id)]},
            headers=headers,
        )
        assert response.status_code == 200

    async def test_viewer_cannot_mark_attendance(self, client, sample_meeting, db_session):
        """Viewer role cannot mark attendance."""
        import uuid
        from app.models.user import User, UserRole, UserStore
        viewer = User(
            id=uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd"),
            email="viewer@ashdown.com",
            name="Viewer User",
            role=UserRole.VIEWER,
        )
        db_session.add(viewer)
        await db_session.flush()
        assoc = UserStore(user_id=viewer.id, store_id=sample_meeting.store_id)
        db_session.add(assoc)
        await db_session.commit()

        headers = auth_header(viewer)
        response = await client.post(
            BASE_URL,
            json={"user_ids": [str(viewer.id)]},
            headers=headers,
        )
        assert response.status_code == 403

    async def test_unauthenticated_blocked(self, client, sample_meeting):
        """POST without auth returns 401."""
        response = await client.post(
            BASE_URL,
            json={"user_ids": ["aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"]},
        )
        assert response.status_code == 401


@pytest.mark.asyncio
class TestUnmarkAttendance:

    async def test_unmark_checked_in_user(self, client, sample_meeting, gm_user, manager_user, auth_headers):
        """DELETE unmarks a checked-in user."""
        # Check in first
        await client.post(
            BASE_URL,
            json={"user_ids": [str(gm_user.id)]},
            headers=auth_headers,
        )
        # Unmark
        response = await client.delete(
            f"{BASE_URL}/{gm_user.id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["checked_in"] is False
        assert data["checked_in_at"] is None
        assert data["checked_in_by_name"] is None

    async def test_unmark_nonexistent_record(self, client, sample_meeting, gm_user, auth_headers):
        """DELETE for a user with no attendance record returns 404."""
        response = await client.delete(
            f"{BASE_URL}/{gm_user.id}",
            headers=auth_headers,
        )
        assert response.status_code == 404

    async def test_unauthenticated_blocked(self, client, sample_meeting):
        """DELETE without auth returns 401."""
        response = await client.delete(
            f"{BASE_URL}/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        )
        assert response.status_code == 401


@pytest.mark.asyncio
class TestAttendanceSummary:

    async def test_summary_counts(self, client, sample_meeting, gm_user, manager_user, auth_headers):
        """GET summary returns correct counts."""
        # Mark gm as present
        await client.post(
            BASE_URL,
            json={"user_ids": [str(gm_user.id)]},
            headers=auth_headers,
        )
        response = await client.get(f"{BASE_URL}/summary", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total_expected"] == 2
        assert data["total_present"] == 1
        assert data["total_absent"] == 1

    async def test_summary_all_absent(self, client, sample_meeting, gm_user, manager_user, auth_headers):
        """GET summary with no check-ins shows all absent."""
        response = await client.get(f"{BASE_URL}/summary", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total_expected"] == 2
        assert data["total_present"] == 0
        assert data["total_absent"] == 2

    async def test_unauthenticated_blocked(self, client, sample_meeting):
        """GET summary without auth returns 401."""
        response = await client.get(f"{BASE_URL}/summary")
        assert response.status_code == 401


@pytest.mark.asyncio
class TestUniqueConstraint:

    async def test_one_record_per_user_per_meeting(self, client, sample_meeting, gm_user, manager_user, auth_headers):
        """Marking the same user twice doesn't create duplicate records — it updates."""
        # Mark twice
        await client.post(
            BASE_URL,
            json={"user_ids": [str(gm_user.id)]},
            headers=auth_headers,
        )
        await client.post(
            BASE_URL,
            json={"user_ids": [str(gm_user.id)]},
            headers=auth_headers,
        )
        # Get attendance — should only have one entry per user
        response = await client.get(BASE_URL, headers=auth_headers)
        data = response.json()
        gm_entries = [item for item in data if item["user_id"] == str(gm_user.id)]
        assert len(gm_entries) == 1
