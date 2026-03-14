"""Tests for execute report API endpoints."""

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


@pytest_asyncio.fixture
async def closed_meeting(db_session, sample_store):
    """Create a closed meeting for execute report tests."""
    meeting = Meeting(
        id=uuid.UUID("33333333-3333-3333-3333-333333333333"),
        store_id=sample_store.id,
        meeting_date=datetime.date(2026, 2, 11),
        status=MeetingStatus.CLOSED,
        closed_at=datetime.datetime(2026, 2, 11, 15, 30, tzinfo=datetime.timezone.utc),
    )
    db_session.add(meeting)
    await db_session.flush()

    # Add some flags with various statuses
    flags = [
        Flag(
            meeting_id=meeting.id, store_id=sample_store.id,
            category=FlagCategory.INVENTORY, severity=FlagSeverity.RED,
            field_name="days_in_stock", message="Used vehicle over 90 days",
            status=FlagStatus.UNRESOLVED,
        ),
        Flag(
            meeting_id=meeting.id, store_id=sample_store.id,
            category=FlagCategory.FINANCIAL, severity=FlagSeverity.RED,
            field_name="over_60", message="Receivable over 60 days",
            status=FlagStatus.VERIFIED,
        ),
        Flag(
            meeting_id=meeting.id, store_id=sample_store.id,
            category=FlagCategory.OPERATIONS, severity=FlagSeverity.YELLOW,
            field_name="days_open", message="Open RO over 14 days",
            status=FlagStatus.RESPONDED,
            response_text="RO closed on 2/15",
            responded_at=datetime.datetime(2026, 2, 15, 10, 0, tzinfo=datetime.timezone.utc),
        ),
    ]
    for f in flags:
        db_session.add(f)
    await db_session.commit()
    return meeting


@pytest.mark.asyncio
class TestDownloadExecuteReport:

    async def test_returns_pdf(self, client, auth_headers, closed_meeting):
        """GET /meetings/{id}/execute-report returns PDF content-type."""
        resp = await client.get(
            f"/api/v1/meetings/{closed_meeting.id}/execute-report",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert resp.content[:5] == b"%PDF-"
        assert len(resp.content) > 100

    async def test_custom_top_n(self, client, auth_headers, closed_meeting):
        """GET /meetings/{id}/execute-report?top_n=5 works."""
        resp = await client.get(
            f"/api/v1/meetings/{closed_meeting.id}/execute-report?top_n=5",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.content[:5] == b"%PDF-"

    async def test_gm_can_download(self, client, gm_user, closed_meeting):
        """GM users can download the execute report."""
        headers = auth_header(gm_user)
        resp = await client.get(
            f"/api/v1/meetings/{closed_meeting.id}/execute-report",
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.content[:5] == b"%PDF-"

    async def test_manager_cannot_download(self, client, manager_user, closed_meeting):
        """Manager role returns 403."""
        headers = auth_header(manager_user)
        resp = await client.get(
            f"/api/v1/meetings/{closed_meeting.id}/execute-report",
            headers=headers,
        )
        assert resp.status_code == 403

    async def test_nonexistent_meeting_returns_404(self, client, auth_headers):
        """Non-existent meeting returns 404."""
        fake_id = "99999999-9999-9999-9999-999999999999"
        resp = await client.get(
            f"/api/v1/meetings/{fake_id}/execute-report",
            headers=auth_headers,
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestSendExecuteReport:

    async def test_send_returns_count(self, client, auth_headers, closed_meeting, corporate_user):
        """POST /meetings/{id}/execute-report/send returns sent count."""
        resp = await client.post(
            f"/api/v1/meetings/{closed_meeting.id}/execute-report/send",
            headers=auth_headers,
            json={},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "sent_to" in data
        assert data["sent_to"] >= 1
        assert "message" in data

    async def test_send_with_specific_recipients(self, client, auth_headers, closed_meeting, corporate_user):
        """POST /meetings/{id}/execute-report/send with recipient_ids."""
        resp = await client.post(
            f"/api/v1/meetings/{closed_meeting.id}/execute-report/send",
            headers=auth_headers,
            json={"recipient_ids": [str(corporate_user.id)]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["sent_to"] >= 1

    async def test_gm_can_send(self, client, gm_user, closed_meeting, corporate_user):
        """GM can send the execute report."""
        headers = auth_header(gm_user)
        resp = await client.post(
            f"/api/v1/meetings/{closed_meeting.id}/execute-report/send",
            headers=headers,
            json={},
        )
        assert resp.status_code == 200

    async def test_manager_cannot_send(self, client, manager_user, closed_meeting):
        """Manager role returns 403."""
        headers = auth_header(manager_user)
        resp = await client.post(
            f"/api/v1/meetings/{closed_meeting.id}/execute-report/send",
            headers=headers,
            json={},
        )
        assert resp.status_code == 403

    async def test_nonexistent_meeting_returns_404(self, client, auth_headers):
        """Non-existent meeting returns 404."""
        fake_id = "99999999-9999-9999-9999-999999999999"
        resp = await client.post(
            f"/api/v1/meetings/{fake_id}/execute-report/send",
            headers=auth_headers,
            json={},
        )
        assert resp.status_code == 404
