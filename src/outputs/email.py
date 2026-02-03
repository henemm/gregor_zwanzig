"""
Email output channel.

Sends weather reports via SMTP email (HTML or plain text).
"""
from __future__ import annotations

import logging
import re
import smtplib
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import TYPE_CHECKING

from outputs.base import OutputConfigError, OutputError

if TYPE_CHECKING:
    from app.config import Settings

logger = logging.getLogger(__name__)


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

    def send(
        self,
        subject: str,
        body: str,
        html: bool = True,
        plain_text_body: str | None = None,
    ) -> None:
        """
        Send email via SMTP with automatic retry on network errors.

        Automatically retries up to 3 times with exponential backoff (5s, 15s, 30s)
        on temporary network errors (DNS, connection issues). Permanent errors
        (authentication) fail immediately without retry.

        SPEC: docs/specs/compare_email.md v4.2 - Multipart Email
        SPEC: docs/specs/bugfix/email_retry_mechanism_spec.md v1.0 - Retry Mechanism

        Args:
            subject: Email subject line
            body: Email body (HTML or plain text)
            html: If True, send as HTML email with plain-text fallback
            plain_text_body: Optional explicit plain-text version.
                             If not provided, plain-text is auto-generated from HTML.

        Raises:
            OutputError: If sending fails after all retry attempts
        """
        # Build message once (outside retry loop)
        if html:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self._from
            msg["To"] = self._to

            # Use explicit plain-text if provided, otherwise auto-generate
            if plain_text_body:
                plain_text = plain_text_body
            else:
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

        # Retry logic with exponential backoff
        # max_attempts includes the first try, so 4 attempts = 3 retries
        max_attempts = 4
        backoff_base = 5

        for attempt in range(max_attempts):
            try:
                with smtplib.SMTP(self._host, self._port) as server:
                    server.starttls()
                    server.login(self._user, self._password)
                    server.sendmail(self._from, [self._to], msg.as_string())

                # Success - log if this was after retry
                if attempt > 0:
                    logger.info(f"Email send succeeded after {attempt + 1} attempt(s)")
                return

            except smtplib.SMTPException as e:
                # Permanent error (Auth) - no retry
                raise OutputError("email", f"SMTP error: {e}")

            except OSError as e:
                # Temporary network error
                if attempt < max_attempts - 1:
                    # Retry with exponential backoff: 5s, 15s, 30s
                    # Formula: backoff_base * (1, 3, 6) = (5, 15, 30)
                    wait_multiplier = [1, 3, 6][attempt]
                    wait = backoff_base * wait_multiplier
                    logger.warning(
                        f"Email send failed (attempt {attempt + 1}/{max_attempts}): {e}. "
                        f"Retrying in {wait}s..."
                    )
                    time.sleep(wait)
                else:
                    # Last attempt failed
                    logger.error(f"Email send failed after {max_attempts} attempts: {e}")
                    raise OutputError("email", f"Connection error: {e}")
