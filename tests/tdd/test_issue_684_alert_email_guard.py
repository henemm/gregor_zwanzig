"""TDD RED — Issue #684: symmetrischer can_send_email()-Guard im Alert-Versand.

Bug (Adversary-Review #638, F003): Der E-Mail-Pfad in
`TripAlertService._send_alert` hat KEINEN `can_send_email()`-Guard (anders als
der Telegram- und der Radar-Pfad). Bei email-only effektivem Kanal mit
unkonfiguriertem SMTP wird der Alert nicht zugestellt — aber Throttle +
Alert-Log werden geschrieben und `check_and_send_alerts` gibt True zurück.
Stille Nicht-Zustellung mit positivem Status (False-Positive im Cockpit).

Mock-frei:
- AC-1/4: echter TripAlertService, echte Settings (model_copy), echte
  Snapshot-/Datei-Zustände.
- AC-2: echter SMTP-Versand über Stalwart (skip wenn nicht konfiguriert).
- AC-3: echter SMTP-Disconnect über einen lokalen Accept-and-Close-Socket
  (smtplib wirft SMTPServerDisconnected → OutputError, kein Mock).
- AC-4: echter HTTP-Roundtrip zu einem lokalen Telegram-Stub-Server.
"""
from __future__ import annotations

import json
import shutil
import socket
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

TEST_USER = "issue684tdduser"


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

    from app.models import MetricConfig, UnifiedWeatherDisplayConfig

    wp = Waypoint(
        id="G1", name="Start", lat=47.0, lon=11.0, elevation_m=1000.0,
        time_window=TimeWindow(start=time(8, 0), end=time(10, 0)),
    )
    stage = Stage(id="T1", name="Tag 1", date=date_type.today(), waypoints=[wp])
    # Issue #946: metric_alert_levels ist die einzige Detektor-Quelle. Die
    # _significant_pair-Deltas (temp 15→45, wind 10→80, precip 0→30) reißen die
    # Standard-Schwellen dieser Metriken → Change wird erkannt.
    # Issue #961 (Fixture-Korrektur): Die zugehörigen Weather-Tab-Metriken müssen
    # aktiv sein (enabled=True), sonst greift die Deaktivieren-Lücke und die Alarme
    # feuern bewusst nicht mehr. temperature_max→temperature, wind_change→wind,
    # precipitation_sum→precipitation.
    trip = Trip(
        id="trip-684", name="Test Trip 684", stages=[stage],
        display_config=UnifiedWeatherDisplayConfig(
            trip_id="trip-684",
            metrics=[
                MetricConfig(metric_id="temperature", enabled=True),
                MetricConfig(metric_id="wind", enabled=True),
                MetricConfig(metric_id="precipitation", enabled=True),
            ],
            metric_alert_levels={
                "temperature_max": "standard",
                "wind_change": "standard",
                "precipitation_sum": "standard",
            },
        ),
    )
    trip.report_config = report_config
    return trip


def _settings(*, email: bool, telegram: bool) -> Settings:
    """Echte Settings mit gezielt gesetzten Kanal-Feldern (model_copy, kein Mock)."""
    upd: dict = {}
    if email:
        upd.update(
            smtp_host="smtp.example.test", smtp_user="alert@example.test",
            smtp_pass="secret", mail_to="gregor-test@henemm.com",
            smtp_port=587, is_test_mode=False,
        )
    else:
        upd.update(smtp_host=None, smtp_user=None, smtp_pass=None, mail_to=None)
    if telegram:
        upd.update(telegram_bot_token="test-token", telegram_chat_id="12345")
    else:
        upd.update(telegram_bot_token="", telegram_chat_id="")
    return Settings().model_copy(update=upd)


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


def _significant_pair():
    """cached vs fresh mit großen Deltas → garantiert signifikante Changes."""
    cached = [_segment_weather(temp_max=15.0, wind_max=10.0, precip=0.0)]
    fresh = [_segment_weather(temp_max=45.0, wind_max=80.0, precip=30.0)]
    return cached, fresh


# --- AC-1: der eigentliche Bug (RED vor Fix) ---


def test_ac1_email_only_unconfigured_smtp_no_false_positive():
    """AC-1: email-only effektiver Kanal + SMTP NICHT konfiguriert (Telegram schon)
    → kein False-Positive: return False, kein Alert-Log, keine Throttle-Sperrzeit.

    Vor Fix: check_and_send_alerts gibt True zurück und schreibt Alert-Log +
    Throttle, obwohl nichts zugestellt wurde.
    """
    from services.trip_alert import TripAlertService

    settings = _settings(email=False, telegram=True)
    assert settings.can_send_email() is False
    assert settings.can_send_telegram() is True

    # report_config=None → effektive Kanäle = {"email"} (Default-Pfad)
    trip = _trip(report_config=None)
    service = TripAlertService(settings=settings, throttle_hours=0, user_id=TEST_USER)
    service.clear_throttle(trip.id)
    assert service._effective_alert_channels(trip) == {"email"}

    cached, fresh = _significant_pair()
    result = service.check_and_send_alerts(trip, cached, fresh_weather=fresh)

    assert result is False, (
        "False-Positive: email-only Alert ohne SMTP-Konfig wurde als gesendet "
        "gemeldet (sollte False sein)."
    )
    assert _alert_log_count(trip.id) == 0, (
        "Alert-Log darf bei nicht-zustellbarem Kanal NICHT geschrieben werden."
    )
    assert trip.id not in service._last_alert_times, (
        "Throttle-Sperrzeit darf bei nicht-zustellbarem Kanal NICHT gesetzt werden."
    )


