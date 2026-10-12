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

import pytest

from app.config import Settings
from app.loader import get_data_dir
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

# Live-Schicht (Test-Politik, CLAUDE.md): braucht echtes Netz/echte Dienste --
# lief im Kern nie gruen (CI-Vermessung 2026-08-04, #1196) und gehoert per
# Marker in den /e2e-verify-Lauf, nicht auf eine Ausnahmeliste.
pytestmark = pytest.mark.live

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

    from app.models import MetricConfig, UnifiedWeatherDisplayConfig

    wp = Waypoint(
        id="G1", name="Start", lat=47.0, lon=11.0, elevation_m=1000.0,
        time_window=TimeWindow(start=time(8, 0), end=time(10, 0)),
    )
    stage = Stage(id="T1", name="Tag 1", date=date_type.today(), waypoints=[wp])
    # Issue #946: metric_alert_levels ist die einzige Detektor-Quelle. Die
    # _significant_pair-Deltas (temp/wind/precip) reißen die Standard-Schwellen.
    # Issue #961 (Fixture-Korrektur): zugehörige Weather-Tab-Metriken aktiv setzen,
    # sonst greift die Deaktivieren-Lücke (temperature_max→temperature,
    # wind_change→wind, precipitation_sum→precipitation).
    trip = Trip(
        id="trip-914", name="Test Trip 914", stages=[stage],
        display_config=UnifiedWeatherDisplayConfig(
            trip_id="trip-914",
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


def _significant_pair():
    cached = [_segment_weather(temp_max=15.0, wind_max=10.0, precip=0.0)]
    fresh = [_segment_weather(temp_max=45.0, wind_max=80.0, precip=30.0)]
    return cached, fresh


def _alert_log_count(trip_id: str) -> int:
    path = get_data_dir(TEST_USER) / "alert_log.json"
    if not path.exists():
        return 0
    data = json.loads(path.read_text())
    # #1467 S1: die Kennung steht jetzt in `entity_id`.
    return sum(1 for e in data.get("entries", []) if e.get("entity_id") == trip_id)


@pytest.fixture(autouse=True)
def _clean_user_dir():
    d = get_data_dir(TEST_USER)
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True, exist_ok=True)
    # Issue #1069: SMS-Versand ist seit dem Tier-Gate an Level standard/premium
    # gebunden (sms_allowed() liefert bei fehlender user.json "free" = False).
    # Dieser Test prueft die SMS-Versandmechanik selbst, nicht das Tier-Gating
    # (das hat eigene Tests in test_issue_1069_tier_channel_gating.py) — daher
    # braucht der Testnutzer ein Level, das SMS ueberhaupt erlaubt.
    (d / "user.json").write_text(json.dumps({"id": TEST_USER, "tier": "standard"}))
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
        assert service._throttle_store.last_sent("trip", trip.id) is not None
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
        assert service._throttle_store.last_sent("trip", trip.id) is None
    finally:
        stub.close()


# --- AC-3 (umgeschrieben, ADR-0086 / #1405 S1): SMS-HTTP-Fehler wird geloggt;
# "gesendet" nur, wenn ein ANDERER Kanal wirklich zustellt ---
#
# ADR-0086 (#1405): Die alte Fassung hiess `..._email_still_delivers` und
# setzte `result is True` voraus — obwohl die E-Mail an `smtp.invalid.test`
# ebenfalls scheiterte. Sie deckte damit faktisch "Totalausfall = gesendet"
# ab (Cockpit-Begruendung #1459 v1.4). Bewusst umgeschrieben (Spec
# fix_1405_s1_alarm_zustellung.md, AC-28): Totalausfall => False, Teilerfolg
# (ein anderer Kanal stellt wirklich zu) => True.


def _briefings_ausserhalb_des_vorlaufs(trip) -> None:
    """ADR-0086 (#1405) / #1594: Briefing-Zeiten ausserhalb des Vorlaufs der
    Alarm-Sperre. Ohne das schweigt der Alarm um 07:00/18:00 Ortszeit schon
    VOR dem Versand — `result is False` waere dann ohne Sendeversuch gruen und
    der Test maesse die Sperre statt des Totalausfalls."""
    from tests.helpers.briefing_zeiten import briefing_zeiten_fuer_trip

    morgen, abend = briefing_zeiten_fuer_trip(trip)
    trip.report_config.morning_time = morgen
    trip.report_config.evening_time = abend


def _total_failure_not_booked(service, trip_id: str) -> None:
    """ADR-0086 (#1405): Totalausfall bucht weder Sperrzeit noch Zustand, setzt
    aber den Fehlversuchs-Backoff (Scope ``trip:retry``)."""
    assert service._throttle_store.last_sent("trip", trip_id) is None, (
        "ADR-0086: Sperrzeit darf bei Totalausfall NICHT gebucht werden."
    )
    throttle_path = get_data_dir(TEST_USER) / "throttle_state.json"
    throttle_data = json.loads(throttle_path.read_text()) if throttle_path.exists() else {}
    assert throttle_data.get("trip:retry"), (
        "ADR-0086: nach Totalausfall muss ein Backoff im Scope 'trip:retry' "
        f"stehen. throttle_state.json: {throttle_data}"
    )


def test_ac3_sms_http_error_and_email_failure_is_total_failure(caplog, monkeypatch):
    """ADR-0086 (#1405), vormals ``test_ac3_sms_http_error_logged_email_still_delivers``:
    SMS + E-Mail effektive Kanaele; seven.io antwortet mit Fehler-Code (≠100)
    UND die E-Mail scheitert real (nicht erreichbarer Host) → SMS-Fehler wird
    geloggt, nichts ist zugestellt ⇒ ``False`` (vorher ``True``), keine
    Sperrzeit, Backoff gesetzt; der Protokoll-Eintrag bleibt (#1459 AC-15)."""
    import logging
    import time as _time_module

    from services.trip_alert import TripAlertService

    # smtp.invalid.test schlaegt real (Verbindungsfehler) fehl, aber die
    # Retry-Backoff-Logik in output.channels.email (5s/15s/30s zwischen
    # Versuchen) wuerde den globalen 30s-Test-Timeout (#1210) reissen.
    # Backoff-Wartezeit im Test deterministisch auf 0 setzen -- die realen
    # Verbindungsversuche selbst bleiben unveraendert, nur das Warten
    # zwischen den Retries wird uebersprungen.
    monkeypatch.setattr(_time_module, "sleep", lambda *_a, **_kw: None)

    stub = _SevenStub(body="305")  # seven.io: ungültige Empfängernummer → OutputError
    try:
        settings = _sms_settings(configured=True, gateway_url=stub.url)
        assert settings.can_send_email() is True
        assert settings.can_send_sms() is True

        config = TripReportConfig(
            trip_id="trip-914", send_email=True, send_telegram=False,
            send_sms=True, alert_on_changes=True,
        )
        trip = _trip(report_config=config)
        _briefings_ausserhalb_des_vorlaufs(trip)
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
        # ADR-0086 (#1405): E-Mail ist zwar konfiguriert, stellt aber NICHT zu —
        # Totalausfall heisst "nicht gesendet" (vorher True).
        assert result is False, (
            "ADR-0086: SMS-Fehler + gescheiterte E-Mail ist ein Totalausfall und "
            "darf nicht als gesendet gelten."
        )
        assert _alert_log_count(trip.id) == 1
        _total_failure_not_booked(service, trip.id)
    finally:
        stub.close()


def test_ac3_sms_only_http_error_is_total_failure(caplog):
    """ADR-0086 (#1405): SMS-Fehler allein (einziger effektiver Kanal SMS,
    seven.io antwortet ≠100) ⇒ ``False``, keine Sperrzeit, Backoff gesetzt."""
    import logging

    from services.trip_alert import TripAlertService

    stub = _SevenStub(body="305")
    try:
        settings = _sms_settings(configured=True, gateway_url=stub.url)
        config = TripReportConfig(
            trip_id="trip-914", send_email=False, send_telegram=False,
            send_sms=True, alert_on_changes=True,
        )
        trip = _trip(report_config=config)
        _briefings_ausserhalb_des_vorlaufs(trip)
        service = TripAlertService(settings=settings, throttle_hours=0, user_id=TEST_USER)
        service.clear_throttle(trip.id)
        assert service._effective_alert_channels(trip) == {"sms"}

        cached, fresh = _significant_pair()
        with caplog.at_level(logging.ERROR):
            result = service.check_and_send_alerts(trip, cached, fresh_weather=fresh)

        assert len(stub.received) == 1, "seven.io muss kontaktiert worden sein."
        assert any("SMS alert failed" in r.message for r in caplog.records), (
            "SMS-Fehler muss geloggt werden."
        )
        assert result is False, (
            "ADR-0086: ein SMS-Fehler auf dem einzigen Kanal ist ein Totalausfall."
        )
        assert _alert_log_count(trip.id) == 1
        _total_failure_not_booked(service, trip.id)
    finally:
        stub.close()


def test_ac3_sms_http_error_with_telegram_delivered_is_partial_success(caplog):
    """ADR-0086 (#1405): SMS scheitert (seven.io ≠100), Telegram stellt real zu
    (lokaler Telegram-HTTP-Stub) ⇒ Teilerfolg ⇒ ``True``, Sperrzeit gebucht,
    KEIN Backoff (kein Wiederholen, sonst Dubletten auf Telegram)."""
    import logging

    from output.channels import telegram as telegram_module
    from services.trip_alert import TripAlertService

    class _TelegramHandler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            length = int(self.headers.get("Content-Length", 0))
            self.rfile.read(length)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true,"result":{"message_id":1}}')

        def log_message(self, *args):  # silence
            pass

    tg_httpd = HTTPServer(("127.0.0.1", 0), _TelegramHandler)
    threading.Thread(target=tg_httpd.serve_forever, daemon=True).start()
    original_base = telegram_module.TELEGRAM_API_BASE
    telegram_module.TELEGRAM_API_BASE = f"http://127.0.0.1:{tg_httpd.server_port}"

    stub = _SevenStub(body="305")
    try:
        settings = _sms_settings(configured=True, gateway_url=stub.url).model_copy(
            update={"telegram_bot_token": "test-token", "telegram_chat_id": "12345"}
        )
        assert settings.can_send_telegram() is True
        config = TripReportConfig(
            trip_id="trip-914", send_email=False, send_telegram=True,
            send_sms=True, alert_on_changes=True,
        )
        trip = _trip(report_config=config)
        _briefings_ausserhalb_des_vorlaufs(trip)
        service = TripAlertService(settings=settings, throttle_hours=0, user_id=TEST_USER)
        service.clear_throttle(trip.id)
        assert service._effective_alert_channels(trip) == {"telegram", "sms"}

        cached, fresh = _significant_pair()
        with caplog.at_level(logging.ERROR):
            result = service.check_and_send_alerts(trip, cached, fresh_weather=fresh)

        assert len(stub.received) == 1, "seven.io muss kontaktiert worden sein."
        assert any("SMS alert failed" in r.message for r in caplog.records), (
            "SMS-Fehler muss geloggt werden."
        )
        assert result is True, (
            "ADR-0086: Teilerfolg (Telegram zugestellt) gilt als gesendet."
        )
        assert _alert_log_count(trip.id) == 1
        assert service._throttle_store.last_sent("trip", trip.id) is not None
        throttle_path = get_data_dir(TEST_USER) / "throttle_state.json"
        throttle_data = json.loads(throttle_path.read_text()) if throttle_path.exists() else {}
        assert not throttle_data.get("trip:retry"), (
            "ADR-0086: bei Teilerfolg darf kein Backoff stehen (keine Wiederholung)."
        )
    finally:
        stub.close()
        telegram_module.TELEGRAM_API_BASE = original_base
        tg_httpd.shutdown()
