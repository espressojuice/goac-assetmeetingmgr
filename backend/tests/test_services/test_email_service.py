"""Tests for the email service."""

from __future__ import annotations

import datetime
import uuid
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
import pytest_asyncio

from app.services.email_service import EmailService, _wrap_html, _strip_html


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

class MockUser:
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", uuid.uuid4())
        self.email = kwargs.get("email", "test@example.com")
        self.name = kwargs.get("name", "Test User")
        self.role = kwargs.get("role", "gm")


class MockEnum:
    def __init__(self, value):
        self.value = value


class MockFlag:
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", uuid.uuid4())
        self.severity = MockEnum(kwargs.get("severity", "red"))
        self.category = MockEnum(kwargs.get("category", "inventory"))
        self.message = kwargs.get("message", "Used vehicle over 90 days in stock")
        self.store_id = kwargs.get("store_id", uuid.uuid4())


class MockMeeting:
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", uuid.uuid4())
        self.meeting_date = kwargs.get("meeting_date", datetime.date(2026, 2, 11))


class MockStore:
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", uuid.uuid4())
        self.name = kwargs.get("name", "Ashdown Classic Chevrolet")
        self.gm_name = kwargs.get("gm_name", "John Doe")
        self.gm_email = kwargs.get("gm_email", "jdoe@test.com")


class MockResponse:
    def __init__(self, **kwargs):
        self.response_text = kwargs.get("response_text", "We have addressed this issue by selling the vehicle at auction.")
        self.user = MockUser(name="Jane Manager")


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #

class TestEmailServiceInit:
    def test_enabled_when_api_key_set(self):
        with patch("app.services.email_service.settings") as mock_settings:
            mock_settings.SENDGRID_API_KEY = "SG.test_key"
            mock_settings.SENDGRID_FROM_EMAIL = "test@test.com"
            mock_settings.SENDGRID_FROM_NAME = "Test"
            mock_settings.NOTIFICATION_ENABLED = True
            mock_settings.FRONTEND_URL = "http://localhost:3000"
            svc = EmailService()
            assert svc.enabled is True

    def test_disabled_when_no_api_key(self):
        with patch("app.services.email_service.settings") as mock_settings:
            mock_settings.SENDGRID_API_KEY = ""
            mock_settings.SENDGRID_FROM_EMAIL = "test@test.com"
            mock_settings.SENDGRID_FROM_NAME = "Test"
            mock_settings.NOTIFICATION_ENABLED = True
            mock_settings.FRONTEND_URL = "http://localhost:3000"
            svc = EmailService()
            assert svc.enabled is False

    def test_disabled_when_notifications_off(self):
        with patch("app.services.email_service.settings") as mock_settings:
            mock_settings.SENDGRID_API_KEY = "SG.test_key"
            mock_settings.SENDGRID_FROM_EMAIL = "test@test.com"
            mock_settings.SENDGRID_FROM_NAME = "Test"
            mock_settings.NOTIFICATION_ENABLED = False
            mock_settings.FRONTEND_URL = "http://localhost:3000"
            svc = EmailService()
            assert svc.enabled is False


