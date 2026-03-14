"""SendGrid email service for all outbound notifications."""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# HTML template fragments (inline CSS for email clients)
# --------------------------------------------------------------------------- #

_BASE_STYLE = """
<style>
body { margin: 0; padding: 0; font-family: Arial, Helvetica, sans-serif; background-color: #f4f4f4; }
.container { max-width: 600px; margin: 0 auto; background: #ffffff; }
.header { background-color: #003366; padding: 20px 30px; }
.header h1 { color: #ffffff; font-size: 18px; margin: 0; font-weight: 600; letter-spacing: 0.5px; }
.content { padding: 30px; color: #333333; line-height: 1.6; font-size: 14px; }
.content h2 { color: #003366; font-size: 16px; margin-top: 0; }
.footer { background-color: #f0f0f0; padding: 15px 30px; font-size: 11px; color: #888888; text-align: center; }
.btn { display: inline-block; background-color: #003366; color: #ffffff; padding: 10px 24px; text-decoration: none; border-radius: 4px; font-size: 14px; font-weight: 600; }
.badge-red { display: inline-block; background: #dc2626; color: #fff; padding: 2px 8px; border-radius: 3px; font-size: 12px; font-weight: 600; }
.badge-yellow { display: inline-block; background: #ca8a04; color: #fff; padding: 2px 8px; border-radius: 3px; font-size: 12px; font-weight: 600; }
.detail-table { width: 100%; border-collapse: collapse; margin: 15px 0; }
.detail-table td { padding: 6px 10px; border-bottom: 1px solid #eee; font-size: 13px; }
.detail-table td:first-child { font-weight: 600; color: #555; width: 35%; }
</style>
"""


