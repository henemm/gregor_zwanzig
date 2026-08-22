"""TDD RED — Issue #2051 S3: Reichweite und Guete tragen in Trip- UND
Ortsvergleich-Flaeche denselben Wortlaut und denselben Wert (ADR-0021).

SPEC: docs/specs/modules/feat_2051_s3_reichweite_und_guete.md — AC-14.

Warum das zaehlt: Trip und Ortsvergleich bauen ihr `OnsetEvent` an ZWEI
verschiedenen Stellen -- `NotificationService.send_radar_alert()` (Trip,
ueber `RadarAlertRequest`) und `to_multi_location_onset_alert_message()`
(Ortsvergleich-Buendel, ueber `NowcastResult`). Wird eines der beiden neuen
Felder (Reichweite, Guete) nur an einer der beiden Stellen durchgereicht,
entsteht in der anderen eine stille Luecke -- genau die Fehlerklasse, die
der Adversary bei #2046 (F001) fand.

Gespiegelt zu `tests/tdd/test_onset_menge_kanalparitaet.py` (Test-Plan der
Spec) -- DIESELBEN Werte einmal ueber den Trip-Pfad (`RadarAlertRequest` ->
`send_radar_alert`) und einmal ueber den Ortsvergleich-Pfad
(`to_multi_location_onset_alert_message`) gerendert.

Annahme (Abweichung von der Spec-Textstelle "Source", dort nicht explizit
benannt): `RadarAlertRequest` bekommt additiv `source_reach_time`/
`source_reach_day_offset` und `location_sharpness_limit_time`/
`location_sharpness_limit_day_offset`, exakt im Muster von
`event_end_time`/`event_end_day_offset` (S1) -- der einzige Weg, wie die
beiden neuen Werte ueberhaupt bis `send_radar_alert()` gelangen koennen,
ohne dass `RadarAlertRequest` intern Displaylogik nachbaut.

RED heute: `RadarAlertRequest`/`NowcastResult` kennen die neuen Felder nicht
-> `TypeError` bereits bei der Konstruktion.

Mock-frei: echter `NotificationService` gegen einen echten lokalen
Telegram-Bot-API-Stub (kein Mock, kein externes Netz), echte Projektion fuer
den Ortsvergleich-Pfad. Die Uhr steht per `freeze_time`, weil beide Pfade
ihre Uhrzeiten aus `datetime.now()` ableiten.
"""
from __future__ import annotations

import http.server
import inspect
import json
import re
import socket
import threading
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from freezegun import freeze_time

import output.channels.telegram as tg_module
from app.config import Settings
from output.renderers.alert.project import to_multi_location_onset_alert_message
from output.renderers.alert.render import render_sms, render_telegram
from services.notification_service import NotificationService, RadarAlertRequest
from services.radar_service import NowcastResult

from tests.helpers.nowcast_gate_fixtures import clean_uid, fresh_uid, make_trip

_TZ = ZoneInfo("Europe/Vienna")
# 18:00 Ortszeit Wien (= 16:00 UTC im Sommer).
_FROZEN_UTC = "2026-08-21 16:00:00+00:00"

# Beginn 20 Min (diesseits der 60-Min-Guete-Grenze, alarmfaehig) -> 18:20.
_ONSET_MIN = 20
_ONSET_HHMM = "18:20"
# Ende 150 Min (jenseits der Guete-Grenze), bekanntes Ende -> 20:30.
_ENDE_MIN = 150
_ENDE_HHMM = "20:30"
# Reichweite 170 Min -> 20:50.
_REACH_MIN = 170
_REACH_HHMM = "20:50"
# Guete-Grenzzeit now + 60 Min -> 19:00 (ausgeloest durch das Ende, 150 > 60).
_GUETE_HHMM = "19:00"

_LANGFORM_REACH_RE = re.compile(r"Radar reicht bis (\d{1,2}:\d{2})")
_LANGFORM_GUETE_RE = re.compile(r"Ortsangabe ab (\d{1,2}:\d{2}) unscharf")
_KURZFORM_GUETE_RE = re.compile(r"@(\d{1,2}:\d{2})\?")


def _free_port() -> int:
    probe = socket.socket()
    probe.bind(("", 0))
    port = probe.getsockname()[1]
    probe.close()
    return port


class _TelegramStub:
    """Lokaler HTTP-Stub der Telegram-Bot-API — zeichnet jede
    `sendMessage`-Nutzlast auf (kein Mock, kein externes Netz)."""

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