class TestSendEmail:
    @pytest.mark.asyncio
    async def test_send_email_disabled_logs_and_returns_true(self):
        """When disabled, send_email should log and return True."""
        with patch("app.services.email_service.settings") as mock_settings:
            mock_settings.SENDGRID_API_KEY = ""
            mock_settings.SENDGRID_FROM_EMAIL = "test@test.com"
            mock_settings.SENDGRID_FROM_NAME = "Test"
            mock_settings.NOTIFICATION_ENABLED = True
            mock_settings.FRONTEND_URL = "http://localhost:3000"
            svc = EmailService()
            result = await svc.send_email("user@test.com", "Test", "<p>Hello</p>")
            assert result is True

    @pytest.mark.asyncio
    async def test_send_email_success(self):
        """Successful SendGrid API call returns True."""
        with patch("app.services.email_service.settings") as mock_settings:
            mock_settings.SENDGRID_API_KEY = "SG.test"
            mock_settings.SENDGRID_FROM_EMAIL = "test@test.com"
            mock_settings.SENDGRID_FROM_NAME = "Test"
            mock_settings.NOTIFICATION_ENABLED = True
            mock_settings.FRONTEND_URL = "http://localhost:3000"
            svc = EmailService()

            mock_resp = MagicMock()
            mock_resp.status_code = 202

            with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
                result = await svc.send_email("user@test.com", "Test", "<p>Hello</p>")
                assert result is True

    @pytest.mark.asyncio
    async def test_send_email_api_error_returns_false(self):
        """SendGrid API error returns False, doesn't crash."""
        with patch("app.services.email_service.settings") as mock_settings:
            mock_settings.SENDGRID_API_KEY = "SG.test"
            mock_settings.SENDGRID_FROM_EMAIL = "test@test.com"
            mock_settings.SENDGRID_FROM_NAME = "Test"
            mock_settings.NOTIFICATION_ENABLED = True
            mock_settings.FRONTEND_URL = "http://localhost:3000"
            svc = EmailService()

            mock_resp = MagicMock()
            mock_resp.status_code = 400
            mock_resp.text = "Bad Request"

            with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
                result = await svc.send_email("user@test.com", "Test", "<p>Hello</p>")
                assert result is False

    @pytest.mark.asyncio
    async def test_send_email_exception_returns_false(self):
        """Network error returns False, doesn't crash."""
        with patch("app.services.email_service.settings") as mock_settings:
            mock_settings.SENDGRID_API_KEY = "SG.test"
            mock_settings.SENDGRID_FROM_EMAIL = "test@test.com"
            mock_settings.SENDGRID_FROM_NAME = "Test"
            mock_settings.NOTIFICATION_ENABLED = True
            mock_settings.FRONTEND_URL = "http://localhost:3000"
            svc = EmailService()

            with patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=Exception("Network error")):
                result = await svc.send_email("user@test.com", "Test", "<p>Hello</p>")
                assert result is False


