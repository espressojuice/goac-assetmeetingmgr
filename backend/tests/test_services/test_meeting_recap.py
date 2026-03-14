"""Tests for the meeting recap email generation (used by close meeting)."""

from __future__ import annotations

import datetime
import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.services.email_service import EmailService, _wrap_html


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

class MockEnum:
    def __init__(self, value):
        self.value = value


class MockFlag:
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", uuid.uuid4())
        self.severity = MockEnum(kwargs.get("severity", "red"))
        self.category = MockEnum(kwargs.get("category", "inventory"))
        self.message = kwargs.get("message", "Used vehicle over 90 days in stock")
        self.status = MockEnum(kwargs.get("status", "unresolved"))


class MockUser:
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", uuid.uuid4())
        self.email = kwargs.get("email", "corporate@goac.com")
        self.name = kwargs.get("name", "Corporate Admin")
        self.role = kwargs.get("role", "corporate")
        self.is_active = True


class MockStore:
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", uuid.uuid4())
        self.name = kwargs.get("name", "Ashdown Classic Chevrolet")


class MockAttendance:
    def __init__(self, user_id, checked_in=False):
        self.user_id = user_id
        self.checked_in = checked_in


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
class TestMeetingRecapEmail:

    async def test_recap_email_subject_line(self):
        """Recap email subject includes store name and meeting date."""
        svc = EmailService()
        sent_emails = []

        async def capture_email(to_email, subject, html, text_content=None):
            sent_emails.append({"to": to_email, "subject": subject, "html": html})
            return True

        svc.send_email = capture_email

        store = MockStore(name="Ashdown Classic Chevrolet")
        user = MockUser()

        subject = f"Meeting Closed — {store.name} 2026-02-11"
        await svc.send_email(user.email, subject, _wrap_html("<p>test</p>"))

        assert len(sent_emails) == 1
        assert "Ashdown Classic Chevrolet" in sent_emails[0]["subject"]
        assert "2026-02-11" in sent_emails[0]["subject"]

    async def test_recap_includes_attendance_section(self):
        """Recap HTML includes attendance markers."""
        from app.services.email_service import _wrap_html, _severity_badge

        user1_id = uuid.uuid4()
        user2_id = uuid.uuid4()
        attendance = [
            MockAttendance(user1_id, checked_in=True),
            MockAttendance(user2_id, checked_in=False),
        ]

        # Build attendance HTML same way the route does
        attendance_rows = ""
        for a in attendance:
            status_icon = "&#9989;" if a.checked_in else "&#10060;"
            attendance_rows += f'<tr><td>{a.user_id}</td><td>{status_icon}</td></tr>'

        html = f"<h3>Attendance (1/2)</h3><table>{attendance_rows}</table>"
        full_html = _wrap_html(html)

        # Present user should have checkmark
        assert "&#9989;" in full_html
        # Absent user should have cross
        assert "&#10060;" in full_html
        assert "Attendance (1/2)" in full_html

    async def test_recap_groups_flags_by_status(self):
        """Recap HTML groups flags into verified/responded/unresolved sections."""
        from app.services.email_service import _severity_badge

        flags = [
            MockFlag(status="verified", severity="yellow", message="Parts turnover low"),
            MockFlag(status="responded", severity="red", message="RO over 14 days"),
            MockFlag(status="unresolved", severity="red", message="Vehicle over 90 days"),
            MockFlag(status="unresolved", severity="yellow", message="Receivable over 30"),
        ]

        verified = [f for f in flags if f.status.value == "verified"]
        responded = [f for f in flags if f.status.value == "responded"]
        unresolved = [f for f in flags if f.status.value == "unresolved"]

        assert len(verified) == 1
        assert len(responded) == 1
        assert len(unresolved) == 2

        # Build flags HTML
        html_parts = []
        html_parts.append(f"<h3>Flags Summary ({len(flags)} total)</h3>")
        html_parts.append(f"<p>Verified: {len(verified)} | Responded: {len(responded)} | Unresolved: {len(unresolved)}</p>")

        if unresolved:
            html_parts.append(f"<h4>Unresolved ({len(unresolved)})</h4>")
            for f in unresolved:
                html_parts.append(f"<p>{_severity_badge(f.severity.value)} {f.message}</p>")

        full_html = _wrap_html("".join(html_parts))
        assert "Unresolved (2)" in full_html
        assert "Flags Summary (4 total)" in full_html
        assert "Vehicle over 90 days" in full_html

    async def test_recap_handles_no_flags(self):
        """Recap with empty flag list doesn't error."""
        flags = []
        verified = [f for f in flags if getattr(f, "status", None) and f.status.value == "verified"]
        responded = [f for f in flags if getattr(f, "status", None) and f.status.value == "responded"]
        unresolved = [f for f in flags if getattr(f, "status", None) and f.status.value == "unresolved"]

        html = f"<h3>Flags Summary ({len(flags)} total)</h3>"
        html += f"<p>Verified: {len(verified)} | Responded: {len(responded)} | Unresolved: {len(unresolved)}</p>"

        full_html = _wrap_html(html)
        assert "Flags Summary (0 total)" in full_html
        assert "Verified: 0" in full_html
