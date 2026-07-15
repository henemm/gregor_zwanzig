"""TDD RED — Feature #1260 (Scheibe S3): Trip-Alarme-Redirect für den
Telegram-Kurzstil.

Deckt ab:
- AC-3 (Abweichungs-Alarm): Ist ``telegram_style="kurzform"`` gesetzt, erhält
  Telegram für einen Trip-Abweichungs-Alarm GENAU EINE Nachricht mit demselben
  kurzen Text wie die SMS-Variante (byte-identisch zu ``render_alert_sms``),
  OHNE reiche HTML-Bubble, mit ``parse_mode=None`` und OHNE Inline-Knöpfe.
  Bei ``rich`` (Default) bleibt der reiche HTML-Alarm (``parse_mode="HTML"``).
- AC-4 (amtliche Trip-Warnung): Ist ``telegram_style="kurzform"`` gesetzt,
  erhält Telegram für eine amtliche Standalone-Warnung denselben kurzen Text
  wie SMS (``render_official_alert_sms``), ``parse_mode=None``. Bei ``rich``
  bleibt die reiche Telegram-Warnvorlage (``parse_mode="HTML"``).
- Guard (keine Kopplung an Compare): ein regulärer Compare-Abweichungs-Alarm
  (``send_multi_location_deviation_alert`` → geteilter ``_dispatch_alert_message``)
  bleibt UNBEEINFLUSST — Default ``rich`` (HTML), weil der Compare-Aufrufer
  ``telegram_style`` nicht setzt und der Dispatch ihn nicht aus einer globalen
  Quelle rät.

KEINE Mocks als Verhaltensbeweis. Beobachtung des Versands über ECHTE lokale
HTTP-Aufzeichnungs-Server (recording sinks), wie in S2
(``test_telegram_kurzstil_trip_briefing.py``): ein seven.io-SMS-Stub und ein
Telegram-Bot-API-Stub; der ``TELEGRAM_API_BASE`` wird per monkeypatch auf den
lokalen Stub umgelenkt (Transport-Umlenkung, kein ``Mock``/``patch`` des
Verhaltens — bewiesen wird die real gesendete HTTP-Nutzlast).

RED-Ursache (vor der Implementierung):
- ``send_deviation_alert`` / ``send_official_alert`` kennen den Parameter
  ``telegram_style`` noch nicht → TypeError beim Aufruf.
- ``_dispatch_alert_message`` verzweigt noch nicht auf den Kurzstil → sendet
  auch bei ``kurzform`` die reiche HTML-Bubble statt ``sms_body``.
- ``trip_alert.py`` löst ``trip.report_config.telegram_style`` noch nicht auf
  und reicht ihn nicht durch → der Trip-Pfad (``_send_alert``) sendet HTML.
"""
from __future__ import annotations

import http.server
import json
import socket
import threading
import urllib.parse
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import output.channels.telegram as tg_module
from app.config import Settings
from app.models import (
    ChangeSeverity, ForecastDataPoint, ForecastMeta, GPXPoint,
    NormalizedTimeseries, Provider, SegmentWeatherData, SegmentWeatherSummary,
    TripReportConfig, TripSegment, WeatherChange,
)
from app.trip import Stage, Trip, Waypoint
from services.notification_service import NotificationService
from services.official_alerts.models import OfficialAlert
from services.trip_alert import TripAlertService


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
        counter = {"mid": 2000}

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

