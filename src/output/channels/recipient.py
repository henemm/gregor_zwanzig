"""Empfaengervertrag (Issue #1412 S4a): belegte Empfaenger statt Selbstbedienung.

Ein Ausgang sendet nur an einen Empfaenger, dessen Herkunft belegt ist. Der
Beleg ist der Zweck (``RecipientPurpose``) plus die Quelle, aus der die Fabrik
den Chat gelesen hat. ``RecipientPurpose`` ist kanaluebergreifend angelegt
(S4b ergaenzt ``verification`` fuer SMS).

``_current_inbound_sender`` traegt den Absender des laufenden Webhook-Updates.
Der Reader (``services.inbound_telegram_reader``) setzt ihn nach dem Parsen
und setzt ihn im ``finally`` zurueck; der Transport liest ihn. Er liegt HIER
und nicht im Reader, weil der Transport (``output``) sonst den Dienst
(``services``) importieren muesste -- Zyklus Reader -> NotificationService ->
TelegramOutput -> Reader.
"""
from __future__ import annotations

import contextvars
import json
import logging
from dataclasses import dataclass, field
from enum import Enum

from output.channels.base import ChannelBlockedError

logger = logging.getLogger(__name__)

_current_inbound_sender: contextvars.ContextVar = contextvars.ContextVar(
    "_current_inbound_sender", default=None,
)

_FABRIK = object()


class RecipientPurpose(str, Enum):
    """Zweck eines Empfaengers -- geschlossene Aufzaehlung, Default ist Block."""

    user_profile = "user_profile"
    inbound_reply = "inbound_reply"


def normalize_chat_id(chat_id) -> str:
    """int aus dem Update und str aus dem Profil vergleichbar machen (AC-5)."""
    return "" if chat_id is None else str(chat_id).strip()


@dataclass(frozen=True)
class TelegramRecipient:
    """Unveraenderlicher, belegter Telegram-Empfaenger -- nur ueber die
    Fabriken ``for_user`` / ``inbound_reply`` erzeugbar."""

    chat_id: str
    purpose: RecipientPurpose
    user_id: str | None = None
    _key: object = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self._key is not _FABRIK:
            raise TypeError("TelegramRecipient nur ueber for_user()/inbound_reply() erzeugen")

    @classmethod
    def for_user(cls, user_id: str, settings) -> "TelegramRecipient":
        """Profil-Chat des Nutzers, frisch aus ``user.json`` gelesen (nie
        ``settings.telegram_chat_id``). Im Testkontext der Test-Chat (AC-12)."""
        if settings.is_test_mode:
            chat = normalize_chat_id(settings.telegram_test_chat_id)
        else:
            chat = normalize_chat_id(_profile_chat_id(user_id))
        if not chat:
            logger.warning(
                "Telegram: kein Chat im Profil von Nutzer %s -- Versand blockiert "
                "(telegram_no_chat_id)", user_id,
            )
            raise ChannelBlockedError(
                "telegram",
                f"kein Telegram-Chat im Profil von Nutzer {user_id!r}.",
                reason_code="telegram_no_chat_id",
            )
        return cls(chat, RecipientPurpose.user_profile, user_id, _FABRIK)

    @classmethod
    def inbound_reply(cls, chat_id) -> "TelegramRecipient":
        """Antwort an den Absender des laufenden Webhook-Updates."""
        return cls(normalize_chat_id(chat_id), RecipientPurpose.inbound_reply, None, _FABRIK)


def _profile_chat_id(user_id: str):
    """``telegram_chat_id`` aus ``user.json``; None bei fehlendem/kaputtem Profil."""
    from app.loader import get_data_dir

    try:
        profile = json.loads((get_data_dir(user_id) / "user.json").read_text())
    except (OSError, ValueError):
        return None
    return profile.get("telegram_chat_id") if isinstance(profile, dict) else None
