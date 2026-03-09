"""APScheduler integration for periodic notification jobs."""

from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.database import async_session
from app.services.notification_scheduler import NotificationScheduler

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="US/Central")


async def _run_reminder_check():
    """Wrapper that creates a DB session and runs the reminder check."""
    async with async_session() as db:
        try:
            ns = NotificationScheduler()
            count = await ns.run_reminder_check(db)
            if count:
                logger.info("Reminder check: sent %d reminders", count)
        except Exception:
            logger.exception("Error in reminder check job")


async def _run_overdue_check():
    """Wrapper that creates a DB session and runs the overdue check."""
    async with async_session() as db:
        try:
            ns = NotificationScheduler()
            count = await ns.run_overdue_check(db)
            if count:
                logger.info("Overdue check: sent %d notifications", count)
        except Exception:
            logger.exception("Error in overdue check job")


async def _run_daily_digest():
    """Wrapper that creates a DB session and runs the daily digest."""
    async with async_session() as db:
        try:
            ns = NotificationScheduler()
            count = await ns.run_daily_digest(db)
            if count:
                logger.info("Daily digest: sent %d emails", count)
        except Exception:
            logger.exception("Error in daily digest job")


def start_scheduler():
    """Configure and start the APScheduler."""
    # Check for approaching deadlines every hour
    scheduler.add_job(
        _run_reminder_check,
        "interval",
        hours=1,
        id="reminder_check",
        replace_existing=True,
    )

    # Check for overdue flags daily at 7:00 AM CT
    scheduler.add_job(
        _run_overdue_check,
        "cron",
        hour=7,
        minute=0,
        id="overdue_check",
        replace_existing=True,
    )

    # Send daily digest at 7:30 AM CT (Mon-Fri handled in the job itself)
    scheduler.add_job(
        _run_daily_digest,
        "cron",
        hour=7,
        minute=30,
        id="daily_digest",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Notification scheduler started (reminder=1h, overdue=7AM CT, digest=7:30AM CT)")
