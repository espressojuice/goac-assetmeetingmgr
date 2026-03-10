"""Role-based access control tests — corporate/gm/manager permissions on all routes."""

import datetime
import io
import uuid
from unittest.mock import AsyncMock, patch

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
async def store_a(db_session):
    """Store A — the 'own' store for GM/manager."""
    s = Store(
        id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        name="Store A",
        code="STORE_A",
        brand="Chevrolet",
        city="Ashdown",
        state="AR",
        gm_name="GM",
        gm_email="gm@a.com",
    )
    db_session.add(s)
    await db_session.commit()
    return s


@pytest_asyncio.fixture
async def store_b(db_session):
    """Store B — another store the user does NOT have access to."""
    s = Store(
        id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
        name="Store B",
        code="STORE_B",
        brand="Toyota",
        city="Hot Springs",
        state="AR",
    )
    db_session.add(s)
    await db_session.commit()
    return s


@pytest_asyncio.fixture
async def corporate_user(db_session):
    u = User(
        id=uuid.UUID("c0c0c0c0-c0c0-c0c0-c0c0-c0c0c0c0c0c0"),
        email="corp@goac.com",
        name="Corporate Admin",
        role=UserRole.CORPORATE,
    )
    db_session.add(u)
    await db_session.commit()
    return u


@pytest_asyncio.fixture
async def gm_user(db_session, store_a):
    u = User(
        id=uuid.UUID("a1a1a1a1-a1a1-a1a1-a1a1-a1a1a1a1a1a1"),
        email="gm@store-a.com",
        name="GM of Store A",
        role=UserRole.GM,
    )
    db_session.add(u)
    await db_session.flush()
    db_session.add(UserStore(user_id=u.id, store_id=store_a.id))
    await db_session.commit()
    return u


@pytest_asyncio.fixture
async def manager_user(db_session, store_a):
    u = User(
        id=uuid.UUID("b2b2b2b2-b2b2-b2b2-b2b2-b2b2b2b2b2b2"),
        email="mgr@store-a.com",
        name="Manager of Store A",
        role=UserRole.MANAGER,
    )
    db_session.add(u)
    await db_session.flush()
    db_session.add(UserStore(user_id=u.id, store_id=store_a.id))
    await db_session.commit()
    return u


@pytest_asyncio.fixture
async def meeting_a(db_session, store_a):
    m = Meeting(
        id=uuid.UUID("aa000000-0000-0000-0000-000000000001"),
        store_id=store_a.id,
        meeting_date=datetime.date(2026, 2, 11),
        status=MeetingStatus.COMPLETED,
    )
    db_session.add(m)
    await db_session.commit()
    return m


@pytest_asyncio.fixture
async def meeting_b(db_session, store_b):
    m = Meeting(
        id=uuid.UUID("bb000000-0000-0000-0000-000000000001"),
        store_id=store_b.id,
        meeting_date=datetime.date(2026, 2, 11),
        status=MeetingStatus.COMPLETED,
    )
    db_session.add(m)
    await db_session.commit()
    return m


@pytest_asyncio.fixture
async def flag_a(db_session, meeting_a, store_a):
    f = Flag(
        id=uuid.UUID("ff000000-0000-0000-0000-000000000001"),
        meeting_id=meeting_a.id,
        store_id=store_a.id,
        category=FlagCategory.INVENTORY,
        severity=FlagSeverity.RED,
        field_name="days_in_stock",
        field_value="95",
        threshold="90",
        message="Used vehicle over 90 days",
        status=FlagStatus.OPEN,
    )
    db_session.add(f)
    await db_session.commit()
    return f


@pytest_asyncio.fixture
async def flag_b(db_session, meeting_b, store_b):
    f = Flag(
        id=uuid.UUID("ff000000-0000-0000-0000-000000000002"),
        meeting_id=meeting_b.id,
        store_id=store_b.id,
        category=FlagCategory.FINANCIAL,
        severity=FlagSeverity.YELLOW,
        field_name="over_60",
        field_value="$500",
        threshold="$0",
        message="Receivable over 60 days",
        status=FlagStatus.OPEN,
    )
    db_session.add(f)
    await db_session.commit()
    return f


@pytest_asyncio.fixture
async def assignment_to_manager(db_session, flag_a, manager_user, corporate_user):
    a = FlagAssignment(
        id=uuid.UUID("aa110000-0000-0000-0000-000000000001"),
        flag_id=flag_a.id,
        assigned_to_id=manager_user.id,
        assigned_by_id=corporate_user.id,
        status=AssignmentStatus.PENDING,
        deadline=datetime.date(2026, 2, 12),
    )
    db_session.add(a)
    await db_session.commit()
    return a


