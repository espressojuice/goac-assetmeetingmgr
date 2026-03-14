"""Tests for meeting scheduling and cadence enforcement service."""

import datetime
import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.models.meeting import Meeting, MeetingStatus
from app.models.meeting_schedule import MeetingCadence, MeetingSchedule
from app.models.store import Store
from app.models.user import User, UserRole
from app.services import scheduling_service


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def store(db):
    s = Store(
        id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        name="Test Store",
        code="TEST",
        city="Dallas",
        state="TX",
    )
    db.add(s)
    await db.commit()
    return s


@pytest_asyncio.fixture
async def user(db):
    u = User(
        id=uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        email="admin@test.com",
        name="Admin",
        role=UserRole.CORPORATE,
    )
    db.add(u)
    await db.commit()
    return u


class TestGetUpcomingMeetings:

    def test_weekly_generates_all_occurrences(self):
        """WEEKLY cadence generates every occurrence of preferred day."""
        # Use a fixed reference date: March 1, 2026 is a Sunday
        ref = datetime.date(2026, 3, 1)
        dates = scheduling_service.get_upcoming_meetings(
            MeetingCadence.WEEKLY,
            preferred_day=1,  # Tuesday
            reference_date=ref,
            months_ahead=0,  # just March
        )
        # March 2026 Tuesdays: 3, 10, 17, 24, 31
        assert len(dates) == 5
        assert dates[0] == datetime.date(2026, 3, 3)
        assert dates[-1] == datetime.date(2026, 3, 31)

    def test_biweekly_generates_every_other(self):
        """BIWEEKLY cadence generates every other occurrence."""
        ref = datetime.date(2026, 3, 1)
        dates = scheduling_service.get_upcoming_meetings(
            MeetingCadence.BIWEEKLY,
            preferred_day=1,  # Tuesday
            reference_date=ref,
            months_ahead=0,
        )
        # Biweekly picks 1st, 3rd, 5th Tuesdays: March 3, 17, 31
        assert len(dates) == 3
        assert dates[0] == datetime.date(2026, 3, 3)
        assert dates[1] == datetime.date(2026, 3, 17)

    def test_first_and_third(self):
        """FIRST_AND_THIRD cadence picks 1st and 3rd occurrence."""
        ref = datetime.date(2026, 3, 1)
        dates = scheduling_service.get_upcoming_meetings(
            MeetingCadence.FIRST_AND_THIRD,
            preferred_day=3,  # Thursday
            reference_date=ref,
            months_ahead=0,
        )
        # March 2026 Thursdays: 5, 12, 19, 26
        # 1st and 3rd: March 5 and March 19
        assert len(dates) == 2
        assert dates[0] == datetime.date(2026, 3, 5)
        assert dates[1] == datetime.date(2026, 3, 19)

    def test_custom_returns_empty(self):
        """CUSTOM cadence returns empty list."""
        dates = scheduling_service.get_upcoming_meetings(
            MeetingCadence.CUSTOM,
            preferred_day=1,
            reference_date=datetime.date(2026, 3, 1),
        )
        assert dates == []

    def test_filters_past_dates(self):
        """Only returns dates >= reference_date."""
        ref = datetime.date(2026, 3, 15)
        dates = scheduling_service.get_upcoming_meetings(
            MeetingCadence.WEEKLY,
            preferred_day=1,  # Tuesday
            reference_date=ref,
            months_ahead=0,
        )
        # Only Tuesdays on or after March 15: 17, 24, 31
        assert all(d >= ref for d in dates)
        assert dates[0] == datetime.date(2026, 3, 17)


