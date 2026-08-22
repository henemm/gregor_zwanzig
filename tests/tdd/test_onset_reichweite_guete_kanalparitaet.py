"""TDD RED — Issue #2051 S3: Reichweite und Guete tragen in Trip- UND
Ortsvergleich-Flaeche denselben Wortlaut und denselben Wert (ADR-0021).

SPEC: docs/specs/modules/feat_2051_s3_reichweite_und_guete.md — AC-14.

Warum das zaehlt: Trip und Ortsvergleich bauen ihr `OnsetEvent` an ZWEI
verschiedenen Stellen -- `trip_alert.check_radar_alerts()` (ueber
`RadarAlertRequest`) und `project.to_multi_location_onset_alert_message()`
(ueber `NowcastResult`). Wird eines der beiden neuen Felder (Reichweite,
Guete) nur an einer der beiden Stellen durchgereicht, entsteht in der
anderen eine stille Luecke -- genau die Fehlerklasse, die der Adversary bei
#2046 (F001) UND bei #2054 fand (dort liess sich der Bildner eines
abgeleiteten Feldes abschalten, ohne dass ein einziger Test rot wurde, weil
alle Tests den Wert als Literal statt ueber die echte Ableitung setzten).

**Korrektur gegenueber einer fruehreren Fassung dieser Datei:** die erste
Fassung baute den Trip-Pfad ueber einen HANDGEBAUTEN `RadarAlertRequest`
mit literalen `source_reach_time`/`location_sharpness_limit_time` -- das
umgeht `trip_alert.py`s eigene Berechnung/Durchreichung VOLLSTAENDIG und
haette eine fehlende Verdrahtung dort nie gefangen (Befund aus dem
Adversary-Durchlauf von #2054, sinngemaess auf diese Spec uebertragen).
DIESE Fassung faehrt stattdessen BEIDE Flaechen ueber ihre echten
Produktivpfade (`TripAlertService.check_radar_alerts()` bzw.
`CompareRadarAlertService.check_all_compare_presets()`) mit DENSELBEN
echten Radar-Frames -- Muster `test_onset_ende_kanalparitaet.py` (S1,
dortige AC-15).

Mock-frei: DIESELBEN echten Radar-Frames (feste absolute Zeitstempel, keine
Wanduhr-Ableitung je Aufruf) laufen durch BEIDE echten Produktivpfade --
echter `RadarNowcastService` -> echtes `NowcastResult` -> echter
Alarm-Service -> echter `NotificationService` -> echter Telegram-Transport
-> Nutzlast am Draht eines lokalen Aufzeichnungs-Servers. Kein `Mock()`,
kein `patch()` von Verhalten, kein externes Netz, kein echter SMS-Versand.

Frame-Aufbau (feste absolute Zeitstempel, von Hand hergeleitet):
  * durchgehend nass (3.0 mm/h) von +20 bis +150 Min im 10-Minuten-Raster
    -> Beginn bei +20 (diesseits `RADAR_ONSET_THRESHOLD_MIN`=55, der Alarm
    feuert), Ende bei +150 (letzter nasser Frame vor dem Trockenuebergang,
    jenseits der 60-Minuten-Guete-Grenze -> Guete-Zeile ausgeloest).
  * ein Trockenframe bei +160 beendet den Block (`event_ongoing_beyond_
    horizon=False` -- die Reichweite wird deshalb NICHT durch E5
    unterdrueckt).
  * kein weiterer Frame danach -> die Reichweite des LETZTEN Frames (+160)
    reicht bis +160 + `_MAX_FRAME_COVERAGE` (15) = +175 (gedeckelt am
    180-Min-Horizont, hier folgenlos).

RED heute: `RadarAlertRequest`/`NowcastResult`/`OnsetEvent` kennen die
neuen Felder nicht bzw. `trip_alert.py`/`project.py` reichen sie noch
nicht durch -- keiner der beiden Texte nennt Reichweite oder Guete.
"""
from __future__ import annotations

