"""TDD — Issue #914 Slice 4: SMS-Block im Alert-Versand (`_send_alert`).

Slice 4 schließt den SMS-Kanal an den kanonischen Alert-Versand an. Bisher war
"sms" ein out-of-scope/known_channel ohne realen Versand. Jetzt:
- effektiver Kanal "sms" + vollständige SMS-Config → realer seven.io-HTTP-Versand
- send_sms False / fehlende Config → kein SMS-Versuch
- SMS-HTTP-Fehler (seven.io != 100) → geloggt, deliverable_any bleibt True
  (E-Mail läuft best-effort durch, kein #656-Anti-Pattern)

Mock-frei: Der seven.io-Endpunkt wird über einen echten lokalen HTTP-Server
gestubbt (gleiches Muster wie der Telegram-Stub in Issue #684). `sms_gateway_url`
zeigt auf 127.0.0.1 — echter httpx-Roundtrip, kein patch()/Mock().
"""
from __future__ import annotations

import json
import shutil
import threading
from datetime import datetime, time, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from app.config import Settings
from app.models import (
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    TripReportConfig,
    TripSegment,
)
from app.trip import Stage, TimeWindow, Trip, Waypoint

TEST_USER = "issue914slice4user"


# --- Helpers (mock-free) ---


def _segment_weather(temp_max: float, wind_max: float, precip: float) -> SegmentWeatherData:
    now = datetime.now(timezone.utc)
    segment = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=47.0, lon=11.0, elevation_m=1000.0),
        end_point=GPXPoint(lat=47.1, lon=11.1, elevation_m=1200.0),
        start_time=now,
        end_time=now + timedelta(hours=2),
        duration_hours=2.0,
        distance_km=5.0,
        ascent_m=200.0,
        descent_m=0.0,
    )
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="test", run=now,
        grid_res_km=1.0, interp="point_grid",
    )
    timeseries = NormalizedTimeseries(
        meta=meta,
        data=[ForecastDataPoint(ts=now, t2m_c=temp_max, wind10m_kmh=wind_max)],
    )
    summary = SegmentWeatherSummary(
        temp_min_c=temp_max - 5, temp_max_c=temp_max, temp_avg_c=temp_max - 2.5,
        wind_max_kmh=wind_max, precip_sum_mm=precip,
    )
    return SegmentWeatherData(
        segment=segment, timeseries=timeseries, aggregated=summary,
        fetched_at=now, provider="openmeteo",
    )


def _trip(report_config: TripReportConfig | None) -> Trip:
    from datetime import date as date_type

    wp = Waypoint(
        id="G1", name="Start", lat=47.0, lon=11.0, elevation_m=1000.0,
        time_window=TimeWindow(start=time(8, 0), end=time(10, 0)),
    )
    stage = Stage(id="T1", name="Tag 1", date=date_type.today(), waypoints=[wp])
    trip = Trip(id="trip-914", name="Test Trip 914", stages=[stage])
    trip.report_config = report_config
    return trip


def _significant_pair():
    cached = [_segment_weather(temp_max=15.0, wind_max=10.0, precip=0.0)]
    fresh = [_segment_weather(temp_max=45.0, wind_max=80.0, precip=30.0)]
    return cached, fresh


def _alert_log_count(trip_id: str) -> int:
    path = Path(f"data/users/{TEST_USER}/alert_log.json")
    if not path.exists():
        return 0
    data = json.loads(path.read_text())
    return sum(1 for e in data.get("entries", []) if e.get("trip_id") == trip_id)


@pytest.fixture(autouse=True)
def _clean_user_dir():
    d = Path(f"data/users/{TEST_USER}")
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True, exist_ok=True)
    yield
    if d.exists():
        shutil.rmtree(d)


class _SevenStub:
    """Echter lokaler HTTP-Server, der den seven.io-Gateway nachbildet.

    `body` ist der zurückgegebene Antwort-Body ("100" = Erfolg, sonst Fehler).
    `received` sammelt die eingegangenen POST-Payloads — Nachweis, ob send()
    tatsächlich aufgerufen wurde.
    """

    def __init__(self, body: str = "100", status: int = 200) -> None:
        self.received: list[bytes] = []
        body_bytes = body.encode()
        received = self.received

        class _Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("Content-Length", 0))
                received.append(self.rfile.read(length))
                self.send_response(status)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(body_bytes)

            def log_message(self, *args):  # silence
                pass

        self._httpd = HTTPServer(("127.0.0.1", 0), _Handler)
        self.url = f"http://127.0.0.1:{self._httpd.server_port}/api/sms"
        threading.Thread(target=self._httpd.serve_forever, daemon=True).start()

    def close(self) -> None:
        self._httpd.shutdown()


def _sms_settings(*, configured: bool, gateway_url: str) -> Settings:
    """Settings mit gezielt gesetzter SMS-Config (model_copy, kein Mock).

    E-Mail bleibt immer konfiguriert (best-effort-Pfad für AC-3), Telegram aus.
    """
    upd: dict = {
        # E-Mail konfiguriert, aber Versand schlägt fehl (nicht erreichbarer Host) —
        # für AC-3 brauchen wir nur, dass deliverable_any über E-Mail True bleibt.
        "smtp_host": "smtp.invalid.test", "smtp_user": "alert@example.test",
        "smtp_pass": "secret", "mail_to": "gregor-test@henemm.com",
        "smtp_port": 587, "is_test_mode": False,
        "telegram_bot_token": "", "telegram_chat_id": "",
    }
    if configured:
        upd.update(
            sms_gateway_url=gateway_url,
            seven_api_key="test-key",
            sms_to="+49123456789",
            sms_from="Gregor",
        )
    else:
        upd.update(sms_gateway_url=gateway_url, seven_api_key=None, sms_to=None)
    return Settings().model_copy(update=upd)


