"""Tests for the CSV export API endpoints."""

from __future__ import annotations

import datetime
import uuid

import pytest
import pytest_asyncio

from app.models.meeting import Meeting, MeetingStatus
from app.models.flag import Flag, FlagCategory, FlagSeverity, FlagStatus
from app.models.user import User, UserRole, UserStore
from app.models.accountability import FlagAssignment, MeetingAttendance
from tests.test_api.conftest import auth_header


@pytest_asyncio.fixture
async def export_data(db_session, sample_store, sample_meeting, corporate_user):
    """Seed minimal data for export endpoint tests."""
    manager = User(
        id=uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"),
        email="export_mgr@test.com", name="Export Manager", role=UserRole.MANAGER,
    )
    db_session.add(manager)
    await db_session.flush()
    db_session.add(UserStore(user_id=manager.id, store_id=sample_store.id))

    flag = Flag(
        meeting_id=sample_meeting.id, store_id=sample_store.id,
        category=FlagCategory.INVENTORY, severity=FlagSeverity.RED,
        field_name="days_in_stock", message="Over 90 days", status=FlagStatus.OPEN,
        expected_resolution_date=datetime.date(2026, 3, 15),
    )
    db_session.add(flag)
    await db_session.flush()

    db_session.add(FlagAssignment(
        flag_id=flag.id, assigned_to_id=manager.id, assigned_by_id=corporate_user.id,
        deadline=datetime.date(2026, 3, 10),
    ))

    db_session.add(MeetingAttendance(
        meeting_id=sample_meeting.id, user_id=manager.id,
        checked_in=True,
        checked_in_at=datetime.datetime(2026, 2, 11, 14, 0, tzinfo=datetime.timezone.utc),
        checked_in_by_id=corporate_user.id,
    ))

    await db_session.commit()
    return {"flag": flag, "manager": manager}


@pytest.mark.asyncio
class TestExportMeetingsAPI:

    async def test_returns_csv_content_type(self, client, auth_headers, export_data):
        resp = await client.get("/api/v1/exports/meetings", headers=auth_headers)
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        assert "meetings_export" in resp.headers["content-disposition"]
        text = resp.text
        assert "Meeting Date" in text
        assert "Ashdown Classic Chevrolet" in text


@pytest.mark.asyncio
class TestExportFlagsAPI:

    async def test_returns_csv_with_correct_columns(self, client, auth_headers, export_data):
        resp = await client.get("/api/v1/exports/flags", headers=auth_headers)
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        text = resp.text
        assert "Priority Score" in text
        assert "days_in_stock" in text


@pytest.mark.asyncio
class TestExportAttendanceAPI:

    async def test_returns_csv(self, client, auth_headers, export_data):
        resp = await client.get("/api/v1/exports/attendance", headers=auth_headers)
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        text = resp.text
        assert "Checked In" in text
        assert "Export Manager" in text


@pytest.mark.asyncio
class TestExportPromiseTrackingAPI:

    async def test_returns_csv(self, client, auth_headers, export_data):
        resp = await client.get("/api/v1/exports/promise-tracking", headers=auth_headers)
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        text = resp.text
        assert "Promise Kept" in text


@pytest.mark.asyncio
class TestExportAccessControl:

    async def test_non_corporate_returns_403(self, client, gm_user, export_data):
        headers = auth_header(gm_user)
        for endpoint in [
            "/api/v1/exports/meetings",
            "/api/v1/exports/flags",
            "/api/v1/exports/attendance",
            "/api/v1/exports/promise-tracking",
        ]:
            resp = await client.get(endpoint, headers=headers)
            assert resp.status_code == 403, f"Expected 403 for {endpoint}"

    async def test_manager_returns_403(self, client, manager_user, export_data):
        headers = auth_header(manager_user)
        resp = await client.get("/api/v1/exports/meetings", headers=headers)
        assert resp.status_code == 403