def _h(user: User) -> dict:
    """Auth header helper."""
    token = create_access_token(str(user.id), user.email, user.role.value)
    return {"Authorization": f"Bearer {token}"}


# ── Unauthenticated Tests ────────────────────────────────────────────


@pytest.mark.asyncio
class TestUnauthenticated:
    """All protected endpoints return 401 without token."""

    async def test_stores_requires_auth(self, client, store_a):
        assert (await client.get("/api/v1/stores")).status_code == 401

    async def test_store_detail_requires_auth(self, client, store_a):
        assert (await client.get(f"/api/v1/stores/{store_a.id}")).status_code == 401

    async def test_meetings_requires_auth(self, client, meeting_a):
        assert (await client.get(f"/api/v1/meetings/{meeting_a.id}")).status_code == 401

    async def test_flags_requires_auth(self, client, meeting_a):
        assert (await client.get(f"/api/v1/flags/{meeting_a.id}")).status_code == 401

    async def test_dashboard_requires_auth(self, client):
        assert (await client.get("/api/v1/dashboard")).status_code == 401

    async def test_upload_requires_auth(self, client, store_a):
        resp = await client.post(
            "/api/v1/upload",
            files=[("file", ("r.pdf", io.BytesIO(b"%PDF"), "application/pdf"))],
            data={"store_id": str(store_a.id), "meeting_date": "2026-02-11"},
        )
        assert resp.status_code == 401

    async def test_health_is_public(self, client):
        assert (await client.get("/health")).status_code == 200

    async def test_auth_callback_is_public(self, client):
        resp = await client.post("/api/v1/auth/callback", json={
            "email": "new@test.com", "name": "N", "google_id": "g123",
        })
        assert resp.status_code == 200


# ── Corporate Tests ───────────────────────────────────────────────────


@pytest.mark.asyncio
class TestCorporateAccess:
    """Corporate users can access everything."""

    async def test_list_all_stores(self, client, store_a, store_b, corporate_user):
        resp = await client.get("/api/v1/stores", headers=_h(corporate_user))
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    async def test_get_any_store(self, client, store_b, corporate_user):
        resp = await client.get(f"/api/v1/stores/{store_b.id}", headers=_h(corporate_user))
        assert resp.status_code == 200

    async def test_create_store(self, client, corporate_user):
        resp = await client.post(
            "/api/v1/stores",
            json={"name": "New", "code": "NEW", "city": "C", "state": "AR"},
            headers=_h(corporate_user),
        )
        assert resp.status_code == 201

    async def test_view_any_meeting(self, client, meeting_b, corporate_user):
        resp = await client.get(f"/api/v1/meetings/{meeting_b.id}", headers=_h(corporate_user))
        assert resp.status_code == 200

    async def test_view_any_flags(self, client, meeting_b, flag_b, corporate_user):
        resp = await client.get(f"/api/v1/flags/{meeting_b.id}", headers=_h(corporate_user))
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    async def test_assign_any_flag(self, client, flag_a, gm_user, corporate_user):
        resp = await client.post(
            f"/api/v1/flags/{flag_a.id}/assign",
            json={"assigned_to_id": str(gm_user.id)},
            headers=_h(corporate_user),
        )
        assert resp.status_code == 200

    async def test_dashboard_shows_all_stores(self, client, store_a, store_b, corporate_user):
        resp = await client.get("/api/v1/dashboard", headers=_h(corporate_user))
        assert resp.status_code == 200
        assert resp.json()["totals"]["total_stores"] == 2

    async def test_upload_to_any_store(self, client, store_b, corporate_user):
        mock_result = {
            "pages_extracted": 1, "records_parsed": {}, "unhandled_pages": [],
            "flags_generated": {"yellow": 0, "red": 0, "total": 0},
        }
        with patch("app.api.routes.upload.ProcessingService") as MockService:
            MockService.return_value.process_upload = AsyncMock(return_value=mock_result)
            resp = await client.post(
                "/api/v1/upload",
                files=[("file", ("r.pdf", io.BytesIO(b"%PDF"), "application/pdf"))],
                data={"store_id": str(store_b.id), "meeting_date": "2026-03-01"},
                headers=_h(corporate_user),
            )
        assert resp.status_code == 200

    async def test_escalate_any_flag(self, client, flag_a, corporate_user):
        resp = await client.post(
            f"/api/v1/flags/{flag_a.id}/escalate",
            json={},
            headers=_h(corporate_user),
        )
        assert resp.status_code == 200


