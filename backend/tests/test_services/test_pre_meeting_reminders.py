"""Tests for pre-meeting reminder function in NotificationScheduler."""

from __future__ import annotations

import datetime
import uuid
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.models.store import Store
from app.models.meeting import Meeting, MeetingStatus
from app.models.flag import Flag, FlagCategory, FlagSeverity, FlagStatus
from app.models.user import User, UserRole
from app.models.accountability import (
    AssignmentStatus,
    FlagAssignment,
    Notification,
    NotificationType,
)
from app.services.notification_scheduler import NotificationScheduler


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
async def db(db_engine):
    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def store(db):
    s = Store(
        id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        name="Test Store",
        code="TEST",
        city="Test City",
        state="AR",
    )
    db.add(s)
    await db.commit()
    return s


@pytest_asyncio.fixture
async def manager(db):
    u = User(
        id=uuid.UUID("33333333-3333-3333-3333-333333333333"),
        email="manager@test.com",
        name="Manager User",
        role=UserRole.MANAGER,
    )
    db.add(u)
    await db.commit()
    return u


@pytest_asyncio.fixture
async def corporate(db):
    u = User(
        id=uuid.UUID("44444444-4444-4444-4444-444444444444"),
        email="corp@test.com",
        name="Corporate User",
        role=UserRole.CORPORATE,
    )
    db.add(u)
    await db.commit()
    return u


def _make_scheduler():
    """Create a scheduler with mocked email service."""
    email = AsyncMock()
    return NotificationScheduler(email_service=email)


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
class TestPreMeetingReminders:

    async def test_reminder_for_meeting_tomorrow(self, db, store, manager, corporate):
        """Reminders are generated for OPEN flags when meeting is tomorrow."""
        tomorrow = datetime.date.today() + datetime.timedelta(days=1)
        meeting = Meeting(
            id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
            store_id=store.id,
            meeting_date=tomorrow,
            status=MeetingStatus.COMPLETED,
        )
        db.add(meeting)

        flag = Flag(
            id=uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            meeting_id=meeting.id,
            store_id=store.id,
            category=FlagCategory.INVENTORY,
            severity=FlagSeverity.RED,
            field_name="days_in_stock",
            field_value="95",
            threshold="90",
            message="Vehicle over 90 days",
            status=FlagStatus.OPEN,
        )
        db.add(flag)

        assignment = FlagAssignment(
            flag_id=flag.id,
            assigned_to_id=manager.id,
            assigned_by_id=corporate.id,
            status=AssignmentStatus.PENDING,
            deadline=tomorrow,
        )
        db.add(assignment)
        await db.commit()

        scheduler = _make_scheduler()
        count = await scheduler.check_pre_meeting_reminders(db)

        assert count == 1

        # Verify notification was created
        result = await db.execute(
            select(Notification).where(
                Notification.user_id == manager.id,
                Notification.title == "Pre-Meeting Response Needed",
            )
        )
        notification = result.scalar_one()
        assert "Test Store" in notification.message
        assert notification.reference_id == flag.id

    async def test_no_reminder_for_responded_flags(self, db, store, manager, corporate):
        """No reminders for flags that have already been responded to."""
        tomorrow = datetime.date.today() + datetime.timedelta(days=1)
        meeting = Meeting(
            id=uuid.UUID("22222222-2222-2222-2222-222222222223"),
            store_id=store.id,
            meeting_date=tomorrow,
            status=MeetingStatus.COMPLETED,
        )
        db.add(meeting)

        flag = Flag(
            id=uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaab"),
            meeting_id=meeting.id,
            store_id=store.id,
            category=FlagCategory.FINANCIAL,
            severity=FlagSeverity.RED,
            field_name="over_60",
            field_value="$1,500",
            threshold="$0",
            message="Receivable over 60 days",
            status=FlagStatus.RESPONDED,
            response_text="Payment received",
            responded_by="Manager User",
        )
        db.add(flag)

        assignment = FlagAssignment(
            flag_id=flag.id,
            assigned_to_id=manager.id,
            assigned_by_id=corporate.id,
            status=AssignmentStatus.RESPONDED,
            deadline=tomorrow,
        )
        db.add(assignment)
        await db.commit()

        scheduler = _make_scheduler()
        count = await scheduler.check_pre_meeting_reminders(db)

        assert count == 0

    async def test_no_reminder_for_distant_meeting(self, db, store, manager, corporate):
        """No reminders when meeting is more than 1 day away."""
        far_date = datetime.date.today() + datetime.timedelta(days=5)
        meeting = Meeting(
            id=uuid.UUID("22222222-2222-2222-2222-222222222224"),
            store_id=store.id,
            meeting_date=far_date,
            status=MeetingStatus.COMPLETED,
        )
        db.add(meeting)

        flag = Flag(
            id=uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaac"),
            meeting_id=meeting.id,
            store_id=store.id,
            category=FlagCategory.INVENTORY,
            severity=FlagSeverity.RED,
            field_name="days_in_stock",
            field_value="100",
            threshold="90",
            message="Vehicle over 90 days",
            status=FlagStatus.OPEN,
        )
        db.add(flag)

        assignment = FlagAssignment(
            flag_id=flag.id,
            assigned_to_id=manager.id,
            assigned_by_id=corporate.id,
            status=AssignmentStatus.PENDING,
            deadline=far_date,
        )
        db.add(assignment)
        await db.commit()

        scheduler = _make_scheduler()
        count = await scheduler.check_pre_meeting_reminders(db)

        assert count == 0
