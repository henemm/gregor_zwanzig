"""TDD RED — Issue #2051 Scheibe S1: die Ende-Angabe erreicht BEIDE Flaechen —
Trip UND Ortsvergleich — mit demselben Wortlaut und demselben Wert.

SPEC: docs/specs/modules/feat_2051_s1_dauer_und_ende.md — AC-15.

Warum das zaehlt (ADR-0021, geteilter Code Trip/Ortsvergleich): Trip und
Ortsvergleich bauen ihr `OnsetEvent` an ZWEI verschiedenen Stellen —
`trip_alert.check_radar_alerts()` ueber `RadarAlertRequest` und
`project.to_multi_location_onset_alert_message()` ueber das `NowcastResult`.
Wird das neue Ende-Feld nur an einer der beiden Stellen durchgereicht,
entsteht in der anderen eine stille Luecke. Genau diese Fehlerklasse fand der
Adversary bei #2046 (F001).

Gespiegelt zu `tests/tdd/test_onset_menge_kanalparitaet.py`.

Mock-frei: DIESELBEN echten Radar-Frames (feste absolute Zeitstempel, keine
Wanduhr-Ableitung je Aufruf) laufen durch BEIDE echten Produktivpfade —
echter `RadarNowcastService` -> echtes `NowcastResult` -> echter
Alarm-Service -> echter `NotificationService` -> echter Telegram-Transport ->
Nutzlast am Draht eines lokalen Aufzeichnungs-Servers. Kein `Mock()`,
kein `patch()` von Verhalten, kein externes Netz, kein echter SMS-Versand.

Beide Flaechen laufen auf DENSELBEN Koordinaten (Atlantic/Reykjavik,
ganzjaehrig UTC+0): der Ortsvergleich loest die Zeitzone JE ORT auf, der
Trip ueber seine Wegpunkte — mit verschiedenen Orten waeren die Uhrzeiten
zulaessig verschieden und der Vergleich wertlos.

RED-Ursache: `NowcastResult` kennt `event_end_minutes` noch nicht, keiner der
beiden Pfade reicht ein Ende durch — in BEIDEN Texten fehlt
`letzter Regen gegen HH:MM` bzw. das zweite Kurzform-Zeit-Token.
"""
from __future__ import annotations

import dataclasses
import http.server
import json
import re
import shutil
import socket
import threading
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

import pytest
from freezegun import freeze_time

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
from tests.helpers.tagesbezug import (
    KURZFORM_ZEIT_TOKEN, expected_day_and_time, extract_day_and_time,
)

# Issue #2096: der WERT (Tagesbezug + Uhrzeit) kommt aus
# `tests/helpers/tagesbezug.py` — eine nackte `HH:MM`-Regex traf ab ~21:05
# UTC nicht mehr, weil der Renderer bei Tagesuebergang korrekt `morgen 00:12`
# bzw. `Mo1:18` schreibt.
#
# Was hier als Regex BLEIBT, ist allein die STRUKTUR: das Ende-Token haengt
# UNMITTELBAR am Beginn-Token, und beide sind minutengenau (`@HH:MM`, kein
# optionaler Minutenteil — die Spec ist uneinheitlich, den Ausschlag gibt
# AC-16, die dort `@23:59` budgetiert). Die Toleranz NICHT wiederherstellen:
# ein Ausdruck, der `@20` und `@20:00` gleichermassen annimmt, bewacht keines
# der beiden Formate. Der Tagesbezug ist in diesem Ausdruck bewusst optional
# — geprueft wird er nicht hier, sondern gegen den hergeleiteten Wert.
_KURZFORM_STRUKTUR_RE = re.compile(
    rf"@{KURZFORM_ZEIT_TOKEN}@{KURZFORM_ZEIT_TOKEN}"
)

# Gestellte Uhr statt Wanduhr (#2096): mittags, weit von beiden
# Mitternachtsgrenzen. Den Tagesuebergang selbst faehrt
# `test_tagesbezug_ueberlauf_spaetuhr.py` als eigener Fall — weggefroren
# waere er nicht bewacht, sondern umgangen. Nebenwirkung: beide Flaechen
# sehen denselben Zeitpunkt, die frueher noetige Ein-Minuten-Toleranz
# entfaellt und verglichen wird auf Gleichheit.
_GEFRORENE_UHR = "2026-08-22 12:00:00+00:00"
_JETZT_UTC = datetime.fromisoformat(_GEFRORENE_UHR)

