"""Issue #2144: Email/Telegram/SMS duerfen bei fehlendem Empfaenger NICHT an
eine leere/``None``-Adresse senden -- sie muessen wie ``PremiumSmsOutput.
_resolve_recipient()`` (Referenzmuster) sauber mit ``ChannelBlockedError``
und einem kanalspezifischen ``reason_code`` abbrechen.

Spec: docs/specs/bugfix/user_recipient_fallback.md, AC-4/AC-5/AC-6.

Kein Netz erlaubt (``--disable-socket``): jeder Test beweist zugleich, dass
KEIN Verbindungsversuch/API-Call stattfand, bevor der Guard greift.

Muss FEHLSCHLAGEN bis implementiert:
* E-Mail/SMS werfen heute den undifferenzierten ``OutputConfigError`` (kein
  ``reason_code``-Attribut) statt ``ChannelBlockedError``.
* Telegram prueft ``chat_id`` ueberhaupt nicht -- ohne die Herkunfts-
  Umschaltung (Testlauf-Herkunft) wuerde heute ein echter API-Call mit
  ``chat_id=None`` versucht.
"""
from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from app.config import Settings
from app.origin_guard import checkout_root
from output.channels.base import ChannelBlockedError

pytestmark = pytest.mark.disable_socket


# ---------------------------------------------------------------------------
# AC-4: EmailOutput ohne mail_to
# ---------------------------------------------------------------------------


def test_email_blocked_when_mail_to_missing_no_smtp_attempt():
    """AC-4 GIVEN ``settings.mail_to`` ist ``None``, ein Trip hat
    ``send_email=True`` / WHEN ``EmailOutput(settings).send(...)`` aufgerufen
    wird / THEN wirft der Kanal ``ChannelBlockedError`` mit
    ``reason_code='email_no_recipient'`` -- ohne jeden SMTP-Verbindungsaufbau
    (erzwungen durch ``--disable-socket``: ein echter Verbindungsversuch
    liesse den Test mit einem Socket-Fehler statt der erwarteten Ausnahme
    scheitern)."""
    from output.channels.email import EmailOutput

    settings = Settings(
        smtp_host="mail.example.invalid", smtp_user="tdd-2144", smtp_pass="kein-echtes-passwort",
        mail_to=None,
    )

    with pytest.raises(ChannelBlockedError) as excinfo:
        EmailOutput(settings).send("Betreff", "Text")

    assert excinfo.value.reason_code == "email_no_recipient", (
        f"BUG #2144: erwartet reason_code='email_no_recipient', bekommen "
        f"{getattr(excinfo.value, 'reason_code', None)!r} (Ausnahmetyp "
        f"{type(excinfo.value).__name__})"
    )


# ---------------------------------------------------------------------------
# AC-5: TelegramOutput ohne chat_id
# ---------------------------------------------------------------------------


def test_telegram_blocked_when_chat_id_missing_no_api_call(monkeypatch):
    """AC-5 GIVEN ``settings.telegram_chat_id`` ist ``None`` / WHEN
    ``TelegramOutput(settings).send(...)`` aufgerufen wird / THEN wirft der
    Kanal ``ChannelBlockedError`` mit ``reason_code='telegram_no_chat_id'`` --
    kein Request an die Bot-API.

    Herkunft wird wie in ``test_telegram_origin_guard.py`` AC-3 auf
    'production' gefaked (echte ``classify_origin()``-Logik, nur die
    Wurzel-Konstante zeigt auf dieses Worktree) -- sonst wuerde die
    bestehende Testlauf-Herkunftssperre (#1476) auf die Test-Chat-ID
    umschalten und die fehlende chat_id waere nie sichtbar."""
    from app import origin_guard as origin_guard_mod
    from output.channels import telegram as telegram_mod

    monkeypatch.setattr(
        origin_guard_mod, "PROD_ROOT", checkout_root(Path(telegram_mod.__file__)),
    )

    calls: list[dict] = []

    def _sink(url, json=None, timeout=None, **kwargs):
        calls.append({"url": url, "payload": json})
        raise AssertionError("kein API-Call haette hier stattfinden duerfen")

    monkeypatch.setattr(httpx, "post", _sink)

    settings = Settings(telegram_bot_token="prod-bot-token").model_copy(
        update={"telegram_chat_id": None},
    )

    with pytest.raises(ChannelBlockedError) as excinfo:
        telegram_mod.TelegramOutput(settings).send("Betreff", "Text")

    assert excinfo.value.reason_code == "telegram_no_chat_id", (
        f"BUG #2144: erwartet reason_code='telegram_no_chat_id', bekommen "
        f"{getattr(excinfo.value, 'reason_code', None)!r} (Ausnahmetyp "
        f"{type(excinfo.value).__name__})"
    )
    assert calls == [], f"API-Call haette nicht stattfinden duerfen: {calls}"


# ---------------------------------------------------------------------------
# AC-6: SMSOutput -- fehlender sms_to unterscheidbar von fehlender API-Config
# ---------------------------------------------------------------------------


def test_sms_blocked_when_sms_to_missing_distinct_reason_code():
    """AC-6 (Fall 1) GIVEN ``settings.sms_to`` ist ``None``,
    ``settings.seven_api_key`` ist GESETZT (API-Konfiguration vollstaendig
    bis auf den Empfaenger) / WHEN ``SMSOutput(settings).send(...)``
    aufgerufen wird / THEN wirft der Kanal ``ChannelBlockedError`` mit
    ``reason_code='sms_no_recipient'`` -- unterscheidbar von einer fehlenden
    API-Konfiguration, nicht mehr der undifferenzierte ``OutputConfigError``."""
    from output.channels.sms import SMSOutput

    settings = Settings(seven_api_key="tdd-2144-key", sms_to=None)

    with pytest.raises(ChannelBlockedError) as excinfo:
        SMSOutput(settings).send("Betreff", "Text")

    assert excinfo.value.reason_code == "sms_no_recipient", (
        f"BUG #2144: erwartet reason_code='sms_no_recipient', bekommen "
        f"{getattr(excinfo.value, 'reason_code', None)!r} (Ausnahmetyp "
        f"{type(excinfo.value).__name__})"
    )


def test_sms_missing_api_key_keeps_distinct_cause_from_missing_recipient():
    """AC-6 (Fall 2, Gegenprobe) GIVEN ``settings.sms_to`` ist GESETZT, aber
    ``settings.seven_api_key`` FEHLT / WHEN ``SMSOutput(settings).send(...)``
    aufgerufen wird / THEN bleibt die bisherige Fehlerursache bestehen --
    NICHT derselbe ``reason_code`` wie beim fehlenden Empfaenger. Ohne diese
    Gegenprobe waere Fall 1 nur zufaellig unterscheidbar (z.B. weil beide
    Faelle ``reason_code=None`` blieben)."""
    from output.channels.sms import SMSOutput

    settings = Settings(seven_api_key=None, sms_to="+491511234567")

    with pytest.raises(Exception) as excinfo:
        SMSOutput(settings).send("Betreff", "Text")

    reason_code = getattr(excinfo.value, "reason_code", None)
    assert reason_code != "sms_no_recipient", (
        f"Fehlende API-Konfiguration darf nicht denselben reason_code "
        f"tragen wie ein fehlender Empfaenger: {reason_code!r}"
    )
