"""Empfaengervertrag Telegram -- Antworten im Webhook-Update und Test-Knopf.

Spec: docs/specs/modules/fix_1412_s4a_empfaengervertrag_telegram.md
(AC-4, AC-7, AC-8, AC-11)

Nachweisform wie ``test_telegram_recipient_contract.py``: Sink am
``httpx``-Rand mit echter ``httpx.Response``, kein ``_post``-Stub, kein
Mock()/MagicMock/patch(), Herkunft auf "production" festgenagelt,
``.env``-Isolation, ``is_test_mode=False``. Einstieg fuer die Reader-Faelle
ist das ECHTE ``InboundTelegramReader._process_update``.

``httpx.post`` ist global gepatcht -- auch ``lib.go_internal.post_internal``
(``/start``-Verknuepfung) laeuft darueber. Der Sink unterscheidet deshalb nach
URL: Bot-API-Aufrufe werden gezaehlt, die interne Go-API antwortet mit einem
pro Test festgelegten Status (200 bzw. 409).

Nutzerkennungen ohne "test"/"tdd" (sonst erzwingt ``is_test_user_id`` den
Testmodus); Chat-IDs numerisch (Formpruefung AC-6).
"""
from __future__ import annotations

import json

import httpx
import pytest

from app.config import Settings
from app.loader import get_data_dir
from output.channels import telegram as telegram_mod
from output.channels.base import ChannelBlockedError
from output.channels.telegram import TelegramOutput, reset_telegram_rate_limit_for_tests

PROD_TOKEN = "111111:prod-token"
TEST_TOKEN = "222222:test-token"
GLOBAL_CHAT = "900000001"
TEST_CHAT = "424242"
BOT_HOST = "api.telegram.org"
# Bewusst NICHT mail.henemm.com: der Resend-Default-Deny (#1122) lenkt im
# pytest-Lauf auch den Produktions-Host dorthin um -- sonst waeren Test- und
# Produktionsweg am Draht ununterscheidbar.
TEST_SMTP_HOST = "stalwart-pruefung.henemm.com"


def _bot_ok(request: httpx.Request, message_id: int) -> httpx.Response:
    return httpx.Response(
        200, json={"ok": True, "result": {"message_id": message_id}}, request=request,
    )


class _HttpxSink:
    """Zeichnet Bot-API-Aufrufe auf (``calls``) und beantwortet die interne
    Go-API mit ``go_status`` (``go_calls``)."""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.go_calls: list[dict] = []
        self.go_status = 200

    def __call__(self, url, json=None, timeout=None, **kwargs):
        request = httpx.Request("POST", url, json=json)
        if BOT_HOST in url:
            self.calls.append({"url": url, "payload": dict(json or {})})
            return _bot_ok(request, message_id=5000 + len(self.calls))
        self.go_calls.append({"url": url, "payload": dict(json or {})})
        return httpx.Response(self.go_status, json={}, request=request)

    def chats(self, methode: str | None = None) -> list[str]:
        return [
            str(c["payload"]["chat_id"]) for c in self.calls
            if "chat_id" in c["payload"] and (methode is None or c["url"].endswith(methode))
        ]

    def texte(self) -> list[str]:
        return [c["payload"].get("text", "") for c in self.calls]


@pytest.fixture(autouse=True)
def _hermetisch(monkeypatch):
    monkeypatch.setattr(telegram_mod, "running_origin", lambda module_file: "production")
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    for key in (
        "GZ_TELEGRAM_BOT_TOKEN", "GZ_TELEGRAM_CHAT_ID", "GZ_TELEGRAM_TEST_CHAT_ID",
        "GZ_TELEGRAM_TEST_BOT_TOKEN", "GZ_IS_TEST_MODE", "GZ_ENV",
    ):
        monkeypatch.delenv(key, raising=False)
    reset_telegram_rate_limit_for_tests()
    yield
    reset_telegram_rate_limit_for_tests()


