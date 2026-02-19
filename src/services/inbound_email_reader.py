"""
Inbound Email Reader — IMAP polling for trip commands.

Polls IMAP inbox for unread emails, extracts trip context from Subject,
delegates to TripCommandProcessor, and sends confirmation reply on
the same channel (email).

SPEC: docs/specs/modules/inbound_command_channels.md v1.1
"""
from __future__ import annotations

import email
import email.utils
import imaplib
import logging
import re
from datetime import datetime, timezone

from app.config import Settings
from app.loader import load_all_trips
from outputs.email import EmailOutput
from services.trip_command_processor import (
    CommandResult,
    InboundMessage,
    TripCommandProcessor,
)

logger = logging.getLogger(__name__)


class InboundEmailReader:
    """Polls IMAP inbox and processes trip commands from email replies."""

    IMAP_HOST = "imap.gmail.com"
    IMAP_PORT = 993

    _SUBJECT_TRIP_RE = re.compile(r"\[(.+?)\]")
    _REPLY_PREFIXES = re.compile(
        r"^(Re|Fwd|AW|WG|Antwort|SV):\s*", re.IGNORECASE,
    )

    def poll_and_process(self, settings: Settings) -> int:
        """
        Read UNSEEN emails, process commands, send confirmations.
        Returns: number of processed commands.
        """
        if not settings.smtp_user or not settings.smtp_pass:
            return 0

        imap = None
        processed = 0
        try:
            imap = imaplib.IMAP4_SSL(self.IMAP_HOST, self.IMAP_PORT)
            imap.login(settings.smtp_user, settings.smtp_pass)
            imap.select("INBOX")

            # Use TO filter if inbound_address is configured (plus-addressing)
            inbound = settings.get_inbound_address()
            if inbound and inbound != settings.smtp_user:
                _, data = imap.search(None, "UNSEEN", "TO", inbound)
            else:
                _, data = imap.search(None, "UNSEEN")
            uids = data[0].split()

            for uid in uids:
                try:
                    processed += self._process_single(imap, uid, settings)
                except Exception as e:
                    logger.error(f"Error processing email uid={uid}: {e}")
        except imaplib.IMAP4.error as e:
            logger.error(f"IMAP error: {e}")
        except OSError as e:
            logger.error(f"Network error: {e}")
        finally:
            if imap:
                try:
                    imap.logout()
                except Exception:
                    pass
        return processed

    def _process_single(
        self,
        imap: imaplib.IMAP4_SSL,
        uid: bytes,
        settings: Settings,
    ) -> int:
        """Process one email. Returns 1 if command processed, else 0."""
        _, msg_data = imap.fetch(uid, "(RFC822)")
        msg = email.message_from_bytes(msg_data[0][1])

        # 1. Authorize sender
        from_addr = self._parse_sender(msg.get("From", ""))
        if not self._authorize(from_addr, settings):
            imap.store(uid, "+FLAGS", "\\Seen")
            return 0

        # 2. Extract trip name from Subject — error reply if missing
        subject = msg.get("Subject", "")
        trip_name = self._extract_trip_name(subject)
        if not trip_name:
            result = CommandResult(
                success=False, command="parse_error",
                confirmation_subject="Befehl nicht erkannt",
                confirmation_body=(
                    "Kein Trip-Name im Betreff gefunden.\n"
                    "Betreff muss [Trip Name] enthalten, z.B.:\n"
                    "  Re: [GR221 Mallorca] Morning Report\n\n"
                    "Befehlsformat im Text:\n"
                    "  ### ruhetag\n"
                    "  ### startdatum 2026-03-01"
                ),
            )
            if settings.can_send_email():
                self._send_email_reply(result, settings)
            imap.store(uid, "+FLAGS", "\\Seen")
            return 0

        # 3. Find trip — error reply if not found
        trip_id = self._find_trip_id(trip_name)
        if not trip_id:
            result = CommandResult(
                success=False, command="trip_not_found",
                confirmation_subject=f"[{trip_name}] Trip nicht gefunden",
                confirmation_body=(
                    f"Kein Trip mit Name '{trip_name}' gefunden.\n"
                    "Bitte pruefen ob der Trip-Name korrekt ist."
                ),
                trip_name=trip_name,
            )
            if settings.can_send_email():
                self._send_email_reply(result, settings)
            imap.store(uid, "+FLAGS", "\\Seen")
            return 0

        # 4. Extract body
        body = self._extract_plain_body(msg)

        # 5. Delegate to processor
        inbound = InboundMessage(
            trip_name=trip_name,
            body=body,
            sender=from_addr,
            channel="email",
            received_at=datetime.now(tz=timezone.utc),
        )
        processor = TripCommandProcessor()
        result = processor.process(inbound)

        # 6. Reply on same channel — ALWAYS send (success and error)
        if settings.can_send_email():
            self._send_email_reply(result, settings)

        # 7. Mark as read
        imap.store(uid, "+FLAGS", "\\Seen")
        return 1

    def _send_email_reply(self, result: CommandResult, settings: Settings) -> None:
        """Send confirmation email reply."""
        try:
            email_output = EmailOutput(settings)
            email_output.send(
                subject=result.confirmation_subject,
                body=result.confirmation_body,
                html=False,
            )
            logger.info(f"Confirmation sent: {result.confirmation_subject}")
        except Exception as e:
            logger.error(f"Failed to send confirmation: {e}")

    def _strip_reply_prefixes(self, subject: str) -> str:
        """Recursively remove Re:, AW:, Fwd:, WG: etc."""
        while True:
            cleaned = self._REPLY_PREFIXES.sub("", subject).strip()
            if cleaned == subject:
                return cleaned
            subject = cleaned

    def _extract_trip_name(self, subject: str) -> str | None:
        """Extract trip name from '[Trip Name] Morning/Evening Report'."""
        clean = self._strip_reply_prefixes(subject)
        match = self._SUBJECT_TRIP_RE.search(clean)
        return match.group(1) if match else None

    def _parse_sender(self, from_header: str) -> str:
        """Extract email address from 'Name <addr>' format."""
        _, addr = email.utils.parseaddr(from_header)
        return addr.lower()

    def _authorize(self, sender: str, settings: Settings) -> bool:
        """Single-user: sender must match mail_to or smtp_user."""
        allowed = {settings.mail_to.lower()}
        if settings.smtp_user:
            allowed.add(settings.smtp_user.lower())
        authorized = sender in allowed
        if not authorized:
            logger.debug(f"Ignoring email from: {sender!r}")
        return authorized

    def _extract_plain_body(self, msg: email.message.Message) -> str:
        """Extract plain-text body. Multipart: first text/plain part."""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    payload = part.get_payload(decode=True)
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                return payload.decode(charset, errors="replace")
        return ""

    def _find_trip_id(self, trip_name: str) -> str | None:
        """Case-insensitive name to trip-ID lookup."""
        for trip in load_all_trips():
            if trip.name.lower() == trip_name.lower():
                return trip.id
        logger.warning(f"No trip found for name: {trip_name!r}")
        return None
