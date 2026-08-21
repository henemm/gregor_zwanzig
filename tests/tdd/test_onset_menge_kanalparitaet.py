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
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

import output.channels.telegram as tg_module
from app.config import Settings
from app.models import TripReportConfig
from output.renderers.alert.model import AlertMessage, OnsetEvent
from output.renderers.alert.project import to_multi_location_onset_alert_message
from output.renderers.alert.render import render_sms
from services.notification_service import NotificationService, RadarAlertRequest
from services.radar_service import NowcastResult

from tests.helpers.briefing_zeiten import briefing_zeiten_fuer_trip
from tests.helpers.nowcast_gate_fixtures import (
    TRIP_ZONE, clean_uid, fresh_uid, make_trip, quiet_window_elsewhere,
    radar_service, reset_radar_cache,
)

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
# AC-1/AC-7 am WIRKORT — der echte Trip-Produktivpfad (Adversary-Finding F001)
#
# Dieser Test prueft die Wirkkette an der Stelle, an der sie WIRKT: der
# einzige Produktivpfad, der im Trip-Betrieb einen `RadarAlertRequest` baut,
# ist `TripAlertService.check_radar_alerts()` (trip_alert.py). Die Tests
# oben konstruieren den Request selbst und beweisen daher nur den Baustein,
# nicht die Verdrahtung — genau diese Luecke fand der Adversary (F001):
# `onset_precip_mm=result.onset_precip_mm` liess sich auf `None` setzen,
# ohne dass ein einziger Test rot wurde.
#
# Kein Baustein wird uebersprungen: echte Radar-Frames -> echter
# `RadarNowcastService` -> echtes `NowcastResult` -> echtes
# `check_radar_alerts()` -> echter `NotificationService` -> echter
# Telegram-Transport -> Nutzlast am Draht. Der Kurzstil-Telegram-Zweig
# sendet den bereits gerenderten `sms_body` (notification_service.py),
# also misst der Draht exakt den Text, den SMS und Premium-SMS ebenfalls
# bekommen (AC-7) — ohne echten SMS-Versand auszuloesen.
# ---------------------------------------------------------------------------


class _DeterministischeOnsetFrames:
    """Echter aufrufbarer `frame_source` (kein Mock): ZWEI nasse, nicht
    konvektive Frames im 15-Minuten-Raster ab `onset_minutes`.

    Die Menge ab dem Beginn ist damit von Hand nachrechenbar und haengt an
    keiner Wanduhrzeit:
      * Frame 1 bei +20 Min, 3.0 mm/h, Deckung bis zum Nachbarn (15 Min,
        = `_MAX_FRAME_COVERAGE`) -> 0.75 mm
      * Frame 2 bei +35 Min, 3.0 mm/h, letzter Frame, auf
        `_MAX_FRAME_COVERAGE` gedeckelt -> 0.75 mm
      * Summe = 1.5 mm -> Token `R1.5@HH:MM`
    """

    RATE_MM_H = 3.0
    ERWARTETE_MENGE = "1.5"

    def __init__(self, onset_minutes: int = 20) -> None:
        self._onset = onset_minutes
        self.calls: list[tuple[float, float]] = []

    def __call__(self, lat: float, lon: float) -> list:
        from providers.brightsky import RadarFrame

        self.calls.append((lat, lon))
        ts = datetime.now(timezone.utc) + timedelta(minutes=self._onset)
        return [
            RadarFrame(
                timestamp=ts, precip_mm_h=self.RATE_MM_H, is_convective=False,
            ),
            RadarFrame(
                timestamp=ts + timedelta(minutes=15),
                precip_mm_h=self.RATE_MM_H, is_convective=False,
            ),
        ]


