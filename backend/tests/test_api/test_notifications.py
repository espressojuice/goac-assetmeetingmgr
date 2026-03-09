"""Tests for notification API endpoints."""

from __future__ import annotations

import datetime
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from unittest.mock import patch

from app.database import Base, get_db
from app.auth import get_current_user
from app.main import app
from app.models.user import User, UserRole
from app.models.accountability import Notification, NotificationType


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

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
    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def test_user(db_session):
    user = User(
        id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        email="test@test.com",
        name="Test User",
        role=UserRole.GM,
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def sample_notifications(db_session, test_user):
    notifs = [
        Notification(
            id=uuid.UUID("aaaa0001-0000-0000-0000-000000000000"),
            user_id=test_user.id,
            notification_type=NotificationType.FLAG_ASSIGNED,
            title="New flag assigned",
            message="You have a RED INVENTORY flag",
            reference_id=uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
            is_read=False,
        ),
        Notification(
            id=uuid.UUID("aaaa0002-0000-0000-0000-000000000000"),
            user_id=test_user.id,
            notification_type=NotificationType.DEADLINE_REMINDER,
            title="Deadline approaching",
            message="6 hours to respond",
            reference_id=uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
            is_read=False,
        ),
        Notification(
            id=uuid.UUID("aaaa0003-0000-0000-0000-000000000000"),
            user_id=test_user.id,
            notification_type=NotificationType.RESPONSE_RECEIVED,
            title="Response received",
            message="A response was submitted",
            is_read=True,
        ),
    ]
    for n in notifs:
        db_session.add(n)
    await db_session.commit()
    return notifs


@pytest_asyncio.fixture
async def client(db_engine, test_user):
    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    async def override_get_user():
        return test_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #

class TestGetNotifications:
    @pytest.mark.asyncio
    async def test_get_notifications(self, client, sample_notifications):
        resp = await client.get("/api/v1/notifications")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3

    @pytest.mark.asyncio
    async def test_get_unread_only(self, client, sample_notifications):
        resp = await client.get("/api/v1/notifications?unread_only=true")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert all(not n["is_read"] for n in data)

    @pytest.mark.asyncio
    async def test_get_with_limit(self, client, sample_notifications):
        resp = await client.get("/api/v1/notifications?limit=1")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1


class TestMarkRead:
    @pytest.mark.asyncio
    async def test_mark_notification_read(self, client, sample_notifications):
        notif_id = "aaaa0001-0000-0000-0000-000000000000"
        resp = await client.patch(f"/api/v1/notifications/{notif_id}/read")
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_read"] is True

    @pytest.mark.asyncio
    async def test_mark_read_not_found(self, client, sample_notifications):
        notif_id = "99999999-9999-9999-9999-999999999999"
        resp = await client.patch(f"/api/v1/notifications/{notif_id}/read")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_mark_read_invalid_id(self, client, sample_notifications):
        resp = await client.patch("/api/v1/notifications/not-a-uuid/read")
        assert resp.status_code == 400


class TestMarkAllRead:
    @pytest.mark.asyncio
    async def test_mark_all_read(self, client, sample_notifications):
        resp = await client.post("/api/v1/notifications/read-all")
        assert resp.status_code == 200

        # Verify all are read
        resp2 = await client.get("/api/v1/notifications?unread_only=true")
        assert resp2.status_code == 200
        assert len(resp2.json()) == 0


class TestUnreadCount:
    @pytest.mark.asyncio
    async def test_unread_count(self, client, sample_notifications):
        resp = await client.get("/api/v1/notifications/unread-count")
        assert resp.status_code == 200
        data = resp.json()
        assert data["unread_count"] == 2

    @pytest.mark.asyncio
    async def test_unread_count_after_mark_all(self, client, sample_notifications):
        await client.post("/api/v1/notifications/read-all")
        resp = await client.get("/api/v1/notifications/unread-count")
        assert resp.status_code == 200
        assert resp.json()["unread_count"] == 0
