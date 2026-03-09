"""Tests for stores API endpoints."""

import pytest


STORES_URL = "/api/v1/stores"
STORE_ID = "11111111-1111-1111-1111-111111111111"
FAKE_STORE = "99999999-9999-9999-9999-999999999999"


@pytest.mark.asyncio
class TestListStores:

    async def test_list_stores(self, client, sample_store):
        """List returns active stores."""
        response = await client.get(STORES_URL)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Ashdown Classic Chevrolet"
        assert data[0]["code"] == "ASHDOWN"

    async def test_list_stores_empty(self, client):
        """Empty store list returns empty array."""
        response = await client.get(STORES_URL)
        assert response.status_code == 200
        assert response.json() == []

    async def test_store_response_shape(self, client, sample_store):
        """Verify store response includes all fields."""
        response = await client.get(STORES_URL)
        store = response.json()[0]
        assert "id" in store
        assert "name" in store
        assert "code" in store
        assert "brand" in store
        assert "city" in store
        assert "state" in store
        assert "timezone" in store
        assert "meeting_cadence" in store
        assert "gm_name" in store
        assert "gm_email" in store
        assert "is_active" in store
        assert "created_at" in store


@pytest.mark.asyncio
class TestGetStoreDetail:

    async def test_get_store_returns_rich_detail(self, client, sample_store):
        """Get store returns rich detail with store, stats, meetings, users."""
        response = await client.get(f"{STORES_URL}/{STORE_ID}")
        assert response.status_code == 200
        data = response.json()
        # Top-level keys
        assert "store" in data
        assert "stats" in data
        assert "recent_meetings" in data
        assert "users" in data

    async def test_get_store_info_shape(self, client, sample_store):
        """Store info has expected fields."""
        response = await client.get(f"{STORES_URL}/{STORE_ID}")
        store = response.json()["store"]
        assert store["name"] == "Ashdown Classic Chevrolet"
        assert store["code"] == "ASHDOWN"
        assert store["brand"] == "Chevrolet"
        assert store["city"] == "Ashdown"
        assert store["state"] == "AR"
        assert store["gm_name"] == "John Doe"
        assert store["is_active"] is True

    async def test_get_store_stats_no_meetings(self, client, sample_store):
        """Stats are zeroed when no meetings exist."""
        response = await client.get(f"{STORES_URL}/{STORE_ID}")
        stats = response.json()["stats"]
        assert stats["total_meetings"] == 0
        assert stats["total_flags_all_time"] == 0
        assert stats["current_open_flags"] == 0
        assert stats["response_rate"] == 0.0
        assert stats["avg_flags_per_meeting"] == 0.0
        assert stats["most_common_flag_category"] is None

    async def test_get_store_stats_with_flags(self, client, sample_store, sample_meeting, sample_flags):
        """Stats reflect actual flag data."""
        response = await client.get(f"{STORES_URL}/{STORE_ID}")
        stats = response.json()["stats"]
        assert stats["total_meetings"] == 1
        assert stats["total_flags_all_time"] == 4
        assert stats["current_open_flags"] == 3  # 3 OPEN, 1 RESPONDED
        assert stats["response_rate"] == 25.0  # 1/4 = 25%
        assert stats["avg_flags_per_meeting"] == 4.0

    async def test_get_store_recent_meetings_with_flags(self, client, sample_store, sample_meeting, sample_flags):
        """Recent meetings include per-meeting flag summaries."""
        response = await client.get(f"{STORES_URL}/{STORE_ID}")
        meetings = response.json()["recent_meetings"]
        assert len(meetings) == 1
        m = meetings[0]
        assert m["meeting_date"] == "2026-02-11"
        assert m["status"] == "completed"
        assert m["flags"]["total"] == 4
        assert m["flags"]["red"] == 2
        assert m["flags"]["yellow"] == 2
        assert m["flags"]["open"] == 3
        assert m["flags"]["responded"] == 1
        assert m["response_rate"] == 25.0

    async def test_get_store_empty_meetings(self, client, sample_store):
        """Store with no meetings returns empty arrays."""
        response = await client.get(f"{STORES_URL}/{STORE_ID}")
        data = response.json()
        assert data["recent_meetings"] == []
        assert data["users"] == []

    async def test_get_store_not_found(self, client):
        """Nonexistent store returns 404."""
        response = await client.get(f"{STORES_URL}/{FAKE_STORE}")
        assert response.status_code == 404

    async def test_get_store_invalid_id(self, client):
        """Invalid UUID returns 422."""
        response = await client.get(f"{STORES_URL}/not-a-uuid")
        assert response.status_code == 422


