"""
Email output channel.

Sends weather reports via SMTP email (HTML or plain text).
"""
from __future__ import annotations

import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import TYPE_CHECKING

from outputs.base import OutputConfigError, OutputError

if TYPE_CHECKING:
    from app.config import Settings


class EmailOutput:
    """
    Email output channel using SMTP.

    Sends HTML emails with plain-text fallback.
    Requires complete SMTP configuration in Settings.

    Example:
        >>> output = EmailOutput(settings)
        >>> output.send("Evening Report", "<h1>Weather</h1><p>5C</p>")
    """

    def __init__(self, settings: "Settings") -> None:
        """
        Initialize email output with settings.

        Args:
            settings: Application settings with SMTP configuration

        Raises:
            OutputConfigError: If SMTP configuration is incomplete
        """
        if not settings.can_send_email():
            raise OutputConfigError(
                "email",
                "Incomplete SMTP configuration. "
                "Required: smtp_host, smtp_user, smtp_pass, mail_to",
            )

        self._host = settings.smtp_host
        self._port = settings.smtp_port
        self._user = settings.smtp_user
        self._password = settings.smtp_pass
        self._to = settings.mail_to
        self._from = settings.mail_from or settings.smtp_user

    @property
    def name(self) -> str:
        """Channel identifier."""
        return "email"

    def send(self, subject: str, body: str, html: bool = True) -> None:
        """
        Send email via SMTP.

        Args:
            subject: Email subject line
            body: Email body (HTML or plain text)
            html: If True, send as HTML email with plain-text fallback

        Raises:
            OutputError: If sending fails
        """
        if html:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self._from
            msg["To"] = self._to

            # Plain text fallback (strip HTML properly)
            # 1. Remove <style>...</style> blocks completely
            plain_text = re.sub(r'<style[^>]*>.*?</style>', '', body, flags=re.DOTALL | re.IGNORECASE)
            # 2. Remove <head>...</head> blocks completely
            plain_text = re.sub(r'<head[^>]*>.*?</head>', '', plain_text, flags=re.DOTALL | re.IGNORECASE)
            # 3. Remove remaining HTML tags
            plain_text = re.sub(r'<[^>]+>', '', plain_text)
            # 4. Replace HTML entities
            plain_text = plain_text.replace('&nbsp;', ' ').replace('&deg;', '°')
            # 5. Clean up excessive whitespace
            plain_text = re.sub(r'\n\s*\n\s*\n', '\n\n', plain_text)
            plain_text = plain_text.strip()

            part1 = MIMEText(plain_text, "plain", "utf-8")
            part2 = MIMEText(body, "html", "utf-8")

            msg.attach(part1)
            msg.attach(part2)
        else:
            msg = MIMEText(body, "plain", "utf-8")
            msg["Subject"] = subject
            msg["From"] = self._from
            msg["To"] = self._to

        try:
            with smtplib.SMTP(self._host, self._port) as server:
                server.starttls()
                server.login(self._user, self._password)
                server.sendmail(self._from, [self._to], msg.as_string())
        except smtplib.SMTPException as e:
            raise OutputError("email", f"SMTP error: {e}")
        except OSError as e:
            raise OutputError("email", f"Connection error: {e}")