# Nasser Block: +20 bis +80 Minuten im 10-Minuten-Raster, danach TROCKEN.
# Das erwartete Ende ist damit von Hand hergeleitet (letzter nasser Frame vor
# dem Trockenuebergang) und NICHT aus der Implementierung abgeschrieben.
ONSET_MIN = 20          # < RADAR_ONSET_THRESHOLD_MIN (55) -> der Alarm feuert
ENDE_MIN = 80
TROCKEN_MIN = 90
RATE_MM_H = 3.0


class _FesterNasserBlock:
    """Echter, aufrufbarer `frame_source` (kein Mock) mit EINMALIG
    festgelegten, absoluten Zeitstempeln.

    Absolut statt "relativ zu jetzt bei jedem Aufruf": beide Flaechen werden
    im selben Test nacheinander gefahren; eine Wanduhr-Ableitung je Aufruf
    verschoebe die Frames zwischen den beiden Laeufen und der Paritaets-
    Vergleich maesse die Uhr statt der Verdrahtung.

    Liefert fuer JEDE Koordinate denselben Satz — beide Flaechen sehen damit
    nachweislich dieselben Frames.
    """

    def __init__(self) -> None:
        self.start = datetime.now(timezone.utc).replace(microsecond=0)
        self.calls: list[tuple[float, float]] = []

    @property
    def erwartetes_ende_utc(self) -> datetime:
        return self.start + timedelta(minutes=ENDE_MIN)

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
        counter = {"mid": 5000}

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
    """Nur Telegram sendebereit — E-Mail, SMS und Premium-SMS ausdruecklich
    AUS. Jedes weggelassene Feld faellt bei pydantic still auf die Prod-`.env`
    des Arbeitsverzeichnisses zurueck (#1477).

    `telegram_test_chat_id` ist Pflicht fuer die Herkunftssperre des
    Telegram-Kanals aus einem Nicht-Prod-Checkout (#1476)."""
    return Settings(
        smtp_host=None, smtp_user=None, smtp_pass=None, mail_to=None,
        telegram_bot_token=f"test-token-2051-{marke}",
        telegram_chat_id="99999", telegram_test_chat_id="99999",
        sms_gateway_url="", seven_api_key="", seven_sandbox_key="",
        sms_to="", sms_from=None,
        premium_sms_reply_to=None, premium_sms_reply_at=None,
    )


# ---------------------------------------------------------------------------
# Die beiden echten Produktivpfade
# ---------------------------------------------------------------------------


def _text_vom_trip_pfad(frames, telegram_stub, monkeypatch, *, stil: str) -> str:
    """Faehrt `TripAlertService.check_radar_alerts()` — den einzigen
    Produktivpfad, der im Trip-Betrieb einen `RadarAlertRequest` baut — und
    gibt den Text zurueck, der am Draht ankam."""
    from services.trip_alert import TripAlertService

    monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", telegram_stub.base_url)

    uid, trip_id = fresh_uid(f"2051-par-trip-{stil}"), f"trip-2051-par-{stil}"
    clean_uid(uid)
    reset_radar_cache()
    try:
        quiet_from, quiet_to = quiet_window_elsewhere(zone=TRIP_ZONE)
        trip = make_trip(
            trip_id, cooldown_minutes=0, quiet_from=quiet_from, quiet_to=quiet_to,
        )
        # Etappen-Startzeit auf "gerade eben" setzen, damit zu JEDER Tageszeit
        # ein Segment aktiv ist. Noetig, weil `app.loader.save_trip` die
        # Ankunftszeiten beim Speichern NEU rechnet (Compute-on-Save, #802):
        # die 00:00-23:59-Spanne aus `make_trip()` ueberlebt den Roundtrip
        # nicht, aus ihr wird die Naismith-Gehzeit ab der Stage-Startzeit
        # (Vorgabe 08:00). Ein abends laufender Test faende danach kein
        # aktives Segment mehr und maesse die Segment-Auswahl statt der
        # Ende-Durchreichung. Mitternachts-Klemme: vor 00:15 Ortszeit bleibt
        # es bei 00:00, sonst rutschte der Start auf den Vortag.
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
        # Der PRODUKTIVE Speicherer: nur er schreibt `telegram_style` mit, und
        # `check_radar_alerts()` liest den Trip von Platte zurueck.
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
    """Funktion statt Konstante (#1595): `get_data_root()` liefert erst zur
    Laufzeit die von der Test-Fixture gesetzte Basis."""
    from app.loader import get_data_root

    return get_data_root() / "users"