# --- AC-2: Normalfall E-Mail (regressionsfrei, echter SMTP-Versand) ---


def test_ac2_email_configured_sends_and_records():
    """AC-2: E-Mail-Kanal + konfiguriertes SMTP → realer Versand, return True,
    Alert-Log + Throttle gesetzt."""
    from services.trip_alert import TripAlertService

    settings = Settings().for_testing()
    if not settings.can_send_email():
        pytest.skip("SMTP nicht konfiguriert — realer E-Mail-Versand nicht möglich")
    settings = settings.model_copy(update={"mail_to": "gregor-test@henemm.com"})

    trip = _trip(report_config=None)
    service = TripAlertService(settings=settings, throttle_hours=0, user_id=TEST_USER)
    service.clear_throttle(trip.id)
    assert service._effective_alert_channels(trip) == {"email"}

    cached, fresh = _significant_pair()
    result = service.check_and_send_alerts(trip, cached, fresh_weather=fresh)

    assert result is True
    assert _alert_log_count(trip.id) == 1
    assert trip.id in service._last_alert_times


# --- AC-3: transienter Send-Fehler → best-effort recording (kein #656-Anti-Pattern) ---


def test_ac3_configured_smtp_transient_failure_still_records():
    """AC-3: SMTP konfiguriert, aber Server bricht Verbindung ab (echter
    Disconnect über lokalen Accept-and-Close-Socket) → Recording bleibt erhalten:
    return True, Alert-Log + Throttle gesetzt. Recording NICHT an Send-Erfolg
    gekoppelt."""
    from services.trip_alert import TripAlertService

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(5)
    port = srv.getsockname()[1]

    def _accept_and_close():
        while True:
            try:
                conn, _ = srv.accept()
            except OSError:
                break
            conn.close()

    threading.Thread(target=_accept_and_close, daemon=True).start()

    try:
        settings = _settings(email=False, telegram=False).model_copy(update={
            "smtp_host": "127.0.0.1", "smtp_port": port,
            "smtp_user": "alert@example.test", "smtp_pass": "secret",
            "mail_to": "gregor-test@henemm.com", "is_test_mode": False,
        })
        assert settings.can_send_email() is True

        trip = _trip(report_config=None)
        service = TripAlertService(settings=settings, throttle_hours=0, user_id=TEST_USER)
        service.clear_throttle(trip.id)

        cached, fresh = _significant_pair()
        result = service.check_and_send_alerts(trip, cached, fresh_weather=fresh)

        assert result is True, (
            "Best-Effort: bei konfiguriertem aber gestörtem SMTP muss das Recording "
            "erhalten bleiben (sonst Alarm-Spam alle 30 Min, #656-Anti-Pattern)."
        )
        assert _alert_log_count(trip.id) == 1
        assert trip.id in service._last_alert_times
    finally:
        srv.close()


# --- AC-4: Telegram-only unverändert (regressionsfrei, echter HTTP-Roundtrip) ---


def test_ac4_telegram_only_unchanged():
    """AC-4: telegram-only effektiver Kanal + konfiguriertes Telegram → return True,
    Alert-Log + Throttle gesetzt (Verhalten unverändert)."""
    from output.channels import telegram as telegram_module
    from services.trip_alert import TripAlertService

    class _Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true,"result":{"message_id":1}}')

        def log_message(self, *args):  # silence
            pass

    httpd = HTTPServer(("127.0.0.1", 0), _Handler)
    port = httpd.server_port
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    original_base = telegram_module.TELEGRAM_API_BASE
    telegram_module.TELEGRAM_API_BASE = f"http://127.0.0.1:{port}"
    try:
        settings = _settings(email=False, telegram=True)
        assert settings.can_send_telegram() is True

        config = TripReportConfig(
            trip_id="trip-684", send_email=False, send_telegram=True,
            alert_on_changes=True,
        )
        trip = _trip(report_config=config)
        service = TripAlertService(settings=settings, throttle_hours=0, user_id=TEST_USER)
        service.clear_throttle(trip.id)
        assert service._effective_alert_channels(trip) == {"telegram"}

        cached, fresh = _significant_pair()
        result = service.check_and_send_alerts(trip, cached, fresh_weather=fresh)

        assert result is True
        assert _alert_log_count(trip.id) == 1
        assert trip.id in service._last_alert_times
    finally:
        telegram_module.TELEGRAM_API_BASE = original_base
        httpd.shutdown()
