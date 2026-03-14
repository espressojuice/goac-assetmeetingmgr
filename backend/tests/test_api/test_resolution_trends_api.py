"""Tests for resolution trends and promise tracking API endpoints."""

from __future__ import annotations

import datetime
import uuid

import pytest
import pytest_asyncio

from app.models.meeting import Meeting, MeetingStatus
from app.models.flag import Flag, FlagCategory, FlagSeverity, FlagStatus
from app.models.user import User, UserRole, UserStore
from app.models.accountability import FlagAssignment
from tests.test_api.conftest import auth_header


MANAGER_ID = uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")


@pytest_asyncio.fixture
async def meeting_with_flags(db_session, sample_store, sample_meeting, corporate_user):
    """Create flags with mixed statuses and promise dates."""
    now = datetime.datetime(2026, 2, 12, 10, 0, tzinfo=datetime.timezone.utc)

    manager = User(id=MANAGER_ID, email="trend_mgr@test.com", name="Trend Manager", role=UserRole.MANAGER)
    db_session.add(manager)
    await db_session.flush()
    db_session.add(UserStore(user_id=manager.id, store_id=sample_store.id))

    f1 = Flag(
        meeting_id=sample_meeting.id, store_id=sample_store.id,
        category=FlagCategory.INVENTORY, severity=FlagSeverity.RED,
        field_name="days_in_stock", message="Over 90 days", status=FlagStatus.VERIFIED,
        verified_at=now, expected_resolution_date=datetime.date(2026, 2, 10),
    )
    f2 = Flag(
        meeting_id=sample_meeting.id, store_id=sample_store.id,
        category=FlagCategory.FINANCIAL, severity=FlagSeverity.RED,
        field_name="over_60", message="Receivable over 60", status=FlagStatus.UNRESOLVED,
        expected_resolution_date=datetime.date(2026, 1, 15),  # broken
    )
    db_session.add_all([f1, f2])
    await db_session.flush()

    for f in [f1, f2]:
        db_session.add(FlagAssignment(
            flag_id=f.id, assigned_to_id=manager.id, assigned_by_id=corporate_user.id,
            deadline=datetime.date(2026, 2, 15),
        ))

    await db_session.commit()
    return [f1, f2]


# ── Resolution Trends Endpoint ────────────────────────────────────


@pytest.mark.asyncio
class TestResolutionTrendsEndpoint:

    async def test_returns_trends(self, client, auth_headers, meeting_with_flags):
        """GET /dashboard/resolution-trends returns list of trends."""
        resp = await client.get("/api/v1/dashboard/resolution-trends", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        trend = data[0]
        assert "meeting_id" in trend
        assert "resolution_rate" in trend
        assert "promises_kept" in trend
        assert "attendance_rate" in trend

    async def test_gm_is_store_scoped(self, client, gm_user, meeting_with_flags):
        """GM sees only their store's trends."""
        headers = auth_header(gm_user)
        resp = await client.get("/api/v1/dashboard/resolution-trends", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        for t in data:
            assert t["store_name"] == "Ashdown Classic Chevrolet"

    async def test_manager_returns_403(self, client, manager_user):
        """Manager role cannot access resolution-trends."""
        headers = auth_header(manager_user)
        resp = await client.get("/api/v1/dashboard/resolution-trends", headers=headers)
        assert resp.status_code == 403


# ── Promise Tracking Endpoint ─────────────────────────────────────


@pytest.mark.asyncio
class TestPromiseTrackingEndpoint:

    async def test_returns_summary(self, client, auth_headers, meeting_with_flags):
        """GET /dashboard/promise-tracking returns summary."""
        resp = await client.get("/api/v1/dashboard/promise-tracking", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "total_promises" in data
        assert "promises_kept" in data
        assert "promises_broken" in data
        assert "promises_pending" in data
        assert "worst_offenders" in data
        assert data["total_promises"] >= 2

    async def test_non_corporate_returns_403(self, client, gm_user):
        """GM cannot access promise-tracking (corporate only)."""
        headers = auth_header(gm_user)
        resp = await client.get("/api/v1/dashboard/promise-tracking", headers=headers)
        assert resp.status_code == 403
