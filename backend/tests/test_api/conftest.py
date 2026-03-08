"""Test fixtures for API tests using in-memory SQLite."""

import datetime
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app
from app.models.store import Store
from app.models.meeting import Meeting, MeetingStatus
from app.models.flag import Flag, FlagCategory, FlagSeverity, FlagStatus


@pytest_asyncio.fixture
async def db_engine():
    """Create an in-memory SQLite engine for tests."""
    engine = create_async_engine("sqlite+aiosqlite:///", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    """Create a database session for tests."""
    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_engine):
    """Create an async test client with dependency override."""
    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def sample_store(db_session):
    """Create a sample store."""
    store = Store(
        id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        name="Ashdown Classic Chevrolet",
        code="ASHDOWN",
        brand="Chevrolet",
        city="Ashdown",
        state="AR",
        meeting_cadence="biweekly",
        gm_name="John Doe",
        gm_email="jdoe@greggorracing.com",
    )
    db_session.add(store)
    await db_session.commit()
    return store


@pytest_asyncio.fixture
async def sample_meeting(db_session, sample_store):
    """Create a sample meeting."""
    meeting = Meeting(
        id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
        store_id=sample_store.id,
        meeting_date=datetime.date(2026, 2, 11),
        status=MeetingStatus.COMPLETED,
        packet_url="/tmp/test_packet.pdf",
        flagged_items_url="/tmp/test_flagged.pdf",
    )
    db_session.add(meeting)
    await db_session.commit()
    return meeting


@pytest_asyncio.fixture
async def sample_flags(db_session, sample_meeting, sample_store):
    """Create sample flags for testing."""
    flags = [
        Flag(
            meeting_id=sample_meeting.id,
            store_id=sample_store.id,
            category=FlagCategory.INVENTORY,
            severity=FlagSeverity.RED,
            field_name="days_in_stock",
            field_value="95",
            threshold="90",
            message="Used vehicle over 90 days in stock",
            status=FlagStatus.OPEN,
        ),
        Flag(
            meeting_id=sample_meeting.id,
            store_id=sample_store.id,
            category=FlagCategory.INVENTORY,
            severity=FlagSeverity.YELLOW,
            field_name="days_in_stock",
            field_value="75",
            threshold="60",
            message="Used vehicle over 60 days in stock",
            status=FlagStatus.OPEN,
        ),
        Flag(
            meeting_id=sample_meeting.id,
            store_id=sample_store.id,
            category=FlagCategory.FINANCIAL,
            severity=FlagSeverity.RED,
            field_name="over_60",
            field_value="$1,500",
            threshold="$0",
            message="Receivable over 60 days",
            status=FlagStatus.RESPONDED,
            response_text="Collected on 2/15",
            responded_by="Jane Smith",
            responded_at=datetime.datetime(2026, 2, 15, 10, 0, tzinfo=datetime.timezone.utc),
        ),
        Flag(
            meeting_id=sample_meeting.id,
            store_id=sample_store.id,
            category=FlagCategory.OPERATIONS,
            severity=FlagSeverity.YELLOW,
            field_name="days_open",
            field_value="18",
            threshold="14",
            message="Open RO over 14 days",
            status=FlagStatus.OPEN,
        ),
    ]
    for f in flags:
        db_session.add(f)
    await db_session.commit()
    return flags
