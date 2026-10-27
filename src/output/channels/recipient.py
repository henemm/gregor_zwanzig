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
import re
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
    verification = "verification"  # nur SMS: Bestaetigungscode (S4b, #2406)


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


def _load_profile(user_id: str) -> dict:
    """``user.json`` frisch gelesen; ``{}`` bei fehlendem/kaputtem Profil oder
    ungueltiger ``user_id`` (``get_data_dir`` wirft dann ``ValueError``)."""
    from app.loader import get_data_dir

    try:
        profile = json.loads((get_data_dir(user_id) / "user.json").read_text())
    except (OSError, ValueError):
        return {}
    return profile if isinstance(profile, dict) else {}


def _profile_chat_id(user_id: str):
    """``telegram_chat_id`` aus ``user.json``; None bei fehlendem/kaputtem Profil."""
    return _load_profile(user_id).get("telegram_chat_id")


def _profile_text(profile: dict, key: str) -> str:
    value = profile.get(key)
    return value.strip() if isinstance(value, str) else ""


# Formregeln (S4b, Kernregel 7) -- bedingungslos, auch im Testmodus.
_SMS_TOLERANT_RE = re.compile(r"[0-9+ ()\-]+")
_E164_RE = re.compile(r"\+[1-9][0-9]{7,14}")
_PREMIUM_RE = re.compile(r"\+?[1-9][0-9]{7,14}")


@dataclass(frozen=True)
class SmsRecipient:
    """Belegte SMS-Nummer (Issue #1412 S4b) -- nur ueber ``for_user`` /
    ``verification`` erzeugbar. Die Nummer geht in der gespeicherten Form raus."""

    number: str
    purpose: RecipientPurpose
    user_id: str
    _key: object = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self._key is not _FABRIK:
            raise TypeError("SmsRecipient nur ueber for_user()/verification() erzeugen")

    def well_formed(self) -> bool:
        if self.purpose == RecipientPurpose.verification:
            return bool(_E164_RE.fullmatch(self.number))
        digits = sum(c.isdigit() for c in self.number)
        return bool(_SMS_TOLERANT_RE.fullmatch(self.number)) and 7 <= digits <= 15

    @classmethod
    def for_user(cls, user_id: str, settings) -> "SmsRecipient":
        """Bestaetigte Nummer, frisch aus ``user.json`` (nie ``settings.sms_to``,
        nie ``GZ_SMS_TO``); bestaetigt heisst ``sms_verified_number == sms_to``."""
        profile = _load_profile(user_id)
        number = _profile_text(profile, "sms_to")
        if not number or _profile_text(profile, "sms_verified_number") != number:
            raise _sms_block(user_id, "sms_no_recipient", "keine bestaetigte SMS-Nummer im Profil")
        return cls(number, RecipientPurpose.user_profile, user_id, _FABRIK)

    @classmethod
    def verification(cls, user_id: str, number: str) -> "SmsRecipient":
        """Bestaetigungscode: nur an die zu beweisende Nummer des Nutzers
        (``pending_sms_to`` sonst ``sms_to``, Go ``smsZielnummer``)."""
        profile = _load_profile(user_id)
        bound = profile.get("pending_sms_to") or profile.get("sms_to")
        bound = bound.strip() if isinstance(bound, str) else ""
        candidate = number.strip() if isinstance(number, str) else ""
        if not bound or candidate != bound:
            raise _sms_block(
                user_id, "sms_verification_number_not_bound",
                "Nummer ist nicht die zu bestaetigende Nummer des Profils",
            )
        return cls(candidate, RecipientPurpose.verification, user_id, _FABRIK)


def _sms_block(user_id: str, reason_code: str, text: str) -> ChannelBlockedError:
    logger.warning("SMS fuer Nutzer %s blockiert (%s): %s", user_id, reason_code, text)
    return ChannelBlockedError("sms", f"{text} (Nutzer {user_id!r}).", reason_code=reason_code)


@dataclass(frozen=True)
class PremiumSmsRecipient:
    """Belegte Premium-SMS-Rueckadresse (Issue #1412 S4b) -- nur ueber
    ``for_user``; einen Zweck ``verification`` gibt es hier nicht (AC-7)."""

    number: str
    purpose: RecipientPurpose
    user_id: str
    _key: object = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self._key is not _FABRIK:
            raise TypeError("PremiumSmsRecipient nur ueber for_user() erzeugen")

    def well_formed(self) -> bool:
        return bool(_PREMIUM_RE.fullmatch(self.number))

    @classmethod
    def for_user(cls, user_id: str, settings) -> "PremiumSmsRecipient":
        """Gelernte Rueckadresse samt Alter, frisch aus ``user.json``; fehlend/
        Zukunft/aelter als die Frist blockt mit den bestehenden Codes."""
        from app.config import _parse_learned_timestamp
        from output.channels.premium_sms import check_reply_address

        profile = _load_profile(user_id)
        number = _profile_text(profile, "premium_sms_reply_to")
        try:
            check_reply_address(number, _parse_learned_timestamp(profile.get("premium_sms_reply_at")))
        except ChannelBlockedError as e:
            logger.warning("Premium-SMS fuer Nutzer %s blockiert (%s)", user_id, e.reason_code)
            raise
        return cls(number, RecipientPurpose.user_profile, user_id, _FABRIK)