class _SpaeterOnsetFrames:
    """Echter aufrufbarer `frame_source` (kein Mock) mit SPAETEM Beginn — der
    fachliche Kernfall des Tickets (Adversary-Finding F003).

    `_DeterministischeOnsetFrames` oben kann die beiden Mengenfelder gar nicht
    unterscheiden: bei einem Beginn nach 20 Minuten liegen alle nassen Frames
    in BEIDEN Fenstern (`[jetzt, jetzt+60]` und `[Beginn, Beginn+60]`), beide
    Felder tragen denselben Wert. Erst ein Beginn kurz vor der Alarmschwelle
    (`RADAR_ONSET_THRESHOLD_MIN = 55`) trennt sie.

    Raster: ein trockener Frame bei +5, dann durchgehend Regen mit 3.0 mm/h ab
    +50 im 15-Minuten-Takt bis +125. Beide Zahlen von Hand hergeleitet
    (`_MAX_FRAME_COVERAGE` = 15 Min, Fensterende ausschliessend, Dauer je
    Frame bis zum eigenen naechsten Nachbarn):

      Menge AB JETZT (`window_precip_mm`, Fenster `[+0, +60)`) — FALSCH fuer
      die Anzeige, dient hier als Gegenprobe:
        * +5  (0.0 mm/h): Deckung bis +20 -> 0.00 mm
        * +50 (3.0 mm/h): Nachbar +65, aber Fensterende +60 kappt -> 10 Min
                          -> 3.0 * 10/60 = 0.50 mm
        * Summe = 0.5 mm  -> Token waere `R0.5@…`

      Menge AB DEM BEGINN (`onset_precip_mm`, Fenster `[+50, +110)`) — die
      Zahl, die in die Kurznachricht gehoert:
        * +50 -> Nachbar +65   -> 15 Min -> 0.75 mm
        * +65 -> Nachbar +80   -> 15 Min -> 0.75 mm
        * +80 -> Nachbar +95   -> 15 Min -> 0.75 mm
        * +95 -> Nachbar +110, zugleich Fensterende -> 15 Min -> 0.75 mm
        * +110/+125 liegen AUSSERHALB (Grenze ausschliessend) -> 0.00 mm
        * Summe = 3.0 mm  -> Token `R3.0@…`

    Faktor 6 zwischen den beiden Feldern: eine Vertauschung von
    `onset_precip_mm` gegen `window_precip_mm` am Wirkort faellt damit sofort
    auf. `onset_minutes = 50` liegt bewusst unter der Alarmschwelle 55, der
    Alarm loest also ueberhaupt aus; die Spitzenrate 3.0 mm/h ergibt im
    180-Minuten-Fenster weiterhin "Mäßiger Regen".
    """

    RATE_MM_H = 3.0
    ONSET_MIN = 50
    ERWARTETE_MENGE_AB_BEGINN = "3.0"
    ERWARTETE_MENGE_AB_JETZT = "0.5"

    def __init__(self) -> None:
        self.calls: list[tuple[float, float]] = []

    def __call__(self, lat: float, lon: float) -> list:
        from providers.brightsky import RadarFrame

        self.calls.append((lat, lon))
        jetzt = datetime.now(timezone.utc)
        frames = [
            RadarFrame(
                timestamp=jetzt + timedelta(minutes=5), precip_mm_h=0.0,
                is_convective=False,
            ),
        ]
        for minute in (50, 65, 80, 95, 110, 125):
            frames.append(
                RadarFrame(
                    timestamp=jetzt + timedelta(minutes=minute),
                    precip_mm_h=self.RATE_MM_H, is_convective=False,
                )
            )
        return frames


def _telegram_kurzform_settings() -> Settings:
    """Nur Telegram sendebereit — E-Mail, SMS und Premium-SMS ausdruecklich
    AUS (jedes weggelassene Feld faellt sonst still auf die Prod-`.env` des
    Arbeitsverzeichnisses zurueck, #1477). `telegram_test_chat_id` ist
    Pflicht fuer die Herkunftssperre aus einem Nicht-Prod-Checkout."""
    return Settings(
        smtp_host=None, smtp_user=None, smtp_pass=None, mail_to=None,
        telegram_bot_token="test-token-2046-f001",
        telegram_chat_id="99999", telegram_test_chat_id="99999",
        sms_gateway_url="", seven_api_key="", seven_sandbox_key="",
        sms_to="", sms_from=None,
        premium_sms_reply_to=None, premium_sms_reply_at=None,
    )


