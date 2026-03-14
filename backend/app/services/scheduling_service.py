"""Meeting scheduling and cadence enforcement service."""

from __future__ import annotations

import calendar
import datetime
import uuid
from typing import Optional

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.meeting import Meeting, MeetingStatus
from app.models.meeting_schedule import MeetingCadence, MeetingSchedule
from app.models.store import Store
from app.models.user import User


async def get_store_schedule(
    db: AsyncSession, store_id: uuid.UUID
) -> Optional[MeetingSchedule]:
    """Return the schedule for a store, or None if not set."""
    result = await db.execute(
        select(MeetingSchedule).where(MeetingSchedule.store_id == store_id)
    )
    return result.scalar_one_or_none()


async def upsert_store_schedule(
    db: AsyncSession,
    store_id: uuid.UUID,
    cadence: MeetingCadence,
    preferred_day: Optional[int],
    preferred_time: Optional[datetime.time],
    minimum_per_month: int,
    notes: Optional[str],
    created_by_id: Optional[uuid.UUID],
    template_name: Optional[str] = None,
    default_attendee_ids: Optional[list] = None,
    auto_create_meetings: bool = False,
    reminder_days_before: int = 2,
) -> MeetingSchedule:
    """Create or update the schedule for a store."""
    existing = await get_store_schedule(db, store_id)
    if existing:
        existing.cadence = cadence
        existing.preferred_day_of_week = preferred_day
        existing.preferred_time = preferred_time
        existing.minimum_per_month = minimum_per_month
        existing.notes = notes
        existing.template_name = template_name
        existing.default_attendee_ids = default_attendee_ids
        existing.auto_create_meetings = auto_create_meetings
        existing.reminder_days_before = reminder_days_before
        await db.commit()
        await db.refresh(existing)
        return existing

    schedule = MeetingSchedule(
        store_id=store_id,
        cadence=cadence,
        preferred_day_of_week=preferred_day,
        preferred_time=preferred_time,
        minimum_per_month=minimum_per_month,
        notes=notes,
        created_by_id=created_by_id,
        template_name=template_name,
        default_attendee_ids=default_attendee_ids,
        auto_create_meetings=auto_create_meetings,
        reminder_days_before=reminder_days_before,
    )
    db.add(schedule)
    await db.commit()
    await db.refresh(schedule)
    return schedule


def get_upcoming_meetings(
    cadence: MeetingCadence,
    preferred_day: Optional[int],
    reference_date: Optional[datetime.date] = None,
    months_ahead: int = 1,
) -> list[datetime.date]:
    """Generate expected meeting dates based on cadence and preferred day.

    Pure date math — no DB access needed.
    """
    if cadence == MeetingCadence.CUSTOM:
        return []

    today = reference_date or datetime.date.today()
    day_of_week = preferred_day if preferred_day is not None else 1  # default Tuesday

    dates: list[datetime.date] = []

    # Generate dates for current month + months_ahead
    for month_offset in range(months_ahead + 1):
        year = today.year
        month = today.month + month_offset
        while month > 12:
            month -= 12
            year += 1

        month_dates = _get_dates_for_month(cadence, day_of_week, year, month)
        dates.extend(month_dates)

    # Filter to dates >= today
    dates = [d for d in dates if d >= today]
    return sorted(dates)


def _get_dates_for_month(
    cadence: MeetingCadence,
    day_of_week: int,
    year: int,
    month: int,
) -> list[datetime.date]:
    """Get all occurrences of day_of_week in the given month."""
    # Find all occurrences of preferred day in this month
    occurrences = _get_weekday_occurrences(year, month, day_of_week)

    if cadence == MeetingCadence.WEEKLY:
        return occurrences

    if cadence == MeetingCadence.BIWEEKLY:
        # Every other week: 1st and 3rd occurrence (or 2nd and 4th if only 4)
        return occurrences[::2]  # 1st, 3rd (and 5th if exists)

    if cadence == MeetingCadence.FIRST_AND_THIRD:
        result = []
        if len(occurrences) >= 1:
            result.append(occurrences[0])
        if len(occurrences) >= 3:
            result.append(occurrences[2])
        return result

    if cadence == MeetingCadence.SECOND_AND_FOURTH:
        result = []
        if len(occurrences) >= 2:
            result.append(occurrences[1])
        if len(occurrences) >= 4:
            result.append(occurrences[3])
        return result

    return []


