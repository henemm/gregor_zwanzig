"""#2157 AC-c/AC-d: Telegram-Kennungen und Inbound-Absenderadressen erscheinen
im Protokoll nur maskiert.

Spec: docs/specs/modules/pii_log_masking.md (Fundstellen 4, 5, 6)

Nachweisform (Mock-Verbot): ersetzt wird AUSSCHLIESSLICH der Netzrand --
``TelegramOutput`` durch eine echte Klasse, die scheitert bzw. mitschreibt
(Muster ``tests/test_inbound_telegram_unknown_chat.py``), und ``httpx.post``
zur Go-API (``localhost:8090``, sonst traefe der Test den lokal laufenden
Dienst). Die Maskierung selbst laeuft echt; geprueft wird am ausgegebenen
Log-Datensatz (``caplog``), also am Wirkort.
"""
from __future__ import annotations

import email
import logging

import httpx
import pytest

from app.config import Settings

CHAT_ID = "123456789"
CHAT_ID_MASKIERT = "…789"  # seven_io_base.mask_number("123456789")

FREMDABSENDER = "finder@example.org"
FREMDABSENDER_MASKIERT = "***@example.org"


def _zeilen(caplog, merkmal: str) -> list[str]:
    return [r.getMessage() for r in caplog.records if merkmal in r.getMessage()]


# ═══════════════════════════ AC-c: notification_service ══════════════════════


@pytest.fixture
def telegram_scheitert(monkeypatch) -> None:
    """``TelegramOutput`` an beiden Nachschlage-Stellen durch eine Klasse
    ersetzen, deren Netzzugriffe mit ``OutputError`` scheitern."""
    from output.channels import telegram as telegram_kanal
    from output.channels.base import OutputError
    from services import notification_service as ns

    class _TelegramScheitert:
        def __init__(self, settings) -> None:
            pass

        def _fehler(self, *args, **kwargs):
            raise OutputError("telegram", "Netzrand im Test absichtlich gescheitert")

        send = edit_message_text = delete_message = answer_callback_query = _fehler

    monkeypatch.setattr(ns, "TelegramOutput", _TelegramScheitert)
    monkeypatch.setattr(telegram_kanal, "TelegramOutput", _TelegramScheitert)


def _dienst():
    from services.notification_service import NotificationService

    return NotificationService(settings=Settings(), user_id="tdd-2157")


def _command_reply(dienst, settings):
    from services.trip_command_processor import CommandResult

    dienst.send_command_reply_telegram(
        CommandResult(success=True, command="hilfe",
                      confirmation_subject="s", confirmation_body="b"),
        CHAT_ID, settings,
    )


_FEHLERPFADE = {
    "command_reply": ("Telegram command reply failed", _command_reply),
    "message": ("Telegram message failed", lambda d, s: d.send_telegram_message(
        chat_id=CHAT_ID, subject="s", body="b", settings=s)),
    "edit": ("Telegram edit_message_text failed", lambda d, s: d.edit_telegram_message_text(
        chat_id=CHAT_ID, message_id=42, text="t", settings=s)),
    "delete": ("Telegram delete_message failed", lambda d, s: d.delete_telegram_message(
        chat_id=CHAT_ID, message_id=42, settings=s)),
    "callback": ("Telegram answer_callback_query failed",
                 lambda d, s: d.answer_telegram_callback_query(
                     callback_query_id=CHAT_ID, settings=s)),
}


@pytest.mark.parametrize("pfad", sorted(_FEHLERPFADE))
def test_ac_c_telegram_fehlerzeile_nennt_chat_id_nur_maskiert(
    pfad, telegram_scheitert, caplog,
):
    merkmal, aufruf = _FEHLERPFADE[pfad]
    with caplog.at_level(logging.ERROR):
        aufruf(_dienst(), Settings())

    zeilen = _zeilen(caplog, merkmal)
    assert len(zeilen) == 1, f"Erwartet genau eine Fehlerzeile {merkmal!r}: {zeilen}"
    assert CHAT_ID not in zeilen[0], (
        f"#2157 AC-c: die Fehlerzeile nennt die Telegram-Kennung im Klartext: {zeilen[0]}"
    )
    assert CHAT_ID_MASKIERT in zeilen[0], (
        f"#2157 AC-c: maskierte Form {CHAT_ID_MASKIERT!r} fehlt: {zeilen[0]}"
    )