@pytest.fixture
def sink(monkeypatch) -> _HttpxSink:
    s = _HttpxSink()
    monkeypatch.setattr(telegram_mod.httpx, "post", s)
    return s


def _settings(**overrides) -> Settings:
    werte = dict(
        _env_file=None,
        env="production",
        is_test_mode=False,
        telegram_bot_token=PROD_TOKEN,
        telegram_chat_id=GLOBAL_CHAT,
        telegram_test_chat_id=TEST_CHAT,
        telegram_test_bot_token=TEST_TOKEN,
    )
    werte.update(overrides)
    return Settings(**werte)


def _profil(user_id: str, **felder) -> None:
    ordner = get_data_dir(user_id)
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / "user.json").write_text(json.dumps({"id": user_id, **felder}))


def _update(chat_id, text: str) -> dict:
    return {"update_id": 1, "message": {"message_id": 10, "text": text, "chat": {"id": chat_id}}}


# ═══════════════════════════ AC-4 ════════════════════════════════════════════


def test_ac4_inbound_reply_ausserhalb_eines_updates_wird_geblockt(sink):
    """AC-4 (ausserhalb).

    GIVEN ein Empfaenger ``inbound_reply(chat_id)``, aber kein laufendes
          Webhook-Update (Herkunftsbeleg leer).
    WHEN  gesendet wird.
    THEN  Block (``ChannelBlockedError``), kein HTTP-Call.
    """
    from output.channels.recipient import TelegramRecipient

    with pytest.raises(ChannelBlockedError):
        TelegramOutput(
            _settings(), recipient=TelegramRecipient.inbound_reply("600000006"),
        ).send("Betreff", "Antwort")
    assert sink.calls == [], f"AC-4: kein HTTP-Call erlaubt, gesehen {sink.calls!r}"


def _sonde_installieren(monkeypatch, ziel_chats: list[str]) -> dict:
    """Minimal-invasive Sonde IM laufenden Update (Auftrag AC-4): die
    Nachbarfunktion ``services.inbound_telegram_reader.load_all_trips`` laeuft
    fuer jeden bekannten Absender NACH dem Parsen des Updates. Sie wird durch
    eine Funktion ersetzt, die je Ziel-Chat einen echten Sendeversuch mit
    ``inbound_reply(ziel)`` macht, das Ergebnis aufzeichnet und ``[]``
    zurueckgibt (kein Trip -> der Reader laeuft normal weiter). Ohne diese
    Sonde gibt es keinen echten Pfad, der INNERHALB eines Updates an einen
    fremden Chat zu senden versucht -- genau das ist der Fall, den der
    Herkunftsbeleg abfangen soll. Der Pruefling (Transport/ContextVar) wird
    nicht gestubbt."""
    from output.channels.recipient import TelegramRecipient
    from services import inbound_telegram_reader as reader_mod

    ergebnis: dict = {}

    def _sonde(user_id, *args, **kwargs):
        for ziel in ziel_chats:
            try:
                TelegramOutput(
                    _settings(), recipient=TelegramRecipient.inbound_reply(ziel),
                ).send("Sonde", f"an {ziel}")
                ergebnis[ziel] = "zugestellt"
            except ChannelBlockedError:
                ergebnis[ziel] = "geblockt"
        return []

    monkeypatch.setattr(reader_mod, "load_all_trips", _sonde)
    return ergebnis


def test_ac4_innerhalb_eines_updates_nur_absender_chat_erlaubt(sink, monkeypatch):
    """AC-4 (innerhalb: gleicher Chat / fremder Chat).

    GIVEN ein bekannter Nutzer schreibt aus Chat 600000006; waehrend des
          ECHTEN ``_process_update`` versucht eine Sonde (s.
          ``_sonde_installieren``) je eine Antwort an den Absender-Chat und
          an einen fremden Chat 600000007.
    WHEN  das Update verarbeitet wird.
    THEN  geht die Antwort an den Absender-Chat raus, der fremde Chat wird
          geblockt und erreicht den Draht nie.
    """
    from services.inbound_telegram_reader import InboundTelegramReader

    _profil("nutzer-sender", telegram_chat_id="600000006")
    ergebnis = _sonde_installieren(monkeypatch, ["600000006", "600000007"])

    InboundTelegramReader()._process_update(_update(600000006, "hilfe"), _settings())

    assert ergebnis == {"600000006": "zugestellt", "600000007": "geblockt"}, (
        f"AC-4: gesehen {ergebnis!r}"
    )
    assert "600000007" not in sink.chats(), f"AC-4: fremder Chat am Draht: {sink.chats()!r}"


