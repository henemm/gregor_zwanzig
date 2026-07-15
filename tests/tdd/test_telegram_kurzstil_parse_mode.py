"""Feature #1260 (AC-7): Sonderzeichen brechen den Kurzstil-Versand nicht.

Sperrt das bereits implementierte Verhalten (Scheiben S2/S3) fest: enthält der
gerenderte Kurzstil-Text Zeichen wie ``&``, ``<`` oder ``>`` (z.B. in einem
Etappen-/Ortsnamen), muss die EINE Telegram-Nachricht

- mit ``parse_mode`` NICHT gesetzt gesendet werden (der SMS-Text ist NICHT
  HTML-escaped, ein gesetztes ``parse_mode="HTML"`` würde die Bot-API bei einem
  rohen ``<Col>`` als kaputtes Tag ablehnen),
- die Sonderzeichen ROH (unescaped) tragen — kein ``&amp;``/``&lt;``/``&gt;``,
- OHNE Inline-Knöpfe (``reply_markup``) auskommen, und
- vom (echten, lokalen) Telegram-Stub mit ``ok:true`` quittiert werden (der
  Versand scheitert nicht).

Zwei Scope-Pfade werden geprüft: das Trip-Briefing (``send_trip_report``) und
die amtliche Trip-Warnung (``send_official_alert``).

KEINE Mocks als Verhaltensbeweis: der Versand wird über einen ECHTEN lokalen
HTTP-Aufzeichnungs-Server beobachtet (Vorbild:
``test_telegram_kurzstil_trip_briefing.py``). ``TELEGRAM_API_BASE`` wird per
monkeypatch auf den lokalen Stub umgelenkt — Transport-Umlenkung auf einen
echten Server, kein ``Mock``/``patch`` des Verhaltens: bewiesen wird die real
gesendete HTTP-Nutzlast.
"""
from __future__ import annotations

import http.server
import json
import socket
import threading
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import output.channels.telegram as tg_module
from app.config import Settings
from app.models import (
    ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries,
    Provider, SegmentWeatherData, SegmentWeatherSummary, TripReportConfig,
    TripSegment,
)
from app.trip import Stage, Trip, Waypoint
from services.notification_service import NotificationService, TripReportRequest
from services.official_alerts.models import OfficialAlert


# ---------------------------------------------------------------------------
# Echter lokaler Aufzeichnungs-Server (keine Mocks)
# ---------------------------------------------------------------------------

def _free_port() -> int:
    s = socket.socket()
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class _TelegramStub:
    """Lokaler HTTP-Stub für die Telegram-Bot-API. Zeichnet jede sendMessage-
    Nutzlast (text/parse_mode/reply_markup/chat_id) auf und antwortet ok:true."""

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


