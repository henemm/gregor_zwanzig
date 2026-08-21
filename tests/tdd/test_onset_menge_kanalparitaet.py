"""TDD RED — Issue #2046: die Mengenangabe erreicht ALLE Kurzkanaele und
sprengt das Zeichenbudget nicht.

SPEC: docs/specs/modules/fix_2046_onset_menge.md — AC-6 (Ortsvergleich-
Bündelpfad fuehrt dieselbe Zahl wie der Trip-Pfad), AC-7 (SMS, Premium-SMS
und Telegram im Kurzstil zeigen denselben Text), AC-9 (Zeichenbudget im
Extremfall).

Warum das zaehlt: auf der Huette am Karnischen Hoehenweg kommt NUR
Premium-SMS (Garmin inReach) an — eine Zahl, die diesen Kanal nicht erreicht,
erreicht dort niemanden. Und der Ortsvergleich-Radarpfad baut sein
`OnsetEvent` an einer ZWEITEN Stelle (`project.to_multi_location_onset_
alert_message`); wird die Zahl nur im Trip-Pfad durchgereicht, entsteht dort
eine stille Luecke.

Mock-frei: echte lokale HTTP-Aufzeichnungs-Server fuer seven.io (SMS UND
Premium-SMS) und die Telegram-Bot-API, echter `NotificationService`-Lauf ueber
`send_radar_alert()`, echter Buendel-Konstruktor. Kein `Mock()`/`patch()` von
Verhalten, kein externes Netz, kein echter Versand.
"""
from __future__ import annotations

import http.server
import json
import re
import socket
import threading
import urllib.parse
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

import output.channels.telegram as tg_module
from app.config import Settings
from output.renderers.alert.model import AlertMessage, OnsetEvent
from output.renderers.alert.project import to_multi_location_onset_alert_message
from output.renderers.alert.render import render_sms
from services.notification_service import NotificationService, RadarAlertRequest
from services.radar_service import NowcastResult

from tests.helpers.nowcast_gate_fixtures import clean_uid, fresh_uid, make_trip

SMS_TO = "+49000000000"
PREMIUM_REPLY_TO = "+4915799912345"
# Regen-Mengen-Token: Kuerzel, Zahl mit einer Nachkommastelle, dann die Zeit.
_MENGEN_TOKEN_RE = re.compile(r"\bR\d+\.\d@\d{1,2}:\d{2}\b")


def _free_port() -> int:
    probe = socket.socket()
    probe.bind(("", 0))
    port = probe.getsockname()[1]
    probe.close()
    return port


class _SevenIoStub:
    """Lokaler HTTP-Server, der die seven.io-POSTs von SMS UND Premium-SMS
    entgegennimmt (Vorbild `test_alert_addendum_sms.py`). Kein Mock: der echte
    Transport laeuft, die Nutzlast wird am Draht gemessen."""

    def __init__(self) -> None:
        self.received: list[dict] = []
        received = self.received

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("Content-Length", 0))
                data = urllib.parse.parse_qs(self.rfile.read(length).decode())
                received.append({k: v[0] for k, v in data.items()})
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"100")

            def log_message(self, *args):  # noqa: D401
                pass

        self.port = _free_port()
        self._server = http.server.HTTPServer(("127.0.0.1", self.port), Handler)
        threading.Thread(target=self._server.serve_forever, daemon=True).start()

    def stop(self) -> None:
        self._server.shutdown()


class _TelegramStub:
    """Lokaler HTTP-Stub der Telegram-Bot-API (Vorbild
    `test_radar_alert_telegram_style.py`) — zeichnet jede `sendMessage`-
    Nutzlast auf."""

    def __init__(self) -> None:
        self.sent: list[dict] = []
        sent = self.sent

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("Content-Length", 0))
                try:
                    payload = json.loads(self.rfile.read(length).decode())
                except ValueError:
                    payload = {}
                sent.append(payload)
                body = json.dumps(
                    {"ok": True, "result": {"message_id": 4711}}
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):  # noqa: D401
                pass

        self.port = _free_port()
        self._server = http.server.HTTPServer(("127.0.0.1", self.port), Handler)
        threading.Thread(target=self._server.serve_forever, daemon=True).start()

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def stop(self) -> None:
        self._server.shutdown()


@pytest.fixture()
def seven_io_stub():
    stub = _SevenIoStub()
    yield stub
    stub.stop()


@pytest.fixture()
def telegram_stub():
    stub = _TelegramStub()
    yield stub
    stub.stop()


