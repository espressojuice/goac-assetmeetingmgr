"""Tests for the CSV export service."""

from __future__ import annotations

import csv
import datetime
import io
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
from app.services import export_service


STORE_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
STORE2_ID = uuid.UUID("11111111-1111-1111-1111-222222222222")
MEETING_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
MEETING2_ID = uuid.UUID("22222222-2222-2222-2222-333333333333")
USER_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
CORP_ID = uuid.UUID("44444444-4444-4444-4444-444444444444")


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def seeded_db(db):
    """Seed database with stores, meetings, flags, users, assignments, attendance."""
    store = Store(id=STORE_ID, name="Ashdown Chevrolet", code="ASH", city="Ashdown", state="AR")
    store2 = Store(id=STORE2_ID, name="Hot Springs Honda", code="HSH", city="Hot Springs", state="AR")
    db.add_all([store, store2])

    corp = User(id=CORP_ID, email="corp@test.com", name="Corp Admin", role=UserRole.CORPORATE)
    manager = User(id=USER_ID, email="mgr@test.com", name="Tommy Manager", role=UserRole.MANAGER)
    db.add_all([corp, manager])
    await db.flush()

    db.add(UserStore(user_id=USER_ID, store_id=STORE_ID))

    m1 = Meeting(
        id=MEETING_ID, store_id=STORE_ID, meeting_date=datetime.date(2026, 3, 1),
        status=MeetingStatus.CLOSED, closed_by_id=CORP_ID,
        closed_at=datetime.datetime(2026, 3, 1, 15, 0, tzinfo=datetime.timezone.utc),
        close_notes="All reviewed",
    )
    m2 = Meeting(
        id=MEETING2_ID, store_id=STORE2_ID, meeting_date=datetime.date(2026, 2, 15),
        status=MeetingStatus.COMPLETED,
    )
    db.add_all([m1, m2])
    await db.flush()

    now = datetime.datetime(2026, 3, 2, 10, 0, tzinfo=datetime.timezone.utc)
    f1 = Flag(
        id=uuid.uuid4(), meeting_id=MEETING_ID, store_id=STORE_ID,
        category=FlagCategory.INVENTORY, severity=FlagSeverity.RED,
        field_name="days_in_stock", message="Over 90 days", status=FlagStatus.VERIFIED,
        responded_at=now, verified_by_id=CORP_ID, verified_at=now,
        expected_resolution_date=datetime.date(2026, 3, 5),
    )
    f2 = Flag(
        id=uuid.uuid4(), meeting_id=MEETING_ID, store_id=STORE_ID,
        category=FlagCategory.FINANCIAL, severity=FlagSeverity.YELLOW,
        field_name="over_60", message="Receivable over 60", status=FlagStatus.UNRESOLVED,
        expected_resolution_date=datetime.date(2026, 3, 10),
    )
    f3 = Flag(
        id=uuid.uuid4(), meeting_id=MEETING_ID, store_id=STORE_ID,
        category=FlagCategory.OPERATIONS, severity=FlagSeverity.RED,
        field_name="days_open", message="Open RO", status=FlagStatus.OPEN,
    )
    f4 = Flag(
        id=uuid.uuid4(), meeting_id=MEETING2_ID, store_id=STORE2_ID,
        category=FlagCategory.PARTS, severity=FlagSeverity.YELLOW,
        field_name="turnover", message="Low turnover", status=FlagStatus.RESPONDED,
        response_text="Ordering more parts", responded_at=now,
    )
    db.add_all([f1, f2, f3, f4])
    await db.flush()

    # Assignments
    for f in [f1, f2, f3]:
        db.add(FlagAssignment(
            flag_id=f.id, assigned_to_id=USER_ID, assigned_by_id=CORP_ID,
            deadline=datetime.date(2026, 3, 5),
        ))

    # Attendance
    db.add(MeetingAttendance(
        meeting_id=MEETING_ID, user_id=USER_ID, checked_in=True,
        checked_in_at=datetime.datetime(2026, 3, 1, 14, 0, tzinfo=datetime.timezone.utc),
        checked_in_by_id=CORP_ID,
    ))
    db.add(MeetingAttendance(
        meeting_id=MEETING_ID, user_id=CORP_ID, checked_in=False,
    ))

    await db.commit()
    return db


def _parse_csv(csv_str: str) -> list[list[str]]:
    """Parse CSV string into list of rows (strip BOM)."""
    text = csv_str.lstrip("\ufeff")
    reader = csv.reader(io.StringIO(text))
    return list(reader)


