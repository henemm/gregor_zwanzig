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
from email.header import decode_header, make_header

from app.config import Settings
from app.loader import load_all_trips
from services.notification_service import NotificationService
from services.trip_command_processor import (
    CommandResult,
    InboundMessage,
    TripCommandProcessor,
)

logger = logging.getLogger(__name__)


def _norm(s: str) -> str:
    """Normalisiert Trip-Namen: Leerzeichen↔Unterstrich, Mehrfach-WS, lowercase."""
    return re.sub(r"\s+", " ", s.replace("_", " ")).strip().lower()


class InboundEmailReader:
    """Polls IMAP inbox and processes trip commands from email replies."""

    DEFAULT_IMAP_PORT = 993

    _SUBJECT_TRIP_RE = re.compile(r"\[(.+?)\]")
    _REPLY_PREFIXES = re.compile(
        r"^(Re|Fwd|AW|WG|Antwort|SV):\s*", re.IGNORECASE,
    )

    def __init__(self) -> None:
        self._notification_service = NotificationService()

    def poll_and_process(self, settings: Settings) -> int:
        """
        Read UNSEEN emails, process commands, send confirmations.
        Returns: number of processed commands.
        """
        imap_user = settings.imap_user or settings.smtp_user
        imap_pass = settings.imap_pass or settings.smtp_pass
        if not imap_user or not imap_pass:
            return 0

        imap = None
        processed = 0
        try:
            imap_host = settings.imap_host or settings.smtp_host
            imap_port = settings.imap_port
            imap = imaplib.IMAP4_SSL(imap_host, imap_port)
            imap.login(imap_user, imap_pass)
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

        # 1. Resolve user-scoped settings for sender, then authorize
        from_addr = self._parse_sender(msg.get("From", ""))
        _user_id, user_settings = self._resolve_settings_for_sender(from_addr, settings)
        if not self._authorize(from_addr, user_settings):
            imap.store(uid, "+FLAGS", "\\Seen")
            return 0

        # 2. Extract trip name from Subject — error reply if missing
        subject = msg.get("Subject", "")
        trip_name = self._extract_trip_name(subject)
        if not trip_name:
            logger.debug(f"Ignoring email without trip brackets: {subject!r}")
            imap.store(uid, "+FLAGS", "\\Seen")
            return 0

        # 3. Find trip — error reply if not found
        trip_id = self._find_trip_id(trip_name, _user_id)
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
            if user_settings.can_send_email():
                self._notification_service.send_command_reply_email(result, user_settings)
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
            user_id=_user_id,
        )
        processor = TripCommandProcessor()
        result = processor.process(inbound)

        # 6. Reply on same channel — ALWAYS send (success and error), AUSSER
        # das Kommando hat bereits das volle Briefing verschickt (Issue #1007:
        # heute/morgen) — dann IST das Briefing die Antwort, keine Doppel-Mail.
        if user_settings.can_send_email() and not result.suppress_email_reply:
            self._notification_service.send_command_reply_email(result, user_settings)

        # 7. Mark as read
        imap.store(uid, "+FLAGS", "\\Seen")
        return 1

    def _strip_reply_prefixes(self, subject: str) -> str:
        """Recursively remove Re:, AW:, Fwd:, WG: etc."""
        while True:
            cleaned = self._REPLY_PREFIXES.sub("", subject).strip()
            if cleaned == subject:
                return cleaned
            subject = cleaned

    def _extract_trip_name(self, subject: str) -> str | None:
        """Extract trip name from '[Trip Name] Morning/Evening Report'.

        RFC-2047-dekodiert den Betreff zuerst (Bug #775: Em-Dash → Q-Encoding,
        Leerzeichen→Underscore, Klammern→=5B/=5D).
        """
        decoded = str(make_header(decode_header(subject)))
        clean = self._strip_reply_prefixes(decoded)
        match = self._SUBJECT_TRIP_RE.search(clean)
        return match.group(1) if match else None

    def _parse_sender(self, from_header: str) -> str:
        """Extract email address from 'Name <addr>' format."""
        _, addr = email.utils.parseaddr(from_header)
        return addr.lower()

    def _authorize(self, sender: str, settings: Settings) -> bool:
        """Single-user: sender must match mail_to or inbound_address (only if distinct from mail_from)."""
        mail_from_lower = (settings.mail_from or "").lower()
        if mail_from_lower and sender == mail_from_lower:
            return False
        if not settings.mail_to:
            return False
        allowed = {settings.mail_to.lower()}
        inbound = settings.get_inbound_address()
        if inbound and inbound.lower() != mail_from_lower:
            allowed.add(inbound.lower())
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

    def _resolve_settings_for_sender(
        self, from_addr: str, base_settings: Settings, data_dir: str = "data"
    ) -> tuple[str, Settings]:
        """Resolve user_id and user-scoped Settings for an incoming sender address.

        Args:
            from_addr: Sender email address (lowercase expected)
            base_settings: Base Settings object to derive user profile from
            data_dir: Root data directory (default: "data")

        Returns:
            (user_id, user_scoped_settings) — user_id is "default" if no match
        """
        from app.loader import lookup_user_by_email
        user_id = lookup_user_by_email(from_addr, data_dir=data_dir) or "default"
        return user_id, base_settings.with_user_profile(user_id)

    def _find_trip_id(self, trip_name: str, user_id: str = "default") -> str | None:
        """Trip-Lookup: primär über GZ#-Shortcode, Fallback toleranter Namensvergleich."""
        trips = load_all_trips(user_id)
        # Shortcode-Routing: "GZ#HERM ..." → erstes Token ist der Code
        first_token = trip_name.split()[0].upper() if trip_name.strip() else ""
        if first_token.startswith("GZ#"):
            for trip in trips:
                if trip.shortcode.upper() == first_token:
                    return trip.id
        # Toleranter Namensvergleich (Leerzeichen ↔ Unterstrich, case-insensitiv)
        query = _norm(trip_name)
        for trip in trips:
            if _norm(trip.name) == query:
                return trip.id
        logger.warning(f"No trip found for name: {trip_name!r} (user={user_id!r})")
        return None
