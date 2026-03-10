"""Tests for the flag response workflow: assignment, response, escalation, recurring detection."""

import datetime
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.auth import create_access_token
from app.database import Base, get_db
from app.main import app
from app.models.flag import Flag, FlagCategory, FlagSeverity, FlagStatus
from app.models.meeting import Meeting, MeetingStatus
from app.models.store import Store
from app.models.user import User, UserRole, UserStore
from app.models.accountability import FlagAssignment, AssignmentStatus


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite:///", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_engine):
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def store(db_session):
    s = Store(
        id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        name="Test Dealership",
        code="TEST",
        brand="Chevrolet",
        city="Ashdown",
        state="AR",
        gm_name="GM User",
        gm_email="gm@test.com",
    )
    db_session.add(s)
    await db_session.commit()
    return s


@pytest_asyncio.fixture
async def gm_user(db_session, store):
    u = User(
        id=uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        email="gm@test.com",
        name="GM User",
        role=UserRole.GM,
    )
    db_session.add(u)
    await db_session.flush()
    # Associate GM with their store
    assoc = UserStore(user_id=u.id, store_id=store.id)
    db_session.add(assoc)
    await db_session.commit()
    return u


@pytest_asyncio.fixture
async def corporate_user(db_session):
    u = User(
        id=uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
        email="corp@test.com",
        name="Corporate User",
        role=UserRole.CORPORATE,
    )
    db_session.add(u)
    await db_session.commit()
    return u


@pytest_asyncio.fixture
async def manager_user(db_session, store):
    u = User(
        id=uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"),
        email="manager@test.com",
        name="Manager User",
        role=UserRole.MANAGER,
    )
    db_session.add(u)
    await db_session.flush()
    assoc = UserStore(user_id=u.id, store_id=store.id)
    db_session.add(assoc)
    await db_session.commit()
    return u


@pytest_asyncio.fixture
async def viewer_user(db_session):
    u = User(
        id=uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd"),
        email="viewer@test.com",
        name="Viewer User",
        role=UserRole.VIEWER,
    )
    db_session.add(u)
    await db_session.commit()
    return u


@pytest_asyncio.fixture
async def meeting(db_session, store):
    m = Meeting(
        id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
        store_id=store.id,
        meeting_date=datetime.date(2026, 2, 11),
        status=MeetingStatus.COMPLETED,
    )
    db_session.add(m)
    await db_session.commit()
    return m


@pytest_asyncio.fixture
async def flags(db_session, meeting, store):
    flag_list = [
        Flag(
            id=uuid.UUID("ff000001-0000-0000-0000-000000000001"),
            meeting_id=meeting.id,
            store_id=store.id,
            category=FlagCategory.INVENTORY,
            severity=FlagSeverity.RED,
            field_name="days_in_stock",
            field_value="95",
            threshold="90",
            message="Used vehicle over 90 days",
            status=FlagStatus.OPEN,
        ),
        Flag(
            id=uuid.UUID("ff000002-0000-0000-0000-000000000002"),
            meeting_id=meeting.id,
            store_id=store.id,
            category=FlagCategory.PARTS,
            severity=FlagSeverity.YELLOW,
            field_name="turnover",
            field_value="3.2",
            threshold="4.0",
            message="Parts turnover below threshold",
            status=FlagStatus.OPEN,
        ),
        Flag(
            id=uuid.UUID("ff000003-0000-0000-0000-000000000003"),
            meeting_id=meeting.id,
            store_id=store.id,
            category=FlagCategory.FINANCIAL,
            severity=FlagSeverity.RED,
            field_name="over_60",
            field_value="$1,500",
            threshold="$0",
            message="Receivable over 60 days",
            status=FlagStatus.OPEN,
        ),
        Flag(
            id=uuid.UUID("ff000004-0000-0000-0000-000000000004"),
            meeting_id=meeting.id,
            store_id=store.id,
            category=FlagCategory.OPERATIONS,
            severity=FlagSeverity.YELLOW,
            field_name="days_open",
            field_value="18",
            threshold="14",
            message="Open RO over 14 days",
            status=FlagStatus.OPEN,
        ),
    ]
    for f in flag_list:
        db_session.add(f)
    await db_session.commit()
    return flag_list


def _auth_header(user: User) -> dict:
    token = create_access_token(str(user.id), user.email, user.role.value)
    return {"Authorization": f"Bearer {token}"}


# ── Auto-assign Tests ────────────────────────────────────────────────


