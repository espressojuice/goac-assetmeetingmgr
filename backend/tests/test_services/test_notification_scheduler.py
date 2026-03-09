"""Tests for the notification scheduler."""

from __future__ import annotations

import datetime
import uuid
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
import pytest_asyncio
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
async def setup_data(db):
    """Create a store, meeting, user, flags, and assignments for testing."""
    store = Store(
        id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        name="Test Store",
        code="TEST",
        city="Test City",
        state="AR",
        gm_name="GM User",
        gm_email="gm@test.com",
    )
    db.add(store)

    meeting = Meeting(
        id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
        store_id=store.id,
        meeting_date=datetime.date.today() - datetime.timedelta(days=2),
        status=MeetingStatus.COMPLETED,
    )
    db.add(meeting)

    gm_user = User(
        id=uuid.UUID("33333333-3333-3333-3333-333333333333"),
        email="gm@test.com",
        name="GM User",
        role=UserRole.GM,
    )
    db.add(gm_user)

    corporate_user = User(
        id=uuid.UUID("44444444-4444-4444-4444-444444444444"),
        email="corp@test.com",
        name="Corporate User",
        role=UserRole.CORPORATE,
    )
    db.add(corporate_user)

    # Flag with approaching deadline (tomorrow)
    flag_approaching = Flag(
        id=uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        meeting_id=meeting.id,
        store_id=store.id,
        category=FlagCategory.INVENTORY,
        severity=FlagSeverity.RED,
        field_name="days_in_stock",
        field_value="95",
        threshold="90",
        message="Used vehicle over 90 days",
        status=FlagStatus.OPEN,
    )
    db.add(flag_approaching)

    assignment_approaching = FlagAssignment(
        id=uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
        flag_id=flag_approaching.id,
        assigned_to_id=gm_user.id,
        assigned_by_id=corporate_user.id,
        status=AssignmentStatus.PENDING,
        deadline=datetime.date.today() + datetime.timedelta(days=1),
    )
    db.add(assignment_approaching)

    # Flag that is overdue (deadline was yesterday)
    flag_overdue = Flag(
        id=uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"),
        meeting_id=meeting.id,
        store_id=store.id,
        category=FlagCategory.FINANCIAL,
        severity=FlagSeverity.RED,
        field_name="over_60",
        field_value="$1500",
        threshold="$0",
        message="Receivable over 60 days",
        status=FlagStatus.OPEN,
    )
    db.add(flag_overdue)

    assignment_overdue = FlagAssignment(
        id=uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd"),
        flag_id=flag_overdue.id,
        assigned_to_id=gm_user.id,
        assigned_by_id=corporate_user.id,
        status=AssignmentStatus.PENDING,
        deadline=datetime.date.today() - datetime.timedelta(days=1),
    )
    db.add(assignment_overdue)

    await db.commit()

    return {
        "store": store,
        "meeting": meeting,
        "gm_user": gm_user,
        "corporate_user": corporate_user,
        "flag_approaching": flag_approaching,
        "assignment_approaching": assignment_approaching,
        "flag_overdue": flag_overdue,
        "assignment_overdue": assignment_overdue,
    }


# --------------------------------------------------------------------------- #
# Reminder check tests
# --------------------------------------------------------------------------- #

class TestReminderCheck:
    @pytest.mark.asyncio
    async def test_finds_approaching_deadline_flags(self, db, setup_data):
        """Should find flags with deadlines within reminder window."""
        mock_email = MagicMock()
        mock_email.send_reminder_approaching = AsyncMock(return_value=True)
        scheduler = NotificationScheduler(email_service=mock_email)

        count = await scheduler.run_reminder_check(db)

        assert count == 1
        mock_email.send_reminder_approaching.assert_called_once()

    @pytest.mark.asyncio
    async def test_does_not_resend_reminder(self, db, setup_data):
        """Should not send a second reminder for the same flag."""
        mock_email = MagicMock()
        mock_email.send_reminder_approaching = AsyncMock(return_value=True)
        scheduler = NotificationScheduler(email_service=mock_email)

        # First run: should send
        count1 = await scheduler.run_reminder_check(db)
        assert count1 == 1

        # Second run: should skip (notification already exists)
        count2 = await scheduler.run_reminder_check(db)
        assert count2 == 0


# --------------------------------------------------------------------------- #
# Overdue check tests
# --------------------------------------------------------------------------- #

