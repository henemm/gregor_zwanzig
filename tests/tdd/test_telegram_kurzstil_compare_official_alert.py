"""TDD RED — Feature #1260 (Scheibe S4): Compare-amtlich-Redirect für den
Telegram-Kurzstil.

Deckt ab:
- AC-5 (amtliche Compare-Warnung): Ist der Kurzstil aktiv (``telegram_style=
  "kurzform"`` im ``display_config`` des Presets), erhält Telegram für eine
  amtliche Ortsvergleich-Warnung GENAU EINE Nachricht mit demselben kurzen
  Text wie die SMS-Variante (byte-identisch zu ``render_official_alert_sms``),
  OHNE reiche Vergleichs-Warnvorlage, mit ``parse_mode=None`` und OHNE
  Inline-Knöpfe. Bei ``rich`` (Default) bleibt die reiche Telegram-Vorlage
  (``parse_mode="HTML"``).
- AC-6 (reguläre Compare-Pfade bleiben E-Mail-only): Das Setzen von
  ``telegram_style`` erzeugt KEINEN neuen Telegram-/SMS-Versandweg. Die
  Kanal-Auflösung (``_effective_channels``) ignoriert den Style-Key; und ein
  amtlicher Dispatch mit ``effective_channels={"email"}`` fasst weder den
  Telegram- noch den SMS-Sink an — auch bei aktivem Kurzstil.
- Threading: ``_effective_telegram_style(preset)`` liest
  ``preset["display_config"]["telegram_style"]`` mit Default ``rich``.

KEINE Mocks als Verhaltensbeweis. Beobachtung des Versands über ECHTE lokale
HTTP-Aufzeichnungs-Server (recording sinks), wie in S3
(``test_telegram_kurzstil_trip_alert.py``): ein seven.io-SMS-Stub und ein
Telegram-Bot-API-Stub; ``TELEGRAM_API_BASE`` wird per monkeypatch auf den
lokalen Stub umgelenkt (Transport-Umlenkung, kein ``Mock``/``patch`` des
Verhaltens — bewiesen wird die real gesendete HTTP-Nutzlast).

RED-Ursache (vor der Implementierung):
- ``send_multi_location_official_alert`` / ``_dispatch_compare_official_telegram``
  kennen den Parameter ``telegram_style`` noch nicht → TypeError beim Aufruf.
- ``compare_official_alert._effective_telegram_style`` existiert noch nicht →
  ImportError.
"""
from __future__ import annotations

import http.server
import json
import socket
import threading
import urllib.parse
from collections import namedtuple
from datetime import datetime, timezone

import output.channels.telegram as tg_module
from app.config import Settings
from services.notification_service import NotificationService
from services.official_alerts.models import OfficialAlert


# ---------------------------------------------------------------------------
# Echte lokale Aufzeichnungs-Server (keine Mocks)
# ---------------------------------------------------------------------------