def _drei_kanal_settings(seven_port: int) -> Settings:
    """SMS, Premium-SMS und Telegram sendebereit, E-Mail bewusst aus.

    `seven_api_key == seven_sandbox_key` haelt beide Sicherheitssperren des
    seven.io-Transports zufrieden; `telegram_test_chat_id` ist Pflicht fuer die
    Herkunftssperre des Telegram-Kanals aus einem Nicht-Prod-Checkout.
    """
    return Settings(
        sms_gateway_url=f"http://127.0.0.1:{seven_port}/api/sms",
        seven_api_key="sandbox-key-2046",
        seven_sandbox_key="sandbox-key-2046",
        sms_to=SMS_TO, sms_from=None,
        premium_sms_reply_to=PREMIUM_REPLY_TO,
        premium_sms_reply_at=datetime.now(timezone.utc),
        telegram_bot_token="test-token-2046",
        telegram_chat_id="99999", telegram_test_chat_id="99999",
        smtp_host=None, smtp_user=None, smtp_pass=None, mail_to=None,
    )


# ---------------------------------------------------------------------------
# AC-6 — der Ortsvergleich-Bündelpfad fuehrt dieselbe Zahl
# ---------------------------------------------------------------------------


def test_ac6_ortsvergleich_buendel_traegt_dieselbe_menge_wie_der_trip_pfad():
    """AC-6 GIVEN einen Ortsvergleich-Bündel-Onset-Alarm mit ZWEI Orten,
    dessen fuehrendes Ereignis `onset_precip_mm=1.8` traegt
    WHEN `to_multi_location_onset_alert_message` die Nachricht baut und
    `render_sms(msg)` sie rendert
    THEN enthaelt der Text `R1.8@…` — dieselbe Zahl und dieselbe Formatregel
    wie im Trip-Pfad (AC-1), nicht bloss eine leere Kurzform mit Ortsnamen.

    Wanduhrfest: der Buendel-Konstruktor leitet `onset_time` aus
    `datetime.now()` ab, deshalb Strukturpruefung der Uhrzeit und exakte
    Pruefung nur an Kopf und Zahl.

    RED heute: `NowcastResult` kennt `onset_precip_mm` nicht (`TypeError`)."""
    fuehrend = NowcastResult(
        onset_minutes=20, intensity_label="Mäßiger Regen", source="radar",
        is_convective=False, onset_precip_mm=1.8,
    )
    zweiter = NowcastResult(
        onset_minutes=35, intensity_label="Leichter Regen", source="AROME-FR",
        is_convective=False, onset_precip_mm=0.4,
    )

    msg = to_multi_location_onset_alert_message(
        [("Zermatt", fuehrend), ("Chamonix", zweiter)],
        tz=timezone.utc, stand_at="10:00",
    )
    sms = render_sms(msg)

    assert sms.startswith("Zermatt: "), (
        f"Voraussetzung: der Kopf ist der Ortsname des fuehrenden Events: "
        f"{sms!r}"
    )
    assert re.search(r"\bR1\.8@\d{1,2}:\d{2}", sms), (
        f"RED: die Menge des fuehrenden Ortes fehlt in der Buendel-Kurzform: "
        f"{sms!r}"
    )
    assert "R@" not in sms, (
        f"Der Vergleichspfad zeigt noch die zahlenlose Alt-Form: {sms!r}"
    )


# ---------------------------------------------------------------------------
# AC-7 — SMS, Premium-SMS und Telegram-Kurzstil zeigen denselben Text
# ---------------------------------------------------------------------------


