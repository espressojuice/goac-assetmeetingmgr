"""Tests for resolution trends and promise tracking in metrics_service."""

from __future__ import annotations

import datetime
import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.models.meeting import Meeting, MeetingStatus
from app.models.flag import Flag, FlagCategory, FlagSeverity, FlagStatus
from app.models.store import Store
from app.models.user import User, UserRole, UserStore
from app.models.accountability import FlagAssignment, MeetingAttendance
from app.services import metrics_service


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


STORE_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
STORE2_ID = uuid.UUID("11111111-1111-1111-1111-222222222222")
MEETING1_ID = uuid.UUID("22222222-2222-2222-2222-222222222201")
MEETING2_ID = uuid.UUID("22222222-2222-2222-2222-222222222202")
MEETING3_ID = uuid.UUID("22222222-2222-2222-2222-222222222203")
USER_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
CORP_ID = uuid.UUID("44444444-4444-4444-4444-444444444444")


@pytest_asyncio.fixture
async def seed_data(db):
    """Seed stores, meetings, flags, assignments, attendance."""
    store = Store(id=STORE_ID, name="Test Store", code="TEST", city="City", state="AR")
    store2 = Store(id=STORE2_ID, name="Other Store", code="OTHER", city="Town", state="TX")
    db.add_all([store, store2])
    await db.flush()

    corp = User(id=CORP_ID, email="corp@test.com", name="Corp Admin", role=UserRole.CORPORATE)
    manager = User(id=USER_ID, email="mgr@test.com", name="Test Manager", role=UserRole.MANAGER)
    db.add_all([corp, manager])
    await db.flush()

    db.add(UserStore(user_id=USER_ID, store_id=STORE_ID))

    now = datetime.datetime(2026, 3, 1, 10, 0, tzinfo=datetime.timezone.utc)
    today = datetime.date(2026, 3, 14)

    # Meeting 1: oldest, 2 flags (1 verified, 1 unresolved)
    m1 = Meeting(id=MEETING1_ID, store_id=STORE_ID, meeting_date=datetime.date(2026, 1, 15),
                 status=MeetingStatus.COMPLETED)
    # Meeting 2: middle, 1 flag (open)
    m2 = Meeting(id=MEETING2_ID, store_id=STORE_ID, meeting_date=datetime.date(2026, 2, 15),
                 status=MeetingStatus.COMPLETED)
    # Meeting 3: different store
    m3 = Meeting(id=MEETING3_ID, store_id=STORE2_ID, meeting_date=datetime.date(2026, 2, 20),
                 status=MeetingStatus.COMPLETED)
    db.add_all([m1, m2, m3])
    await db.flush()

    # Flags for meeting 1
    f1 = Flag(meeting_id=MEETING1_ID, store_id=STORE_ID, category=FlagCategory.INVENTORY,
              severity=FlagSeverity.RED, field_name="days_in_stock", message="Over 90 days",
              status=FlagStatus.VERIFIED, verified_at=now,
              expected_resolution_date=datetime.date(2026, 2, 1))  # promise kept
    f2 = Flag(meeting_id=MEETING1_ID, store_id=STORE_ID, category=FlagCategory.FINANCIAL,
              severity=FlagSeverity.RED, field_name="over_60", message="Receivable over 60",
              status=FlagStatus.UNRESOLVED,
              expected_resolution_date=datetime.date(2026, 2, 1))  # promise broken (past due, not verified)
    db.add_all([f1, f2])
    await db.flush()

    # Assignments for promise tracking
    a1 = FlagAssignment(flag_id=f1.id, assigned_to_id=USER_ID, assigned_by_id=CORP_ID,
                        deadline=datetime.date(2026, 2, 1))
    a2 = FlagAssignment(flag_id=f2.id, assigned_to_id=USER_ID, assigned_by_id=CORP_ID,
                        deadline=datetime.date(2026, 2, 1))
    db.add_all([a1, a2])

    # Flag for meeting 2 (open, no promise date)
    f3 = Flag(meeting_id=MEETING2_ID, store_id=STORE_ID, category=FlagCategory.OPERATIONS,
              severity=FlagSeverity.YELLOW, field_name="days_open", message="Open RO",
              status=FlagStatus.OPEN)
    db.add(f3)
    await db.flush()

    # Flag for meeting 3 (different store, promise pending — future date)
    f4 = Flag(meeting_id=MEETING3_ID, store_id=STORE2_ID, category=FlagCategory.PARTS,
              severity=FlagSeverity.YELLOW, field_name="turnover", message="Low turnover",
              status=FlagStatus.RESPONDED,
              expected_resolution_date=datetime.date(2026, 12, 1))  # pending
    db.add(f4)
    await db.flush()

    a4 = FlagAssignment(flag_id=f4.id, assigned_to_id=USER_ID, assigned_by_id=CORP_ID,
                        deadline=datetime.date(2026, 3, 1))
    db.add(a4)

    # Attendance for meeting 1: 2 expected, 1 present
    att1 = MeetingAttendance(meeting_id=MEETING1_ID, user_id=USER_ID, checked_in=True,
                             checked_in_at=now)
    att2 = MeetingAttendance(meeting_id=MEETING1_ID, user_id=CORP_ID, checked_in=False)
    db.add_all([att1, att2])

    await db.commit()
    return {"flags": [f1, f2, f3, f4]}