# ── GM Tests ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestGMAccess:
    """GM users can only access their own stores."""

    async def test_list_only_own_stores(self, client, store_a, store_b, gm_user):
        resp = await client.get("/api/v1/stores", headers=_h(gm_user))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["code"] == "STORE_A"

    async def test_get_own_store(self, client, store_a, gm_user):
        resp = await client.get(f"/api/v1/stores/{store_a.id}", headers=_h(gm_user))
        assert resp.status_code == 200

    async def test_cannot_get_other_store(self, client, store_b, gm_user):
        resp = await client.get(f"/api/v1/stores/{store_b.id}", headers=_h(gm_user))
        assert resp.status_code == 403

    async def test_cannot_create_store(self, client, gm_user):
        resp = await client.post(
            "/api/v1/stores",
            json={"name": "New", "code": "NEW", "city": "C", "state": "AR"},
            headers=_h(gm_user),
        )
        assert resp.status_code == 403

    async def test_view_own_meeting(self, client, meeting_a, gm_user):
        resp = await client.get(f"/api/v1/meetings/{meeting_a.id}", headers=_h(gm_user))
        assert resp.status_code == 200

    async def test_cannot_view_other_meeting(self, client, meeting_b, gm_user):
        resp = await client.get(f"/api/v1/meetings/{meeting_b.id}", headers=_h(gm_user))
        assert resp.status_code == 403

    async def test_view_own_flags(self, client, meeting_a, flag_a, gm_user):
        resp = await client.get(f"/api/v1/flags/{meeting_a.id}", headers=_h(gm_user))
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    async def test_cannot_view_other_flags(self, client, meeting_b, flag_b, gm_user):
        resp = await client.get(f"/api/v1/flags/{meeting_b.id}", headers=_h(gm_user))
        assert resp.status_code == 403

    async def test_assign_own_store_flag(self, client, flag_a, manager_user, gm_user):
        resp = await client.post(
            f"/api/v1/flags/{flag_a.id}/assign",
            json={"assigned_to_id": str(manager_user.id)},
            headers=_h(gm_user),
        )
        assert resp.status_code == 200

    async def test_cannot_assign_other_store_flag(self, client, flag_b, manager_user, gm_user):
        resp = await client.post(
            f"/api/v1/flags/{flag_b.id}/assign",
            json={"assigned_to_id": str(manager_user.id)},
            headers=_h(gm_user),
        )
        assert resp.status_code == 403

    async def test_dashboard_shows_only_own_stores(self, client, store_a, store_b, gm_user):
        resp = await client.get("/api/v1/dashboard", headers=_h(gm_user))
        assert resp.status_code == 200
        data = resp.json()
        assert data["totals"]["total_stores"] == 1
        assert data["stores"][0]["code"] == "STORE_A"

    async def test_upload_to_own_store(self, client, store_a, gm_user):
        mock_result = {
            "pages_extracted": 1, "records_parsed": {}, "unhandled_pages": [],
            "flags_generated": {"yellow": 0, "red": 0, "total": 0},
        }
        with patch("app.api.routes.upload.ProcessingService") as MockService:
            MockService.return_value.process_upload = AsyncMock(return_value=mock_result)
            resp = await client.post(
                "/api/v1/upload",
                files=[("file", ("r.pdf", io.BytesIO(b"%PDF"), "application/pdf"))],
                data={"store_id": str(store_a.id), "meeting_date": "2026-03-01"},
                headers=_h(gm_user),
            )
        assert resp.status_code == 200

    async def test_cannot_upload_to_other_store(self, client, store_b, gm_user):
        resp = await client.post(
            "/api/v1/upload",
            files=[("file", ("r.pdf", io.BytesIO(b"%PDF"), "application/pdf"))],
            data={"store_id": str(store_b.id), "meeting_date": "2026-03-01"},
            headers=_h(gm_user),
        )
        assert resp.status_code == 403

    async def test_escalate_own_store_flag(self, client, flag_a, gm_user):
        resp = await client.post(
            f"/api/v1/flags/{flag_a.id}/escalate",
            json={},
            headers=_h(gm_user),
        )
        assert resp.status_code == 200

    async def test_cannot_escalate_other_store_flag(self, client, flag_b, gm_user):
        resp = await client.post(
            f"/api/v1/flags/{flag_b.id}/escalate",
            json={},
            headers=_h(gm_user),
        )
        assert resp.status_code == 403

    async def test_auto_assign_own_meeting(self, client, meeting_a, flag_a, gm_user):
        resp = await client.post(
            f"/api/v1/meetings/{meeting_a.id}/auto-assign",
            headers=_h(gm_user),
        )
        assert resp.status_code == 200

    async def test_cannot_auto_assign_other_meeting(self, client, meeting_b, flag_b, gm_user):
        resp = await client.post(
            f"/api/v1/meetings/{meeting_b.id}/auto-assign",
            headers=_h(gm_user),
        )
        assert resp.status_code == 403


