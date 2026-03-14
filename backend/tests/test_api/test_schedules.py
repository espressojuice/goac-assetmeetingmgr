"""Tests for meeting scheduling API endpoints."""

import datetime
import uuid

import pytest
import pytest_asyncio

from tests.test_api.conftest import auth_header
from app.models.meeting import Meeting, MeetingStatus
from app.models.meeting_schedule import MeetingCadence, MeetingSchedule

STORE_ID = "11111111-1111-1111-1111-111111111111"


@pytest_asyncio.fixture
async def store_schedule(db_session, sample_store, corporate_user):
    """Create a schedule for sample_store."""
    schedule = MeetingSchedule(
        store_id=sample_store.id,
        cadence=MeetingCadence.BIWEEKLY,
        preferred_day_of_week=1,  # Tuesday
        preferred_time=datetime.time(14, 0),
        minimum_per_month=2,
        notes="Every other Tuesday",
        created_by_id=corporate_user.id,
    )
    db_session.add(schedule)
    await db_session.commit()
    return schedule


@pytest.mark.asyncio
class TestGetStoreSchedule:

    async def test_returns_schedule_with_upcoming(self, client, store_schedule, auth_headers):
        """GET returns schedule with upcoming_dates populated."""
        response = await client.get(f"/api/v1/stores/{STORE_ID}/schedule", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["store_name"] == "Ashdown Classic Chevrolet"
        assert data["cadence"] == "biweekly"
        assert data["preferred_day_of_week"] == 1
        assert data["preferred_time"] == "14:00"
        assert data["minimum_per_month"] == 2
        assert len(data["upcoming_dates"]) > 0

    async def test_404_when_no_schedule(self, client, sample_store, auth_headers):
        """GET returns 404 when store has no schedule."""
        response = await client.get(f"/api/v1/stores/{STORE_ID}/schedule", headers=auth_headers)
        assert response.status_code == 404

    async def test_unauthenticated_blocked(self, client, sample_store, store_schedule):
        """GET without auth returns 401."""
        response = await client.get(f"/api/v1/stores/{STORE_ID}/schedule")
        assert response.status_code == 401


@pytest.mark.asyncio
class TestSetStoreSchedule:

    async def test_creates_new_schedule(self, client, sample_store, auth_headers):
        """PUT creates schedule when none exists."""
        response = await client.put(
            f"/api/v1/stores/{STORE_ID}/schedule",
            json={
                "cadence": "weekly",
                "preferred_day_of_week": 3,
                "preferred_time": "10:00",
                "minimum_per_month": 4,
                "notes": "Weekly on Thursday",
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["cadence"] == "weekly"
        assert data["preferred_day_of_week"] == 3
        assert data["preferred_time"] == "10:00"
        assert data["minimum_per_month"] == 4

    async def test_updates_existing_schedule(self, client, store_schedule, auth_headers):
        """PUT updates existing schedule."""
        response = await client.put(
            f"/api/v1/stores/{STORE_ID}/schedule",
            json={
                "cadence": "first_and_third",
                "preferred_day_of_week": 4,
                "minimum_per_month": 2,
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["cadence"] == "first_and_third"
        assert data["preferred_day_of_week"] == 4

    async def test_gm_can_set_own_store(self, client, sample_store, gm_user):
        """GM can PUT schedule for their own store."""
        headers = auth_header(gm_user)
        response = await client.put(
            f"/api/v1/stores/{STORE_ID}/schedule",
            json={"cadence": "biweekly", "preferred_day_of_week": 2},
            headers=headers,
        )
        assert response.status_code == 200

    async def test_gm_blocked_from_other_store(self, client, gm_user, db_session):
        """GM cannot PUT schedule for a store they don't manage."""
        from app.models.store import Store
        other_store = Store(
            id=uuid.UUID("99999999-9999-9999-9999-999999999999"),
            name="Other Store",
            code="OTHER",
            city="Dallas",
            state="TX",
        )
        db_session.add(other_store)
        await db_session.commit()

        headers = auth_header(gm_user)
        response = await client.put(
            f"/api/v1/stores/{other_store.id}/schedule",
            json={"cadence": "biweekly"},
            headers=headers,
        )
        assert response.status_code == 403

    async def test_manager_blocked(self, client, sample_store, manager_user):
        """Manager cannot access schedule endpoints (403)."""
        headers = auth_header(manager_user)
        response = await client.put(
            f"/api/v1/stores/{STORE_ID}/schedule",
            json={"cadence": "biweekly"},
            headers=headers,
        )
        assert response.status_code == 403


@pytest.mark.asyncio
class TestComplianceEndpoint:

    async def test_returns_all_stores(self, client, store_schedule, auth_headers, db_session, sample_store):
        """GET /schedules/compliance returns compliance for all scheduled stores."""
        # Add a meeting to make it partially compliant
        db_session.add(Meeting(
            store_id=sample_store.id,
            meeting_date=datetime.date.today().replace(day=5),
            status=MeetingStatus.COMPLETED,
        ))
        await db_session.commit()

        response = await client.get("/api/v1/schedules/compliance", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert "store_name" in data[0]
        assert "is_compliant" in data[0]
        assert "actual_count" in data[0]

    async def test_non_corporate_blocked(self, client, store_schedule, gm_user):
        """Non-corporate users cannot access compliance endpoint."""
        headers = auth_header(gm_user)
        response = await client.get("/api/v1/schedules/compliance", headers=headers)
        assert response.status_code == 403


@pytest.mark.asyncio
class TestTemplateFields:

    async def test_put_with_template_fields(self, client, sample_store, auth_headers, corporate_user):
        """PUT schedule with template fields saves them."""
        response = await client.put(
            f"/api/v1/stores/{STORE_ID}/schedule",
            json={
                "cadence": "biweekly",
                "preferred_day_of_week": 1,
                "template_name": "Weekly Asset Meeting",
                "default_attendee_ids": [str(corporate_user.id)],
                "auto_create_meetings": True,
                "reminder_days_before": 3,
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["template_name"] == "Weekly Asset Meeting"
        assert data["auto_create_meetings"] is True
        assert data["reminder_days_before"] == 3
        assert len(data["default_attendee_ids"]) == 1
        assert data["default_attendee_names"] == ["Corporate Admin"]

    async def test_get_returns_template_fields(self, client, sample_store, auth_headers, corporate_user, db_session):
        """GET returns template fields including resolved attendee names."""
        schedule = MeetingSchedule(
            store_id=sample_store.id,
            cadence=MeetingCadence.BIWEEKLY,
            preferred_day_of_week=1,
            minimum_per_month=2,
            template_name="Test Template",
            default_attendee_ids=[str(corporate_user.id)],
            auto_create_meetings=False,
            reminder_days_before=5,
            created_by_id=corporate_user.id,
        )
        db_session.add(schedule)
        await db_session.commit()

        response = await client.get(f"/api/v1/stores/{STORE_ID}/schedule", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["template_name"] == "Test Template"
        assert data["auto_create_meetings"] is False
        assert data["reminder_days_before"] == 5
        assert data["default_attendee_names"] == ["Corporate Admin"]


@pytest.mark.asyncio
class TestAutoCreateEndpoint:

    async def test_creates_meetings(self, client, auth_headers, db_session, sample_store, corporate_user):
        """POST /schedules/auto-create creates meetings."""
        schedule = MeetingSchedule(
            store_id=sample_store.id,
            cadence=MeetingCadence.BIWEEKLY,
            preferred_day_of_week=1,
            minimum_per_month=2,
            auto_create_meetings=True,
            is_active=True,
            created_by_id=corporate_user.id,
        )
        db_session.add(schedule)
        await db_session.commit()

        response = await client.post("/api/v1/schedules/auto-create", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["created"] > 0
        assert len(data["meetings"]) == data["created"]

    async def test_corporate_only(self, client, gm_user):
        """POST /schedules/auto-create is corporate only (403 for GM)."""
        headers = auth_header(gm_user)
        response = await client.post("/api/v1/schedules/auto-create", headers=headers)
        assert response.status_code == 403


@pytest.mark.asyncio
class TestOverdueEndpoint:

    async def test_returns_overdue_stores(self, client, store_schedule, auth_headers, db_session, sample_store):
        """GET /schedules/overdue returns stores behind on cadence."""
        # Add old meeting (25 days ago)
        db_session.add(Meeting(
            store_id=sample_store.id,
            meeting_date=datetime.date.today() - datetime.timedelta(days=25),
            status=MeetingStatus.COMPLETED,
        ))
        await db_session.commit()

        response = await client.get("/api/v1/schedules/overdue", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["store_name"] == "Ashdown Classic Chevrolet"
        assert data[0]["days_overdue"] > 0

    async def test_non_corporate_blocked(self, client, store_schedule, manager_user):
        """Non-corporate users cannot access overdue endpoint."""
        headers = auth_header(manager_user)
        response = await client.get("/api/v1/schedules/overdue", headers=headers)
        assert response.status_code == 403
