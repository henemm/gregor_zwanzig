"""
Email output channel.

Sends weather reports via SMTP email.
"""
from __future__ import annotations

import smtplib
from email.mime.text import MIMEText
from typing import TYPE_CHECKING

from outputs.base import OutputConfigError, OutputError

if TYPE_CHECKING:
    from app.config import Settings


class EmailOutput:
    """
    Email output channel using SMTP.

    Sends plain-text emails with configurable SMTP settings.
    Requires complete SMTP configuration in Settings.

    Example:
        >>> output = EmailOutput(settings)
        >>> output.send("Evening Report", "Temperature: 5C")
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

    def send(self, subject: str, body: str) -> None:
        """
        Send email via SMTP.

        Args:
            subject: Email subject line
            body: Email body (plain text)

        Raises:
            OutputError: If sending fails
        """
        msg = MIMEText(body)
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
