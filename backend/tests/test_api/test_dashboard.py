"""Tests for the corporate dashboard endpoint."""

import pytest


@pytest.mark.asyncio
class TestDashboard:
    async def test_dashboard_empty(self, client, auth_headers):
        """Dashboard with no stores returns empty."""
        resp = await client.get("/api/v1/dashboard", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["stores"] == []
        assert data["totals"]["total_stores"] == 0
        assert data["totals"]["total_open_flags"] == 0

    async def test_dashboard_with_store(self, client, sample_store, auth_headers):
        """Dashboard includes active stores."""
        resp = await client.get("/api/v1/dashboard", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["totals"]["total_stores"] == 1
        assert data["stores"][0]["name"] == "Ashdown Classic Chevrolet"
        assert data["stores"][0]["code"] == "ASHDOWN"

    async def test_dashboard_with_meeting_and_flags(
        self, client, sample_store, sample_meeting, sample_flags, auth_headers
    ):
        """Dashboard aggregates flag stats correctly."""
        resp = await client.get("/api/v1/dashboard", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()

        store = data["stores"][0]
        assert store["last_meeting_date"] == "2026-02-11"
        assert store["flags"]["total"] == 4
        assert store["flags"]["red"] == 2
        assert store["flags"]["yellow"] == 2
        assert store["flags"]["open"] == 3
        assert store["flags"]["responded"] == 1

        # Response rate: 1 responded / 4 total = 25%
        assert store["response_rate"] == 25.0

        # Totals
        assert data["totals"]["total_open_flags"] == 3
        assert data["totals"]["avg_response_rate"] == 25.0

    async def test_dashboard_excludes_inactive_stores(
        self, client, db_session, sample_store, auth_headers
    ):
        """Inactive stores don't appear in dashboard."""
        sample_store.is_active = False
        await db_session.commit()

        resp = await client.get("/api/v1/dashboard", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()["stores"]) == 0

    async def test_dashboard_unauthenticated_returns_401(self, client):
        """Unauthenticated request returns 401."""
        resp = await client.get("/api/v1/dashboard")
        assert resp.status_code == 401
