"""
Google Calendar integration — STUB for future implementation.
Design: When a meeting is created/scheduled, sync it to Google Calendar.

Required setup (future):
- Google Cloud project with Calendar API enabled
- Service account or OAuth2 credentials
- GOOGLE_CALENDAR_CREDENTIALS_JSON env var
- GOOGLE_CALENDAR_ID env var (per-store or shared)

Implementation plan:
1. On meeting create → create Google Calendar event
2. On meeting reschedule → update calendar event
3. On meeting cancel → delete calendar event
4. On schedule change → update recurring event series
5. Include attendees from default_attendee_ids
"""

from __future__ import annotations

from datetime import date, time
from typing import Optional
from uuid import UUID


class CalendarService:
    """Stub calendar service — all methods are no-ops that log intent."""

    def __init__(self):
        self.enabled = False  # Will be True when credentials are configured

    async def create_event(
        self,
        store_name: str,
        meeting_date: date,
        meeting_time: Optional[time],
        attendee_emails: list[str],
        description: str = "",
    ) -> Optional[str]:
        """Create a calendar event. Returns event_id or None if disabled."""
        if not self.enabled:
            return None
        # TODO: Implement with Google Calendar API
        # from googleapiclient.discovery import build
        # event = { 'summary': f'Asset Meeting - {store_name}', ... }
        return None

    async def update_event(self, event_id: str, **kwargs) -> bool:
        """Update an existing calendar event."""
        if not self.enabled:
            return False
        return False

    async def delete_event(self, event_id: str) -> bool:
        """Delete a calendar event."""
        if not self.enabled:
            return False
        return False

    async def sync_schedule(self, store_id: UUID, schedule) -> int:
        """Sync a store's meeting schedule to calendar as recurring events.
        Returns count of events created/updated."""
        if not self.enabled:
            return 0
        return 0