def _wrap_html(body: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">{_BASE_STYLE}</head>
<body>
<div class="container">
<div class="header"><h1>GREGG ORR AUTO COLLECTION</h1></div>
<div class="content">{body}</div>
<div class="footer">GOAC Asset Meeting Manager &mdash; Confidential<br>This is an automated message.</div>
</div>
</body>
</html>"""


def _strip_html(html: str) -> str:
    """Crude HTML-to-text for plain text fallback."""
    import re
    text = re.sub(r"<br\s*/?>", "\n", html)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _severity_badge(severity: str) -> str:
    cls = "badge-red" if severity == "red" else "badge-yellow"
    return f'<span class="{cls}">{severity.upper()}</span>'


class EmailService:
    """SendGrid email service for all outbound notifications."""

    def __init__(self):
        self.api_key = settings.SENDGRID_API_KEY
        self.from_email = settings.SENDGRID_FROM_EMAIL
        self.from_name = settings.SENDGRID_FROM_NAME
        self.enabled = bool(self.api_key) and settings.NOTIFICATION_ENABLED
        self.frontend_url = settings.FRONTEND_URL

    # ------------------------------------------------------------------ #
    # Core send
    # ------------------------------------------------------------------ #
    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
    ) -> bool:
        """Send a single email via SendGrid v3 API.

        Returns True if sent (or logged in dev mode), False on error.
        Never raises — logs errors instead.
        """
        if not text_content:
            text_content = _strip_html(html_content)

        if not self.enabled:
            logger.info(
                "Email disabled — would send to=%s subject=%s",
                to_email,
                subject,
            )
            return True

        payload = {
            "personalizations": [{"to": [{"email": to_email}]}],
            "from": {"email": self.from_email, "name": self.from_name},
            "subject": subject,
            "content": [
                {"type": "text/plain", "value": text_content},
                {"type": "text/html", "value": html_content},
            ],
            "headers": {
                "List-Unsubscribe": f"<mailto:unsubscribe@{self.from_email.split('@')[-1]}>"
            },
        }

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://api.sendgrid.com/v3/mail/send",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    timeout=10.0,
                )
            if resp.status_code in (200, 201, 202):
                logger.info("Email sent to=%s subject=%s", to_email, subject)
                return True
            else:
                logger.error(
                    "SendGrid error %s: %s", resp.status_code, resp.text
                )
                return False
        except Exception:
            logger.exception("Failed to send email to %s", to_email)
            return False

    # ------------------------------------------------------------------ #
    # Core send with attachment
    # ------------------------------------------------------------------ #
    async def send_email_with_attachment(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        attachment_bytes: bytes,
        attachment_filename: str,
        attachment_type: str = "application/pdf",
        text_content: Optional[str] = None,
    ) -> bool:
        """Send email with a file attachment via SendGrid v3 API.

        Returns True if sent, False on error. Never raises.
        """
        import base64

        if not text_content:
            text_content = _strip_html(html_content)

        if not self.enabled:
            logger.info(
                "Email disabled — would send to=%s subject=%s (with attachment %s, %d bytes)",
                to_email, subject, attachment_filename, len(attachment_bytes),
            )
            return True

        encoded = base64.b64encode(attachment_bytes).decode("ascii")
        payload = {
            "personalizations": [{"to": [{"email": to_email}]}],
            "from": {"email": self.from_email, "name": self.from_name},
            "subject": subject,
            "content": [
                {"type": "text/plain", "value": text_content},
                {"type": "text/html", "value": html_content},
            ],
            "attachments": [
                {
                    "content": encoded,
                    "filename": attachment_filename,
                    "type": attachment_type,
                    "disposition": "attachment",
                }
            ],
            "headers": {
                "List-Unsubscribe": f"<mailto:unsubscribe@{self.from_email.split('@')[-1]}>"
            },
        }

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://api.sendgrid.com/v3/mail/send",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    timeout=30.0,
                )
            if resp.status_code in (200, 201, 202):
                logger.info("Email with attachment sent to=%s subject=%s", to_email, subject)
                return True
            else:
                logger.error("SendGrid error %s: %s", resp.status_code, resp.text)
                return False
        except Exception:
            logger.exception("Failed to send email with attachment to %s", to_email)
            return False

    # ------------------------------------------------------------------ #
    # Flag assigned
    # ------------------------------------------------------------------ #
    async def send_flag_assigned(self, user, flag, meeting, store) -> bool:
        """Notify a manager that a flag has been assigned to them."""
        subject = f"[ACTION REQUIRED] Flag Assigned \u2014 {store.name} Meeting {meeting.meeting_date}"
        deadline_str = str(meeting.meeting_date)
        body = f"""
<h2>New Flag Assigned</h2>
<p>Hi {user.name},</p>
<p>A flag has been assigned to you for the upcoming asset meeting.</p>
<table class="detail-table">
<tr><td>Store</td><td>{store.name}</td></tr>
<tr><td>Meeting Date</td><td>{meeting.meeting_date}</td></tr>
<tr><td>Severity</td><td>{_severity_badge(flag.severity.value)}</td></tr>
<tr><td>Category</td><td>{flag.category.value.upper()}</td></tr>
<tr><td>Issue</td><td>{flag.message}</td></tr>
<tr><td>Deadline</td><td><strong>{deadline_str} CT</strong></td></tr>
</table>
<p><a class="btn" href="{self.frontend_url}/flags/{flag.id}">Respond to This Flag</a></p>
"""
        return await self.send_email(user.email, subject, _wrap_html(body))

    # ------------------------------------------------------------------ #
    # Reminder approaching
    # ------------------------------------------------------------------ #
    async def send_reminder_approaching(
        self, user, flag, meeting, store, hours_remaining: int
    ) -> bool:
        """Remind a manager their deadline is approaching."""
        subject = f"[REMINDER] Response Due in {hours_remaining} Hours \u2014 {store.name}"
        body = f"""
<h2>Deadline Approaching</h2>
<p>Hi {user.name},</p>
<p>You have <strong>{hours_remaining} hours</strong> remaining to respond to the following flag:</p>
<table class="detail-table">
<tr><td>Store</td><td>{store.name}</td></tr>
<tr><td>Severity</td><td>{_severity_badge(flag.severity.value)}</td></tr>
<tr><td>Issue</td><td>{flag.message}</td></tr>
</table>
<p><a class="btn" href="{self.frontend_url}/flags/{flag.id}">Respond Now</a></p>
"""
        return await self.send_email(user.email, subject, _wrap_html(body))

    # ------------------------------------------------------------------ #
    # Overdue — to manager
    # ------------------------------------------------------------------ #
    async def send_overdue_to_manager(self, user, flags: list, store) -> bool:
        """Notify a manager they have overdue flags."""
        count = len(flags)
        subject = f"[OVERDUE] {count} Unanswered Flag{'s' if count != 1 else ''} \u2014 {store.name}"

        rows = ""
        for f in flags:
            days = f.get("days_overdue", 0) if isinstance(f, dict) else 0
            msg = f.get("message", "") if isinstance(f, dict) else getattr(f, "message", "")
            fid = f.get("id", "") if isinstance(f, dict) else str(getattr(f, "id", ""))
            rows += f'<tr><td>{msg[:80]}</td><td>{days} day{"s" if days != 1 else ""}</td><td><a href="{self.frontend_url}/flags/{fid}">Respond</a></td></tr>'

        body = f"""
<h2>Overdue Flags</h2>
<p>Hi {user.name},</p>
<p>You have <strong>{count}</strong> overdue flag{"s" if count != 1 else ""} at <strong>{store.name}</strong> that require{"" if count == 1 else ""} a response.</p>
<table style="width:100%;border-collapse:collapse;margin:15px 0;">
<tr style="background:#003366;color:#fff;"><th style="padding:8px;text-align:left;">Issue</th><th style="padding:8px;">Overdue</th><th style="padding:8px;">Action</th></tr>
{rows}
</table>
<p style="color:#dc2626;font-weight:600;">Corporate has been notified of overdue items.</p>
"""
        return await self.send_email(user.email, subject, _wrap_html(body))

    # ------------------------------------------------------------------ #
    # Overdue — to corporate
    # ------------------------------------------------------------------ #
    async def send_overdue_to_corporate(
        self, corporate_users: list, store, overdue_flags: list
    ) -> bool:
        """Notify corporate that a store has overdue flags."""
        count = len(overdue_flags)
        subject = f"[ESCALATION] {count} Overdue Flag{'s' if count != 1 else ''} at {store.name}"

        red_count = sum(1 for f in overdue_flags if (f.get("severity") if isinstance(f, dict) else getattr(f, "severity", "")) in ("red", "RED"))
        yellow_count = count - red_count

        rows = ""
        for f in overdue_flags:
            if isinstance(f, dict):
                msg = f.get("message", "")[:80]
                sev = f.get("severity", "")
                days = f.get("days_overdue", 0)
                assigned = f.get("assigned_to_name", "Unknown")
            else:
                msg = getattr(f, "message", "")[:80]
                sev = getattr(f, "severity", "")
                days = getattr(f, "days_overdue", 0)
                assigned = getattr(f, "assigned_to_name", "Unknown")
            rows += f'<tr><td style="padding:6px 10px;border-bottom:1px solid #eee;">{msg}</td><td style="padding:6px 10px;border-bottom:1px solid #eee;">{_severity_badge(sev)}</td><td style="padding:6px 10px;border-bottom:1px solid #eee;">{days}d</td><td style="padding:6px 10px;border-bottom:1px solid #eee;">{assigned}</td></tr>'

        body = f"""
<h2>Escalation: Overdue Flags at {store.name}</h2>
<p>The following flags are past their deadline:</p>
<p><strong>{red_count}</strong> red, <strong>{yellow_count}</strong> yellow &mdash; <strong>{count} total</strong></p>
{f'<p>GM: {store.gm_name or "N/A"} ({store.gm_email or "N/A"})</p>' if store.gm_email else ''}
<table style="width:100%;border-collapse:collapse;margin:15px 0;">
<tr style="background:#003366;color:#fff;"><th style="padding:8px;text-align:left;">Issue</th><th style="padding:8px;">Severity</th><th style="padding:8px;">Overdue</th><th style="padding:8px;">Assigned To</th></tr>
{rows}
</table>
<p><a class="btn" href="{self.frontend_url}/stores/{store.id}">View Store Dashboard</a></p>
"""
        html = _wrap_html(body)
        success = True
        for u in corporate_users:
            if not await self.send_email(u.email, subject, html):
                success = False
        return success

    # ------------------------------------------------------------------ #
    # Response received
    # ------------------------------------------------------------------ #
    async def send_response_received(
        self, corporate_users: list, flag, response, store
    ) -> bool:
        """Notify corporate that a flag response was submitted."""
        subject = f"[RESPONSE] Flag Addressed \u2014 {store.name}"
        responder_name = getattr(response, "user", None)
        if responder_name and hasattr(responder_name, "name"):
            responder_name = responder_name.name
        else:
            responder_name = "A manager"

        body = f"""
<h2>Flag Response Received</h2>
<table class="detail-table">
<tr><td>Store</td><td>{store.name}</td></tr>
<tr><td>Severity</td><td>{_severity_badge(flag.severity.value)}</td></tr>
<tr><td>Category</td><td>{flag.category.value.upper()}</td></tr>
<tr><td>Issue</td><td>{flag.message}</td></tr>
<tr><td>Responder</td><td>{responder_name}</td></tr>
</table>
<h3>Response</h3>
<p style="background:#f8f8f8;padding:12px;border-left:3px solid #003366;">{response.response_text}</p>
<p><a class="btn" href="{self.frontend_url}/flags/{flag.id}">Review Response</a></p>
"""
        html = _wrap_html(body)
        success = True
        for u in corporate_users:
            if not await self.send_email(u.email, subject, html):
                success = False
        return success

    # ------------------------------------------------------------------ #
    # Meeting packet ready
    # ------------------------------------------------------------------ #
    async def send_meeting_packet_ready(
        self, users: list, meeting, store, red_count: int = 0, yellow_count: int = 0
    ) -> bool:
        """Notify store users that a meeting packet has been generated."""
        subject = f"Meeting Packet Ready \u2014 {store.name} {meeting.meeting_date}"
        body = f"""
<h2>Meeting Packet Generated</h2>
<p>The asset meeting packet for <strong>{store.name}</strong> ({meeting.meeting_date}) is now available.</p>
<table class="detail-table">
<tr><td>Store</td><td>{store.name}</td></tr>
<tr><td>Meeting Date</td><td>{meeting.meeting_date}</td></tr>
<tr><td>Red Flags</td><td><span class="badge-red">{red_count}</span></td></tr>
<tr><td>Yellow Flags</td><td><span class="badge-yellow">{yellow_count}</span></td></tr>
</table>
<p><a class="btn" href="{self.frontend_url}/stores/{store.store_id if hasattr(store, 'store_id') else store.id}/meetings/{meeting.id}">View Meeting Details</a></p>
"""
        html = _wrap_html(body)
        success = True
        for u in users:
            if not await self.send_email(u.email, subject, html):
                success = False
        return success

    # ------------------------------------------------------------------ #
    # Daily digest
    # ------------------------------------------------------------------ #
    async def send_daily_digest(
        self, user, date_str: str, store_summaries: list
    ) -> bool:
        """Send daily summary to a corporate user."""
        subject = f"[DAILY] GOAC Flag Status \u2014 {date_str}"

        rows = ""
        for s in store_summaries:
            rows += (
                f'<tr><td style="padding:6px 10px;border-bottom:1px solid #eee;">{s["store_name"]}</td>'
                f'<td style="padding:6px 10px;border-bottom:1px solid #eee;">{s["open_flags"]}</td>'
                f'<td style="padding:6px 10px;border-bottom:1px solid #eee;">{s["responded_today"]}</td>'
                f'<td style="padding:6px 10px;border-bottom:1px solid #eee;">{s["newly_overdue"]}</td></tr>'
            )

        body = f"""
<h2>Daily Flag Status &mdash; {date_str}</h2>
<table style="width:100%;border-collapse:collapse;margin:15px 0;">
<tr style="background:#003366;color:#fff;"><th style="padding:8px;text-align:left;">Store</th><th style="padding:8px;">Open</th><th style="padding:8px;">Responded Today</th><th style="padding:8px;">Newly Overdue</th></tr>
{rows}
</table>
<p><a class="btn" href="{self.frontend_url}/dashboard">View Dashboard</a></p>
"""
        return await self.send_email(user.email, subject, _wrap_html(body))