def _text_vom_ortsvergleich_pfad(frames, telegram_stub, monkeypatch, *, stil: str) -> str:
    """Faehrt `CompareRadarAlertService.check_all_compare_presets()` — den
    Ortsvergleich-Produktivpfad, der sein `OnsetEvent` ueber
    `to_multi_location_onset_alert_message()` selbst baut."""
    from services.compare_radar_alert import CompareRadarAlertService

    monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", telegram_stub.base_url)

    uid = fresh_uid(f"2051-par-cmp-{stil}")
    preset_id = f"cp-2051-par-{stil}"
    clean_uid(uid)
    reset_radar_cache()
    try:
        # DIESELBEN Koordinaten wie der Trip (Atlantic/Reykjavik, UTC+0) —
        # sonst waeren die Uhrzeiten zulaessig verschieden.
        save_location(
            SavedLocation(
                id="loc-2051", name="Reykjavik-Paritaet",
                lat=TRIP_LAT, lon=TRIP_LON, elevation_m=100,
            ),
            user_id=uid,
        )
        write_compare_briefings(_compare_users_root() / uid, [{
            "id": preset_id,
            "name": preset_id,
            "user_id": uid,
            "location_ids": ["loc-2051"],
            # Aktiver Zeitplan noetig (#1467 S2 AG6), sonst gilt das Preset als
            # pausiert und schweigt in allen Alarm-Pfaden.
            "schedule": "daily",
            "weekday": 4,
            "profil": "ALLGEMEIN",
            "hour_from": 9,
            "hour_to": 16,
            "empfaenger": ["gregor-test@henemm.com"],
            "letzter_versand": None,
            "top_ort_letzter_versand": None,
            "created_at": "2026-08-21T00:00:00Z",
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


# ---------------------------------------------------------------------------
# AC-15 — Langform: Trip und Ortsvergleich nennen dasselbe Ende
# ---------------------------------------------------------------------------


@freeze_time(_GEFRORENE_UHR)
def test_ac15_langform_traegt_in_beiden_flaechen_dasselbe_ende(
    telegram_stub, monkeypatch,
):
    """AC-15 GIVEN DIESELBEN Radar-Frames (nasser Block +20 bis +80 Minuten,
    danach trocken) einmal ueber den Trip-Pfad
    (`trip_alert.check_radar_alerts`) und einmal ueber den
    Ortsvergleich-Pfad (`compare_radar_alert.check_all_compare_presets`),
    beide auf denselben Koordinaten und im reichen Telegram-Stil
    WHEN beide Alarme tatsaechlich abgesetzt werden
    THEN traegt die Ende-Angabe in BEIDEN Flaechen denselben Wortlaut
    (`letzter Regen gegen ...`) und dasselbe Paar aus Tagesbezug und Uhrzeit —
    keine Flaeche zeigt das Ende, ohne dass es die andere auch taete.

    Zusaetzlich wird der Wert gegen das aus den Frames HERGELEITETE Ende
    (Beginn + 80 Min) geprueft, nicht nur die beiden Flaechen gegeneinander:
    zwei gleich falsche Angaben waeren sonst gruen. Issue #2096: geprueft
    wird das PAAR — eine Uhrzeit ohne ihren Kalendertag ist keine Aussage.

    RED heute: `NowcastResult` kennt `event_end_minutes` nicht — beide Texte
    nennen ueberhaupt kein Ende."""
    frames = _FesterNasserBlock()

    trip_text = _text_vom_trip_pfad(frames, telegram_stub, monkeypatch, stil="rich")
    cmp_text = _text_vom_ortsvergleich_pfad(
        frames, telegram_stub, monkeypatch, stil="rich",
    )

    erwartet = expected_day_and_time(
        frames.erwartetes_ende_utc, _JETZT_UTC, TRIP_ZONE,
    )
    gemessen = {
        name: extract_day_and_time(text, "letzter Regen gegen")
        for name, text in (("Trip", trip_text), ("Ortsvergleich", cmp_text))
    }
    for name, paar in gemessen.items():
        assert paar == erwartet, (
            f"{name} nennt als Ende {paar!r} statt des aus den Frames "
            f"hergeleiteten Paares {erwartet!r}: "
            f"{(trip_text if name == 'Trip' else cmp_text)!r}"
        )
    assert gemessen["Trip"] == gemessen["Ortsvergleich"], (
        f"Trip und Ortsvergleich nennen verschiedene Enden: {gemessen!r}"
    )


# ---------------------------------------------------------------------------
# AC-15 — Kurzform: dieselbe Zusicherung fuer den einzigen Satelliten-Kanal
# ---------------------------------------------------------------------------


@freeze_time(_GEFRORENE_UHR)
def test_ac15_kurzform_traegt_in_beiden_flaechen_dasselbe_ende_token(
    telegram_stub, monkeypatch,
):
    """AC-15 (Kurzform) GIVEN denselben Aufbau, aber beide Flaechen im
    Telegram-KURZSTIL — dem Stil, der denselben `sms_body` traegt, den SMS
    und Premium-SMS bekommen
    WHEN beide Alarme abgesetzt werden
    THEN traegt das minutengenaue Ende-Token (`@HH:MM`) in BEIDEN Flaechen
    dasselbe Paar aus Tagesbezug (DE-Wochentagskuerzel) und Uhrzeit, und es
    haengt UNMITTELBAR am Beginn-Token.

    Warum eigens geprueft: die Kurzform ist ein anderer Codepfad als die
    Langform (`_render_sms_onset` statt `_render_telegram_onset`), und auf der
    Huette am Karnischen Hoehenweg kommt NUR Premium-SMS an — eine Angabe,
    die den Kurzpfad einer Flaeche nicht erreicht, erreicht dort niemanden.

    Minutengenau, nicht `@HH`: den Ausschlag gibt AC-16 (dort budgetiert die
    Spec `@23:59`) und die Konsistenz mit dem Beginn-Token aus #2046. Der
    Ausdruck laesst deshalb bewusst KEINEN optionalen Minutenteil zu.

    RED heute: `NowcastResult` kennt `event_end_minutes` nicht — in beiden
    Texten steht nur EIN Zeit-Token."""
    frames = _FesterNasserBlock()

    trip_text = _text_vom_trip_pfad(
        frames, telegram_stub, monkeypatch, stil="kurzform",
    )
    cmp_text = _text_vom_ortsvergleich_pfad(
        frames, telegram_stub, monkeypatch, stil="kurzform",
    )

    erwartet = expected_day_and_time(
        frames.erwartetes_ende_utc, _JETZT_UTC, TRIP_ZONE, style="kurzform",
    )
    gemessen: dict[str, tuple[str | None, str]] = {}
    for name, text in (("Trip", trip_text), ("Ortsvergleich", cmp_text)):
        assert _KURZFORM_STRUKTUR_RE.search(text), (
            f"RED: {name} traegt kein minutengenaues Ende-Token unmittelbar "
            f"am Beginn-Token: {text!r}"
        )
        gemessen[name] = extract_day_and_time(text, "@", style="kurzform")
        assert gemessen[name] == erwartet, (
            f"{name} nennt als Ende {gemessen[name]!r} statt des aus den "
            f"Frames hergeleiteten Paares {erwartet!r}: {text!r}"
        )

    assert gemessen["Trip"] == gemessen["Ortsvergleich"], (
        f"Trip und Ortsvergleich tragen verschiedene Ende-Token: {gemessen!r}"
    )