def test_ac7_sms_premium_sms_und_telegram_kurzstil_zeigen_dieselbe_menge(
    seven_io_stub, telegram_stub, monkeypatch,
):
    """AC-7 GIVEN dieselben Onset-Ereignisse fuer SMS, Premium-SMS und
    Telegram im Kurzstil (`onset_precip_mm=2.5`, `onset_time="16:45"`)
    WHEN `send_radar_alert(...)` alle drei konfigurierten Kanaele bedient
    THEN zeigen ALLE DREI denselben Token-Text INKLUSIVE Menge — kein Kanal
    zeigt eine andere Zahl, keiner laesst sie aus.

    Die Zusicherung ist der VERGLEICH der drei tatsaechlich abgesetzten
    Nutzlasten, gemessen am Draht der lokalen Aufzeichnungs-Server.

    RED heute: `RadarAlertRequest` kennt `onset_precip_mm` nicht
    (`TypeError`)."""
    monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", telegram_stub.base_url)

    uid = fresh_uid("2046-ac7")
    clean_uid(uid)
    try:
        settings = _drei_kanal_settings(seven_io_stub.port)
        svc = NotificationService(settings, uid)

        svc.send_radar_alert(
            trip=make_trip("trip-2046-ac7"),
            request=RadarAlertRequest(
                onset_minutes=25, onset_time="16:45", km_from=0.0, km_to=6.0,
                is_convective=False, intensity_label="Mäßiger Regen",
                source_label="Radar (DWD)", tz=ZoneInfo("Europe/Vienna"),
                segment_id="Ziel", onset_precip_mm=2.5,
            ),
            source="Radar (DWD)",
            cooldown_display="2 Stunden",
            effective_channels={"sms", "premium_sms", "telegram"},
            telegram_style="kurzform",
        )

        nach_ziel = {p.get("to"): p.get("text") for p in seven_io_stub.received}
        assert set(nach_ziel) == {SMS_TO, PREMIUM_REPLY_TO}, (
            "Erwartet je EINEN seven.io-POST fuer SMS und Premium-SMS, "
            f"empfangen: {seven_io_stub.received!r}"
        )
        assert len(telegram_stub.sent) == 1, (
            f"Erwartet genau EINE Telegram-Nachricht: {telegram_stub.sent!r}"
        )

        sms_text = nach_ziel[SMS_TO]
        premium_text = nach_ziel[PREMIUM_REPLY_TO]
        telegram_text = telegram_stub.sent[0].get("text") or ""

        assert "R2.5@16:45" in sms_text, (
            f"RED: die SMS nennt die Menge nicht: {sms_text!r}"
        )
        assert premium_text == sms_text, (
            "RED: Premium-SMS und SMS muessen denselben Renderer-Ausgang "
            f"tragen.\n  premium = {premium_text!r}\n  sms     = {sms_text!r}"
        )
        assert telegram_text == sms_text, (
            "RED: der Telegram-Kurzstil muss denselben Text tragen wie die "
            f"SMS.\n  telegram = {telegram_text!r}\n  sms      = {sms_text!r}"
        )
    finally:
        clean_uid(uid)


# ---------------------------------------------------------------------------
# AC-9 — Zeichenbudget im Extremfall
# ---------------------------------------------------------------------------


def test_ac9_langer_ortsname_mit_extremwert_bleibt_im_zeichenbudget():
    """AC-9 GIVEN einen Onset-Alarm mit einem 30 Zeichen langen Ortsnamen UND
    `onset_precip_mm=99.9` (Extremfall, maximale Zeichenlaenge der Zahl)
    WHEN `render_sms(msg, limit=140)` rendert
    THEN bleibt der Text unter 140 Zeichen, OHNE dass der harte Schnitt
    `body[:limit]` greift — die zusaetzliche Zahl verbraucht Zeichenbudget,
    reisst es bei realistischen Ortsnamen aber nicht.

    Reine Laengenpruefung plus Nachweis, dass die Zahl VOLLSTAENDIG dasteht
    (ein abgeschnittener Text bestuende die Laengenpruefung sonst trivial).

    RED heute: `OnsetEvent` kennt `onset_precip_mm` nicht (`TypeError`)."""
    ortsname = "Obertilliacher Bergwiesenalm"  # 28 Zeichen + Puffer unten
    ortsname = ortsname.ljust(30, "x")
    assert len(ortsname) == 30, "Voraussetzung: 30-Zeichen-Ortsname"

    event = OnsetEvent(
        onset_minutes=40, onset_time="18:00", km_from=0.0, km_to=0.0,
        is_convective=False, intensity_label="Starker Regen",
        source_label="Radar (DWD)", location_label=ortsname,
        onset_precip_mm=99.9,
    )
    msg = AlertMessage(
        trip_short="Alpen", stand_at="17:20", events=(event,),
        source="Radar (DWD)",
    )
    sms = render_sms(msg, limit=140)

    assert len(sms) <= 140, (
        f"RED: {len(sms)} Zeichen ueberschreiten das Render-Limit: {sms!r}"
    )
    assert "R99.9@18:00" in sms, (
        f"RED: der Extremwert steht nicht vollstaendig in der SMS: {sms!r}"
    )
    assert _MENGEN_TOKEN_RE.search(sms), (
        f"Der Mengen-Token ist beschaedigt oder abgeschnitten: {sms!r}"
    )
    assert sms.isascii(), f"Kurznachricht ist nicht ASCII-rein: {sms!r}"