def _make_segment_data() -> SegmentWeatherData:
    points = [
        ForecastDataPoint(
            ts=datetime(2026, 5, 1, 9 + h, 0, tzinfo=timezone.utc),
            t2m_c=15.0 + h, wind10m_kmh=10.0 + h, gust_kmh=22.0 + h,
            pop_pct=40, precip_1h_mm=0.4, wind_chill_c=12.0 + h, cloud_total_pct=55,
        )
        for h in range(6)
    ]
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="icon_d2",
        run=datetime(2026, 5, 1, 0, 0, tzinfo=timezone.utc),
        grid_res_km=2.0, interp="point_grid",
    )
    ts = NormalizedTimeseries(meta=meta, data=points)
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.2, lon=9.05, elevation_m=400.0),
        end_point=GPXPoint(lat=42.25, lon=9.09, elevation_m=1200.0),
        start_time=datetime(2026, 5, 1, 9, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 5, 1, 13, 0, tzinfo=timezone.utc),
        duration_hours=4.0, distance_km=8.0, ascent_m=800.0, descent_m=0.0,
    )
    agg = SegmentWeatherSummary(
        temp_min_c=15.0, temp_max_c=20.0, temp_avg_c=17.5,
        wind_max_kmh=16.0, gust_max_kmh=28.0, precip_sum_mm=2.4, cloud_avg_pct=55,
    )
    return SegmentWeatherData(
        segment=seg, timeseries=ts, aggregated=agg,
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )


def _make_change() -> WeatherChange:
    return WeatherChange(
        metric="temp_max_c", old_value=18.0, new_value=26.0, delta=8.0,
        threshold=5.0, severity=ChangeSeverity.MODERATE, direction="increase",
        segment_id="1", occurred_at="12:00",
    )


def _make_trip(telegram_style: str, *, send_sms: bool) -> Trip:
    stage = Stage(
        id="S1", name="Etappe 1", date=datetime(2026, 5, 1).date(),
        waypoints=[
            Waypoint(id="W1", name="Start", lat=42.2, lon=9.05, elevation_m=400),
            Waypoint(id="W2", name="Ziel", lat=42.25, lon=9.09, elevation_m=1200),
        ],
    )
    return Trip(
        id="trip-1260-alert", name="Kurzstil-Trip", stages=[stage],
        report_config=TripReportConfig(
            trip_id="trip-1260-alert", send_email=False, send_sms=send_sms,
            send_telegram=True, telegram_style=telegram_style,
        ),
    )


def _make_official_notices() -> list:
    alert = OfficialAlert(
        source="vigilance", hazard="thunderstorm", level=3,
        label="Gewitter & Sturm <stark>",
        valid_from=datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc),
        valid_to=datetime(2026, 5, 1, 20, 0, tzinfo=timezone.utc),
        region_label="Haute-Corse",
    )
    return [(alert, ["1"])]


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
# AC-3 — Trip-Abweichungs-Alarm im Kurzstil
# ---------------------------------------------------------------------------

