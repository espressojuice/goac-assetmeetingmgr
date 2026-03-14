"""Tests for the condensed packet endpoint."""

from __future__ import annotations

import datetime
import uuid

import pytest
import pytest_asyncio

from app.models.meeting import Meeting, MeetingStatus
from app.models.flag import Flag, FlagCategory, FlagSeverity, FlagStatus
from app.models.user import User, UserRole, UserStore
from app.models.accountability import MeetingAttendance
from tests.test_api.conftest import auth_header


ATTENDEE_ID = uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeee01")


@pytest_asyncio.fixture
async def meeting_with_mixed_flags(db_session, sample_store, sample_meeting, corporate_user):
    """Create a meeting with flags in multiple categories and attendance records."""
    # Flags: inventory (2), financial (1), operations (0 — no flags in this category)
    f1 = Flag(
        meeting_id=sample_meeting.id, store_id=sample_store.id,
        category=FlagCategory.INVENTORY, severity=FlagSeverity.RED,
        field_name="days_in_stock", message="Over 90 days", status=FlagStatus.OPEN,
    )
    f2 = Flag(
        meeting_id=sample_meeting.id, store_id=sample_store.id,
        category=FlagCategory.INVENTORY, severity=FlagSeverity.YELLOW,
        field_name="days_in_stock", message="Over 60 days", status=FlagStatus.VERIFIED,
    )
    f3 = Flag(
        meeting_id=sample_meeting.id, store_id=sample_store.id,
        category=FlagCategory.FINANCIAL, severity=FlagSeverity.RED,
        field_name="over_60", message="Receivable over 60", status=FlagStatus.UNRESOLVED,
    )
    db_session.add_all([f1, f2, f3])
    await db_session.flush()

    # Add attendance: 1 present, 1 absent
    attendee = User(id=ATTENDEE_ID, email="attendee@test.com", name="Bob Wilson", role=UserRole.MANAGER)
    db_session.add(attendee)
    await db_session.flush()

    db_session.add(UserStore(user_id=attendee.id, store_id=sample_store.id))

    att1 = MeetingAttendance(
        meeting_id=sample_meeting.id, user_id=corporate_user.id,
        checked_in=True, checked_in_at=datetime.datetime.now(datetime.timezone.utc),
    )
    att2 = MeetingAttendance(
        meeting_id=sample_meeting.id, user_id=attendee.id,
        checked_in=False,
    )
    db_session.add_all([att1, att2])
    await db_session.commit()
    return [f1, f2, f3]


@pytest.mark.asyncio
class TestCondensedPacket:

    async def test_returns_only_flagged_sections(
        self, client, auth_headers, meeting_with_mixed_flags,
    ):
        """GET /packets/{id}/condensed returns only sections with flags."""
        meeting_id = "22222222-2222-2222-2222-222222222222"
        resp = await client.get(f"/api/v1/packets/{meeting_id}/condensed", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()

        assert data["store_name"] == "Ashdown Classic Chevrolet"
        assert data["summary"]["total_flags"] == 3
        assert data["summary"]["red"] == 2
        assert data["summary"]["yellow"] == 1

        # Only inventory and financial should appear (operations has no flags)
        categories = [s["category"] for s in data["sections"]]
        assert "inventory" in categories
        assert "financial" in categories
        assert "operations" not in categories
        assert "parts" not in categories

    async def test_skips_sections_with_zero_flags(
        self, client, auth_headers, meeting_with_mixed_flags,
    ):
        """Sections with zero flags are excluded."""
        meeting_id = "22222222-2222-2222-2222-222222222222"
        resp = await client.get(f"/api/v1/packets/{meeting_id}/condensed", headers=auth_headers)
        data = resp.json()
        for section in data["sections"]:
            assert section["flag_count"] > 0

    async def test_includes_attendance_summary(
        self, client, auth_headers, meeting_with_mixed_flags,
    ):
        """Condensed response includes attendance data."""
        meeting_id = "22222222-2222-2222-2222-222222222222"
        resp = await client.get(f"/api/v1/packets/{meeting_id}/condensed", headers=auth_headers)
        data = resp.json()
        att = data["attendance"]
        assert att["expected"] == 2
        assert att["present"] == 1
        assert "Bob Wilson" in att["absent"]

    async def test_non_authorized_gets_403(self, client, manager_user):
        """Manager role cannot access condensed packet (corporate/GM only)."""
        headers = auth_header(manager_user)
        meeting_id = "22222222-2222-2222-2222-222222222222"
        resp = await client.get(f"/api/v1/packets/{meeting_id}/condensed", headers=headers)
        assert resp.status_code == 403
