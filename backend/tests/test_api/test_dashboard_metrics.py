"""Tests for the new dashboard metrics endpoints (manager-metrics, store-comparison, top-priorities)."""

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


MANAGER_ID = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")


@pytest_asyncio.fixture
async def manager_with_flags(db_session, sample_store, sample_meeting, corporate_user):
    """Create a manager with flag assignments of mixed statuses."""
    manager = User(
        id=MANAGER_ID, email="tommy@test.com", name="Tommy Test", role=UserRole.MANAGER,
    )
    db_session.add(manager)
    await db_session.flush()

    assoc = UserStore(user_id=manager.id, store_id=sample_store.id)
    db_session.add(assoc)

    now = datetime.datetime(2026, 2, 12, 10, 0, tzinfo=datetime.timezone.utc)
    flags = [
        Flag(
            meeting_id=sample_meeting.id, store_id=sample_store.id,
            category=FlagCategory.INVENTORY, severity=FlagSeverity.RED,
            field_name="days_in_stock", message="Over 90 days", status=FlagStatus.VERIFIED,
            responded_at=now,
        ),
        Flag(
            meeting_id=sample_meeting.id, store_id=sample_store.id,
            category=FlagCategory.FINANCIAL, severity=FlagSeverity.RED,
            field_name="over_60", message="Receivable over 60", status=FlagStatus.UNRESOLVED,
        ),
        Flag(
            meeting_id=sample_meeting.id, store_id=sample_store.id,
            category=FlagCategory.OPERATIONS, severity=FlagSeverity.YELLOW,
            field_name="days_open", message="Open RO over 14 days", status=FlagStatus.OPEN,
        ),
    ]
    for f in flags:
        db_session.add(f)
    await db_session.flush()

    for f in flags:
        assignment = FlagAssignment(
            flag_id=f.id, assigned_to_id=manager.id, assigned_by_id=corporate_user.id,
            deadline=datetime.date(2026, 2, 15),
        )
        db_session.add(assignment)

    await db_session.commit()
    return manager, flags


# ── Manager Metrics Tests ─────────────────────────────────────────────


@pytest.mark.asyncio
class TestManagerMetricsEndpoint:

    async def test_returns_metrics_for_managers(
        self, client, auth_headers, manager_with_flags,
    ):
        """GET /dashboard/manager-metrics returns metrics for all managers."""
        resp = await client.get("/api/v1/dashboard/manager-metrics", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        tommy = next(m for m in data if m["user_name"] == "Tommy Test")
        assert tommy["total_assigned"] == 3
        assert tommy["total_resolved"] == 1

    async def test_with_store_id_filter(
        self, client, auth_headers, sample_store, manager_with_flags,
    ):
        """Filtering by store_id works."""
        resp = await client.get(
            f"/api/v1/dashboard/manager-metrics?store_id={sample_store.id}",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1

    async def test_non_corporate_returns_403(self, client, gm_user):
        """GM users cannot access manager-metrics."""
        headers = auth_header(gm_user)
        resp = await client.get("/api/v1/dashboard/manager-metrics", headers=headers)
        assert resp.status_code == 403


# ── Store Comparison Tests ────────────────────────────────────────────


@pytest.mark.asyncio
class TestStoreComparisonEndpoint:

    async def test_returns_all_stores(
        self, client, auth_headers, sample_store, manager_with_flags,
    ):
        """GET /dashboard/store-comparison returns all stores."""
        resp = await client.get("/api/v1/dashboard/store-comparison", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        ashdown = next(s for s in data if s["store_name"] == "Ashdown Classic Chevrolet")
        assert ashdown["total_flags"] >= 3

    async def test_non_corporate_returns_403(self, client, gm_user):
        """GM users cannot access store-comparison."""
        headers = auth_header(gm_user)
        resp = await client.get("/api/v1/dashboard/store-comparison", headers=headers)
        assert resp.status_code == 403


# ── Top Priorities Tests ──────────────────────────────────────────────


@pytest.mark.asyncio
class TestTopPrioritiesEndpoint:

    async def test_returns_scored_items(
        self, client, auth_headers, manager_with_flags,
    ):
        """GET /dashboard/top-priorities returns scored items sorted by priority."""
        resp = await client.get("/api/v1/dashboard/top-priorities", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        # Should have UNRESOLVED and OPEN flags (VERIFIED excluded)
        assert len(data) >= 2
        # First item should have highest score
        scores = [item["priority_score"] for item in data]
        assert scores == sorted(scores, reverse=True)

    async def test_gm_sees_only_own_stores(
        self, client, gm_user, manager_with_flags,
    ):
        """GM users only see priority items for their stores."""
        headers = auth_header(gm_user)
        resp = await client.get("/api/v1/dashboard/top-priorities", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        # GM has access to sample_store, should see its flags
        for item in data:
            assert item["store_name"] == "Ashdown Classic Chevrolet"

    async def test_manager_returns_403(self, client, manager_user):
        """Manager role cannot access top-priorities."""
        headers = auth_header(manager_user)
        resp = await client.get("/api/v1/dashboard/top-priorities", headers=headers)
        assert resp.status_code == 403


# ── Enhanced Dashboard Tests ──────────────────────────────────────────


@pytest.mark.asyncio
class TestEnhancedDashboard:

    async def test_dashboard_includes_new_fields(
        self, client, auth_headers, sample_store, manager_with_flags,
    ):
        """Enhanced GET /dashboard includes top_priority_count and worst_resolution_rate."""
        resp = await client.get("/api/v1/dashboard", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        totals = data["totals"]
        assert "top_priority_count" in totals
        assert "worst_resolution_rate" in totals
        assert isinstance(totals["top_priority_count"], int)