def _get_weekday_occurrences(
    year: int, month: int, day_of_week: int
) -> list[datetime.date]:
    """Return all dates in a month that fall on the given weekday (0=Mon, 6=Sun)."""
    # Find first occurrence
    first_day = datetime.date(year, month, 1)
    days_ahead = day_of_week - first_day.weekday()
    if days_ahead < 0:
        days_ahead += 7
    first_occurrence = first_day + datetime.timedelta(days=days_ahead)

    _, days_in_month = calendar.monthrange(year, month)
    occurrences = []
    current = first_occurrence
    while current.month == month:
        occurrences.append(current)
        current += datetime.timedelta(days=7)
    return occurrences


async def get_cadence_compliance(
    db: AsyncSession,
    store_id: Optional[uuid.UUID] = None,
    month: Optional[int] = None,
    year: Optional[int] = None,
) -> list[dict]:
    """Check cadence compliance for each store.

    Returns per-store: store info, scheduled cadence, minimum required,
    actual meeting count, compliance status, next expected date, days since last.
    """
    today = datetime.date.today()
    target_month = month or today.month
    target_year = year or today.year

    # Get all active schedules (or for a specific store)
    schedule_query = select(MeetingSchedule, Store).join(
        Store, MeetingSchedule.store_id == Store.id
    ).where(MeetingSchedule.is_active == True)

    if store_id:
        schedule_query = schedule_query.where(MeetingSchedule.store_id == store_id)

    result = await db.execute(schedule_query)
    rows = result.all()

    compliance_list = []

    for schedule, store in rows:
        # Count actual meetings in the target month (exclude cancelled)
        month_start = datetime.date(target_year, target_month, 1)
        _, days_in_month = calendar.monthrange(target_year, target_month)
        month_end = datetime.date(target_year, target_month, days_in_month)

        meeting_count_result = await db.execute(
            select(func.count(Meeting.id)).where(
                and_(
                    Meeting.store_id == store.id,
                    Meeting.meeting_date >= month_start,
                    Meeting.meeting_date <= month_end,
                    Meeting.status != MeetingStatus.ERROR,
                )
            )
        )
        actual_count = meeting_count_result.scalar() or 0

        # Get most recent meeting
        last_meeting_result = await db.execute(
            select(Meeting.meeting_date)
            .where(
                and_(
                    Meeting.store_id == store.id,
                    Meeting.status != MeetingStatus.ERROR,
                )
            )
            .order_by(Meeting.meeting_date.desc())
            .limit(1)
        )
        last_meeting_date = last_meeting_result.scalar_one_or_none()

        days_since = None
        if last_meeting_date:
            days_since = (today - last_meeting_date).days

        # Get next expected date
        upcoming = get_upcoming_meetings(
            schedule.cadence,
            schedule.preferred_day_of_week,
            reference_date=today,
            months_ahead=1,
        )
        next_expected = upcoming[0] if upcoming else None

        compliance_list.append({
            "store_id": str(store.id),
            "store_name": store.name,
            "cadence": schedule.cadence.value,
            "minimum_required": schedule.minimum_per_month,
            "actual_count": actual_count,
            "is_compliant": actual_count >= schedule.minimum_per_month,
            "next_expected_date": str(next_expected) if next_expected else None,
            "days_since_last_meeting": days_since,
        })

    return compliance_list