def _kurznachricht_vom_echten_trip_pfad(frames, telegram_stub, monkeypatch, suffix):
    """Faehrt den ECHTEN Trip-Produktivpfad und gibt den Text zurueck, der am
    Draht ankam. Kein Baustein wird uebersprungen: echte Radar-Frames ->
    echter `RadarNowcastService` -> echtes `NowcastResult` -> echtes
    `check_radar_alerts()` -> echter `NotificationService` -> echter
    Telegram-Transport."""
    from app.loader import save_trip
    from services.trip_alert import TripAlertService

    monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", telegram_stub.base_url)

    uid, trip_id = fresh_uid(f"2046-{suffix}"), f"trip-2046-{suffix}"
    clean_uid(uid)
    reset_radar_cache()
    try:
        quiet_from, quiet_to = quiet_window_elsewhere(zone=TRIP_ZONE)
        trip = make_trip(
            trip_id, cooldown_minutes=0, quiet_from=quiet_from, quiet_to=quiet_to,
        )
        morgen, abend = briefing_zeiten_fuer_trip(trip)
        trip.report_config = TripReportConfig(
            trip_id=trip_id, send_email=False, send_sms=False,
            send_telegram=True, send_premium_sms=False,
            alert_on_changes=True, telegram_style="kurzform",
            morning_time=morgen, evening_time=abend,
        )
        # Der PRODUKTIVE Speicherer (`app.loader.save_trip`), nicht der
        # verkuerzte Test-Helfer: nur er schreibt `telegram_style` mit, und
        # `check_radar_alerts()` liest den Trip von Platte zurueck.
        save_trip(trip, user_id=uid)

        svc = TripAlertService(
            settings=_telegram_kurzform_settings(), throttle_hours=0,
            user_id=uid, radar_service=radar_service(frames),
        )

        sent = svc.check_radar_alerts()

        assert sent == 1, (
            f"Voraussetzung: genau EIN Radar-Alarm erwartet, war {sent}. "
            f"Nowcast-Abrufe: {frames.calls!r}"
        )
        assert len(telegram_stub.sent) == 1, (
            f"Erwartet genau EINE Kurznachricht am Draht: {telegram_stub.sent!r}"
        )
        return telegram_stub.sent[0].get("text") or ""
    finally:
        clean_uid(uid)


def test_ac1_der_echte_trip_pfad_stellt_die_menge_zu(telegram_stub, monkeypatch):
    """AC-1/AC-7 GIVEN einen Trip mit aktivem Segment, dessen ECHTER
    Nowcast-Abruf aus echten Radar-Frames ein `NowcastResult` mit
    `onset_precip_mm == 1.5` ableitet (2 x 3.0 mm/h x 15 Min)
    WHEN `TripAlertService.check_radar_alerts()` laeuft — der einzige
    Produktivpfad, der im Trip-Betrieb einen `RadarAlertRequest` baut —
    THEN traegt die TATSAECHLICH abgesetzte Kurznachricht am Draht das
    Token `R1.5@HH:MM`, nicht die zahlenlose Alt-Form `R@HH:MM`.

    Wirkort-Nachweis (Adversary-Finding F001): kein direkt konstruierter
    `RadarAlertRequest`. Wird die Durchreichung in `trip_alert.py`
    (`onset_precip_mm=result.onset_precip_mm`) entfernt, faellt der Text auf
    `R@HH:MM` zurueck und dieser Test wird rot.

    Frueher Beginn (+20 Min) — beide Mengenfelder tragen hier denselben Wert.
    Die UNTERSCHEIDUNG der beiden Felder leistet der Test darunter
    (`…_bei_spaetem_beginn_…`, Adversary-Finding F003).
    """
    frames = _DeterministischeOnsetFrames()
    text = _kurznachricht_vom_echten_trip_pfad(
        frames, telegram_stub, monkeypatch, "f001",
    )

    assert re.search(r"\bR1\.5@\d{1,2}:\d{2}", text), (
        "F001: der echte Trip-Produktivpfad reicht die Mengenangabe nicht "
        f"bis zur abgesetzten Kurznachricht durch: {text!r}"
    )
    assert not re.search(r"\bR@\d{1,2}:\d{2}", text), (
        f"Die zahlenlose Alt-Form steht noch im Text: {text!r}"
    )
    assert _MENGEN_TOKEN_RE.search(text), (
        f"Der Mengen-Token ist beschaedigt: {text!r}"
    )