def _telegram_only_settings(marke: str) -> Settings:
    """Nur Telegram sendebereit -- E-Mail, SMS und Premium-SMS ausdruecklich
    AUS (jedes weggelassene Feld faellt sonst still auf die Prod-`.env`
    zurueck, #1477)."""
    return Settings(
        smtp_host=None, smtp_user=None, smtp_pass=None, mail_to=None,
        telegram_bot_token=f"test-token-2051-s3-{marke}",
        telegram_chat_id="99999", telegram_test_chat_id="99999",
        sms_gateway_url="", seven_api_key="", seven_sandbox_key="",
        sms_to="", sms_from=None,
        premium_sms_reply_to=None, premium_sms_reply_at=None,
    )


def _trip_pfad_request() -> RadarAlertRequest:
    """DIESELBEN Werte wie der Ortsvergleich-Pfad, direkt als
    `RadarAlertRequest`-Felder (Muster `event_end_time`, S1)."""
    return RadarAlertRequest(
        onset_minutes=_ONSET_MIN, onset_time=_ONSET_HHMM, km_from=0.0, km_to=6.0,
        is_convective=False, intensity_label="Mäßiger Regen",
        source_label="Radar (DWD)", tz=_TZ, segment_id="Ziel",
        event_end_time=_ENDE_HHMM, event_ongoing_beyond_horizon=False,
        source_reach_time=_REACH_HHMM,
        location_sharpness_limit_time=_GUETE_HHMM,
    )


def _ortsvergleich_pfad_nowcast() -> NowcastResult:
    """DIESELBEN Werte als Minutenangaben -- die Quelle, aus der
    `to_multi_location_onset_alert_message` sein `OnsetEvent` baut."""
    return NowcastResult(
        onset_minutes=_ONSET_MIN, intensity_label="Mäßiger Regen",
        source="radar", is_convective=False,
        event_end_minutes=_ENDE_MIN, event_ongoing_beyond_horizon=False,
        source_reach_minutes=_REACH_MIN,
    )


def test_prueling_stammt_aus_diesem_arbeitsbaum():
    """Vorbedingung (kein AC): Projektion, Renderer und Benachrichtigungs-
    dienst werden RELATIV ZU DIESER Testdatei aufgeloest."""
    from output.renderers.alert import project as project_module
    from output.renderers.alert import render as render_module
    from services import notification_service as notif_module

    arbeitsbaum = Path(__file__).resolve().parents[2]
    for modul in (project_module, render_module, notif_module):
        modul_pfad = Path(inspect.getfile(modul)).resolve()
        assert modul_pfad.is_relative_to(arbeitsbaum), (
            f"Prueling stammt nicht aus diesem Arbeitsbaum: {modul_pfad}"
        )


# ---------------------------------------------------------------------------
# AC-14 -- Langform: Trip und Ortsvergleich nennen dieselben Werte
# ---------------------------------------------------------------------------


@freeze_time(_FROZEN_UTC)
def test_ac14_langform_traegt_in_beiden_flaechen_reichweite_und_guete(monkeypatch):
    """AC-14 GIVEN denselben Onset-Alarm einmal ueber den Trip-Pfad
    (`RadarAlertRequest` -> `NotificationService.send_radar_alert`) und
    einmal ueber den Ortsvergleich-Pfad
    (`to_multi_location_onset_alert_message`) gerendert
    WHEN beide Pfade dieselben Werte erhalten
    THEN tragen Reichweiten- UND Guete-Angabe in BEIDEN Flaechen denselben
    Wortlaut und denselben Wert (`Radar reicht bis 20:50`,
    `Ortsangabe ab 19:00 unscharf`).

    RED heute: `RadarAlertRequest`/`NowcastResult` kennen die neuen Felder
    nicht (`TypeError`)."""
    stub = _TelegramStub()
    monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", stub.base_url)
    try:
        uid = fresh_uid("2051-s3-par-rich")
        clean_uid(uid)
        try:
            svc = NotificationService(_telegram_only_settings("rich"), uid)
            svc.send_radar_alert(
                trip=make_trip("trip-2051-s3-par-rich"),
                request=_trip_pfad_request(),
                source="Radar (DWD)",
                cooldown_display="2 Stunden",
                effective_channels={"telegram"},
                telegram_style="rich",
            )
        finally:
            clean_uid(uid)

        assert len(stub.sent) == 1, (
            f"Erwartet genau EINE Trip-Nachricht am Draht: {stub.sent!r}"
        )
        trip_text = stub.sent[0].get("text") or ""
    finally:
        stub.stop()

    cmp_msg = to_multi_location_onset_alert_message(
        [("Reykjavik", _ortsvergleich_pfad_nowcast())], tz=_TZ, stand_at="10:00",
    )
    cmp_text = render_telegram(cmp_msg)

    trip_reach = _LANGFORM_REACH_RE.search(trip_text)
    cmp_reach = _LANGFORM_REACH_RE.search(cmp_text)
    assert trip_reach and cmp_reach, (
        f"RED: mindestens eine Flaeche nennt die Reichweite nicht.\n"
        f"  Trip          = {trip_text!r}\n  Ortsvergleich = {cmp_text!r}"
    )
    assert trip_reach.group(1) == cmp_reach.group(1) == _REACH_HHMM, (
        f"Trip und Ortsvergleich nennen unterschiedliche Reichweiten:\n"
        f"  Trip          = {trip_reach.group(1)}\n"
        f"  Ortsvergleich = {cmp_reach.group(1)}"
    )

    trip_guete = _LANGFORM_GUETE_RE.search(trip_text)
    cmp_guete = _LANGFORM_GUETE_RE.search(cmp_text)
    assert trip_guete and cmp_guete, (
        f"RED: mindestens eine Flaeche nennt die Guete-Zeile nicht.\n"
        f"  Trip          = {trip_text!r}\n  Ortsvergleich = {cmp_text!r}"
    )
    assert trip_guete.group(1) == cmp_guete.group(1) == _GUETE_HHMM, (
        f"Trip und Ortsvergleich nennen unterschiedliche Guete-Grenzzeiten:\n"
        f"  Trip          = {trip_guete.group(1)}\n"
        f"  Ortsvergleich = {cmp_guete.group(1)}"
    )