class TestAC3DeviationAlertKurzstil:
    def test_kurzform_trip_path_sends_plaintext_no_parse_mode(self, monkeypatch) -> None:
        """Vollständiger Trip-Pfad (TripAlertService._send_alert): der aus
        ``trip.report_config.telegram_style`` aufgelöste Kurzstil erreicht den
        Dispatch — Telegram bekommt Plaintext ohne parse_mode/Knöpfe."""
        tg_stub = _TelegramStub()
        try:
            monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", tg_stub.base_url)
            settings = _settings(sms_port=_free_port())
            svc = TripAlertService(settings=settings, user_id="tdd-1260-alert-a")

            # Telegram-only (kein SMS-Tier-Gate); Style aus dem Trip aufgelöst.
            trip = _make_trip("kurzform", send_sms=False)
            # RED: telegram_style-Threading fehlt → _send_alert sendet HTML-Bubble.
            svc._send_alert(trip, [_make_segment_data()], [_make_change()])

            assert len(tg_stub.sent) == 1, (
                "RED: Kurzstil muss EINE Telegram-Nachricht senden, gesendet "
                f"wurden {len(tg_stub.sent)} (noch die reiche HTML-Bubble)."
            )
            payload = tg_stub.sent[0]
            assert "parse_mode" not in payload, (
                "RED: Kurzstil-Redirect muss parse_mode=None nutzen; gefunden: "
                f"parse_mode={payload.get('parse_mode')!r} (HTML-Bubble-Pfad)."
            )
            assert "reply_markup" not in payload, (
                "RED: Kurzstil darf keine Inline-Knöpfe (reply_markup) mitsenden."
            )
            assert "<b>" not in (payload.get("text") or ""), (
                "RED: Kurzstil-Body enthält HTML-Tags — es ist noch der reiche "
                f"Telegram-Alarm: {payload.get('text')!r}"
            )
        finally:
            tg_stub.stop()

    def test_rich_trip_path_still_sends_html(self, monkeypatch) -> None:
        tg_stub = _TelegramStub()
        try:
            monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", tg_stub.base_url)
            settings = _settings(sms_port=_free_port())
            svc = TripAlertService(settings=settings, user_id="tdd-1260-alert-b")

            trip = _make_trip("rich", send_sms=False)
            svc._send_alert(trip, [_make_segment_data()], [_make_change()])

            assert len(tg_stub.sent) >= 1
            assert all(p.get("parse_mode") == "HTML" for p in tg_stub.sent), (
                "Regression: rich/Default muss den HTML-Alarm unverändert senden; "
                f"gefunden: {[p.get('parse_mode') for p in tg_stub.sent]!r}."
            )
        finally:
            tg_stub.stop()

    def test_kurzform_telegram_body_equals_sms_body(self, monkeypatch) -> None:
        """Byte-Identität: bei aktivem Kurzstil ist der Telegram-Body identisch
        zum parallel gesendeten SMS-Text (beide aus demselben AlertMessage)."""
        tg_stub = _TelegramStub()
        sms_stub = _SMSStub()
        try:
            monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", tg_stub.base_url)
            settings = _settings(sms_port=sms_stub.port)
            svc = NotificationService(settings=settings, user_id="tdd-1260-alert-c")

            trip = _make_trip("kurzform", send_sms=True)
            # RED: send_deviation_alert kennt telegram_style noch nicht → TypeError.
            svc.send_deviation_alert(
                trip=trip,
                weather=[_make_segment_data()],
                changes=[_make_change()],
                effective_channels={"telegram", "sms"},
                telegram_style=trip.report_config.telegram_style,
            )

            assert len(tg_stub.sent) == 1
            assert len(sms_stub.received) == 1
            payload = tg_stub.sent[0]
            sms_text = sms_stub.received[0]["text"]
            assert sms_text, "Setup: SMS-Text darf nicht leer sein."
            assert "parse_mode" not in payload
            assert "reply_markup" not in payload
            assert payload.get("text") == sms_text, (
                "RED: Telegram-Body im Kurzstil ist nicht byte-identisch zum "
                f"SMS-Text.\n  Telegram={payload.get('text')!r}\n  SMS={sms_text!r}"
            )
        finally:
            tg_stub.stop()
            sms_stub.stop()


# ---------------------------------------------------------------------------
# AC-4 — Amtliche Trip-Warnung im Kurzstil
# ---------------------------------------------------------------------------