def test_ac4_herkunftsbeleg_ist_nach_exception_im_update_zurueckgesetzt(sink, monkeypatch):
    """AC-4 (nach Exception, eigener Testfall).

    GIVEN ein bekannter Nutzer schreibt aus Chat 600000008; im ECHTEN
          ``_process_update`` wirft die Nachbarfunktion ``load_all_trips``
          (laeuft nach dem Parsen, also nach dem Setzen des Belegs) eine
          Ausnahme. Minimal-invasiv begruendet: es gibt keinen Eingabe-Weg,
          der nach dem Parsen deterministisch eine Ausnahme ausloest --
          ``load_all_trips`` schluckt kaputte Dateien, ``is_user_disabled``
          ebenfalls.
    WHEN  danach -- ausserhalb des Updates -- an denselben Chat per
          ``inbound_reply`` gesendet wird.
    THEN  ist ``_current_inbound_sender`` leer und der Versand wird geblockt,
          kein HTTP-Call.
    """
    from output.channels.recipient import TelegramRecipient
    from services import inbound_telegram_reader as reader_mod
    from services.inbound_telegram_reader import InboundTelegramReader, _current_inbound_sender

    _profil("nutzer-absturz", telegram_chat_id="600000008")

    def _wirft(user_id, *args, **kwargs):
        raise RuntimeError("Absturz im Update")

    monkeypatch.setattr(reader_mod, "load_all_trips", _wirft)
    with pytest.raises(RuntimeError):
        InboundTelegramReader()._process_update(_update(600000008, "hilfe"), _settings())

    assert not _current_inbound_sender.get(None), (
        f"AC-4: Beleg nach Exception nicht zurueckgesetzt: {_current_inbound_sender.get(None)!r}"
    )
    vorher = len(sink.calls)
    with pytest.raises(ChannelBlockedError):
        TelegramOutput(
            _settings(), recipient=TelegramRecipient.inbound_reply("600000008"),
        ).send("Betreff", "Nachzuegler")
    assert len(sink.calls) == vorher, f"AC-4: Nachzuegler am Draht: {sink.calls!r}"


# ═══════════════════════════ AC-7 ════════════════════════════════════════════


def test_ac7_befehlsantwort_ueber_echten_webhook_pfad_geht_an_den_absender(sink):
    """AC-7 (echter Pfad; heute vermutlich gruen -- kein kuenstliches Rot).

    GIVEN ein bekannter Nutzer (Profil-Chat 700000007) schickt ``hilfe``
          ueber den echten Webhook-Pfad ``_process_update``; die
          Basis-Einstellungen tragen den globalen Betreiber-Chat.
          ``hilfe`` statt ``heute``: zielloser Befehl, kein Trip-/Wetterabruf,
          keine Bubbles -- gemessen wird nur die Antwortadresse.
    WHEN  die Antwort gesendet wird.
    THEN  geht sie (mindestens eine Nachricht) an 700000007 und nie an den
          globalen Chat.

    Heute laeuft die Antwort ueber ``user_settings`` (Profil-Chat == Absender)
    und landet zufaellig richtig; der R7-Defekt selbst wird im naechsten Test
    sichtbar gemacht. Dieser Test bewacht, dass die Umstellung auf
    ``inbound_reply`` die Antwort nicht verstummen laesst.
    """
    from services.inbound_telegram_reader import InboundTelegramReader

    _profil("nutzer-befehl", telegram_chat_id="700000007")
    InboundTelegramReader()._process_update(_update(700000007, "hilfe"), _settings())

    gesendet = sink.chats("/sendMessage")
    assert gesendet, f"AC-7: keine Antwort gesendet, Aufrufe {sink.calls!r}"
    assert set(gesendet) == {"700000007"}, f"AC-7: gesehen {gesendet!r}"


