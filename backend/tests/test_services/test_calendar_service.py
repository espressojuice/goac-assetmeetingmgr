"""Tests for calendar service stub."""

import datetime

import pytest

from app.services.calendar_service import CalendarService


@pytest.mark.asyncio
class TestCalendarService:

    async def test_enabled_is_false_by_default(self):
        """CalendarService.enabled is False by default."""
        service = CalendarService()
        assert service.enabled is False

    async def test_create_event_returns_none_when_disabled(self):
        """create_event returns None when service is disabled."""
        service = CalendarService()
        result = await service.create_event(
            store_name="Test Store",
            meeting_date=datetime.date(2026, 3, 15),
            meeting_time=datetime.time(14, 0),
            attendee_emails=["test@example.com"],
        )
        assert result is None