# --- AC-1: send_sms=True + SMS-Config → SMSOutput.send wird aufgerufen ---


def test_ac1_sms_configured_sends_via_seven():
    """AC-1: effektiver Kanal "sms" + vollständige SMS-Config → realer seven.io-
    HTTP-POST wird abgesetzt (Stub empfängt die Payload), Alert wird recorded."""
    from services.trip_alert import TripAlertService

    stub = _SevenStub(body="100")
    try:
        settings = _sms_settings(configured=True, gateway_url=stub.url)
        assert settings.can_send_sms() is True

        config = TripReportConfig(
            trip_id="trip-914", send_email=False, send_telegram=False,
            send_sms=True, alert_on_changes=True,
        )
        trip = _trip(report_config=config)
        service = TripAlertService(settings=settings, throttle_hours=0, user_id=TEST_USER)
        service.clear_throttle(trip.id)
        assert service._effective_alert_channels(trip) == {"sms"}

        cached, fresh = _significant_pair()
        result = service.check_and_send_alerts(trip, cached, fresh_weather=fresh)

        assert result is True, "sms-only mit Config muss deliverable sein"
        assert len(stub.received) == 1, (
            "seven.io-Gateway wurde NICHT aufgerufen — SMS-Block fehlt im Versand."
        )
        payload = stub.received[0].decode()
        assert "text=" in payload, "SMS-Body fehlt im seven.io-POST"
        assert _alert_log_count(trip.id) == 1
        assert trip.id in service._last_alert_times
    finally:
        stub.close()


# --- AC-2: fehlende SMS-Config → kein SMS-Versuch ---


def test_ac2_sms_channel_without_config_no_send():
    """AC-2: effektiver Kanal "sms", aber SMS NICHT konfiguriert (kein api_key/sms_to)
    → kein HTTP-POST an seven.io, kein False-Positive-Recording (nichts zustellbar)."""
    from services.trip_alert import TripAlertService

    stub = _SevenStub(body="100")
    try:
        settings = _sms_settings(configured=False, gateway_url=stub.url)
        assert settings.can_send_sms() is False

        config = TripReportConfig(
            trip_id="trip-914", send_email=False, send_telegram=False,
            send_sms=True, alert_on_changes=True,
        )
        trip = _trip(report_config=config)
        service = TripAlertService(settings=settings, throttle_hours=0, user_id=TEST_USER)
        service.clear_throttle(trip.id)
        assert service._effective_alert_channels(trip) == {"sms"}

        cached, fresh = _significant_pair()
        result = service.check_and_send_alerts(trip, cached, fresh_weather=fresh)

        assert result is False, (
            "sms-only ohne Config darf NICHT als zustellbar gelten (False-Positive)."
        )
        assert len(stub.received) == 0, "Es darf KEIN seven.io-POST abgesetzt werden."
        assert _alert_log_count(trip.id) == 0
        assert trip.id not in service._last_alert_times
    finally:
        stub.close()


# --- AC-3: SMS-HTTP-Fehler → geloggt, deliverable_any bleibt True via E-Mail ---


def test_ac3_sms_http_error_logged_email_still_delivers(caplog):
    """AC-3: SMS + E-Mail effektive Kanäle; seven.io antwortet mit Fehler-Code
    (≠100) → SMS-Fehler wird geloggt, aber deliverable_any bleibt True
    (E-Mail-Kanal ist konfiguriert), Alert wird best-effort recorded."""
    import logging

    from services.trip_alert import TripAlertService

    stub = _SevenStub(body="305")  # seven.io: ungültige Empfängernummer → OutputError
    try:
        settings = _sms_settings(configured=True, gateway_url=stub.url)
        # E-Mail bleibt konfiguriert → deliverable_any True trotz SMS-Fehler.
        assert settings.can_send_email() is True
        assert settings.can_send_sms() is True

        config = TripReportConfig(
            trip_id="trip-914", send_email=True, send_telegram=False,
            send_sms=True, alert_on_changes=True,
        )
        trip = _trip(report_config=config)
        service = TripAlertService(settings=settings, throttle_hours=0, user_id=TEST_USER)
        service.clear_throttle(trip.id)
        assert service._effective_alert_channels(trip) == {"email", "sms"}

        cached, fresh = _significant_pair()
        with caplog.at_level(logging.ERROR):
            result = service.check_and_send_alerts(trip, cached, fresh_weather=fresh)

        # seven.io wurde kontaktiert (Fehler-Roundtrip), aber Versand schlug fehl.
        assert len(stub.received) == 1, "seven.io muss kontaktiert worden sein."
        assert any("SMS alert failed" in r.message for r in caplog.records), (
            "SMS-Fehler muss geloggt werden."
        )
        # E-Mail ist konfiguriert → deliverable_any bleibt True, Recording erhalten.
        assert result is True, (
            "deliverable_any muss True bleiben (E-Mail-Kanal zustellbar)."
        )
        assert _alert_log_count(trip.id) == 1
        assert trip.id in service._last_alert_times
    finally:
        stub.close()