# ── get_resolution_trends Tests ──────────────────────────────────


@pytest.mark.asyncio
class TestGetResolutionTrends:

    async def test_returns_correct_meeting_metrics(self, db, seed_data):
        """Verify per-meeting flag counts and resolution rate."""
        trends = await metrics_service.get_resolution_trends(db)
        assert len(trends) == 3  # 3 completed meetings
        # Sorted ascending by date
        assert trends[0]["meeting_date"] <= trends[1]["meeting_date"]

        # Meeting 1 (Jan 15): 2 flags (1 verified, 1 unresolved)
        m1 = next(t for t in trends if t["meeting_id"] == str(MEETING1_ID))
        assert m1["total_flags"] == 2
        assert m1["verified"] == 1
        assert m1["unresolved"] == 1
        assert m1["resolution_rate"] == 50.0

    async def test_store_id_filter(self, db, seed_data):
        """Filtering by store_id returns only that store's meetings."""
        trends = await metrics_service.get_resolution_trends(db, store_id=STORE_ID)
        assert len(trends) == 2  # only store 1 meetings
        for t in trends:
            assert t["store_name"] == "Test Store"

    async def test_last_n_meetings_limit(self, db, seed_data):
        """last_n_meetings limits the number of returned meetings."""
        trends = await metrics_service.get_resolution_trends(db, last_n_meetings=1)
        assert len(trends) == 1
        # Should be the most recent meeting
        assert trends[0]["meeting_date"] == "2026-02-20"

    async def test_promises_kept_broken(self, db, seed_data):
        """Promise counts are accurate per meeting."""
        trends = await metrics_service.get_resolution_trends(db)
        m1 = next(t for t in trends if t["meeting_id"] == str(MEETING1_ID))
        assert m1["promises_kept"] == 1  # f1 verified with expected_resolution_date
        assert m1["promises_broken"] == 1  # f2 unresolved past expected date

    async def test_attendance_rate(self, db, seed_data):
        """Attendance rate calculated correctly."""
        trends = await metrics_service.get_resolution_trends(db)
        m1 = next(t for t in trends if t["meeting_id"] == str(MEETING1_ID))
        assert m1["attendance_rate"] == 50.0  # 1 of 2 checked in

        # Meeting 2 has no attendance records
        m2 = next(t for t in trends if t["meeting_id"] == str(MEETING2_ID))
        assert m2["attendance_rate"] == 0.0


# ── get_promise_tracking_summary Tests ────────────────────────────


@pytest.mark.asyncio
class TestGetPromiseTrackingSummary:

    async def test_returns_correct_aggregates(self, db, seed_data):
        """Summary includes correct promise counts."""
        summary = await metrics_service.get_promise_tracking_summary(db)
        assert summary["total_promises"] == 3  # f1, f2, f4 have expected_resolution_date
        assert summary["promises_kept"] == 1   # f1 verified
        assert summary["promises_broken"] == 1  # f2 past due, not verified
        assert summary["promises_pending"] == 1  # f4 future date

    async def test_avg_days_late(self, db, seed_data):
        """avg_days_late calculated for broken promises."""
        summary = await metrics_service.get_promise_tracking_summary(db)
        assert summary["avg_days_late"] is not None
        assert summary["avg_days_late"] > 0

    async def test_worst_offenders_sorted(self, db, seed_data):
        """Worst offenders sorted by broken_count descending."""
        summary = await metrics_service.get_promise_tracking_summary(db)
        offenders = summary["worst_offenders"]
        assert len(offenders) >= 1
        assert offenders[0]["user_name"] == "Test Manager"
        assert offenders[0]["broken_count"] == 1

    async def test_no_promises_returns_zeros(self, db):
        """When no flags have expected_resolution_date, return zeros."""
        store = Store(id=STORE_ID, name="Empty", code="EMPTY", city="X", state="TX")
        db.add(store)
        await db.commit()

        summary = await metrics_service.get_promise_tracking_summary(db)
        assert summary["total_promises"] == 0
        assert summary["promises_kept"] == 0
        assert summary["promises_broken"] == 0
        assert summary["promises_pending"] == 0
        assert summary["avg_days_late"] is None
        assert summary["worst_offenders"] == []