import dataclasses
import http.server
import inspect
import json
import re
import shutil
import socket
import threading
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

import pytest

import output.channels.telegram as tg_module
from app.config import Settings
from app.loader import save_location, save_trip
from app.models import TripReportConfig
from app.user import SavedLocation

from tests.helpers.briefing_zeiten import briefing_zeiten_fuer_trip
from tests.helpers.compare_briefings import write_compare_briefings
from tests.helpers.nowcast_gate_fixtures import (
    TRIP_LAT, TRIP_LON, TRIP_ZONE, clean_uid, fresh_uid, make_trip,
    quiet_window_elsewhere, radar_service, reset_radar_cache,
)

# Langform-Wortlaute, mit gefangener Uhrzeit.
_REACH_RE = re.compile(r"Radar reicht bis (\d{1,2}:\d{2})")
_GUETE_RE = re.compile(r"Ortsangabe ab (\d{1,2}:\d{2}) unscharf")
# Kurzform: das Guete-Zeichen `?` unmittelbar hinter einem Zeit-Token.
_KURZFORM_GUETE_RE = re.compile(r"@(?P<beginn>\d{1,2}:\d{2})\?")

# Nasser Block: +20 bis +150 Minuten im 10-Minuten-Raster, danach TROCKEN,
# danach KEINE weiteren Frames mehr.
ONSET_MIN = 20          # < RADAR_ONSET_THRESHOLD_MIN (55) -> der Alarm feuert
ENDE_MIN = 150          # > LOCATION_SHARPNESS_LIMIT_MIN (60) -> Guete-Zeile
TROCKEN_MIN = 160       # letzter Frame ueberhaupt (dry) -> Reichweite daraus
RATE_MM_H = 3.0


class _FesterBlockMitReichweite:
    """Echter, aufrufbarer `frame_source` (kein Mock) mit EINMALIG
    festgelegten, absoluten Zeitstempeln (Muster
    `test_onset_ende_kanalparitaet.py::_FesterNasserBlock`).

    Absolut statt "relativ zu jetzt bei jedem Aufruf": beide Flaechen werden
    im selben Test nacheinander gefahren; eine Wanduhr-Ableitung je Aufruf
    verschoebe die Frames zwischen den beiden Laeufen und der Paritaets-
    Vergleich maesse die Uhr statt der Verdrahtung.
    """

    def __init__(self) -> None:
        self.start = datetime.now(timezone.utc).replace(microsecond=0)
        self.calls: list[tuple[float, float]] = []

    @property
    def erwartetes_ende_utc(self) -> datetime:
        return self.start + timedelta(minutes=ENDE_MIN)

    @property
    def erwartete_reichweite_utc(self) -> datetime:
        # Letzter Frame (+160, trocken) hat keinen Nachbarn mehr -> Deckung
        # bis +160 + _MAX_FRAME_COVERAGE (15) = +175.
        return self.start + timedelta(minutes=TROCKEN_MIN + 15)

    @property
    def erwartete_guete_grenze_utc(self) -> datetime:
        # LOCATION_SHARPNESS_LIMIT_MIN = 60 (E2) -- von Hand aus der Spec
        # uebernommen, nicht aus der Implementierung abgeschrieben.
        return self.start + timedelta(minutes=60)

    def __call__(self, lat: float, lon: float) -> list:
        from providers.brightsky import RadarFrame

        self.calls.append((lat, lon))
        frames = [
            RadarFrame(
                timestamp=self.start + timedelta(minutes=m),
                precip_mm_h=RATE_MM_H, is_convective=False,
            )
            for m in range(ONSET_MIN, ENDE_MIN + 1, 10)
        ]
        frames.append(RadarFrame(
            timestamp=self.start + timedelta(minutes=TROCKEN_MIN),
            precip_mm_h=0.0, is_convective=False,
        ))
        return frames


# ---------------------------------------------------------------------------
# Echter lokaler Telegram-Bot-API-Stub (kein Mock)
# ---------------------------------------------------------------------------