@pytest.mark.asyncio
class TestAutoAssign:
    async def test_auto_assign_assigns_to_gm(
        self, client, store, meeting, flags, gm_user, corporate_user
    ):
        resp = await client.post(
            f"/api/v1/meetings/{meeting.id}/auto-assign",
            headers=_auth_header(corporate_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["assigned_count"] == 4
        assert data["unassigned_count"] == 0

    async def test_auto_assign_sets_deadline(
        self, client, db_session, store, meeting, flags, gm_user, corporate_user
    ):
        resp = await client.post(
            f"/api/v1/meetings/{meeting.id}/auto-assign",
            headers=_auth_header(corporate_user),
        )
        assert resp.status_code == 200

        # Check deadline = meeting_date + 1 day
        from sqlalchemy import select as sel
        result = await db_session.execute(
            sel(FlagAssignment).where(FlagAssignment.flag_id == flags[0].id)
        )
        assignment = result.scalar_one_or_none()
        assert assignment is not None
        expected_deadline = meeting.meeting_date + datetime.timedelta(days=1)
        assert assignment.deadline == expected_deadline

    async def test_auto_assign_falls_back_to_gm(
        self, client, store, meeting, flags, gm_user, corporate_user
    ):
        """Parts/financial/operations flags all fall back to GM since no store-user mapping."""
        resp = await client.post(
            f"/api/v1/meetings/{meeting.id}/auto-assign",
            headers=_auth_header(corporate_user),
        )
        data = resp.json()
        # All categories should be assigned
        assert "inventory" in data["by_category"]
        assert "parts" in data["by_category"]

    async def test_auto_assign_by_category(
        self, client, store, meeting, flags, gm_user, corporate_user
    ):
        resp = await client.post(
            f"/api/v1/meetings/{meeting.id}/auto-assign",
            headers=_auth_header(corporate_user),
        )
        data = resp.json()
        assert data["by_category"]["inventory"] == 1
        assert data["by_category"]["parts"] == 1
        assert data["by_category"]["financial"] == 1
        assert data["by_category"]["operations"] == 1

    async def test_auto_assign_requires_auth(self, client, meeting, flags):
        resp = await client.post(f"/api/v1/meetings/{meeting.id}/auto-assign")
        assert resp.status_code == 401 or resp.status_code == 403


# ── Manual Assign Tests ──────────────────────────────────────────────


@pytest.mark.asyncio
class TestManualAssign:
    async def test_assign_flag(
        self, client, flags, gm_user, corporate_user
    ):
        resp = await client.post(
            f"/api/v1/flags/{flags[0].id}/assign",
            headers=_auth_header(corporate_user),
            json={"assigned_to_id": str(gm_user.id)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["assigned_to_id"] == str(gm_user.id)
        assert data["status"] == "pending"

    async def test_assign_flag_requires_corporate_or_gm(
        self, client, flags, manager_user
    ):
        resp = await client.post(
            f"/api/v1/flags/{flags[0].id}/assign",
            headers=_auth_header(manager_user),
            json={"assigned_to_id": str(manager_user.id)},
        )
        assert resp.status_code == 403


# ── Response Tests ───────────────────────────────────────────────────


@pytest.mark.asyncio
class TestFlagResponse:
    async def test_submit_response(
        self, client, db_session, flags, gm_user, corporate_user
    ):
        # First assign
        await client.post(
            f"/api/v1/flags/{flags[0].id}/assign",
            headers=_auth_header(corporate_user),
            json={"assigned_to_id": str(gm_user.id)},
        )
        # Then respond
        resp = await client.post(
            f"/api/v1/flags/{flags[0].id}/respond-workflow",
            headers=_auth_header(gm_user),
            json={"response_text": "Vehicle has been marked down and listed on AutoTrader."},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["response_text"] == "Vehicle has been marked down and listed on AutoTrader."

    async def test_response_updates_flag_status(
        self, client, flags, gm_user, corporate_user
    ):
        # Assign + respond
        await client.post(
            f"/api/v1/flags/{flags[0].id}/assign",
            headers=_auth_header(corporate_user),
            json={"assigned_to_id": str(gm_user.id)},
        )
        await client.post(
            f"/api/v1/flags/{flags[0].id}/respond-workflow",
            headers=_auth_header(gm_user),
            json={"response_text": "Vehicle has been marked down and listed on AutoTrader."},
        )

        # Verify via the API (avoids stale session issues)
        resp = await client.get(
            "/api/v1/flags/my/assigned",
            headers=_auth_header(gm_user),
        )
        responded = [f for f in resp.json() if f["id"] == str(flags[0].id)]
        assert len(responded) == 1
        assert responded[0]["status"] == "responded"
        assert responded[0]["response_text"] == "Vehicle has been marked down and listed on AutoTrader."

    async def test_response_requires_min_10_chars(
        self, client, flags, gm_user, corporate_user
    ):
        await client.post(
            f"/api/v1/flags/{flags[0].id}/assign",
            headers=_auth_header(corporate_user),
            json={"assigned_to_id": str(gm_user.id)},
        )
        resp = await client.post(
            f"/api/v1/flags/{flags[0].id}/respond-workflow",
            headers=_auth_header(gm_user),
            json={"response_text": "ok done"},
        )
        assert resp.status_code == 422

    async def test_only_assigned_user_or_corporate_can_respond(
        self, client, flags, gm_user, corporate_user, manager_user
    ):
        # Assign to GM
        await client.post(
            f"/api/v1/flags/{flags[0].id}/assign",
            headers=_auth_header(corporate_user),
            json={"assigned_to_id": str(gm_user.id)},
        )
        # Manager tries to respond (not assigned)
        resp = await client.post(
            f"/api/v1/flags/{flags[0].id}/respond-workflow",
            headers=_auth_header(manager_user),
            json={"response_text": "I should not be able to respond to this flag."},
        )
        assert resp.status_code == 403

    async def test_corporate_can_respond_to_any_flag(
        self, client, flags, gm_user, corporate_user
    ):
        await client.post(
            f"/api/v1/flags/{flags[0].id}/assign",
            headers=_auth_header(corporate_user),
            json={"assigned_to_id": str(gm_user.id)},
        )
        resp = await client.post(
            f"/api/v1/flags/{flags[0].id}/respond-workflow",
            headers=_auth_header(corporate_user),
            json={"response_text": "Corporate override response for accountability."},
        )
        assert resp.status_code == 200


# ── My Flags Tests ───────────────────────────────────────────────────


@pytest.mark.asyncio
class TestMyFlags:
    async def test_get_my_flags_returns_assigned(
        self, client, flags, gm_user, corporate_user
    ):
        # Assign all flags to GM
        for f in flags:
            await client.post(
                f"/api/v1/flags/{f.id}/assign",
                headers=_auth_header(corporate_user),
                json={"assigned_to_id": str(gm_user.id)},
            )

        resp = await client.get(
            "/api/v1/flags/my/assigned",
            headers=_auth_header(gm_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 4

    async def test_get_my_flags_sorted_overdue_first(
        self, client, db_session, flags, gm_user, corporate_user
    ):
        # Assign flags with different deadlines
        from sqlalchemy import select as sel

        # Assign all
        for f in flags:
            await client.post(
                f"/api/v1/flags/{f.id}/assign",
                headers=_auth_header(corporate_user),
                json={"assigned_to_id": str(gm_user.id)},
            )

        # Make one flag's deadline in the past
        result = await db_session.execute(
            sel(FlagAssignment).where(FlagAssignment.flag_id == flags[0].id)
        )
        assignment = result.scalar_one()
        assignment.deadline = datetime.date(2025, 1, 1)  # Way in the past
        await db_session.commit()

        resp = await client.get(
            "/api/v1/flags/my/assigned",
            headers=_auth_header(gm_user),
        )
        data = resp.json()
        assert data[0]["is_overdue"] is True

    async def test_my_flags_only_shows_own(
        self, client, flags, gm_user, corporate_user, manager_user
    ):
        # Assign to GM only
        await client.post(
            f"/api/v1/flags/{flags[0].id}/assign",
            headers=_auth_header(corporate_user),
            json={"assigned_to_id": str(gm_user.id)},
        )

        # Manager should see no flags
        resp = await client.get(
            "/api/v1/flags/my/assigned",
            headers=_auth_header(manager_user),
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 0


# ── Overdue Flags Tests ──────────────────────────────────────────────


@pytest.mark.asyncio
class TestOverdueFlags:
    async def test_overdue_returns_past_deadline(
        self, client, db_session, flags, gm_user, corporate_user
    ):
        # Assign with past deadline
        await client.post(
            f"/api/v1/flags/{flags[0].id}/assign",
            headers=_auth_header(corporate_user),
            json={"assigned_to_id": str(gm_user.id)},
        )
        from sqlalchemy import select as sel
        result = await db_session.execute(
            sel(FlagAssignment).where(FlagAssignment.flag_id == flags[0].id)
        )
        assignment = result.scalar_one()
        assignment.deadline = datetime.date(2025, 1, 1)
        await db_session.commit()

        resp = await client.get(
            "/api/v1/flags/overdue/all",
            headers=_auth_header(corporate_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["days_overdue"] > 0


# ── Escalate Tests ───────────────────────────────────────────────────


@pytest.mark.asyncio
class TestEscalate:
    async def test_escalate_flag(
        self, client, flags, corporate_user
    ):
        resp = await client.post(
            f"/api/v1/flags/{flags[0].id}/escalate",
            headers=_auth_header(corporate_user),
            json={"reason": "No response after 48 hours"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "escalated"
        assert data["escalation_level"] == 1

    async def test_escalate_increments_level(
        self, client, flags, corporate_user
    ):
        # Escalate twice
        await client.post(
            f"/api/v1/flags/{flags[0].id}/escalate",
            headers=_auth_header(corporate_user),
            json={},
        )
        resp = await client.post(
            f"/api/v1/flags/{flags[0].id}/escalate",
            headers=_auth_header(corporate_user),
            json={},
        )
        assert resp.json()["escalation_level"] == 2


# ── Recurring Flag Detection Tests ───────────────────────────────────


@pytest.mark.asyncio
class TestRecurringFlags:
    async def test_detect_recurring_links_flags(
        self, db_session, store
    ):
        """Flags with same category+field_name+field_value from previous meeting are linked."""
        from app.services.flag_service import FlagService

        # Previous meeting with an unresolved flag
        prev_meeting = Meeting(
            id=uuid.UUID("33333333-3333-3333-3333-333333333333"),
            store_id=store.id,
            meeting_date=datetime.date(2026, 1, 28),
            status=MeetingStatus.COMPLETED,
        )
        db_session.add(prev_meeting)

        prev_flag = Flag(
            id=uuid.UUID("ee000001-0000-0000-0000-000000000001"),
            meeting_id=prev_meeting.id,
            store_id=store.id,
            category=FlagCategory.INVENTORY,
            severity=FlagSeverity.YELLOW,
            field_name="days_in_stock",
            field_value="95",
            threshold="90",
            message="Used vehicle over 90 days",
            status=FlagStatus.OPEN,  # Not responded
        )
        db_session.add(prev_flag)

        # Current meeting with same flag
        curr_meeting = Meeting(
            id=uuid.UUID("44444444-4444-4444-4444-444444444444"),
            store_id=store.id,
            meeting_date=datetime.date(2026, 2, 11),
            status=MeetingStatus.COMPLETED,
        )
        db_session.add(curr_meeting)

        curr_flag = Flag(
            meeting_id=curr_meeting.id,
            store_id=store.id,
            category=FlagCategory.INVENTORY,
            severity=FlagSeverity.YELLOW,
            field_name="days_in_stock",
            field_value="95",
            threshold="90",
            message="Used vehicle over 90 days",
            status=FlagStatus.OPEN,
        )
        db_session.add(curr_flag)
        await db_session.commit()

        svc = FlagService()
        count = await svc.detect_recurring_flags(str(curr_meeting.id), db_session)
        assert count == 1

        # Verify linkage
        await db_session.refresh(curr_flag)
        assert curr_flag.previous_flag_id == prev_flag.id
        assert curr_flag.escalation_level == 1

    async def test_recurring_flag_escalates_to_red(
        self, db_session, store
    ):
        from app.services.flag_service import FlagService

        prev_mid = uuid.uuid4()
        prev_meeting = Meeting(
            id=prev_mid,
            store_id=store.id,
            meeting_date=datetime.date(2026, 1, 28),
            status=MeetingStatus.COMPLETED,
        )
        db_session.add(prev_meeting)
        await db_session.flush()

        prev_flag = Flag(
            meeting_id=prev_mid,
            store_id=store.id,
            category=FlagCategory.PARTS,
            severity=FlagSeverity.YELLOW,
            field_name="turnover",
            field_value="3.2",
            threshold="4.0",
            message="Parts turnover below threshold",
            status=FlagStatus.OPEN,
        )
        db_session.add(prev_flag)

        curr_mid = uuid.uuid4()
        curr_meeting = Meeting(
            id=curr_mid,
            store_id=store.id,
            meeting_date=datetime.date(2026, 2, 11),
            status=MeetingStatus.COMPLETED,
        )
        db_session.add(curr_meeting)
        await db_session.flush()

        curr_flag = Flag(
            meeting_id=curr_mid,
            store_id=store.id,
            category=FlagCategory.PARTS,
            severity=FlagSeverity.YELLOW,
            field_name="turnover",
            field_value="3.2",
            threshold="4.0",
            message="Parts turnover below threshold",
            status=FlagStatus.OPEN,
        )
        db_session.add(curr_flag)
        await db_session.commit()

        svc = FlagService()
        await svc.detect_recurring_flags(str(curr_mid), db_session)

        await db_session.refresh(curr_flag)
        assert curr_flag.severity == FlagSeverity.RED
        assert "RECURRING" in curr_flag.message

    async def test_recurring_increments_escalation_level(
        self, db_session, store
    ):
        from app.services.flag_service import FlagService

        m1_id, m2_id, m3_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

        m1 = Meeting(id=m1_id, store_id=store.id, meeting_date=datetime.date(2026, 1, 14), status=MeetingStatus.COMPLETED)
        db_session.add(m1)
        await db_session.flush()
        f1 = Flag(
            meeting_id=m1_id, store_id=store.id,
            category=FlagCategory.INVENTORY, severity=FlagSeverity.YELLOW,
            field_name="days_in_stock", field_value="95", threshold="90",
            message="Used vehicle over 90 days", status=FlagStatus.OPEN,
            escalation_level=0,
        )
        db_session.add(f1)

        m2 = Meeting(id=m2_id, store_id=store.id, meeting_date=datetime.date(2026, 1, 28), status=MeetingStatus.COMPLETED)
        db_session.add(m2)
        await db_session.flush()
        f2 = Flag(
            meeting_id=m2_id, store_id=store.id,
            category=FlagCategory.INVENTORY, severity=FlagSeverity.YELLOW,
            field_name="days_in_stock", field_value="95", threshold="90",
            message="Used vehicle over 90 days", status=FlagStatus.OPEN,
            escalation_level=0,
        )
        db_session.add(f2)
        await db_session.commit()

        svc = FlagService()
        await svc.detect_recurring_flags(str(m2_id), db_session)
        await db_session.refresh(f2)
        assert f2.escalation_level == 1

        m3 = Meeting(id=m3_id, store_id=store.id, meeting_date=datetime.date(2026, 2, 11), status=MeetingStatus.COMPLETED)
        db_session.add(m3)
        await db_session.flush()
        f3 = Flag(
            meeting_id=m3_id, store_id=store.id,
            category=FlagCategory.INVENTORY, severity=FlagSeverity.YELLOW,
            field_name="days_in_stock", field_value="95", threshold="90",
            message="Used vehicle over 90 days", status=FlagStatus.OPEN,
            escalation_level=0,
        )
        db_session.add(f3)
        await db_session.commit()

        await svc.detect_recurring_flags(str(m3_id), db_session)
        await db_session.refresh(f3)
        assert f3.escalation_level == 2
        assert "Meeting #3" in f3.message

    async def test_responded_flag_does_not_recur(
        self, db_session, store
    ):
        from app.services.flag_service import FlagService

        prev_mid = uuid.uuid4()
        prev_meeting = Meeting(
            id=prev_mid,
            store_id=store.id,
            meeting_date=datetime.date(2026, 1, 28),
            status=MeetingStatus.COMPLETED,
        )
        db_session.add(prev_meeting)
        await db_session.flush()

        prev_flag = Flag(
            meeting_id=prev_mid, store_id=store.id,
            category=FlagCategory.INVENTORY, severity=FlagSeverity.RED,
            field_name="days_in_stock", field_value="95", threshold="90",
            message="Used vehicle over 90 days",
            status=FlagStatus.RESPONDED,
            response_text="Marked down",
        )
        db_session.add(prev_flag)

        curr_mid = uuid.uuid4()
        curr_meeting = Meeting(
            id=curr_mid,
            store_id=store.id,
            meeting_date=datetime.date(2026, 2, 11),
            status=MeetingStatus.COMPLETED,
        )
        db_session.add(curr_meeting)
        await db_session.flush()

        curr_flag = Flag(
            meeting_id=curr_mid, store_id=store.id,
            category=FlagCategory.INVENTORY, severity=FlagSeverity.YELLOW,
            field_name="days_in_stock", field_value="95", threshold="90",
            message="Used vehicle over 90 days", status=FlagStatus.OPEN,
        )
        db_session.add(curr_flag)
        await db_session.commit()

        svc = FlagService()
        count = await svc.detect_recurring_flags(str(curr_mid), db_session)
        assert count == 0
        await db_session.refresh(curr_flag)
        assert curr_flag.previous_flag_id is None