def _free_port() -> int:
    s = socket.socket()
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class _TelegramStub:
    """Lokaler HTTP-Stub für die Telegram-Bot-API. Zeichnet jede sendMessage-
    Nutzlast (text/parse_mode/reply_markup) auf und antwortet mit ok:true."""

    def __init__(self) -> None:
        self.sent: list[dict] = []
        sent = self.sent
        counter = {"mid": 3000}

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                try:
                    payload = json.loads(body.decode())
                except ValueError:
                    payload = {}
                sent.append(payload)
                counter["mid"] += 1
                resp = json.dumps(
                    {"ok": True, "result": {"message_id": counter["mid"]}}
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(resp)

            def log_message(self, *args):  # noqa: D401
                pass

        self.port = _free_port()
        self._server = http.server.HTTPServer(("127.0.0.1", self.port), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def stop(self) -> None:
        self._server.shutdown()


class _SMSStub:
    """Lokaler HTTP-Stub für seven.io — empfängt den echten POST von SMSOutput."""

    def __init__(self) -> None:
        self.received: list[dict] = []
        received = self.received

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                data = urllib.parse.parse_qs(body.decode())
                received.append({k: v[0] for k, v in data.items()})
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"100")

            def log_message(self, *args):  # noqa: D401
                pass

        self.port = _free_port()
        self._server = http.server.HTTPServer(("127.0.0.1", self.port), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()


# ---------------------------------------------------------------------------
# Fixture-Daten (echte DTOs, kein Netz)
# ---------------------------------------------------------------------------

_Loc = namedtuple("_Loc", ["id", "name", "lat", "lon"])


def _make_locations() -> list:
    return [
        _Loc(id="loc-a", name="Calenzana", lat=42.51, lon=8.85),
        _Loc(id="loc-b", name="Vizzavona", lat=42.11, lon=9.13),
    ]


def _make_tagged_alerts() -> list:
    alert = OfficialAlert(
        source="vigilance", hazard="thunderstorm", level=3,
        label="Gewitter & Sturm <stark>",
        valid_from=datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc),
        valid_to=datetime(2026, 5, 1, 20, 0, tzinfo=timezone.utc),
        region_label="Haute-Corse",
    )
    return [(alert, ["loc-a", "loc-b"])]


def _settings(*, sms_port: int) -> Settings:
    return Settings(
        telegram_bot_token="test-bot-token",
        telegram_chat_id="99999",
        sms_gateway_url=f"http://127.0.0.1:{sms_port}/api/sms",
        seven_api_key="test-stub-key",
        sms_to="+49000000000",
        sms_from=None,
    )


# ---------------------------------------------------------------------------
# AC-5 — Amtliche Compare-Warnung im Kurzstil
# ---------------------------------------------------------------------------

class TestAC5CompareOfficialKurzstil:
    def test_kurzform_telegram_body_equals_official_sms(self, monkeypatch) -> None:
        tg_stub = _TelegramStub()
        sms_stub = _SMSStub()
        try:
            monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", tg_stub.base_url)
            settings = _settings(sms_port=sms_stub.port)
            svc = NotificationService(settings=settings, user_id="tdd-1260-cmp-off-a")

            # RED: send_multi_location_official_alert kennt telegram_style noch
            # nicht → TypeError.
            svc.send_multi_location_official_alert(
                "Korsika-Vergleich",
                _make_locations(),
                _make_tagged_alerts(),
                {"telegram", "sms"},
                telegram_style="kurzform",
            )

            assert len(tg_stub.sent) == 1, (
                "RED: Kurzstil muss GENAU EINE Telegram-Nachricht senden, "
                f"gesendet wurden {len(tg_stub.sent)}."
            )
            assert len(sms_stub.received) == 1
            payload = tg_stub.sent[0]
            sms_text = sms_stub.received[0]["text"]
            assert sms_text, "Setup: amtlicher Compare-SMS-Text darf nicht leer sein."
            assert "parse_mode" not in payload, (
                "RED: amtliche Compare-Warnung im Kurzstil muss parse_mode=None "
                f"nutzen; gefunden parse_mode={payload.get('parse_mode')!r}."
            )
            assert "reply_markup" not in payload, (
                "RED: Kurzstil darf keine Inline-Knöpfe (reply_markup) mitsenden."
            )
            assert payload.get("text") == sms_text, (
                "RED: Telegram-Body der amtlichen Compare-Warnung im Kurzstil ist "
                "nicht identisch zum render_official_alert_sms-Text.\n"
                f"  Telegram={payload.get('text')!r}\n  SMS={sms_text!r}"
            )
        finally:
            tg_stub.stop()
            sms_stub.stop()

    def test_rich_sends_html_official_compare_telegram(self, monkeypatch) -> None:
        tg_stub = _TelegramStub()
        try:
            monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", tg_stub.base_url)
            settings = _settings(sms_port=_free_port())
            svc = NotificationService(settings=settings, user_id="tdd-1260-cmp-off-b")

            svc.send_multi_location_official_alert(
                "Korsika-Vergleich",
                _make_locations(),
                _make_tagged_alerts(),
                {"telegram"},
                telegram_style="rich",
            )

            assert len(tg_stub.sent) == 1
            assert tg_stub.sent[0].get("parse_mode") == "HTML", (
                "Regression: rich/Default muss die reiche Compare-Warnvorlage "
                f"(parse_mode='HTML') senden; gefunden "
                f"{tg_stub.sent[0].get('parse_mode')!r}."
            )
        finally:
            tg_stub.stop()


# ---------------------------------------------------------------------------
# AC-6 — reguläre Compare-Pfade bleiben E-Mail-only trotz gesetztem Style
# ---------------------------------------------------------------------------

class TestAC6RegularCompareStaysEmailOnly:
    def test_effective_channels_ignores_telegram_style(self) -> None:
        """Der Kurzstil-Key im display_config darf NIE einen Telegram-/SMS-Kanal
        aktivieren — er ist reine Darstellungs-Präferenz, kein Opt-in."""
        from services.compare_official_alert import CompareOfficialAlertService

        svc = CompareOfficialAlertService(
            settings=_settings(sms_port=_free_port()), user_id="tdd-1260-cmp-chan",
        )
        preset = {
            "id": "p1", "name": "Nur-Style",
            "display_config": {"telegram_style": "kurzform"},
            # KEIN send_telegram / send_sms Opt-in.
        }
        assert svc._effective_channels(preset) == {"email"}, (
            "AC-6: telegram_style darf die Kanal-Auflösung nicht beeinflussen — "
            "ohne send_telegram/send_sms-Opt-in bleibt es E-Mail-only."
        )

    def test_email_only_dispatch_never_touches_telegram_or_sms(self, monkeypatch) -> None:
        """Selbst mit aktivem Kurzstil fabriziert der amtliche Dispatch keinen
        Telegram-/SMS-Versand, wenn nur ``email`` in den effective_channels ist."""
        tg_stub = _TelegramStub()
        sms_stub = _SMSStub()
        mails: list = []
        try:
            monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", tg_stub.base_url)
            settings = _settings(sms_port=sms_stub.port)
            svc = NotificationService(settings=settings, user_id="tdd-1260-cmp-eo")

            svc.send_multi_location_official_alert(
                "Korsika-Vergleich",
                _make_locations(),
                _make_tagged_alerts(),
                {"email"},
                telegram_style="kurzform",
                mail_sink=lambda subject, body: mails.append((subject, body)),
            )

            assert len(mails) == 1, "E-Mail-Pfad muss weiterhin zustellen."
            assert tg_stub.sent == [], (
                "AC-6: E-Mail-only-Dispatch darf trotz Kurzstil KEINEN Telegram-"
                f"Versand auslösen; gefunden {tg_stub.sent!r}."
            )
            assert sms_stub.received == [], (
                "AC-6: E-Mail-only-Dispatch darf trotz Kurzstil KEINEN SMS-"
                f"Versand auslösen; gefunden {sms_stub.received!r}."
            )
        finally:
            tg_stub.stop()
            sms_stub.stop()


# ---------------------------------------------------------------------------
# Threading — _effective_telegram_style liest display_config (Default rich)
# ---------------------------------------------------------------------------

class TestEffectiveTelegramStyleResolver:
    def test_reads_display_config_and_defaults_rich(self) -> None:
        # RED: _effective_telegram_style existiert noch nicht → ImportError.
        from services.compare_official_alert import _effective_telegram_style

        assert _effective_telegram_style(
            {"display_config": {"telegram_style": "kurzform"}}
        ) == "kurzform"
        # Kein display_config → Default rich.
        assert _effective_telegram_style({"id": "p"}) == "rich"
        # display_config vorhanden, aber ohne den Key → Default rich.
        assert _effective_telegram_style({"display_config": {"channels": []}}) == "rich"
        # display_config explizit None → Default rich (kein Crash).
        assert _effective_telegram_style({"display_config": None}) == "rich"