def _free_port() -> int:
    probe = socket.socket()
    probe.bind(("", 0))
    port = probe.getsockname()[1]
    probe.close()
    return port


class _TelegramStub:
    def __init__(self) -> None:
        self.sent: list[dict] = []
        sent = self.sent
        counter = {"mid": 6000}

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("Content-Length", 0))
                try:
                    payload = json.loads(self.rfile.read(length).decode())
                except ValueError:
                    payload = {}
                sent.append(payload)
                counter["mid"] += 1
                body = json.dumps(
                    {"ok": True, "result": {"message_id": counter["mid"]}}
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
def telegram_stub():
    stub = _TelegramStub()
    yield stub
    stub.stop()


def _telegram_only_settings(marke: str) -> Settings:
    """Nur Telegram sendebereit -- E-Mail, SMS und Premium-SMS ausdruecklich
    AUS. Jedes weggelassene Feld faellt bei pydantic sonst still auf die
    Prod-`.env` des Arbeitsverzeichnisses zurueck (#1477)."""
    return Settings(
        smtp_host=None, smtp_user=None, smtp_pass=None, mail_to=None,
        telegram_bot_token=f"test-token-2051-s3-{marke}",
        telegram_chat_id="99999", telegram_test_chat_id="99999",
        sms_gateway_url="", seven_api_key="", seven_sandbox_key="",
        sms_to="", sms_from=None,
        premium_sms_reply_to=None, premium_sms_reply_at=None,
    )


# ---------------------------------------------------------------------------
# Die beiden echten Produktivpfade
# ---------------------------------------------------------------------------


def _text_vom_trip_pfad(frames, telegram_stub, monkeypatch, *, stil: str) -> str:
    """Faehrt `TripAlertService.check_radar_alerts()` -- den einzigen
    Produktivpfad, der im Trip-Betrieb einen `RadarAlertRequest` baut -- und
    gibt den Text zurueck, der am Draht ankam."""
    from services.trip_alert import TripAlertService

    monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", telegram_stub.base_url)

    uid, trip_id = fresh_uid(f"2051-s3-par-trip-{stil}"), f"trip-2051-s3-par-{stil}"
    clean_uid(uid)
    reset_radar_cache()
    try:
        quiet_from, quiet_to = quiet_window_elsewhere(zone=TRIP_ZONE)
        trip = make_trip(
            trip_id, cooldown_minutes=0, quiet_from=quiet_from, quiet_to=quiet_to,
        )
        # Etappen-Startzeit auf "gerade eben" setzen (Muster S1), damit zu
        # JEDER Tageszeit ein Segment aktiv ist -- Compute-on-Save (#802)
        # rechnet die Ankunftszeiten sonst neu.
        lokal = datetime.now(timezone.utc).astimezone(TRIP_ZONE)
        start = max(
            lokal - timedelta(minutes=15),
            lokal.replace(hour=0, minute=0, second=0, microsecond=0),
        )
        trip.stages[0] = dataclasses.replace(
            trip.stages[0], start_time=time(start.hour, start.minute),
        )
        morgen, abend = briefing_zeiten_fuer_trip(trip)
        trip.report_config = TripReportConfig(
            trip_id=trip_id, send_email=False, send_sms=False,
            send_telegram=True, send_premium_sms=False,
            alert_on_changes=True, telegram_style=stil,
            morning_time=morgen, evening_time=abend,
        )
        save_trip(trip, user_id=uid)

        svc = TripAlertService(
            settings=_telegram_only_settings(f"trip-{stil}"), throttle_hours=0,
            user_id=uid, radar_service=radar_service(frames),
        )
        vorher = len(telegram_stub.sent)
        sent = svc.check_radar_alerts()

        assert sent == 1, (
            f"Voraussetzung: genau EIN Trip-Radar-Alarm erwartet, war {sent}. "
            f"Nowcast-Abrufe: {frames.calls!r}"
        )
        neu = telegram_stub.sent[vorher:]
        assert len(neu) == 1, (
            f"Erwartet genau EINE Trip-Nachricht am Draht: {neu!r}"
        )
        return neu[0].get("text") or ""
    finally:
        clean_uid(uid)


def _compare_users_root() -> Path:
    from app.loader import get_data_root

    return get_data_root() / "users"


def _text_vom_ortsvergleich_pfad(frames, telegram_stub, monkeypatch, *, stil: str) -> str:
    """Faehrt `CompareRadarAlertService.check_all_compare_presets()` -- den
    Ortsvergleich-Produktivpfad, der sein `OnsetEvent` ueber
    `to_multi_location_onset_alert_message()` selbst baut."""
    from services.compare_radar_alert import CompareRadarAlertService

    monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", telegram_stub.base_url)

    uid = fresh_uid(f"2051-s3-par-cmp-{stil}")
    preset_id = f"cp-2051-s3-par-{stil}"
    clean_uid(uid)
    reset_radar_cache()
    try:
        # DIESELBEN Koordinaten wie der Trip (Atlantic/Reykjavik, UTC+0).
        save_location(
            SavedLocation(
                id="loc-2051-s3", name="Reykjavik-Paritaet-S3",
                lat=TRIP_LAT, lon=TRIP_LON, elevation_m=100,
            ),
            user_id=uid,
        )
        write_compare_briefings(_compare_users_root() / uid, [{
            "id": preset_id,
            "name": preset_id,
            "user_id": uid,
            "location_ids": ["loc-2051-s3"],
            "schedule": "daily",
            "weekday": 4,
            "profil": "ALLGEMEIN",
            "hour_from": 9,
            "hour_to": 16,
            "empfaenger": ["gregor-test@henemm.com"],
            "letzter_versand": None,
            "top_ort_letzter_versand": None,
            "created_at": "2026-08-22T00:00:00Z",
            "radar_alert_enabled": True,
            "send_telegram": True,
            "display_config": {"telegram_style": stil},
        }])

        svc = CompareRadarAlertService(
            settings=_telegram_only_settings(f"cmp-{stil}"), user_id=uid,
            radar_service=radar_service(frames),
        )
        vorher = len(telegram_stub.sent)
        sent = svc.check_all_compare_presets()

        assert sent == 1, (
            f"Voraussetzung: genau EIN Ortsvergleich-Radar-Alarm erwartet, "
            f"war {sent}. Nowcast-Abrufe: {frames.calls!r}"
        )
        neu = telegram_stub.sent[vorher:]
        assert len(neu) == 1, (
            f"Erwartet genau EINE Ortsvergleich-Nachricht am Draht: {neu!r}"
        )
        return neu[0].get("text") or ""
    finally:
        clean_uid(uid)
        d = _compare_users_root() / uid
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)