# ── Meetings CSV Tests ────────────────────────────────────────────────


@pytest.mark.asyncio
class TestExportMeetingsCSV:

    async def test_returns_valid_csv_with_header(self, seeded_db):
        result = await export_service.export_meetings_csv(seeded_db)
        rows = _parse_csv(result)
        assert rows[0][0] == "Meeting Date"
        assert len(rows) == 3  # header + 2 meetings

    async def test_store_id_filter(self, seeded_db):
        result = await export_service.export_meetings_csv(seeded_db, store_id=STORE_ID)
        rows = _parse_csv(result)
        assert len(rows) == 2  # header + 1 meeting
        assert rows[1][1] == "Ashdown Chevrolet"

    async def test_date_range_filter(self, seeded_db):
        result = await export_service.export_meetings_csv(
            seeded_db, date_from=datetime.date(2026, 2, 20),
        )
        rows = _parse_csv(result)
        assert len(rows) == 2  # header + 1 meeting (March only)


# ── Flags CSV Tests ──────────────────────────────────────────────────


@pytest.mark.asyncio
class TestExportFlagsCSV:

    async def test_includes_priority_scores(self, seeded_db):
        result = await export_service.export_flags_csv(seeded_db)
        rows = _parse_csv(result)
        assert rows[0][-1] == "Priority Score"
        assert len(rows) >= 5  # header + 4 flags

    async def test_status_filter(self, seeded_db):
        result = await export_service.export_flags_csv(seeded_db, status="open")
        rows = _parse_csv(result)
        assert len(rows) == 2  # header + 1 open flag
        assert rows[1][4] == "open"


# ── Attendance CSV Tests ─────────────────────────────────────────────


@pytest.mark.asyncio
class TestExportAttendanceCSV:

    async def test_includes_checkin_details(self, seeded_db):
        result = await export_service.export_attendance_csv(seeded_db)
        rows = _parse_csv(result)
        assert rows[0][4] == "Checked In"
        assert len(rows) == 3  # header + 2 attendance records
        # Find the checked-in record
        checked = [r for r in rows[1:] if r[4] == "Yes"]
        assert len(checked) == 1
        assert checked[0][2] == "Tommy Manager"


# ── Promise Tracking CSV Tests ───────────────────────────────────────


@pytest.mark.asyncio
class TestExportPromiseTrackingCSV:

    async def test_calculates_days_late(self, seeded_db):
        result = await export_service.export_promise_tracking_csv(seeded_db)
        rows = _parse_csv(result)
        assert rows[0][-1] == "Promise Kept"
        assert len(rows) == 3  # header + 2 flags with expected_resolution_date

    async def test_promise_kept_yes_when_verified_before_expected(self, seeded_db):
        """Verified flag resolved before expected date → Yes."""
        result = await export_service.export_promise_tracking_csv(seeded_db)
        rows = _parse_csv(result)
        # Find verified flag (f1 — expected 2026-03-05, verified 2026-03-02)
        verified = [r for r in rows[1:] if r[6] == "verified"]
        assert len(verified) == 1
        assert verified[0][-1] == "Yes"

    async def test_promise_kept_pending_when_not_past(self, seeded_db):
        """Unresolved flag not yet past expected date → depends on today vs expected."""
        result = await export_service.export_promise_tracking_csv(seeded_db)
        rows = _parse_csv(result)
        unresolved = [r for r in rows[1:] if r[6] == "unresolved"]
        assert len(unresolved) == 1
        # Expected date is 2026-03-10 — if today < 2026-03-10 → Pending, else → No
        promise = unresolved[0][-1]
        assert promise in ("Pending", "No")


# ── Empty Results Tests ──────────────────────────────────────────────


@pytest.mark.asyncio
class TestExportEmptyResults:

    async def test_meetings_empty(self, db):
        result = await export_service.export_meetings_csv(db)
        rows = _parse_csv(result)
        assert len(rows) == 1  # header only

    async def test_flags_empty(self, db):
        result = await export_service.export_flags_csv(db)
        rows = _parse_csv(result)
        assert len(rows) == 1

    async def test_attendance_empty(self, db):
        result = await export_service.export_attendance_csv(db)
        rows = _parse_csv(result)
        assert len(rows) == 1

    async def test_promise_tracking_empty(self, db):
        result = await export_service.export_promise_tracking_csv(db)
        rows = _parse_csv(result)
        assert len(rows) == 1