# ---------------------------------------------------------------------------
# AC-14 -- Kurzform: dasselbe Guete-Zeichen an derselben Stelle
# ---------------------------------------------------------------------------


@freeze_time(_FROZEN_UTC)
def test_ac14_kurzform_traegt_in_beiden_flaechen_dasselbe_guete_zeichen():
    """AC-14 (Kurzform) GIVEN denselben Aufbau
    WHEN die Kurzform gerendert wird (Muster fuer SMS/Premium-SMS/
    Telegram-Kurzstil, dieselbe `render_sms`-Ausgabe)
    THEN traegt sie in BEIDEN Flaechen dasselbe Guete-Zeichen `?` hinter
    demselben Beginn-Token -- keine Reichweite in der Kurzform (E6).

    RED heute: `RadarAlertRequest`/`NowcastResult`/`OnsetEvent` kennen die
    neuen Felder nicht (`TypeError`)."""
    from output.renderers.alert.model import AlertMessage, OnsetEvent

    trip_event = OnsetEvent(
        onset_minutes=_ONSET_MIN, onset_time=_ONSET_HHMM, km_from=0.0, km_to=6.0,
        is_convective=False, intensity_label="Mäßiger Regen",
        source_label="Radar (DWD)", segment_id="Ziel",
        event_end_time=_ENDE_HHMM, event_ongoing_beyond_horizon=False,
        location_sharpness_limit_time=_GUETE_HHMM,
        source_reach_time=_REACH_HHMM,
    )
    trip_sms = render_sms(AlertMessage(
        trip_short="KHW 403", stand_at="17:30", events=(trip_event,),
        source="Radar (DWD)",
    ))

    cmp_msg = to_multi_location_onset_alert_message(
        [("Reykjavik", _ortsvergleich_pfad_nowcast())], tz=_TZ, stand_at="10:00",
    )
    cmp_sms = render_sms(cmp_msg)

    trip_treffer = _KURZFORM_GUETE_RE.search(trip_sms)
    cmp_treffer = _KURZFORM_GUETE_RE.search(cmp_sms)
    assert trip_treffer and cmp_treffer, (
        f"RED: mindestens eine Flaeche traegt kein Guete-Zeichen.\n"
        f"  Trip          = {trip_sms!r}\n  Ortsvergleich = {cmp_sms!r}"
    )
    assert trip_treffer.group(1) == cmp_treffer.group(1) == _ONSET_HHMM, (
        f"Trip und Ortsvergleich haengen das Guete-Zeichen an "
        f"unterschiedliche Zeit-Token:\n"
        f"  Trip          = {trip_treffer.group(1)}\n"
        f"  Ortsvergleich = {cmp_treffer.group(1)}"
    )
    assert _REACH_HHMM not in trip_sms and _REACH_HHMM not in cmp_sms, (
        f"Die Reichweite darf in KEINER Flaeche in der Kurzform auftauchen "
        f"(E6):\n  Trip          = {trip_sms!r}\n  Ortsvergleich = {cmp_sms!r}"
    )