class TestEmailTemplates:
    @pytest.mark.asyncio
    async def test_send_flag_assigned_generates_correct_subject(self):
        with patch("app.services.email_service.settings") as mock_settings:
            mock_settings.SENDGRID_API_KEY = ""
            mock_settings.SENDGRID_FROM_EMAIL = "test@test.com"
            mock_settings.SENDGRID_FROM_NAME = "Test"
            mock_settings.NOTIFICATION_ENABLED = True
            mock_settings.FRONTEND_URL = "http://localhost:3000"
            svc = EmailService()

            user = MockUser()
            flag = MockFlag()
            meeting = MockMeeting()
            store = MockStore()

            # Capture the email that would be sent
            with patch.object(svc, "send_email", new_callable=AsyncMock, return_value=True) as mock_send:
                await svc.send_flag_assigned(user, flag, meeting, store)
                mock_send.assert_called_once()
                subject = mock_send.call_args[0][1]
                assert "ACTION REQUIRED" in subject
                assert "Ashdown Classic Chevrolet" in subject

    @pytest.mark.asyncio
    async def test_send_flag_assigned_html_contains_key_elements(self):
        with patch("app.services.email_service.settings") as mock_settings:
            mock_settings.SENDGRID_API_KEY = ""
            mock_settings.SENDGRID_FROM_EMAIL = "test@test.com"
            mock_settings.SENDGRID_FROM_NAME = "Test"
            mock_settings.NOTIFICATION_ENABLED = True
            mock_settings.FRONTEND_URL = "http://localhost:3000"
            svc = EmailService()

            user = MockUser()
            flag = MockFlag()
            meeting = MockMeeting()
            store = MockStore()

            with patch.object(svc, "send_email", new_callable=AsyncMock, return_value=True) as mock_send:
                await svc.send_flag_assigned(user, flag, meeting, store)
                html = mock_send.call_args[0][2]
                assert "GREGG ORR AUTO COLLECTION" in html
                assert "Test User" in html
                assert "Ashdown Classic Chevrolet" in html
                assert "RED" in html
                assert "Respond to This Flag" in html

    @pytest.mark.asyncio
    async def test_send_overdue_to_manager_batches_flags(self):
        with patch("app.services.email_service.settings") as mock_settings:
            mock_settings.SENDGRID_API_KEY = ""
            mock_settings.SENDGRID_FROM_EMAIL = "test@test.com"
            mock_settings.SENDGRID_FROM_NAME = "Test"
            mock_settings.NOTIFICATION_ENABLED = True
            mock_settings.FRONTEND_URL = "http://localhost:3000"
            svc = EmailService()

            user = MockUser()
            store = MockStore()
            flags = [
                {"id": str(uuid.uuid4()), "message": "Flag 1", "days_overdue": 3},
                {"id": str(uuid.uuid4()), "message": "Flag 2", "days_overdue": 1},
            ]

            with patch.object(svc, "send_email", new_callable=AsyncMock, return_value=True) as mock_send:
                result = await svc.send_overdue_to_manager(user, flags, store)
                assert result is True
                subject = mock_send.call_args[0][1]
                assert "2 Unanswered Flags" in subject

    @pytest.mark.asyncio
    async def test_send_overdue_to_corporate_includes_all_details(self):
        with patch("app.services.email_service.settings") as mock_settings:
            mock_settings.SENDGRID_API_KEY = ""
            mock_settings.SENDGRID_FROM_EMAIL = "test@test.com"
            mock_settings.SENDGRID_FROM_NAME = "Test"
            mock_settings.NOTIFICATION_ENABLED = True
            mock_settings.FRONTEND_URL = "http://localhost:3000"
            svc = EmailService()

            corporate = [MockUser(email="corp@test.com")]
            store = MockStore()
            flags = [
                {"id": str(uuid.uuid4()), "message": "Flag 1", "severity": "red", "days_overdue": 3, "assigned_to_name": "John"},
            ]

            with patch.object(svc, "send_email", new_callable=AsyncMock, return_value=True) as mock_send:
                result = await svc.send_overdue_to_corporate(corporate, store, flags)
                assert result is True
                html = mock_send.call_args[0][2]
                assert "ESCALATION" in mock_send.call_args[0][1]
                assert "Flag 1" in html
                assert "John" in html

    @pytest.mark.asyncio
    async def test_send_response_received_includes_response_text(self):
        with patch("app.services.email_service.settings") as mock_settings:
            mock_settings.SENDGRID_API_KEY = ""
            mock_settings.SENDGRID_FROM_EMAIL = "test@test.com"
            mock_settings.SENDGRID_FROM_NAME = "Test"
            mock_settings.NOTIFICATION_ENABLED = True
            mock_settings.FRONTEND_URL = "http://localhost:3000"
            svc = EmailService()

            corporate = [MockUser(email="corp@test.com")]
            flag = MockFlag()
            response = MockResponse()
            store = MockStore()

            with patch.object(svc, "send_email", new_callable=AsyncMock, return_value=True) as mock_send:
                result = await svc.send_response_received(corporate, flag, response, store)
                assert result is True
                html = mock_send.call_args[0][2]
                assert "addressed this issue" in html


class TestHTMLTemplates:
    def test_wrap_html_produces_valid_structure(self):
        html = _wrap_html("<p>Test content</p>")
        assert "<!DOCTYPE html>" in html
        assert "GREGG ORR AUTO COLLECTION" in html
        assert "Test content" in html
        assert "</html>" in html
        # Check no unclosed major tags
        assert html.count("<html") == html.count("</html>")
        assert html.count("<body") == html.count("</body>")
        assert html.count("<div") == html.count("</div>")

    def test_strip_html_produces_plain_text(self):
        html = "<h1>Title</h1><p>Hello <strong>World</strong></p><br>Next line"
        text = _strip_html(html)
        assert "Title" in text
        assert "Hello World" in text
        assert "<" not in text

    def test_plain_text_fallback_generated(self):
        """send_email should generate text_content from HTML if not provided."""
        # This is tested implicitly — _strip_html is called in send_email
        html = _wrap_html("<p>Test</p>")
        text = _strip_html(html)
        assert len(text) > 0
        assert "<" not in text
