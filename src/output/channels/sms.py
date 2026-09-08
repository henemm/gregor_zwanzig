"""SMS output channel via seven.io HTTP API."""
from pathlib import Path
from typing import Optional

from app.origin_guard import running_origin
from output.channels.base import ChannelBlockedError
from output.channels.seven_io_base import SevenIoChannelBase


class SMSOutput(SevenIoChannelBase):
    """Sends SMS via seven.io REST API.

    Implements the OutputChannel protocol: send(subject, body).
    subject is ignored — SMS has no subject field.
    Uses a 10s timeout; on failure raises OutputError.

    Issue #1676 S2a: Sicherheitssperren und HTTP-Transport liegen jetzt in
    `SevenIoChannelBase` — dieselbe Basis traegt den vierten Kanal
    (`premium_sms`), damit die beiden Sperren genau einmal existieren
    (ADR-0049). Das Verhalten dieses Kanals ist dadurch unveraendert: Ziel
    bleibt `sms_to`, `from` wird weiterhin nur gesetzt, wenn `sms_from`
    gefuellt ist.
    """

    CHANNEL_NAME = "sms"

    # Issue #2144: kein eigener _validate_config()-Override mehr -- der
    # Empfaenger ist ein legitimer Laufzeitzustand (Nutzer ohne eigenes
    # sms_to), keine Fehlkonfiguration, und wird erst in
    # `_resolve_recipient()` geprueft (Vorbild premium_sms.py). Die Basis
    # (`SevenIoChannelBase._validate_config`) prueft weiterhin Gateway und
    # API-Key -- unterscheidbar von fehlendem Empfaenger.

    def _origin(self) -> str:
        """Herkunft DIESES Moduls — siehe `SevenIoChannelBase._origin`."""
        return running_origin(Path(__file__))

    def _resolve_sender(self) -> Optional[str]:
        return self._settings.sms_from or None

    def _resolve_recipient(self) -> str:
        sms_to = self._settings.sms_to
        if not sms_to:
            raise ChannelBlockedError(
                self.name,
                "kein Empfaenger bekannt -- settings.sms_to ist nicht "
                "gesetzt.",
                reason_code="sms_no_recipient",
            )
        return sms_to