@pytest.mark.asyncio
class TestGetStoreFlagTrends:

    async def test_flag_trends_structure(self, client, sample_store, sample_meeting, sample_flags):
        """Flag trends returns correct structure."""
        response = await client.get(f"{STORES_URL}/{STORE_ID}/flag-trends")
        assert response.status_code == 200
        data = response.json()
        assert "meetings" in data
        assert len(data["meetings"]) == 1
        m = data["meetings"][0]
        assert "date" in m
        assert "red" in m
        assert "yellow" in m
        assert "responded" in m
        assert "response_rate" in m

    async def test_flag_trends_values(self, client, sample_store, sample_meeting, sample_flags):
        """Flag trends reflect actual data."""
        response = await client.get(f"{STORES_URL}/{STORE_ID}/flag-trends")
        m = response.json()["meetings"][0]
        assert m["date"] == "2026-02-11"
        assert m["red"] == 2
        assert m["yellow"] == 2
        assert m["responded"] == 1
        assert m["response_rate"] == 25.0

    async def test_flag_trends_empty(self, client, sample_store):
        """No completed meetings returns empty list."""
        response = await client.get(f"{STORES_URL}/{STORE_ID}/flag-trends")
        assert response.status_code == 200
        assert response.json()["meetings"] == []

    async def test_flag_trends_not_found(self, client):
        """Nonexistent store returns 404."""
        response = await client.get(f"{STORES_URL}/{FAKE_STORE}/flag-trends")
        assert response.status_code == 404


@pytest.mark.asyncio
class TestCreateStore:

    async def test_create_store(self, client):
        """Create a new store returns 201."""
        response = await client.post(
            STORES_URL,
            json={
                "name": "Hot Springs Toyota",
                "code": "HOTSPRINGS",
                "city": "Hot Springs",
                "state": "AR",
                "brand": "Toyota",
                "meeting_cadence": "biweekly",
                "gm_name": "Mike Johnson",
                "gm_email": "mjohnson@greggorracing.com",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Hot Springs Toyota"
        assert data["code"] == "HOTSPRINGS"
        assert data["is_active"] is True
        assert data["timezone"] == "US/Central"

    async def test_create_store_minimal(self, client):
        """Create store with only required fields."""
        response = await client.post(
            STORES_URL,
            json={
                "name": "Test Store",
                "code": "TEST",
                "city": "Test City",
                "state": "AR",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["meeting_cadence"] == "biweekly"  # default
        assert data["brand"] is None

    async def test_create_store_duplicate_code(self, client, sample_store):
        """Creating a store with duplicate code returns 409."""
        response = await client.post(
            STORES_URL,
            json={
                "name": "Another Store",
                "code": "ASHDOWN",  # already exists
                "city": "Ashdown",
                "state": "AR",
            },
        )
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]

    async def test_create_store_missing_required(self, client):
        """Missing required fields returns 422."""
        response = await client.post(
            STORES_URL,
            json={"name": "Incomplete Store"},
        )
        assert response.status_code == 422


@pytest.mark.asyncio
class TestGetStoreMeetings:

    async def test_get_store_meetings(self, client, sample_store, sample_meeting):
        """Get meetings for a store."""
        response = await client.get(f"{STORES_URL}/{STORE_ID}/meetings")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["meeting_date"] == "2026-02-11"

    async def test_get_store_meetings_empty(self, client, sample_store):
        """Store with no meetings returns empty list."""
        response = await client.get(f"{STORES_URL}/{STORE_ID}/meetings")
        assert response.status_code == 200
        assert response.json() == []

    async def test_get_store_meetings_limit(self, client, sample_store, sample_meeting):
        """Limit parameter is respected."""
        response = await client.get(f"{STORES_URL}/{STORE_ID}/meetings?limit=1")
        assert response.status_code == 200
        assert len(response.json()) <= 1

    async def test_get_meetings_store_not_found(self, client):
        """Meetings for nonexistent store returns 404."""
        response = await client.get(f"{STORES_URL}/{FAKE_STORE}/meetings")
        assert response.status_code == 404