# ═══════════════════════════ AC-c: inbound_telegram_reader ═══════════════════


def test_ac_c_registrierungszeile_nennt_chat_id_nur_maskiert(monkeypatch, caplog):
    from output.channels import telegram as telegram_kanal
    from services import notification_service as ns
    from services.inbound_telegram_reader import InboundTelegramReader

    go_api_aufrufe: list[dict] = []

    def _go_api(url, json=None, timeout=None, **kwargs):
        go_api_aufrufe.append({"url": url, "json": json})
        return httpx.Response(200, json={"ok": True})

    class _TelegramAufzeichner:
        def __init__(self, settings) -> None:
            pass

        def send(self, *args, **kwargs) -> int:
            return 1

    monkeypatch.setattr(httpx, "post", _go_api)
    monkeypatch.setattr(ns, "TelegramOutput", _TelegramAufzeichner)
    monkeypatch.setattr(telegram_kanal, "TelegramOutput", _TelegramAufzeichner)

    with caplog.at_level(logging.INFO):
        InboundTelegramReader()._process_start_command("tok-2157", CHAT_ID, Settings())

    assert go_api_aufrufe, "Die Go-API-Steckdose wurde nie erreicht (Pruefort != Wirkort)"
    zeilen = _zeilen(caplog, "via token registriert")
    assert len(zeilen) == 1, f"Erwartet genau eine Registrierungszeile: {zeilen}"
    assert CHAT_ID not in zeilen[0], (
        f"#2157 AC-c: die Registrierungszeile nennt die chat_id im Klartext: {zeilen[0]}"
    )
    assert CHAT_ID_MASKIERT in zeilen[0], (
        f"#2157 AC-c: maskierte Form {CHAT_ID_MASKIERT!r} fehlt: {zeilen[0]}"
    )


# ═══════════════════════════ AC-d: inbound_email_reader ══════════════════════


def _mail() -> email.message.Message:
    return email.message_from_string(
        f"From: {FREMDABSENDER}\nTo: gregor@henemm.com\nSubject: [Trip] hilfe\n\nhilfe\n"
    )


def _pruefe_absenderzeile(caplog, merkmal: str) -> None:
    zeilen = _zeilen(caplog, merkmal)
    assert len(zeilen) == 1, f"Erwartet genau eine Zeile {merkmal!r}: {zeilen}"
    assert FREMDABSENDER not in zeilen[0], (
        f"#2157 AC-d: die Zeile nennt die Absenderadresse im Klartext: {zeilen[0]}"
    )
    assert FREMDABSENDER_MASKIERT in zeilen[0], (
        f"#2157 AC-d: maskierte Form {FREMDABSENDER_MASKIERT!r} fehlt: {zeilen[0]}"
    )


def test_ac_d_nicht_autorisierter_absender_erscheint_nur_maskiert(caplog):
    from services.inbound_email_reader import InboundEmailReader

    settings = Settings(mail_to="konto-inhaber@beispiel.de", mail_from="gregor@henemm.com")
    with caplog.at_level(logging.DEBUG):
        erlaubt = InboundEmailReader()._authorize(FREMDABSENDER, settings, _mail())

    assert erlaubt is False
    _pruefe_absenderzeile(caplog, "Ignoring email from")


def test_ac_d_unverifizierter_absender_erscheint_nur_maskiert(caplog):
    from services.inbound_email_reader import InboundEmailReader

    settings = Settings(
        mail_to=FREMDABSENDER, mail_from="gregor@henemm.com", email_verified_at=None,
    )
    with caplog.at_level(logging.DEBUG):
        erlaubt = InboundEmailReader()._authorize(FREMDABSENDER, settings, _mail())

    assert erlaubt is False
    _pruefe_absenderzeile(caplog, "Sender not verified")