class TestOverdueCheck:
    @pytest.mark.asyncio
    async def test_finds_past_deadline_flags(self, db, setup_data):
        """Should find flags past their deadline."""
        mock_email = MagicMock()
        mock_email.send_overdue_to_manager = AsyncMock(return_value=True)
        mock_email.send_overdue_to_corporate = AsyncMock(return_value=True)
        scheduler = NotificationScheduler(email_service=mock_email)

        count = await scheduler.run_overdue_check(db)

        assert count >= 1
        mock_email.send_overdue_to_manager.assert_called_once()

    @pytest.mark.asyncio
    async def test_sends_escalation_to_corporate(self, db, setup_data):
        """Should send escalation email to corporate users."""
        mock_email = MagicMock()
        mock_email.send_overdue_to_manager = AsyncMock(return_value=True)
        mock_email.send_overdue_to_corporate = AsyncMock(return_value=True)
        scheduler = NotificationScheduler(email_service=mock_email)

        await scheduler.run_overdue_check(db)

        mock_email.send_overdue_to_corporate.assert_called_once()

    @pytest.mark.asyncio
    async def test_batches_per_user_per_store(self, db, setup_data):
        """Should send one email per user per store, not one per flag."""
        mock_email = MagicMock()
        mock_email.send_overdue_to_manager = AsyncMock(return_value=True)
        mock_email.send_overdue_to_corporate = AsyncMock(return_value=True)
        scheduler = NotificationScheduler(email_service=mock_email)

        await scheduler.run_overdue_check(db)

        # Only one manager email even if there are multiple flags
        assert mock_email.send_overdue_to_manager.call_count == 1


# --------------------------------------------------------------------------- #
# Daily digest tests
# --------------------------------------------------------------------------- #

class TestDailyDigest:
    @pytest.mark.asyncio
    async def test_skips_weekends(self, db, setup_data):
        """Should skip digest on Saturday and Sunday."""
        mock_email = MagicMock()
        mock_email.send_daily_digest = AsyncMock(return_value=True)
        scheduler = NotificationScheduler(email_service=mock_email)

        # Find next Saturday
        today = datetime.date.today()
        days_until_saturday = (5 - today.weekday()) % 7
        saturday = today + datetime.timedelta(days=days_until_saturday)

        with patch("app.services.notification_scheduler.datetime") as mock_dt:
            mock_dt.date.today.return_value = saturday
            mock_dt.datetime = datetime.datetime
            mock_dt.timezone = datetime.timezone
            mock_dt.timedelta = datetime.timedelta
            count = await scheduler.run_daily_digest(db)
            assert count == 0

    @pytest.mark.asyncio
    async def test_sends_to_corporate_on_weekday(self, db, setup_data):
        """Should send digest to corporate users on weekdays."""
        mock_email = MagicMock()
        mock_email.send_daily_digest = AsyncMock(return_value=True)
        scheduler = NotificationScheduler(email_service=mock_email)

        # Find next Monday
        today = datetime.date.today()
        days_until_monday = (0 - today.weekday()) % 7
        if days_until_monday == 0 and today.weekday() >= 5:
            days_until_monday = 7
        monday = today + datetime.timedelta(days=days_until_monday)

        with patch("app.services.notification_scheduler.datetime") as mock_dt:
            mock_dt.date.today.return_value = monday
            mock_dt.datetime = datetime.datetime
            mock_dt.timezone = datetime.timezone
            mock_dt.timedelta = datetime.timedelta
            count = await scheduler.run_daily_digest(db)
            assert count == 1
            mock_email.send_daily_digest.assert_called_once()


# --------------------------------------------------------------------------- #
# Empty result handling
# --------------------------------------------------------------------------- #

class TestEmptyResults:
    @pytest.mark.asyncio
    async def test_reminder_check_no_approaching_flags(self, db):
        """Should handle zero approaching flags gracefully."""
        mock_email = MagicMock()
        scheduler = NotificationScheduler(email_service=mock_email)
        count = await scheduler.run_reminder_check(db)
        assert count == 0

    @pytest.mark.asyncio
    async def test_overdue_check_no_overdue_flags(self, db):
        """Should handle zero overdue flags gracefully."""
        mock_email = MagicMock()
        scheduler = NotificationScheduler(email_service=mock_email)
        count = await scheduler.run_overdue_check(db)
        assert count == 0

    @pytest.mark.asyncio
    async def test_daily_digest_no_corporate_users(self, db):
        """Should handle zero corporate users gracefully."""
        mock_email = MagicMock()
        mock_email.send_daily_digest = AsyncMock(return_value=True)
        scheduler = NotificationScheduler(email_service=mock_email)

        # Use a weekday
        today = datetime.date.today()
        days_until_monday = (0 - today.weekday()) % 7
        if days_until_monday == 0 and today.weekday() >= 5:
            days_until_monday = 7
        monday = today + datetime.timedelta(days=days_until_monday)

        with patch("app.services.notification_scheduler.datetime") as mock_dt:
            mock_dt.date.today.return_value = monday
            mock_dt.datetime = datetime.datetime
            mock_dt.timezone = datetime.timezone
            mock_dt.timedelta = datetime.timedelta
            count = await scheduler.run_daily_digest(db)
            assert count == 0
