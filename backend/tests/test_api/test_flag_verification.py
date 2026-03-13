"""Tests for flag verification endpoint (POST /flags/{flag_id}/verify)."""

from __future__ import annotations

import datetime
import uuid

import pytest
import pytest_asyncio

from app.models.flag import Flag, FlagCategory, FlagSeverity, FlagStatus
from app.models.accountability import AssignmentStatus, FlagAssignment
from tests.test_api.conftest import auth_header


@pytest_asyncio.fixture
async def responded_flag(db_session, sample_meeting, sample_store):
    """Create a flag in RESPONDED status for verification testing."""
    flag = Flag(
        id=uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd"),
        meeting_id=sample_meeting.id,
        store_id=sample_store.id,
        category=FlagCategory.FINANCIAL,
        severity=FlagSeverity.RED,
        field_name="over_60",
        field_value="$2,000",
        threshold="$0",
        message="Receivable over 60 days",
        status=FlagStatus.RESPONDED,
        response_text="Working with customer on payment plan",
        responded_by="Manager User",
        responded_at=datetime.datetime(2026, 3, 10, 10, 0, tzinfo=datetime.timezone.utc),
    )
    db_session.add(flag)
    await db_session.commit()
    return flag


@pytest_asyncio.fixture
async def open_flag(db_session, sample_meeting, sample_store):
    """Create a flag in OPEN status (not yet responded)."""
    flag = Flag(
        id=uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"),
        meeting_id=sample_meeting.id,
        store_id=sample_store.id,
        category=FlagCategory.INVENTORY,
        severity=FlagSeverity.RED,
        field_name="days_in_stock",
        field_value="120",
        threshold="90",
        message="Used vehicle over 90 days",
        status=FlagStatus.OPEN,
    )
    db_session.add(flag)
    await db_session.commit()
    return flag


@pytest_asyncio.fixture
async def responded_flag_with_assignment(db_session, responded_flag, manager_user, corporate_user):
    """Create a responded flag with an active assignment."""
    assignment = FlagAssignment(
        id=uuid.UUID("ffffffff-ffff-ffff-ffff-ffffffffffff"),
        flag_id=responded_flag.id,
        assigned_to_id=manager_user.id,
        assigned_by_id=corporate_user.id,
        status=AssignmentStatus.RESPONDED,
        deadline=datetime.date(2026, 3, 15),
    )
    db_session.add(assignment)
    await db_session.commit()
    return assignment


@pytest.mark.asyncio
class TestFlagVerification:
    """Test POST /api/v1/flags/{flag_id}/verify."""

    async def test_verify_flag_as_verified(
        self, client, responded_flag, corporate_user, auth_headers
    ):
        """Corporate user can mark a responded flag as verified."""
        resp = await client.post(
            f"/api/v1/flags/{responded_flag.id}/verify",
            json={"status": "verified"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "verified"
        assert data["verified_by_id"] == str(corporate_user.id)
        assert data["verified_at"] is not None

    async def test_verify_flag_as_unresolved_with_date(
        self, client, responded_flag, corporate_user, auth_headers
    ):
        """Corporate user can mark a flag as unresolved with expected resolution date."""
        resp = await client.post(
            f"/api/v1/flags/{responded_flag.id}/verify",
            json={
                "status": "unresolved",
                "verification_notes": "Answer not sufficient, need receipts",
                "expected_resolution_date": "2026-03-20",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "unresolved"
        assert data["verification_notes"] == "Answer not sufficient, need receipts"
        assert data["expected_resolution_date"] == "2026-03-20"

    async def test_verify_rejects_open_flag(
        self, client, open_flag, auth_headers
    ):
        """Cannot verify a flag that hasn't been responded to yet."""
        resp = await client.post(
            f"/api/v1/flags/{open_flag.id}/verify",
            json={"status": "verified"},
            headers=auth_headers,
        )
        assert resp.status_code == 422
        assert "responded" in resp.json()["detail"].lower()

    async def test_verify_rejects_manager_role(
        self, client, responded_flag, manager_user
    ):
        """Manager cannot verify flags — only corporate/GM."""
        headers = auth_header(manager_user)
        resp = await client.post(
            f"/api/v1/flags/{responded_flag.id}/verify",
            json={"status": "verified"},
            headers=headers,
        )
        assert resp.status_code == 403

    async def test_verify_notes_saved(
        self, client, responded_flag, auth_headers
    ):
        """Verification notes are persisted correctly."""
        notes = "Discussed at meeting — confirmed payment received"
        resp = await client.post(
            f"/api/v1/flags/{responded_flag.id}/verify",
            json={"status": "verified", "verification_notes": notes},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["verification_notes"] == notes

    async def test_verify_propagates_date_to_assignment(
        self, client, responded_flag_with_assignment, responded_flag,
        corporate_user, auth_headers, db_session
    ):
        """expected_resolution_date propagates to active FlagAssignment."""
        resp = await client.post(
            f"/api/v1/flags/{responded_flag.id}/verify",
            json={
                "status": "unresolved",
                "expected_resolution_date": "2026-03-25",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200

        # Refresh assignment from DB
        from sqlalchemy import select
        result = await db_session.execute(
            select(FlagAssignment).where(
                FlagAssignment.id == responded_flag_with_assignment.id
            )
        )
        assignment = result.scalar_one()
        assert assignment.expected_resolution_date == datetime.date(2026, 3, 25)

    async def test_verify_gm_can_verify(
        self, client, responded_flag, gm_user
    ):
        """GM user can verify flags for their store."""
        headers = auth_header(gm_user)
        resp = await client.post(
            f"/api/v1/flags/{responded_flag.id}/verify",
            json={"status": "verified"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "verified"

    async def test_verify_unauthenticated_rejected(
        self, client, responded_flag
    ):
        """Unauthenticated requests are rejected."""
        resp = await client.post(
            f"/api/v1/flags/{responded_flag.id}/verify",
            json={"status": "verified"},
        )
        assert resp.status_code == 401

    async def test_verify_flag_not_found(self, client, auth_headers):
        """Verifying a nonexistent flag returns 404."""
        fake_id = "99999999-9999-9999-9999-999999999999"
        resp = await client.post(
            f"/api/v1/flags/{fake_id}/verify",
            json={"status": "verified"},
            headers=auth_headers,
        )
        assert resp.status_code == 404