# ── Manager Tests ─────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestManagerAccess:
    """Managers: read-only on their store, respond to own flags only."""

    async def test_list_only_own_stores(self, client, store_a, store_b, manager_user):
        resp = await client.get("/api/v1/stores", headers=_h(manager_user))
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["code"] == "STORE_A"

    async def test_cannot_create_store(self, client, manager_user):
        resp = await client.post(
            "/api/v1/stores",
            json={"name": "New", "code": "NEW", "city": "C", "state": "AR"},
            headers=_h(manager_user),
        )
        assert resp.status_code == 403

    async def test_cannot_upload(self, client, store_a, manager_user):
        resp = await client.post(
            "/api/v1/upload",
            files=[("file", ("r.pdf", io.BytesIO(b"%PDF"), "application/pdf"))],
            data={"store_id": str(store_a.id), "meeting_date": "2026-03-01"},
            headers=_h(manager_user),
        )
        assert resp.status_code == 403

    async def test_view_own_store_meetings(self, client, meeting_a, manager_user):
        resp = await client.get(f"/api/v1/meetings/{meeting_a.id}", headers=_h(manager_user))
        assert resp.status_code == 200

    async def test_cannot_view_other_store_meetings(self, client, meeting_b, manager_user):
        resp = await client.get(f"/api/v1/meetings/{meeting_b.id}", headers=_h(manager_user))
        assert resp.status_code == 403

    async def test_see_only_assigned_flags(
        self, client, meeting_a, flag_a, assignment_to_manager, manager_user
    ):
        """Manager only sees flags assigned to them, not all meeting flags."""
        resp = await client.get(f"/api/v1/flags/{meeting_a.id}", headers=_h(manager_user))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == str(flag_a.id)

    async def test_cannot_see_unassigned_flags(self, client, meeting_a, flag_a, manager_user):
        """Without assignment, manager sees no flags."""
        resp = await client.get(f"/api/v1/flags/{meeting_a.id}", headers=_h(manager_user))
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    async def test_cannot_assign_flags(self, client, flag_a, gm_user, manager_user):
        resp = await client.post(
            f"/api/v1/flags/{flag_a.id}/assign",
            json={"assigned_to_id": str(gm_user.id)},
            headers=_h(manager_user),
        )
        assert resp.status_code == 403

    async def test_can_respond_to_own_flag(
        self, client, flag_a, assignment_to_manager, manager_user
    ):
        resp = await client.post(
            f"/api/v1/flags/{flag_a.id}/respond-workflow",
            json={"response_text": "Vehicle has been marked down for clearance sale."},
            headers=_h(manager_user),
        )
        assert resp.status_code == 200

    async def test_cannot_respond_to_others_flag(
        self, client, db_session, flag_a, gm_user, corporate_user, manager_user
    ):
        """Manager cannot respond to a flag assigned to someone else."""
        # Assign to GM instead
        a = FlagAssignment(
            flag_id=flag_a.id,
            assigned_to_id=gm_user.id,
            assigned_by_id=corporate_user.id,
            status=AssignmentStatus.PENDING,
            deadline=datetime.date(2026, 2, 12),
        )
        db_session.add(a)
        await db_session.commit()

        resp = await client.post(
            f"/api/v1/flags/{flag_a.id}/respond-workflow",
            json={"response_text": "I should not be able to respond to this flag."},
            headers=_h(manager_user),
        )
        assert resp.status_code == 403

    async def test_cannot_escalate_flags(self, client, flag_a, manager_user):
        resp = await client.post(
            f"/api/v1/flags/{flag_a.id}/escalate",
            json={},
            headers=_h(manager_user),
        )
        assert resp.status_code == 403

    async def test_cannot_auto_assign(self, client, meeting_a, flag_a, manager_user):
        resp = await client.post(
            f"/api/v1/meetings/{meeting_a.id}/auto-assign",
            headers=_h(manager_user),
        )
        assert resp.status_code == 403

    async def test_my_flags_returns_only_own(
        self, client, flag_a, assignment_to_manager, manager_user
    ):
        resp = await client.get("/api/v1/flags/my/assigned", headers=_h(manager_user))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1

    async def test_dashboard_shows_only_own_stores(self, client, store_a, store_b, manager_user):
        resp = await client.get("/api/v1/dashboard", headers=_h(manager_user))
        assert resp.status_code == 200
        data = resp.json()
        assert data["totals"]["total_stores"] == 1
        assert data["stores"][0]["code"] == "STORE_A"