def test_ac1_bei_spaetem_beginn_zeigt_der_trip_pfad_die_menge_ab_beginn(
    telegram_stub, monkeypatch,
):
    """AC-1 GIVEN einen Trip, dessen ECHTER Nowcast-Abruf einen SPAETEN
    Beginn liefert (+50 Min, knapp unter der Alarmschwelle 55) mit
    durchgehendem Regen von 3.0 mm/h bis +125 Min
    WHEN `TripAlertService.check_radar_alerts()` laeuft
    THEN traegt die abgesetzte Kurznachricht `R3.0@HH:MM` — die Menge der
    Stunde AB DEM BEGINN — und ausdruecklich NICHT `R0.5@HH:MM`, die Menge
    der Stunde ab jetzt.

    Das ist der fachliche Kernfall des Tickets: der Alarm feuert bis zu
    `RADAR_ONSET_THRESHOLD_MIN` (55) Minuten VOR dem Beginn; das Fenster
    „ab jetzt" deckt dann fast nur Trockenzeit ab und untertreibt die Menge
    systematisch — hier um den Faktor 6.

    Wirkort-Nachweis (Adversary-Finding F003): der Test oben kann die beiden
    Felder nicht unterscheiden (frueher Beginn -> beide Fenster deckungs-
    gleich). Wird in `trip_alert.py` `onset_precip_mm=result.onset_precip_mm`
    gegen `result.window_precip_mm` vertauscht, wird DIESER Test rot.

    Beide Zahlen sind aus den Frames hergeleitet, nicht aus der
    Implementierung abgeschrieben — Rechenweg im Docstring von
    `_SpaeterOnsetFrames`.
    """
    frames = _SpaeterOnsetFrames()
    text = _kurznachricht_vom_echten_trip_pfad(
        frames, telegram_stub, monkeypatch, "f003",
    )

    erwartet = frames.ERWARTETE_MENGE_AB_BEGINN   # "3.0" — ab dem Beginn
    falsch = frames.ERWARTETE_MENGE_AB_JETZT      # "0.5" — ab jetzt

    assert re.search(rf"\bR{re.escape(erwartet)}@\d{{1,2}}:\d{{2}}", text), (
        f"F003: die Kurznachricht muss die Menge AB DEM BEGINN nennen "
        f"(R{erwartet}@HH:MM = 4 x 3.0 mm/h x 15 Min im Fenster "
        f"[Beginn, Beginn+60min)): {text!r}"
    )
    assert not re.search(rf"\bR{re.escape(falsch)}@\d{{1,2}}:\d{{2}}", text), (
        f"F003: die Kurznachricht zeigt die Menge AB JETZT (R{falsch}@HH:MM) "
        f"statt der Menge ab dem Beginn — bei spaetem Beginn deckt das "
        f"Fenster ab jetzt fast nur Trockenzeit ab: {text!r}"
    )
    assert not re.search(r"\bR@\d{1,2}:\d{2}", text), (
        f"Die zahlenlose Alt-Form steht noch im Text: {text!r}"
    )


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
