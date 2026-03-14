"""Tests for the accountability metrics service."""

from __future__ import annotations

import datetime
import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.models.store import Store
from app.models.meeting import Meeting, MeetingStatus
from app.models.flag import Flag, FlagCategory, FlagSeverity, FlagStatus
from app.models.user import User, UserRole, UserStore
from app.models.accountability import FlagAssignment, MeetingAttendance
from app.services import metrics_service


# ── Fixtures ──────────────────────────────────────────────────────────

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
STORE2_ID = uuid.UUID("22222222-1111-1111-1111-111111111111")
MEETING_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
MEETING2_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
MANAGER_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
CORP_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


async def seed_base(db: AsyncSession):
    """Seed stores, meetings, users, and flags for testing."""
    store = Store(id=STORE_ID, name="Ashdown", code="ASH", city="Ashdown", state="AR")
    store2 = Store(id=STORE2_ID, name="Hot Springs", code="HS", city="Hot Springs", state="AR")
    db.add_all([store, store2])

    meeting = Meeting(
        id=MEETING_ID, store_id=STORE_ID,
        meeting_date=datetime.date(2026, 2, 11), status=MeetingStatus.COMPLETED,
    )
    meeting2 = Meeting(
        id=MEETING2_ID, store_id=STORE2_ID,
        meeting_date=datetime.date(2026, 3, 1), status=MeetingStatus.COMPLETED,
    )
    db.add_all([meeting, meeting2])

    manager = User(id=MANAGER_ID, email="mgr@test.com", name="Tommy Manager", role=UserRole.MANAGER)
    corp = User(id=CORP_ID, email="corp@test.com", name="Corporate User", role=UserRole.CORPORATE)
    db.add_all([manager, corp])

    assoc = UserStore(user_id=MANAGER_ID, store_id=STORE_ID)
    db.add(assoc)

    now = datetime.datetime(2026, 2, 12, 10, 0, tzinfo=datetime.timezone.utc)
    flags = [
        Flag(
            id=uuid.uuid4(), meeting_id=MEETING_ID, store_id=STORE_ID,
            category=FlagCategory.INVENTORY, severity=FlagSeverity.RED,
            field_name="days_in_stock", message="Over 90 days",
            status=FlagStatus.VERIFIED,
            responded_at=now,
        ),
        Flag(
            id=uuid.uuid4(), meeting_id=MEETING_ID, store_id=STORE_ID,
            category=FlagCategory.INVENTORY, severity=FlagSeverity.YELLOW,
            field_name="days_in_stock", message="Over 60 days",
            status=FlagStatus.OPEN,
        ),
        Flag(
            id=uuid.uuid4(), meeting_id=MEETING_ID, store_id=STORE_ID,
            category=FlagCategory.FINANCIAL, severity=FlagSeverity.RED,
            field_name="over_60", message="Receivable over 60",
            status=FlagStatus.UNRESOLVED,
        ),
        Flag(
            id=uuid.uuid4(), meeting_id=MEETING_ID, store_id=STORE_ID,
            category=FlagCategory.OPERATIONS, severity=FlagSeverity.YELLOW,
            field_name="days_open", message="Open RO over 14 days",
            status=FlagStatus.RESPONDED,
            responded_at=now,
        ),
    ]
    db.add_all(flags)
    await db.flush()

    # Create assignments for all flags to the manager
    for f in flags:
        assignment = FlagAssignment(
            flag_id=f.id, assigned_to_id=MANAGER_ID, assigned_by_id=CORP_ID,
            deadline=datetime.date(2026, 2, 15),
        )
        db.add(assignment)

    await db.commit()
    return flags


# ── Manager Resolution Rate Tests ─────────────────────────────────────