@pytest.mark.asyncio
class TestCadenceCompliance:

    async def test_compliant_when_meetings_meet_minimum(self, db, store, user):
        """Store is compliant when actual meetings >= minimum."""
        # Create schedule: minimum 2/month
        schedule = MeetingSchedule(
            store_id=store.id,
            cadence=MeetingCadence.BIWEEKLY,
            minimum_per_month=2,
            preferred_day_of_week=1,
            created_by_id=user.id,
        )
        db.add(schedule)

        # Create 2 meetings in March 2026
        for day in [5, 19]:
            db.add(Meeting(
                store_id=store.id,
                meeting_date=datetime.date(2026, 3, day),
                status=MeetingStatus.COMPLETED,
            ))
        await db.commit()

        results = await scheduling_service.get_cadence_compliance(
            db, month=3, year=2026
        )
        assert len(results) == 1
        assert results[0]["is_compliant"] is True
        assert results[0]["actual_count"] == 2

    async def test_not_compliant_when_below_minimum(self, db, store, user):
        """Store is not compliant when actual meetings < minimum."""
        schedule = MeetingSchedule(
            store_id=store.id,
            cadence=MeetingCadence.BIWEEKLY,
            minimum_per_month=2,
            preferred_day_of_week=1,
            created_by_id=user.id,
        )
        db.add(schedule)

        # Only 1 meeting in March
        db.add(Meeting(
            store_id=store.id,
            meeting_date=datetime.date(2026, 3, 5),
            status=MeetingStatus.COMPLETED,
        ))
        await db.commit()

        results = await scheduling_service.get_cadence_compliance(
            db, month=3, year=2026
        )
        assert len(results) == 1
        assert results[0]["is_compliant"] is False
        assert results[0]["actual_count"] == 1

    async def test_excludes_error_meetings(self, db, store, user):
        """Error meetings don't count toward compliance."""
        schedule = MeetingSchedule(
            store_id=store.id,
            cadence=MeetingCadence.BIWEEKLY,
            minimum_per_month=2,
            preferred_day_of_week=1,
            created_by_id=user.id,
        )
        db.add(schedule)

        db.add(Meeting(
            store_id=store.id,
            meeting_date=datetime.date(2026, 3, 5),
            status=MeetingStatus.COMPLETED,
        ))
        db.add(Meeting(
            store_id=store.id,
            meeting_date=datetime.date(2026, 3, 19),
            status=MeetingStatus.ERROR,
        ))
        await db.commit()

        results = await scheduling_service.get_cadence_compliance(
            db, month=3, year=2026
        )
        assert results[0]["actual_count"] == 1
        assert results[0]["is_compliant"] is False


@pytest.mark.asyncio
class TestOverdueMeetings:

    async def test_finds_overdue_store(self, db, store, user):
        """Store past grace period is flagged as overdue."""
        schedule = MeetingSchedule(
            store_id=store.id,
            cadence=MeetingCadence.BIWEEKLY,
            minimum_per_month=2,
            preferred_day_of_week=1,
            created_by_id=user.id,
        )
        db.add(schedule)

        # Last meeting was 25 days ago (biweekly max = 15 + 3 = 18 days)
        db.add(Meeting(
            store_id=store.id,
            meeting_date=datetime.date.today() - datetime.timedelta(days=25),
            status=MeetingStatus.COMPLETED,
        ))
        await db.commit()

        results = await scheduling_service.check_overdue_meetings(db)
        assert len(results) == 1
        assert results[0]["store_name"] == "Test Store"
        assert results[0]["days_overdue"] > 0

    async def test_not_overdue_within_grace(self, db, store, user):
        """Store within grace period is NOT flagged."""
        schedule = MeetingSchedule(
            store_id=store.id,
            cadence=MeetingCadence.BIWEEKLY,
            minimum_per_month=2,
            preferred_day_of_week=1,
            created_by_id=user.id,
        )
        db.add(schedule)

        # Last meeting was 10 days ago (biweekly max = 18 days)
        db.add(Meeting(
            store_id=store.id,
            meeting_date=datetime.date.today() - datetime.timedelta(days=10),
            status=MeetingStatus.COMPLETED,
        ))
        await db.commit()

        results = await scheduling_service.check_overdue_meetings(db)
        assert len(results) == 0

    async def test_excludes_error_from_last_meeting(self, db, store, user):
        """Error meetings don't count as last meeting."""
        schedule = MeetingSchedule(
            store_id=store.id,
            cadence=MeetingCadence.BIWEEKLY,
            minimum_per_month=2,
            preferred_day_of_week=1,
            created_by_id=user.id,
        )
        db.add(schedule)

        # Real meeting 25 days ago, error meeting 5 days ago
        db.add(Meeting(
            store_id=store.id,
            meeting_date=datetime.date.today() - datetime.timedelta(days=25),
            status=MeetingStatus.COMPLETED,
        ))
        db.add(Meeting(
            store_id=store.id,
            meeting_date=datetime.date.today() - datetime.timedelta(days=5),
            status=MeetingStatus.ERROR,
        ))
        await db.commit()

        results = await scheduling_service.check_overdue_meetings(db)
        assert len(results) == 1