def _make_trip(name: str, telegram_style: str) -> Trip:
    stage = Stage(
        id="S1", name="Etappe 1", date=datetime(2026, 5, 1).date(),
        waypoints=[
            Waypoint(id="W1", name="Start", lat=42.2, lon=9.05, elevation_m=400),
            Waypoint(id="W2", name="Ziel", lat=42.25, lon=9.09, elevation_m=1200),
        ],
    )
    return Trip(
        id="trip-1260-parsemode", name=name, stages=[stage],
        report_config=TripReportConfig(
            trip_id="trip-1260-parsemode", send_email=False, send_sms=False,
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


def _settings() -> Settings:
    return Settings(
        telegram_bot_token="test-bot-token",
        telegram_chat_id="99999",
    )


def _assert_raw_special_chars(text: str) -> None:
    """Die drei kritischen Zeichen kommen ROH an, NICHT HTML-escaped."""
    assert text, "Setup: Kurzstil-Text darf nicht leer sein."
    assert "&" in text and "<" in text and ">" in text, (
        f"Sonderzeichen fehlen im Kurzstil-Text: {text!r}"
    )
    assert "&amp;" not in text and "&lt;" not in text and "&gt;" not in text, (
        "RED: Kurzstil-Text ist HTML-escaped statt roh — Redirect-Pfad hätte "
        f"parse_mode=None nutzen müssen: {text!r}"
    )


# ---------------------------------------------------------------------------
# AC-7 — Trip-Briefing im Kurzstil mit Sonderzeichen im Etappennamen
# ---------------------------------------------------------------------------

class TestAC7BriefingSpecialChars:
    def test_kurzform_briefing_sends_raw_specials_without_parse_mode(
        self, monkeypatch,
    ) -> None:
        tg_stub = _TelegramStub()
        try:
            monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", tg_stub.base_url)
            settings = _settings()
            svc = NotificationService(settings=settings, user_id="tdd-1260-pm-briefing")

            trip = _make_trip(name="Refuge d'Ortu & <Col>", telegram_style="kurzform")
            request = TripReportRequest(
                trip=trip,
                report_type="evening",
                segment_weather=[_make_segment_data()],
                trip_tz=ZoneInfo("Europe/Vienna"),
                # Sonderzeichen VORNE im Etappennamen: der SMS-Prefix zieht die
                # ersten 10 Zeichen — so landen &/</> sicher im Kurzstil-Text.
                stage_name="&<Col> Grat",
                report_config=trip.report_config,
                send_email=False,
                send_sms=False,
                send_telegram=True,
            )

            result = svc.send_trip_report(request)

            assert len(tg_stub.sent) == 1, (
                "Kurzstil muss GENAU EINE Telegram-Nachricht senden; gesendet "
                f"wurden {len(tg_stub.sent)}."
            )
            payload = tg_stub.sent[0]
            assert "parse_mode" not in payload, (
                "RED: Sonderzeichen-sicherer Kurzstil braucht parse_mode=None; "
                f"gefunden parse_mode={payload.get('parse_mode')!r} — ein rohes "
                "'<Col>' würde die Bot-API im HTML-Modus als kaputtes Tag ablehnen."
            )
            assert "reply_markup" not in payload, (
                "Kurzstil darf keine Inline-Knöpfe (reply_markup) mitsenden."
            )
            _assert_raw_special_chars(payload.get("text") or "")

            # Der (echte) Stub hat mit ok:true quittiert → der Versand scheitert
            # nicht: Telegram gilt als zugestellt.
            assert "telegram" in result.sent_channels
            assert result.telegram_fully_sent is True
        finally:
            tg_stub.stop()


# ---------------------------------------------------------------------------
# AC-7 — Amtliche Trip-Warnung im Kurzstil mit Sonderzeichen im Trip-Namen
# ---------------------------------------------------------------------------

class TestAC7OfficialAlertSpecialChars:
    def test_kurzform_official_alert_sends_raw_specials_without_parse_mode(
        self, monkeypatch,
    ) -> None:
        tg_stub = _TelegramStub()
        try:
            monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", tg_stub.base_url)
            settings = _settings()
            svc = NotificationService(settings=settings, user_id="tdd-1260-pm-official")

            # Trip-Name (ohne Leerzeichen zusammengezogen) wird zum SMS-Prefix,
            # der die Sonderzeichen in den amtlichen Kurzstil-Text trägt.
            trip = _make_trip(name="Ort & <X>", telegram_style="kurzform")
            result = svc.send_official_alert(
                trip=trip,
                notices=_make_official_notices(),
                effective_channels={"telegram"},
                telegram_style="kurzform",
            )

            assert len(tg_stub.sent) == 1, (
                "Amtliche Trip-Warnung im Kurzstil muss GENAU EINE Telegram-"
                f"Nachricht senden; gesendet wurden {len(tg_stub.sent)}."
            )
            payload = tg_stub.sent[0]
            assert "parse_mode" not in payload, (
                "RED: amtliche Kurzstil-Warnung braucht parse_mode=None; gefunden "
                f"parse_mode={payload.get('parse_mode')!r}."
            )
            assert "reply_markup" not in payload
            _assert_raw_special_chars(payload.get("text") or "")

            assert "telegram" in result.sent_channels
        finally:
            tg_stub.stop()
