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

from output.channels.base import OutputConfigError, OutputError

if TYPE_CHECKING:
    from app.config import Settings

logger = logging.getLogger(__name__)


def build_mime_message(
    subject: str,
    body: str,
    from_addr: str,
    to_header: str,
    reply_to: str | None,
    html: bool,
    plain_text_body: str | None,
    mail_type: str | None = None,
    mail_format: str | None = None,
):
    """Issue #722: Build a MIME message. Pure function, no SMTP side-effects.

    html=True  → MIMEMultipart("alternative") with plain + html parts (full path).
    html=False → single MIMEText("plain"), us-ascii/7bit for ASCII bodies.

    Issue #733: Optionale Marker-Header X-GZ-Mail-Type / X-GZ-Format für den
    kanonischen Briefing-Mail-Validator. Backward-Compat: ohne die Params bleibt
    die Message header-frei.
    """
    if html:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = from_addr
        msg["To"] = to_header
        if reply_to:
            msg["Reply-To"] = reply_to
        if mail_type is not None:
            msg["X-GZ-Mail-Type"] = mail_type
        if mail_format is not None:
            msg["X-GZ-Format"] = mail_format
        if plain_text_body:
            plain_text = plain_text_body
        else:
            plain_text = re.sub(r'<style[^>]*>.*?</style>', '', body, flags=re.DOTALL | re.IGNORECASE)
            plain_text = re.sub(r'<head[^>]*>.*?</head>', '', plain_text, flags=re.DOTALL | re.IGNORECASE)
            plain_text = re.sub(r'<[^>]+>', '', plain_text)
            plain_text = plain_text.replace('&nbsp;', ' ').replace('&deg;', '°')
            plain_text = re.sub(r'\n\s*\n\s*\n', '\n\n', plain_text)
            plain_text = plain_text.strip()
        msg.attach(MIMEText(plain_text, "plain", "utf-8"))
        msg.attach(MIMEText(body, "html", "utf-8"))
    else:
        charset = "us-ascii" if body.isascii() else "utf-8"
        msg = MIMEText(body, "plain", charset)
        msg["Subject"] = subject
        msg["From"] = from_addr
        msg["To"] = to_header
        if reply_to:
            msg["Reply-To"] = reply_to
        if mail_type is not None:
            msg["X-GZ-Mail-Type"] = mail_type
        if mail_format is not None:
            msg["X-GZ-Format"] = mail_format
    return msg


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

        # Hard-Guard: Staging darf NIEMALS über Resend senden — unabhängig von is_test_mode.
        # Issue #924: verhindert neue Code-Pfade, die for_testing() vergessen.
        if (getattr(settings, "env", "") or "").lower() == "staging" and "resend" in (settings.smtp_host or "").lower():
            raise OutputConfigError(
                "email",
                "Staging darf NICHT über Resend senden! "
                "GZ_SMTP_HOST muss auf mail.henemm.com zeigen. "
                "Prüfe /home/hem/gregor_zwanzig_staging/.env (Issue #924).",
            )
        if getattr(settings, "is_test_mode", False) and "resend" in (settings.smtp_host or "").lower():
            raise OutputConfigError(
                "email",
                "Test-Versand über Resend ist gesperrt. "
                "Test-Mails MÜSSEN über Stalwart gehen — siehe Settings.for_testing(). "
                "Konfiguriere GZ_TEST_SMTP_USER/PASS oder verwende einen Test-User "
                "(User-ID enthält 'test' oder 'tdd').",
            )

        self._host = settings.smtp_host
        self._port = settings.smtp_port
        self._user = settings.smtp_user
        self._password = settings.smtp_pass
        self._to = settings.mail_to
        self._from = settings.mail_from or settings.smtp_user
        self._reply_to = settings.get_inbound_address()
        self._fallback_host = getattr(settings, 'imap_host', None)
        self._fallback_user = getattr(settings, 'imap_user', None)
        self._fallback_pass = getattr(settings, 'imap_pass', None)

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
        to: list[str] | None = None,
        mail_type: str | None = None,
        mail_format: str | None = None,
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
        # Use inbound address as From if set (Gmail supports plus-addresses)
        from_addr = self._reply_to or self._from

        # Issue #252: per-call recipient override.
        # `to` may be a list of addresses; falsy/empty falls back to settings.mail_to.
        recipients: list[str] = list(to) if to else [self._to]
        to_header = ", ".join(recipients)

        msg = build_mime_message(
            subject=subject,
            body=body,
            from_addr=from_addr,
            to_header=to_header,
            reply_to=self._reply_to,
            html=html,
            plain_text_body=plain_text_body,
            mail_type=mail_type,
            mail_format=mail_format,
        )

        # Retry logic with exponential backoff
        # max_attempts includes the first try, so 4 attempts = 3 retries
        max_attempts = 4
        backoff_base = 5

        for attempt in range(max_attempts):
            try:
                with smtplib.SMTP(self._host, self._port) as server:
                    server.starttls()
                    server.login(self._user, self._password)
                    if len(recipients) == 1:
                        server.sendmail(from_addr, recipients, msg.as_string())
                    else:
                        for recipient in recipients:
                            try:
                                server.sendmail(from_addr, [recipient], msg.as_string())
                            except smtplib.SMTPException as exc:
                                logger.error(
                                    "SMTP-Fehler für Empfänger %s: %s", recipient, exc
                                )

                # Success - log if this was after retry
                if attempt > 0:
                    logger.info(f"Email send succeeded after {attempt + 1} attempt(s)")
                return

            except smtplib.SMTPAuthenticationError as e:
                # Auth failure (535 etc.) is permanent — never retry. Must be
                # caught BEFORE SMTPResponseException (it's a subclass with a
                # 5xx-ish code we still don't want to treat as transient).
                raise OutputError("email", f"SMTP authentication error: {e}")

            except smtplib.SMTPResponseException as e:
                # Issue #766: distinguish temporary 4xx (rate-limit 452,
                # service-busy 421) from permanent 5xx errors.
                if e.smtp_code >= 500:
                    raise OutputError(
                        "email",
                        f"SMTP permanent error {e.smtp_code}: {e.smtp_error}",
                    )
                # 4xx = temporary — retry with the same backoff schedule as OSError.
                if attempt < max_attempts - 1:
                    wait_multiplier = [1, 3, 6][attempt]
                    wait = backoff_base * wait_multiplier
                    logger.warning(
                        f"SMTP temporary error {e.smtp_code} "
                        f"(attempt {attempt + 1}/{max_attempts}): "
                        f"{e.smtp_error}. Retrying in {wait}s..."
                    )
                    time.sleep(wait)
                else:
                    if self._fallback_host:
                        try:
                            with smtplib.SMTP(self._fallback_host, 587) as fb_server:
                                fb_server.starttls()
                                fb_server.login(self._fallback_user, self._fallback_pass)
                                if len(recipients) == 1:
                                    fb_server.sendmail(from_addr, recipients, msg.as_string())
                                else:
                                    for recipient in recipients:
                                        fb_server.sendmail(from_addr, [recipient], msg.as_string())
                            logger.info("[SMTP-FALLBACK] sent via fallback SMTP")
                            return
                        except Exception as fb_err:
                            raise OutputError(
                                "email",
                                f"SMTP temporary error {e.smtp_code} after {max_attempts} attempts (fallback also failed: {fb_err})",
                            )
                    raise OutputError(
                        "email",
                        f"SMTP temporary error {e.smtp_code} after "
                        f"{max_attempts} attempts: {e.smtp_error}",
                    )

            except smtplib.SMTPException as e:
                # Other SMTP errors (e.g. SMTPRecipientsRefused) - no retry
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
                    # Last attempt failed — try fallback SMTP if configured
                    logger.error(f"Email send failed after {max_attempts} attempts: {e}")
                    if self._fallback_host:
                        try:
                            with smtplib.SMTP(self._fallback_host, 587) as fb_server:
                                fb_server.starttls()
                                fb_server.login(self._fallback_user, self._fallback_pass)
                                if len(recipients) == 1:
                                    fb_server.sendmail(from_addr, recipients, msg.as_string())
                                else:
                                    for recipient in recipients:
                                        fb_server.sendmail(from_addr, [recipient], msg.as_string())
                            logger.info("[SMTP-FALLBACK] sent via fallback SMTP")
                            return
                        except Exception as fb_err:
                            raise OutputError("email", f"Connection error: {e} (fallback also failed: {fb_err})")
                    raise OutputError("email", f"Connection error: {e}")

# test