def test_ac_d_spf_dkim_fehlschlag_erscheint_nur_maskiert(caplog):
    from services.inbound_email_reader import InboundEmailReader

    settings = Settings(
        mail_to=FREMDABSENDER, mail_from="gregor@henemm.com",
        email_verified_at="2026-09-01T00:00:00Z", mail_server_hostname=None,
    )
    with caplog.at_level(logging.DEBUG):
        erlaubt = InboundEmailReader()._authorize(FREMDABSENDER, settings, _mail())

    assert erlaubt is False
    _pruefe_absenderzeile(caplog, "SPF/DKIM check failed")


class _ImapPostfach:
    """Netzrand: liefert genau eine Mail, merkt sich gesetzte Flags."""

    def __init__(self, mail: email.message.Message) -> None:
        self._roh = mail.as_bytes()
        self.flags: list[tuple] = []

    def fetch(self, uid, teile):
        return "OK", [(uid, self._roh)]

    def store(self, uid, modus, flag):
        self.flags.append((uid, modus, flag))
        return "OK", [b""]


def test_ac_d_unaufgeloester_absender_erscheint_nur_maskiert(caplog):
    from services.inbound_email_reader import InboundEmailReader

    settings = Settings(mail_to="konto-inhaber@beispiel.de", mail_from="gregor@henemm.com")
    postfach = _ImapPostfach(_mail())
    with caplog.at_level(logging.DEBUG):
        verarbeitet = InboundEmailReader()._process_single(postfach, b"1", settings)

    assert verarbeitet == 0
    assert postfach.flags == [(b"1", "+FLAGS", "\\Seen")]
    _pruefe_absenderzeile(caplog, "Unresolved/ambiguous sender")


# ═══════════════════ AC-b: Empfaenger-Guards in email.py (Listen) ════════════

LISTE = f"gregor-test@henemm.com, {FREMDABSENDER}"
LISTE_MASKIERT = f"gregor-test@henemm.com, {FREMDABSENDER_MASKIERT}"


def _guard_block(monkeypatch, caplog, host: str) -> Exception:
    from output.channels import email as email_module
    from output.channels.base import OutputConfigError

    monkeypatch.setattr(email_module, "running_origin", lambda module_file: "production")
    s = Settings(
        smtp_host="mail.henemm.com", smtp_port=587, smtp_user="resend",
        smtp_pass="re_2157_test_invalid_key", mail_to=FREMDABSENDER,
        mail_from="bot@henemm.com", _env_file=None,
    ).model_copy(update={"smtp_host": host, "is_test_mode": False})
    with caplog.at_level(logging.WARNING):
        with pytest.raises(OutputConfigError) as exc:
            email_module.EmailOutput(s).send("GZ #2157", "Koerper", to=[LISTE])
    return exc.value


@pytest.mark.parametrize("host, merkmal", [
    ("smtp.resend.com", "Resend-Allowlist-Guard blockiert"),
    ("mail.henemm.com", "Lokal-Guard blockiert"),
])
def test_ac_b_guard_maskiert_jede_listenadresse(monkeypatch, caplog, host, merkmal):
    fehler = _guard_block(monkeypatch, caplog, host)

    zeilen = _zeilen(caplog, merkmal)
    assert len(zeilen) == 1, f"Erwartet genau eine Zeile {merkmal!r}: {zeilen}"
    assert FREMDABSENDER not in zeilen[0], f"#2157 AC-b: Klartext im Log: {zeilen[0]}"
    assert LISTE_MASKIERT in zeilen[0], f"#2157 AC-b: {LISTE_MASKIERT!r} fehlt: {zeilen[0]}"
    assert FREMDABSENDER not in str(fehler), f"#2157 AC-b: Klartext im Fehler: {fehler}"