def test_ac7_r7_uebergebene_chat_id_wird_tatsaechlich_verwendet(sink):
    """AC-7 (R7 geschlossen).

    GIVEN ein laufendes Update von Absender 700000008 (Herkunftsbeleg) und
          Einstellungen, die einen ANDEREN Chat (globaler Betreiber-Chat)
          tragen.
    WHEN  ``NotificationService.send_command_reply_telegram`` bzw.
          ``send_telegram_message`` mit ``chat_id=700000008`` aufgerufen wird.
    THEN  geht die Nachricht an 700000008 -- das Argument wird verwendet,
          nicht nur geloggt -- und nie an den Chat aus den Einstellungen.

    RED heute: beide Methoden verwerfen ``chat_id`` und senden an
    ``settings.telegram_chat_id``.
    """
    from services.inbound_telegram_reader import _current_inbound_sender
    from services.notification_service import NotificationService
    from services.trip_command_processor import CommandResult

    settings = _settings()
    dienst = NotificationService(settings=settings, user_id=None)
    ergebnis = CommandResult(
        success=True, command="hilfe",
        confirmation_subject="Hilfe", confirmation_body="Befehle: ...",
    )
    token = _current_inbound_sender.set("700000008")
    try:
        dienst.send_command_reply_telegram(ergebnis, chat_id="700000008", settings=settings)
        dienst.send_telegram_message(
            chat_id="700000008", subject="Fehler", body="x", settings=settings,
        )
    finally:
        _current_inbound_sender.reset(token)

    assert sink.chats() == ["700000008", "700000008"], f"AC-7: gesehen {sink.chats()!r}"


# ═══════════════════════════ AC-8 ════════════════════════════════════════════


def test_ac8_unbekannter_absender_erhaelt_registrierungshinweis(sink):
    """AC-8 -- Erhaltung, bewusst gruen.

    GIVEN ein Absender (Chat 800000008) ohne verknuepftes Konto; die
          Basis-Einstellungen tragen den globalen Betreiber-Chat.
    WHEN  er dem Bot schreibt (echter ``_process_update``).
    THEN  erhaelt genau er den Registrierungshinweis (``/start``-Anleitung),
          ohne Nutzerdaten; der Betreiber-Chat erhaelt nichts.
    """
    from services.inbound_telegram_reader import InboundTelegramReader

    InboundTelegramReader()._process_update(_update(800000008, "hallo gregor"), _settings())

    assert sink.chats() == ["800000008"], f"AC-8: gesehen {sink.chats()!r}"
    assert "/start" in sink.texte()[0], f"AC-8: kein Registrierungshinweis: {sink.texte()!r}"


@pytest.mark.parametrize(
    "go_status, erwartet",
    [(200, "Du bist jetzt mit Gregor verbunden"), (409, "bereits mit einem anderen")],
)
def test_ac8_start_ok_und_409_erreichen_den_absender(sink, go_status, erwartet):
    """AC-8 (``/start`` OK und 409) -- Erhaltung, bewusst gruen.

    GIVEN ein Absender (Chat 800000009) sendet ``/start <token>``; die
          interne Go-API antwortet 200 (verknuepft) bzw. 409 (Chat gehoert
          einem anderen Konto); es existiert KEIN Profil mit diesem Chat
          (die Antwort kann also nicht aus einem Profil stammen).
    WHEN  das Update verarbeitet wird.
    THEN  erhaelt genau der Absender die Bestaetigung bzw. den Konflikthinweis,
          der Betreiber-Chat nichts.
    """
    from services.inbound_telegram_reader import InboundTelegramReader

    sink.go_status = go_status
    InboundTelegramReader()._process_update(_update(800000009, "/start abc123"), _settings())

    assert sink.go_calls, "Vorbedingung: die Go-Verknuepfung wurde angefragt"
    assert sink.chats() == ["800000009"], f"AC-8: gesehen {sink.chats()!r}"
    assert erwartet in sink.texte()[0], f"AC-8: gesehen {sink.texte()!r}"