async def check_overdue_meetings(db: AsyncSession) -> list[dict]:
    """Find stores behind on their meeting cadence.

    A store is overdue if days_since_last_meeting > (30 / minimum_per_month) + 3 days grace.
    """
    today = datetime.date.today()

    result = await db.execute(
        select(MeetingSchedule, Store)
        .join(Store, MeetingSchedule.store_id == Store.id)
        .where(MeetingSchedule.is_active == True)
    )
    rows = result.all()

    overdue_list = []

    for schedule, store in rows:
        # Get most recent meeting (not ERROR)
        last_result = await db.execute(
            select(Meeting.meeting_date)
            .where(
                and_(
                    Meeting.store_id == store.id,
                    Meeting.status != MeetingStatus.ERROR,
                )
            )
            .order_by(Meeting.meeting_date.desc())
            .limit(1)
        )
        last_date = last_result.scalar_one_or_none()

        if not last_date:
            # No meetings ever — consider overdue
            overdue_list.append({
                "store_id": str(store.id),
                "store_name": store.name,
                "last_meeting_date": None,
                "days_overdue": 999,  # sentinel for "never met"
                "cadence": schedule.cadence.value,
            })
            continue

        days_since = (today - last_date).days
        expected_interval = 30 / schedule.minimum_per_month
        grace_period = 3
        max_allowed = expected_interval + grace_period

        if days_since > max_allowed:
            days_overdue = int(days_since - expected_interval)
            overdue_list.append({
                "store_id": str(store.id),
                "store_name": store.name,
                "last_meeting_date": str(last_date),
                "days_overdue": days_overdue,
                "cadence": schedule.cadence.value,
            })

    return overdue_list


async def auto_create_upcoming_meetings(db: AsyncSession) -> list[dict]:
    """Auto-create Meeting records for schedules with auto_create_meetings=True.

    For each active auto-create schedule, generates expected dates for the next
    30 days and creates Meeting records for any dates that don't already exist.
    Idempotent — never creates duplicates for the same store + date.
    """
    today = datetime.date.today()

    result = await db.execute(
        select(MeetingSchedule, Store)
        .join(Store, MeetingSchedule.store_id == Store.id)
        .where(
            and_(
                MeetingSchedule.is_active == True,
                MeetingSchedule.auto_create_meetings == True,
            )
        )
    )
    rows = result.all()

    created_meetings = []

    for schedule, store in rows:
        upcoming = get_upcoming_meetings(
            schedule.cadence,
            schedule.preferred_day_of_week,
            reference_date=today,
            months_ahead=1,
        )
        # Filter to next 30 days
        cutoff = today + datetime.timedelta(days=30)
        upcoming = [d for d in upcoming if d <= cutoff]

        for meeting_date in upcoming:
            # Check if meeting already exists for this store + date
            exists_result = await db.execute(
                select(func.count(Meeting.id)).where(
                    and_(
                        Meeting.store_id == store.id,
                        Meeting.meeting_date == meeting_date,
                    )
                )
            )
            if exists_result.scalar() > 0:
                continue

            meeting = Meeting(
                store_id=store.id,
                meeting_date=meeting_date,
                status=MeetingStatus.PENDING,
            )
            db.add(meeting)
            await db.flush()

            created_meetings.append({
                "store_name": store.name,
                "meeting_date": str(meeting_date),
                "meeting_id": str(meeting.id),
            })

    await db.commit()
    return created_meetings


async def get_template_details(
    db: AsyncSession, store_id: uuid.UUID
) -> Optional[dict]:
    """Return schedule with template info and resolved attendee names."""
    schedule = await get_store_schedule(db, store_id)
    if not schedule:
        return None

    # Get store name
    store_result = await db.execute(select(Store).where(Store.id == store_id))
    store = store_result.scalar_one_or_none()
    store_name = store.name if store else "Unknown"

    # Resolve attendee names from UUIDs
    attendee_names = []
    if schedule.default_attendee_ids:
        for uid_str in schedule.default_attendee_ids:
            try:
                uid = uuid.UUID(uid_str) if isinstance(uid_str, str) else uid_str
                user_result = await db.execute(
                    select(User.name).where(User.id == uid)
                )
                name = user_result.scalar_one_or_none()
                if name:
                    attendee_names.append(name)
            except (ValueError, TypeError):
                continue

    return {
        "id": str(schedule.id),
        "store_id": str(schedule.store_id),
        "store_name": store_name,
        "cadence": schedule.cadence.value,
        "template_name": schedule.template_name,
        "default_attendee_ids": schedule.default_attendee_ids or [],
        "default_attendee_names": attendee_names,
        "auto_create_meetings": schedule.auto_create_meetings,
        "reminder_days_before": schedule.reminder_days_before,
    }