@pytest.mark.asyncio
class TestUpsertSchedule:

    async def test_creates_new_schedule(self, db, store, user):
        """upsert creates a new schedule when none exists."""
        schedule = await scheduling_service.upsert_store_schedule(
            db=db,
            store_id=store.id,
            cadence=MeetingCadence.WEEKLY,
            preferred_day=2,
            preferred_time=datetime.time(14, 0),
            minimum_per_month=4,
            notes="Weekly except last week",
            created_by_id=user.id,
        )
        assert schedule.cadence == MeetingCadence.WEEKLY
        assert schedule.minimum_per_month == 4
        assert schedule.preferred_day_of_week == 2
        assert schedule.notes == "Weekly except last week"

    async def test_updates_existing_schedule(self, db, store, user):
        """upsert updates an existing schedule."""
        # Create initial
        await scheduling_service.upsert_store_schedule(
            db=db,
            store_id=store.id,
            cadence=MeetingCadence.BIWEEKLY,
            preferred_day=1,
            preferred_time=None,
            minimum_per_month=2,
            notes=None,
            created_by_id=user.id,
        )

        # Update
        updated = await scheduling_service.upsert_store_schedule(
            db=db,
            store_id=store.id,
            cadence=MeetingCadence.WEEKLY,
            preferred_day=3,
            preferred_time=datetime.time(10, 30),
            minimum_per_month=4,
            notes="Changed to weekly",
            created_by_id=user.id,
        )
        assert updated.cadence == MeetingCadence.WEEKLY
        assert updated.minimum_per_month == 4
        assert updated.notes == "Changed to weekly"

    async def test_template_fields_saved(self, db, store, user):
        """upsert saves template fields."""
        schedule = await scheduling_service.upsert_store_schedule(
            db=db,
            store_id=store.id,
            cadence=MeetingCadence.BIWEEKLY,
            preferred_day=1,
            preferred_time=None,
            minimum_per_month=2,
            notes=None,
            created_by_id=user.id,
            template_name="Weekly Asset Meeting",
            default_attendee_ids=[str(user.id)],
            auto_create_meetings=True,
            reminder_days_before=3,
        )
        assert schedule.template_name == "Weekly Asset Meeting"
        assert schedule.default_attendee_ids == [str(user.id)]
        assert schedule.auto_create_meetings is True
        assert schedule.reminder_days_before == 3


@pytest.mark.asyncio
class TestAutoCreateUpcomingMeetings:

    async def test_creates_meetings_for_next_30_days(self, db, store, user):
        """auto_create creates meetings based on schedule."""
        schedule = MeetingSchedule(
            store_id=store.id,
            cadence=MeetingCadence.BIWEEKLY,
            preferred_day_of_week=1,  # Tuesday
            minimum_per_month=2,
            auto_create_meetings=True,
            is_active=True,
            created_by_id=user.id,
        )
        db.add(schedule)
        await db.commit()

        created = await scheduling_service.auto_create_upcoming_meetings(db)
        assert len(created) > 0
        for item in created:
            assert "store_name" in item
            assert "meeting_date" in item
            assert "meeting_id" in item

    async def test_skips_existing_meetings(self, db, store, user):
        """auto_create is idempotent — skips dates with existing meetings."""
        schedule = MeetingSchedule(
            store_id=store.id,
            cadence=MeetingCadence.BIWEEKLY,
            preferred_day_of_week=1,
            minimum_per_month=2,
            auto_create_meetings=True,
            is_active=True,
            created_by_id=user.id,
        )
        db.add(schedule)
        await db.commit()

        # First run
        created1 = await scheduling_service.auto_create_upcoming_meetings(db)
        # Second run — should create nothing new
        created2 = await scheduling_service.auto_create_upcoming_meetings(db)
        assert len(created2) == 0
        assert len(created1) > 0

    async def test_only_processes_active_auto_create(self, db, store, user):
        """auto_create ignores inactive schedules and those without auto_create."""
        # Inactive schedule
        s1 = MeetingSchedule(
            store_id=store.id,
            cadence=MeetingCadence.BIWEEKLY,
            preferred_day_of_week=1,
            minimum_per_month=2,
            auto_create_meetings=True,
            is_active=False,
            created_by_id=user.id,
        )
        db.add(s1)
        await db.commit()

        created = await scheduling_service.auto_create_upcoming_meetings(db)
        assert len(created) == 0


@pytest.mark.asyncio
class TestGetTemplateDetails:

    async def test_returns_attendee_names(self, db, store, user):
        """get_template_details resolves attendee UUIDs to names."""
        schedule = MeetingSchedule(
            store_id=store.id,
            cadence=MeetingCadence.BIWEEKLY,
            preferred_day_of_week=1,
            minimum_per_month=2,
            template_name="Test Template",
            default_attendee_ids=[str(user.id)],
            auto_create_meetings=False,
            created_by_id=user.id,
        )
        db.add(schedule)
        await db.commit()

        details = await scheduling_service.get_template_details(db, store.id)
        assert details is not None
        assert details["template_name"] == "Test Template"
        assert details["default_attendee_names"] == ["Admin"]
        assert details["store_name"] == "Test Store"

    async def test_returns_none_when_no_schedule(self, db, store):
        """get_template_details returns None if no schedule exists."""
        details = await scheduling_service.get_template_details(db, store.id)
        assert details is None