class TestAC4OfficialAlertKurzstil:
    def test_kurzform_telegram_body_equals_official_sms(self, monkeypatch) -> None:
        tg_stub = _TelegramStub()
        sms_stub = _SMSStub()
        try:
            monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", tg_stub.base_url)
            settings = _settings(sms_port=sms_stub.port)
            svc = NotificationService(settings=settings, user_id="tdd-1260-off-a")

            trip = _make_trip("kurzform", send_sms=True)
            # RED: send_official_alert kennt telegram_style noch nicht → TypeError.
            svc.send_official_alert(
                trip=trip,
                notices=_make_official_notices(),
                effective_channels={"telegram", "sms"},
                telegram_style="kurzform",
            )

            assert len(tg_stub.sent) == 1
            assert len(sms_stub.received) == 1
            payload = tg_stub.sent[0]
            sms_text = sms_stub.received[0]["text"]
            assert sms_text, "Setup: amtlicher SMS-Text darf nicht leer sein."
            assert "parse_mode" not in payload, (
                "RED: amtliche Trip-Warnung im Kurzstil muss parse_mode=None "
                f"nutzen; gefunden parse_mode={payload.get('parse_mode')!r}."
            )
            assert "reply_markup" not in payload
            assert payload.get("text") == sms_text, (
                "RED: Telegram-Body der amtlichen Warnung im Kurzstil ist nicht "
                "identisch zum render_official_alert_sms-Text.\n"
                f"  Telegram={payload.get('text')!r}\n  SMS={sms_text!r}"
            )
        finally:
            tg_stub.stop()
            sms_stub.stop()

    def test_rich_sends_html_official_telegram(self, monkeypatch) -> None:
        tg_stub = _TelegramStub()
        try:
            monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", tg_stub.base_url)
            settings = _settings(sms_port=_free_port())
            svc = NotificationService(settings=settings, user_id="tdd-1260-off-b")

            trip = _make_trip("rich", send_sms=False)
            svc.send_official_alert(
                trip=trip,
                notices=_make_official_notices(),
                effective_channels={"telegram"},
                telegram_style="rich",
            )

            assert len(tg_stub.sent) == 1
            assert tg_stub.sent[0].get("parse_mode") == "HTML", (
                "Regression: rich/Default muss die reiche Telegram-Warnvorlage "
                f"(parse_mode='HTML') senden; gefunden "
                f"{tg_stub.sent[0].get('parse_mode')!r}."
            )
        finally:
            tg_stub.stop()


# ---------------------------------------------------------------------------
# Guard — regulärer Compare-Abweichungs-Alarm bleibt unbeeinflusst (Default rich)
# ---------------------------------------------------------------------------

class TestGuardCompareDeviationUnaffected:
    def test_compare_deviation_defaults_to_rich(self, monkeypatch) -> None:
        """Der geteilte ``_dispatch_alert_message`` darf ``telegram_style`` NUR
        aus seinem Parameter beziehen. Ein Compare-Aufrufer, der ihn nicht
        setzt, muss den reichen HTML-Alarm behalten (keine Kopplung an ein
        Trip-Feld)."""
        tg_stub = _TelegramStub()
        try:
            monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", tg_stub.base_url)
            settings = _settings(sms_port=_free_port())
            svc = NotificationService(settings=settings, user_id="tdd-1260-cmp")

            point = GPXPoint(lat=42.2, lon=9.05, elevation_m=400.0)
            svc.send_multi_location_deviation_alert(
                entities=[("Ort A", [point], [_make_change()])],
                effective_channels={"telegram"},
            )

            assert len(tg_stub.sent) >= 1
            assert all(p.get("parse_mode") == "HTML" for p in tg_stub.sent), (
                "Kopplungs-Guard: Compare-Abweichungs-Alarm muss den reichen "
                f"HTML-Alarm behalten; gefunden "
                f"{[p.get('parse_mode') for p in tg_stub.sent]!r}."
            )
        finally:
            tg_stub.stop()


# ---------------------------------------------------------------------------
# Wiring — der Resolver liest report_config.telegram_style (Default rich)
# ---------------------------------------------------------------------------

class TestTelegramStyleResolver:
    def test_resolver_reads_report_config_and_defaults_rich(self) -> None:
        from services.trip_alert import _trip_telegram_style

        kurz = _make_trip("kurzform", send_sms=False)
        assert _trip_telegram_style(kurz) == "kurzform"

        rich = _make_trip("rich", send_sms=False)
        assert _trip_telegram_style(rich) == "rich"

        no_cfg = Trip(id="t", name="Ohne Config", stages=[], report_config=None)
        assert _trip_telegram_style(no_cfg) == "rich"
