"""Handles scheduled notification checks — runs periodically."""

from __future__ import annotations

import datetime
import logging
from typing import Optional

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.flag import Flag, FlagStatus
from app.models.meeting import Meeting
from app.models.store import Store
from app.models.user import User, UserRole
from app.models.accountability import (
    AssignmentStatus,
    FlagAssignment,
    Notification,
    NotificationType,
)
from app.services.email_service import EmailService

logger = logging.getLogger(__name__)


class NotificationScheduler:
    """Handles scheduled notification checks."""

    def __init__(self, email_service: Optional[EmailService] = None):
        self.email = email_service or EmailService()

    # ------------------------------------------------------------------ #
    # Reminder check (runs every hour)
    # ------------------------------------------------------------------ #
    async def run_reminder_check(self, db: AsyncSession) -> int:
        """Check for flags approaching deadline. Send reminder to assignees.

        Only sends one reminder per assignment (tracks via Notification record
        with type DEADLINE_REMINDER for that reference_id).

        Returns count of reminders sent.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        reminder_hours = settings.NOTIFICATION_REMINDER_HOURS
        reminder_cutoff = now + datetime.timedelta(hours=reminder_hours)

        # Find assignments approaching deadline that haven't been responded to
        query = (
            select(FlagAssignment, Flag, Meeting, Store, User)
            .join(Flag, FlagAssignment.flag_id == Flag.id)
            .join(Meeting, Flag.meeting_id == Meeting.id)
            .join(Store, Flag.store_id == Store.id)
            .join(User, FlagAssignment.assigned_to_id == User.id)
            .where(
                and_(
                    FlagAssignment.status.in_([
                        AssignmentStatus.PENDING,
                        AssignmentStatus.ACKNOWLEDGED,
                    ]),
                    # Deadline is a date — compare with cutoff date
                    FlagAssignment.deadline <= reminder_cutoff.date(),
                    FlagAssignment.deadline >= now.date(),
                )
            )
        )

        result = await db.execute(query)
        rows = result.all()

        sent_count = 0
        for assignment, flag, meeting, store, user in rows:
            # Check if reminder already sent for this assignment
            existing = await db.execute(
                select(Notification).where(
                    and_(
                        Notification.reference_id == flag.id,
                        Notification.notification_type == NotificationType.DEADLINE_REMINDER,
                        Notification.user_id == user.id,
                    )
                )
            )
            if existing.scalar_one_or_none():
                continue

            # Calculate hours remaining
            deadline_dt = datetime.datetime.combine(
                assignment.deadline,
                datetime.time(23, 59, 59),
                tzinfo=datetime.timezone.utc,
            )
            hours_remaining = max(1, int((deadline_dt - now).total_seconds() / 3600))

            # Send email
            await self.email.send_reminder_approaching(
                user, flag, meeting, store, hours_remaining
            )

            # Record notification
            notification = Notification(
                user_id=user.id,
                notification_type=NotificationType.DEADLINE_REMINDER,
                title="Deadline approaching",
                message=f"You have {hours_remaining} hours to respond to a {flag.severity.value} {flag.category.value} flag at {store.name}",
                reference_id=flag.id,
                email_sent=True,
            )
            db.add(notification)
            sent_count += 1

        if sent_count > 0:
            await db.commit()
            logger.info("Sent %d deadline reminders", sent_count)

        return sent_count

    # ------------------------------------------------------------------ #
    # Overdue check (runs daily at 7 AM CT)
    # ------------------------------------------------------------------ #
    async def run_overdue_check(self, db: AsyncSession) -> int:
        """Check for overdue flags. Notify managers and corporate.

        Batches overdue flags per user per store. Sends one email per
        manager per store, and one escalation email per store to corporate.

        Only sends once per day per store (checks for existing OVERDUE_NOTICE
        notification created today).

        Returns count of notifications sent.
        """
        today = datetime.date.today()

        # Find all overdue assignments
        query = (
            select(FlagAssignment, Flag, Meeting, Store, User)
            .join(Flag, FlagAssignment.flag_id == Flag.id)
            .join(Meeting, Flag.meeting_id == Meeting.id)
            .join(Store, Flag.store_id == Store.id)
            .join(User, FlagAssignment.assigned_to_id == User.id)
            .where(
                and_(
                    FlagAssignment.deadline < today,
                    FlagAssignment.status.in_([
                        AssignmentStatus.PENDING,
                        AssignmentStatus.ACKNOWLEDGED,
                    ]),
                )
            )
        )

        result = await db.execute(query)
        rows = result.all()

        if not rows:
            return 0

        # Group by (store_id, user_id)
        by_store_user: dict[tuple, list] = {}
        store_map: dict = {}
        user_map: dict = {}
        for assignment, flag, meeting, store, user in rows:
            key = (str(store.id), str(user.id))
            if key not in by_store_user:
                by_store_user[key] = []
            days_overdue = (today - assignment.deadline).days
            by_store_user[key].append({
                "id": str(flag.id),
                "message": flag.message,
                "severity": flag.severity.value,
                "days_overdue": days_overdue,
                "assigned_to_name": user.name,
            })
            store_map[str(store.id)] = store
            user_map[str(user.id)] = user

        # Check if overdue notice already sent today for each store
        sent_count = 0
        notified_stores = set()

        for (store_id, user_id), flags_data in by_store_user.items():
            store = store_map[store_id]
            user = user_map[user_id]

            # Check if already notified today
            existing = await db.execute(
                select(Notification).where(
                    and_(
                        Notification.user_id == user.id,
                        Notification.notification_type == NotificationType.OVERDUE_NOTICE,
                        func.date(Notification.created_at) == today,
                    )
                )
            )
            if existing.scalar_one_or_none():
                continue

            # Send overdue email to manager
            await self.email.send_overdue_to_manager(user, flags_data, store)

            notification = Notification(
                user_id=user.id,
                notification_type=NotificationType.OVERDUE_NOTICE,
                title=f"{len(flags_data)} overdue flags at {store.name}",
                message=f"You have {len(flags_data)} overdue flag(s) at {store.name}. Corporate has been notified.",
                reference_id=None,
                email_sent=True,
            )
            db.add(notification)
            sent_count += 1

            # Track stores for corporate escalation
            if store_id not in notified_stores:
                notified_stores.add(store_id)

        # Send escalation to corporate for each store
        if notified_stores:
            corporate_result = await db.execute(
                select(User).where(
                    and_(
                        User.role == UserRole.CORPORATE,
                        User.is_active == True,  # noqa: E712
                    )
                )
            )
            corporate_users = list(corporate_result.scalars().all())

            if corporate_users:
                for store_id in notified_stores:
                    store = store_map[store_id]
                    # Collect all overdue flags for this store
                    store_flags = []
                    for (sid, _), flags_data in by_store_user.items():
                        if sid == store_id:
                            store_flags.extend(flags_data)

                    await self.email.send_overdue_to_corporate(
                        corporate_users, store, store_flags
                    )

                    # Create notification for each corporate user
                    for cu in corporate_users:
                        notification = Notification(
                            user_id=cu.id,
                            notification_type=NotificationType.ESCALATION,
                            title=f"Escalation: {len(store_flags)} overdue at {store.name}",
                            message=f"{store.name} has {len(store_flags)} overdue flag(s).",
                            reference_id=None,
                            email_sent=True,
                        )
                        db.add(notification)
                        sent_count += 1

        if sent_count > 0:
            await db.commit()
            logger.info("Sent %d overdue notifications", sent_count)

        return sent_count

    # ------------------------------------------------------------------ #
    # Pre-meeting reminders (runs daily)
    # ------------------------------------------------------------------ #
    async def check_pre_meeting_reminders(self, db: AsyncSession) -> int:
        """Send reminders for unanswered flags when a meeting is today or tomorrow.

        For each meeting scheduled today or tomorrow, finds flags with
        status=OPEN that are assigned to someone but not yet responded.
        Creates a DEADLINE_REMINDER notification (and sends email) for
        each such user, but only once per flag per user.

        Returns count of reminders sent.
        """
        from zoneinfo import ZoneInfo

        now_ct = datetime.datetime.now(ZoneInfo("US/Central"))
        today = now_ct.date()
        tomorrow = today + datetime.timedelta(days=1)

        # Find meetings scheduled for today or tomorrow
        meeting_query = select(Meeting).where(
            Meeting.meeting_date.in_([today, tomorrow]),
        )
        meeting_result = await db.execute(meeting_query)
        meetings = list(meeting_result.scalars().all())

        if not meetings:
            return 0

        sent_count = 0
        for meeting in meetings:
            # Find OPEN flags for this meeting that are assigned
            query = (
                select(FlagAssignment, Flag, Store, User)
                .join(Flag, FlagAssignment.flag_id == Flag.id)
                .join(Store, Flag.store_id == Store.id)
                .join(User, FlagAssignment.assigned_to_id == User.id)
                .where(
                    and_(
                        Flag.meeting_id == meeting.id,
                        Flag.status == FlagStatus.OPEN,
                        FlagAssignment.status.in_([
                            AssignmentStatus.PENDING,
                            AssignmentStatus.ACKNOWLEDGED,
                        ]),
                    )
                )
            )
            result = await db.execute(query)
            rows = result.all()

            for assignment, flag, store, user in rows:
                # Check if reminder already sent for this flag+user
                existing = await db.execute(
                    select(Notification).where(
                        and_(
                            Notification.reference_id == flag.id,
                            Notification.notification_type == NotificationType.DEADLINE_REMINDER,
                            Notification.user_id == user.id,
                            Notification.title == "Pre-Meeting Response Needed",
                        )
                    )
                )
                if existing.scalar_one_or_none():
                    continue

                meeting_date_str = meeting.meeting_date.strftime("%B %d, %Y")
                message = (
                    f"You have unanswered flags for the {store.name} asset meeting "
                    f"on {meeting_date_str}. Please respond before the meeting."
                )

                notification = Notification(
                    user_id=user.id,
                    notification_type=NotificationType.DEADLINE_REMINDER,
                    title="Pre-Meeting Response Needed",
                    message=message,
                    reference_id=flag.id,
                    email_sent=True,
                )
                db.add(notification)

                # Send email
                await self.email.send_reminder_approaching(
                    user, flag, meeting, store,
                    hours_remaining=24 if meeting.meeting_date == tomorrow else 0,
                )

                sent_count += 1

        if sent_count > 0:
            await db.commit()
            logger.info("Sent %d pre-meeting reminders", sent_count)

        return sent_count

    # ------------------------------------------------------------------ #
    # Daily digest (runs Mon-Fri at 7:30 AM CT)
    # ------------------------------------------------------------------ #
    async def run_daily_digest(self, db: AsyncSession) -> int:
        """Send daily summary to corporate users. Skips weekends.

        Returns count of digests sent.
        """
        today = datetime.date.today()

        # Skip weekends (Mon=0, Sun=6)
        if today.weekday() >= 5:
            logger.info("Skipping daily digest — weekend")
            return 0

        # Get corporate users
        corporate_result = await db.execute(
            select(User).where(
                and_(
                    User.role == UserRole.CORPORATE,
                    User.is_active == True,  # noqa: E712
                )
            )
        )
        corporate_users = list(corporate_result.scalars().all())
        if not corporate_users:
            return 0

        # Get all active stores with flag stats
        stores_result = await db.execute(
            select(Store).where(Store.is_active == True)  # noqa: E712
        )
        stores = list(stores_result.scalars().all())

        store_summaries = []
        for store in stores:
            # Open flags
            open_count_result = await db.execute(
                select(func.count(Flag.id)).where(
                    and_(
                        Flag.store_id == store.id,
                        Flag.status == FlagStatus.OPEN,
                    )
                )
            )
            open_flags = open_count_result.scalar() or 0

            # Responded today
            responded_result = await db.execute(
                select(func.count(Flag.id)).where(
                    and_(
                        Flag.store_id == store.id,
                        Flag.status == FlagStatus.RESPONDED,
                        func.date(Flag.responded_at) == today,
                    )
                )
            )
            responded_today = responded_result.scalar() or 0

            # Newly overdue (assignments past deadline, not responded)
            overdue_result = await db.execute(
                select(func.count(FlagAssignment.id))
                .join(Flag, FlagAssignment.flag_id == Flag.id)
                .where(
                    and_(
                        Flag.store_id == store.id,
                        FlagAssignment.deadline < today,
                        FlagAssignment.status.in_([
                            AssignmentStatus.PENDING,
                            AssignmentStatus.ACKNOWLEDGED,
                        ]),
                    )
                )
            )
            newly_overdue = overdue_result.scalar() or 0

            store_summaries.append({
                "store_name": store.name,
                "open_flags": open_flags,
                "responded_today": responded_today,
                "newly_overdue": newly_overdue,
            })

        # Send to each corporate user
        date_str = today.strftime("%B %d, %Y")
        sent_count = 0
        for user in corporate_users:
            await self.email.send_daily_digest(user, date_str, store_summaries)
            sent_count += 1

        logger.info("Sent daily digest to %d corporate users", sent_count)
        return sent_count