def _minuten(hhmm: str) -> int:
    stunde, _, minute = hhmm.partition(":")
    return int(stunde) * 60 + (int(minute) if minute else 0)


def _abstand_minuten(a: str, b: str) -> int:
    roh = abs(_minuten(a) - _minuten(b))
    return min(roh, 24 * 60 - roh)


# Die beiden Laeufe liegen Sekundenbruchteile auseinander; springt dazwischen
# die Minute um, unterscheiden sich die zurueckgerechneten Uhrzeiten um
# hoechstens 1 Minute -- kein echter Wertunterschied.
_WANDUHR_TOLERANZ_MIN = 1


def test_prueling_stammt_aus_diesem_arbeitsbaum():
    """Vorbedingung (kein AC): Alarm-Services werden RELATIV ZU DIESER
    Testdatei aufgeloest."""
    from services import compare_radar_alert as cmp_module
    from services import trip_alert as trip_module

    arbeitsbaum = Path(__file__).resolve().parents[2]
    for modul in (trip_module, cmp_module):
        modul_pfad = Path(inspect.getfile(modul)).resolve()
        assert modul_pfad.is_relative_to(arbeitsbaum), (
            f"Prueling stammt nicht aus diesem Arbeitsbaum: {modul_pfad}"
        )


# ---------------------------------------------------------------------------
# AC-14 -- Langform: Trip und Ortsvergleich nennen dieselbe Reichweite und
# dieselbe Guete-Grenzzeit
# ---------------------------------------------------------------------------