# ═══════════════════════════ AC-11 ═══════════════════════════════════════════


@pytest.fixture
def knopf_env(monkeypatch):
    """Produktionsnahe Umgebung fuer den Test-Knopf: ``Settings()`` wird in
    ``channel_test_service`` intern gebaut, daher per ``GZ_``-Umgebung. Der
    Test-Chat ist gesetzt (wie in Produktion, Befund M3)."""
    for key, wert in {
        "GZ_ENV": "production",
        "GZ_IS_TEST_MODE": "false",
        "GZ_TELEGRAM_BOT_TOKEN": PROD_TOKEN,
        "GZ_TELEGRAM_CHAT_ID": GLOBAL_CHAT,
        "GZ_TELEGRAM_TEST_CHAT_ID": TEST_CHAT,
        "GZ_TELEGRAM_TEST_BOT_TOKEN": TEST_TOKEN,
        "GZ_SMTP_HOST": "smtp.resend.com",
        "GZ_SMTP_USER": "resend",
        "GZ_SMTP_PASS": "kein-echtes-passwort",
        "GZ_MAIL_FROM": "gregor_zwanzig@henemm.com",
        "GZ_TEST_SMTP_HOST": TEST_SMTP_HOST,
        "GZ_TEST_SMTP_USER": "gregor-test",
        "GZ_TEST_SMTP_PASS": "kein-echtes-passwort",
    }.items():
        monkeypatch.setenv(key, wert)


def test_ac11_test_knopf_telegram_geht_an_profil_chat_ueber_produktions_bot(sink, knopf_env):
    """AC-11.

    GIVEN ein Nutzer mit Profil-Chat 110000011, ``GZ_TELEGRAM_TEST_CHAT_ID``
          gesetzt, ``is_test_mode=False``.
    WHEN  er "Telegram testen" drueckt (``send_test_message("telegram", uid)``).
    THEN  Erfolg, genau eine Nachricht an 110000011 ueber den
          Produktions-Bot-Token -- nicht an den Betreiber-Test-Chat, nicht
          ueber den Test-Bot.

    RED heute: ``for_testing()`` biegt Chat und Token auf die Test-Werte um.
    """
    from services.channel_test_service import send_test_message

    _profil("nutzer-knopf", telegram_chat_id="110000011", mail_to="knopf@henemm.com")
    ergebnis = send_test_message("telegram", "nutzer-knopf")

    assert ergebnis == {"status": "ok"}, f"AC-11: gesehen {ergebnis!r}"
    assert sink.chats() == ["110000011"], f"AC-11: gesehen {sink.chats()!r}"
    assert f"/bot{PROD_TOKEN}/" in sink.calls[0]["url"], f"AC-11: URL {sink.calls[0]['url']!r}"


def test_ac11_test_knopf_ohne_profil_chat_meldet_fehler_statt_erfolg(sink, knopf_env):
    """AC-11 (ohne Profil-Chat).

    GIVEN ein Nutzer OHNE Telegram-Chat im Profil, Test-Chat konfiguriert.
    WHEN  er "Telegram testen" drueckt.
    THEN  erhaelt er eine Fehlermeldung (kein ``status: ok``), kein HTTP-Call.

    RED heute: die Nachricht geht an den Betreiber-Test-Chat, die Oberflaeche
    meldet Erfolg.
    """
    from services.channel_test_service import send_test_message

    _profil("nutzer-ohne-chat", mail_to="ohne@henemm.com")
    ergebnis = send_test_message("telegram", "nutzer-ohne-chat")

    assert "error" in ergebnis and "status" not in ergebnis, f"AC-11: gesehen {ergebnis!r}"
    assert sink.calls == [], f"AC-11: kein HTTP-Call erlaubt, gesehen {sink.calls!r}"


