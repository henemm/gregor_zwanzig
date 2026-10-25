"""SMS output channel via seven.io HTTP API."""
from pathlib import Path
from typing import Optional

from app.origin_guard import running_origin
from output.channels.recipient import SmsRecipient
from output.channels.seven_io_base import SevenIoChannelBase


class SMSOutput(SevenIoChannelBase):
    """Sends SMS via seven.io REST API.

    Implements the OutputChannel protocol: send(subject, body).
    subject is ignored — SMS has no subject field.
    Uses a 10s timeout; on failure raises OutputError.

    Issue #1676 S2a: Sicherheitssperren und HTTP-Transport liegen jetzt in
    `SevenIoChannelBase` — dieselbe Basis traegt den vierten Kanal
    (`premium_sms`), damit die beiden Sperren genau einmal existieren
    (ADR-0049). `from` wird nur gesetzt, wenn `sms_from` gefuellt ist.
    """

    CHANNEL_NAME = "sms"
    # Issue #1412 S4b: Empfaenger nur als `SmsRecipient` (bestaetigte
    # Profilnummer bzw. Bestaetigungscode-Ziel), nie `settings.sms_to`. Ein
    # fehlender Empfaenger ist ein Laufzeitzustand (#2144), keine
    # Fehlkonfiguration -- er blockt erst beim Senden.
    RECIPIENT_TYPE = SmsRecipient
    NO_RECIPIENT_REASON = "sms_no_recipient"

    def _origin(self) -> str:
        """Herkunft DIESES Moduls — siehe `SevenIoChannelBase._origin`."""
        return running_origin(Path(__file__))

    def _resolve_sender(self) -> Optional[str]:
        return self._settings.sms_from or None