def test_ac14_langform_traegt_in_beiden_flaechen_reichweite_und_guete(
    telegram_stub, monkeypatch,
):
    """AC-14 GIVEN DIESELBEN Radar-Frames (nasser Block +20 bis +150 Minuten,
    danach ein Trockenframe bei +160, danach keine weiteren Beobachtungen)
    einmal ueber den ECHTEN Trip-Pfad (`TripAlertService.check_radar_alerts`)
    und einmal ueber den ECHTEN Ortsvergleich-Pfad
    (`CompareRadarAlertService.check_all_compare_presets`), beide im reichen
    Telegram-Stil
    WHEN beide Alarme tatsaechlich abgesetzt werden
    THEN tragen BEIDE Texte dieselbe Reichweite (`Radar reicht bis HH:MM`)
    UND dieselbe Guete-Grenzzeit (`Ortsangabe ab HH:MM unscharf`) -- gegen
    das aus den Frames HERGELEITETE Ende geprueft, nicht nur gegeneinander
    (zwei gleich falsche Angaben waeren sonst gruen).

    RED heute: `RadarAlertRequest`/`NowcastResult`/`OnsetEvent` kennen die
    neuen Felder nicht -- keiner der beiden Texte nennt Reichweite oder
    Guete."""
    frames = _FesterBlockMitReichweite()

    trip_text = _text_vom_trip_pfad(frames, telegram_stub, monkeypatch, stil="rich")
    cmp_text = _text_vom_ortsvergleich_pfad(
        frames, telegram_stub, monkeypatch, stil="rich",
    )

    trip_reach = _REACH_RE.search(trip_text)
    cmp_reach = _REACH_RE.search(cmp_text)
    fehlend_reach = [
        n for n, t in (("Trip", trip_reach), ("Ortsvergleich", cmp_reach)) if t is None
    ]
    assert not fehlend_reach, (
        f"RED: diese Flaeche(n) nennen keine Reichweite: {fehlend_reach}\n"
        f"  Trip          = {trip_text!r}\n  Ortsvergleich = {cmp_text!r}"
    )

    erwartete_reichweite = (
        frames.erwartete_reichweite_utc.astimezone(TRIP_ZONE).strftime("%H:%M")
    )
    for name, treffer, text in (
        ("Trip", trip_reach, trip_text), ("Ortsvergleich", cmp_reach, cmp_text),
    ):
        assert _abstand_minuten(treffer.group(1), erwartete_reichweite) <= _WANDUHR_TOLERANZ_MIN, (
            f"{name} nennt {treffer.group(1)} statt der aus den Frames "
            f"hergeleiteten Reichweite {erwartete_reichweite}: {text!r}"
        )
    assert _abstand_minuten(trip_reach.group(1), cmp_reach.group(1)) <= _WANDUHR_TOLERANZ_MIN, (
        "Trip und Ortsvergleich nennen verschiedene Reichweiten:\n"
        f"  Trip          = {trip_reach.group(1)}\n"
        f"  Ortsvergleich = {cmp_reach.group(1)}"
    )

    trip_guete = _GUETE_RE.search(trip_text)
    cmp_guete = _GUETE_RE.search(cmp_text)
    fehlend_guete = [
        n for n, t in (("Trip", trip_guete), ("Ortsvergleich", cmp_guete)) if t is None
    ]
    assert not fehlend_guete, (
        f"RED: diese Flaeche(n) nennen keine Guete-Zeile: {fehlend_guete}\n"
        f"  Trip          = {trip_text!r}\n  Ortsvergleich = {cmp_text!r}"
    )

    erwartete_guete = (
        frames.erwartete_guete_grenze_utc.astimezone(TRIP_ZONE).strftime("%H:%M")
    )
    for name, treffer, text in (
        ("Trip", trip_guete, trip_text), ("Ortsvergleich", cmp_guete, cmp_text),
    ):
        assert _abstand_minuten(treffer.group(1), erwartete_guete) <= _WANDUHR_TOLERANZ_MIN, (
            f"{name} nennt {treffer.group(1)} statt der hergeleiteten "
            f"Guete-Grenzzeit {erwartete_guete}: {text!r}"
        )
    assert _abstand_minuten(trip_guete.group(1), cmp_guete.group(1)) <= _WANDUHR_TOLERANZ_MIN, (
        "Trip und Ortsvergleich nennen verschiedene Guete-Grenzzeiten:\n"
        f"  Trip          = {trip_guete.group(1)}\n"
        f"  Ortsvergleich = {cmp_guete.group(1)}"
    )