def test_ac11_test_knopf_email_zweig_unveraendert_ueber_testpostausgang(monkeypatch, knopf_env):
    """AC-11 (E-Mail-Zweig, #198) -- Erhaltung, bewusst gruen.

    GIVEN ein Nutzer mit ``mail_to`` im Profil; Produktions-SMTP ist Resend,
          Test-SMTP ist Stalwart.
    WHEN  er "E-Mail testen" drueckt.
    THEN  Erfolg, und die SMTP-Verbindung geht an den Test-Postausgang
          (``for_testing()`` bleibt fuer E-Mail), nicht an Resend.
    """
    from output.channels import email as email_mod
    from services.channel_test_service import send_test_message

    verbindungen: list[str] = []

    class _SmtpAufzeichner:
        def __init__(self, host, port, timeout=None):
            verbindungen.append(host)

            class _Sock:
                def settimeout(self, t):
                    pass

            self.sock = _Sock()

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def starttls(self):
            pass

        def login(self, user, password):
            pass

        def sendmail(self, from_addr, to_addrs, msg):
            pass

    monkeypatch.setattr(email_mod.smtplib, "SMTP", _SmtpAufzeichner)
    monkeypatch.setattr(email_mod, "running_origin", lambda module_file: "production")

    _profil("nutzer-mail", mail_to="nutzer-mail@henemm.com")
    ergebnis = send_test_message("email", "nutzer-mail")

    assert ergebnis == {"status": "ok"}, f"AC-11: gesehen {ergebnis!r}"
    assert verbindungen == [TEST_SMTP_HOST], f"AC-11: gesehen {verbindungen!r}"


# ═══════════════════════ Fix-Loop 1 (Adversary F005) ═════════════════════════


def test_f005_knopfklick_editiert_beim_absender_und_blockt_fremden_chat(sink, monkeypatch):
    """F005 (Herkunftsbeleg im Callback-Pfad).

    GIVEN ein UNBEKANNTER Absender (Chat 900000021) klickt einen Knopf; das
          ECHTE ``_process_callback_query`` laeuft. Waehrend des Klicks
          versucht eine Sonde (Nachbarfunktion ``_bare_public_host``, laeuft
          nach dem Setzen des Belegs) eine Antwort an den fremden Chat
          900000022.
    WHEN  der Klick verarbeitet wird.
    THEN  geht der Registrierungs-Edit an 900000021, der Spinner wird
          beendet, der fremde Chat wird geblockt und erreicht den Draht nie.
    """
    from output.channels.recipient import TelegramRecipient
    from services import inbound_telegram_reader as reader_mod
    from services.inbound_telegram_reader import InboundTelegramReader

    ergebnis: dict = {}

    def _sonde(settings):
        try:
            TelegramOutput(
                _settings(), recipient=TelegramRecipient.inbound_reply("900000022"),
            ).send("Sonde", "fremd")
            ergebnis["fremd"] = "zugestellt"
        except ChannelBlockedError:
            ergebnis["fremd"] = "geblockt"
        return None

    monkeypatch.setattr(reader_mod, "_bare_public_host", _sonde)
    update = {"update_id": 2, "callback_query": {
        "id": "cq-f005", "data": "glance",
        "message": {"message_id": 77, "chat": {"id": 900000021}},
    }}
    InboundTelegramReader()._process_update(update, _settings())

    assert ergebnis == {"fremd": "geblockt"}, f"F005: gesehen {ergebnis!r}"
    assert sink.chats("/editMessageText") == ["900000021"], f"F005: {sink.calls!r}"
    assert "900000022" not in sink.chats(), f"F005: fremder Chat am Draht: {sink.calls!r}"
    assert any(c["url"].endswith("/answerCallbackQuery") for c in sink.calls)