@pytest.mark.asyncio
class TestManagerResolutionRates:

    async def test_correct_counts_mixed_statuses(self, db):
        """Manager with mixed flag statuses returns correct counts."""
        await seed_base(db)
        results = await metrics_service.get_manager_resolution_rates(db)
        assert len(results) == 1
        m = results[0]
        assert m["user_name"] == "Tommy Manager"
        assert m["total_assigned"] == 4
        assert m["total_resolved"] == 1  # VERIFIED
        assert m["total_unresolved"] == 1  # UNRESOLVED
        assert m["total_responded"] == 1  # RESPONDED
        assert m["total_open"] == 1  # OPEN

    async def test_with_store_id_filter(self, db):
        """Filtering by store_id only includes flags for that store."""
        await seed_base(db)
        # Manager has assignments in STORE_ID only
        results = await metrics_service.get_manager_resolution_rates(db, store_id=STORE_ID)
        assert len(results) == 1
        # No flags in STORE2_ID for this manager
        results2 = await metrics_service.get_manager_resolution_rates(db, store_id=STORE2_ID)
        assert len(results2) == 0

    async def test_with_date_range_filter(self, db):
        """Filtering by date range excludes meetings outside range."""
        await seed_base(db)
        # Meeting date is 2026-02-11, filter to March only
        results = await metrics_service.get_manager_resolution_rates(
            db, date_from=datetime.date(2026, 3, 1), date_to=datetime.date(2026, 3, 31),
        )
        assert len(results) == 0

    async def test_resolution_rate_calculation(self, db):
        """Resolution rate = verified / total_assigned * 100."""
        await seed_base(db)
        results = await metrics_service.get_manager_resolution_rates(db)
        m = results[0]
        # 1 verified / 4 total = 25%
        assert m["resolution_rate"] == 25.0


# ── Store Comparison Tests ────────────────────────────────────────────


@pytest.mark.asyncio
class TestStoreComparison:

    async def test_returns_all_accessible_stores(self, db):
        """Returns metrics for all active stores."""
        await seed_base(db)
        results = await metrics_service.get_store_comparison(db)
        assert len(results) == 2
        store_names = {r["store_name"] for r in results}
        assert "Ashdown" in store_names
        assert "Hot Springs" in store_names

    async def test_store_flag_metrics(self, db):
        """Correct flag counts per store."""
        await seed_base(db)
        results = await metrics_service.get_store_comparison(db)
        # Find Ashdown (has 4 flags)
        ashdown = next(r for r in results if r["store_name"] == "Ashdown")
        assert ashdown["total_flags"] == 4
        assert ashdown["total_verified"] == 1
        assert ashdown["total_unresolved"] == 1
        assert ashdown["total_open"] == 1
        assert ashdown["resolution_rate"] == 25.0

        # Hot Springs has no flags
        hs = next(r for r in results if r["store_name"] == "Hot Springs")
        assert hs["total_flags"] == 0
        assert hs["resolution_rate"] == 0.0


# ── Top Priority Items Tests ─────────────────────────────────────────


@pytest.mark.asyncio
class TestTopPriorityItems:

    async def test_unresolved_scores_higher_than_open(self, db):
        """UNRESOLVED flags get +10 vs OPEN flags which get less."""
        await seed_base(db)
        results = await metrics_service.get_top_priority_items(db, limit=10)
        # Find the UNRESOLVED flag and an OPEN flag
        unresolved = next(r for r in results if r["status"] == "unresolved")
        open_flag = next(r for r in results if r["status"] == "open")
        assert unresolved["priority_score"] > open_flag["priority_score"]

    async def test_red_scores_higher_than_yellow(self, db):
        """RED severity adds 3 vs YELLOW adds 1."""
        await seed_base(db)
        results = await metrics_service.get_top_priority_items(db, limit=10)
        # UNRESOLVED RED flag (score: 10 + 3 = 13) vs OPEN YELLOW (score: 1)
        unresolved_red = next(r for r in results if r["status"] == "unresolved" and r["severity"] == "red")
        open_yellow = next(r for r in results if r["status"] == "open" and r["severity"] == "yellow")
        assert unresolved_red["priority_score"] > open_yellow["priority_score"]

    async def test_respects_limit(self, db):
        """Limit parameter caps the number of results."""
        await seed_base(db)
        results = await metrics_service.get_top_priority_items(db, limit=2)
        assert len(results) <= 2

    async def test_with_store_id_filter(self, db):
        """Only returns flags for the specified store."""
        await seed_base(db)
        results = await metrics_service.get_top_priority_items(db, store_id=STORE2_ID)
        # No flags in store 2
        assert len(results) == 0

    async def test_broken_promise_adds_score(self, db):
        """Flag with past expected_resolution_date gets +5."""
        flags = await seed_base(db)
        # Set expected_resolution_date in the past on the OPEN flag
        open_flag = next(f for f in flags if f.status == FlagStatus.OPEN)
        open_flag.expected_resolution_date = datetime.date(2026, 1, 1)
        await db.commit()

        results = await metrics_service.get_top_priority_items(db, limit=10)
        open_item = next(r for r in results if r["flag_id"] == str(open_flag.id))
        # OPEN YELLOW: severity=1 + broken_promise=5 = 6
        assert open_item["priority_score"] >= 6