# ---------------------------------------------------------------------------
# AC-14 -- Kurzform: dasselbe Guete-Zeichen an derselben Stelle
# ---------------------------------------------------------------------------


def test_ac14_kurzform_traegt_in_beiden_flaechen_dasselbe_guete_zeichen(
    telegram_stub, monkeypatch,
):
    """AC-14 (Kurzform) GIVEN denselben Aufbau, aber beide Flaechen im
    Telegram-KURZSTIL -- dem Stil, der denselben `sms_body` traegt, den SMS
    und Premium-SMS bekommen
    WHEN beide Alarme abgesetzt werden
    THEN traegt das Guete-Zeichen `?` in BEIDEN Flaechen denselben
    Zeit-Token, und die Reichweite steht in KEINER Flaeche in der Kurzform
    (E6).

    Warum eigens geprueft: die Kurzform ist ein anderer Codepfad als die
    Langform, und auf der Huette am Karnischen Hoehenweg kommt NUR
    Premium-SMS an.

    RED heute: keiner der beiden Texte traegt ein Guete-Zeichen."""
    frames = _FesterBlockMitReichweite()

    trip_text = _text_vom_trip_pfad(
        frames, telegram_stub, monkeypatch, stil="kurzform",
    )
    cmp_text = _text_vom_ortsvergleich_pfad(
        frames, telegram_stub, monkeypatch, stil="kurzform",
    )

    trip_treffer = _KURZFORM_GUETE_RE.search(trip_text)
    cmp_treffer = _KURZFORM_GUETE_RE.search(cmp_text)
    fehlend = [
        n for n, t in (("Trip", trip_treffer), ("Ortsvergleich", cmp_treffer))
        if t is None
    ]
    assert not fehlend, (
        f"RED: diese Flaeche(n) tragen kein Guete-Zeichen: {fehlend}\n"
        f"  Trip          = {trip_text!r}\n  Ortsvergleich = {cmp_text!r}"
    )
    assert _abstand_minuten(
        trip_treffer.group("beginn"), cmp_treffer.group("beginn"),
    ) <= _WANDUHR_TOLERANZ_MIN, (
        "Trip und Ortsvergleich haengen das Guete-Zeichen an "
        "unterschiedliche Zeit-Token:\n"
        f"  Trip          = {trip_treffer.group('beginn')}\n"
        f"  Ortsvergleich = {cmp_treffer.group('beginn')}"
    )

    erwartete_reichweite = (
        frames.erwartete_reichweite_utc.astimezone(TRIP_ZONE).strftime("%H:%M")
    )
    assert erwartete_reichweite not in trip_text, (
        f"Die Reichweite darf in der Trip-Kurzform nicht auftauchen (E6): "
        f"{trip_text!r}"
    )
    assert erwartete_reichweite not in cmp_text, (
        f"Die Reichweite darf in der Ortsvergleich-Kurzform nicht "
        f"auftauchen (E6): {cmp_text!r}"
    )
