"""TDD RED — Feature #1260 (Scheibe S2): Trip-Briefing-Redirect für den
Telegram-Kurzstil.

Deckt ab:
- AC-2 (kurzform): Ist ``telegram_style="kurzform"`` gesetzt, erhält Telegram
  GENAU EINE Nachricht mit demselben kurzen Text wie die SMS-Variante
  (byte-identisch zu ``report.sms_text``), OHNE Bubbles, OHNE Inline-Knöpfe,
  mit ``parse_mode=None`` (kein HTML).
- AC-1 (rich / Default): Regression — Telegram erhält weiterhin die reiche
  Bubble-Liste mit ``parse_mode="HTML"``.

KEINE Mocks als Verhaltensbeweis. Beobachtung des Versands über ECHTE lokale
HTTP-Aufzeichnungs-Server (recording sinks): ein seven.io-SMS-Stub (Vorbild:
test_issue_1069_tier_channel_gating.py) und ein Telegram-Bot-API-Stub. Der
Telegram-``TELEGRAM_API_BASE`` wird per monkeypatch auf den lokalen Stub
umgelenkt (Vorbild: test_issue_686_telegram_functional_live.py:92) — das ist
Transport-Umlenkung auf einen echten Server, kein ``Mock``/``patch`` des
Verhaltens: bewiesen wird die real gesendete HTTP-Nutzlast.

RED-Ursache (vor der Implementierung):
- ``TripReportConfig`` kennt ``telegram_style`` noch nicht → TypeError beim
  Konstruieren der Test-Config.
- ``send_trip_report`` verzweigt noch nicht auf den Kurzstil → sendet auch bei
  ``kurzform`` die Bubbles mit ``parse_mode="HTML"`` statt ``report.sms_text``.
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
    ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries,
    Provider, SegmentWeatherData, SegmentWeatherSummary, TripSegment,
)
from app.trip import Stage, Trip, Waypoint
from services.notification_service import NotificationService, TripReportRequest


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
        counter = {"mid": 1000}

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


def _make_trip(telegram_style: str) -> Trip:
    from app.models import TripReportConfig
    stage = Stage(
        id="S1", name="Etappe 1", date=datetime(2026, 5, 1).date(),
        waypoints=[
            Waypoint(id="W1", name="Start", lat=42.2, lon=9.05, elevation_m=400),
            Waypoint(id="W2", name="Ziel", lat=42.25, lon=9.09, elevation_m=1200),
        ],
    )
    return Trip(
        id="trip-1260-briefing", name="Kurzstil-Trip", stages=[stage],
        report_config=TripReportConfig(
            trip_id="trip-1260-briefing", send_email=False, send_sms=True,
            send_telegram=True, telegram_style=telegram_style,
        ),
    )


def _settings(telegram_base_port: int, sms_port: int) -> Settings:
    return Settings(
        telegram_bot_token="test-bot-token",
        telegram_chat_id="99999",
        sms_gateway_url=f"http://127.0.0.1:{sms_port}/api/sms",
        seven_api_key="test-stub-key",
        sms_to="+49000000000",
        sms_from=None,
    )


def _make_request(trip: Trip, *, send_sms: bool) -> TripReportRequest:
    return TripReportRequest(
        trip=trip,
        report_type="evening",
        segment_weather=[_make_segment_data()],
        trip_tz=ZoneInfo("Europe/Vienna"),
        report_config=trip.report_config,
        send_email=False,
        send_sms=send_sms,
        send_telegram=True,
    )


# ---------------------------------------------------------------------------
# AC-2 — Kurzstil: Telegram bekommt EINE Nachricht = SMS-Text, kein HTML/Bubble
# ---------------------------------------------------------------------------

class TestAC2KurzstilRedirectsSmsTextToTelegram:
    def test_kurzform_sends_single_sms_text_to_telegram(self, monkeypatch) -> None:
        tg_stub = _TelegramStub()
        sms_stub = _SMSStub()
        try:
            monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", tg_stub.base_url)

            settings = _settings(tg_stub.port, sms_stub.port)
            svc = NotificationService(settings=settings, user_id="tdd-1260-briefing")

            # RED: TripReportConfig(telegram_style="kurzform") wirft hier TypeError.
            trip = _make_trip(telegram_style="kurzform")
            request = _make_request(trip, send_sms=True)

            svc.send_trip_report(request)

            # (a) Genau EINE Telegram-Nachricht — keine Bubble-Kette.
            assert len(tg_stub.sent) == 1, (
                "RED: Kurzstil muss EINE Telegram-Nachricht senden, gesendet wurden "
                f"{len(tg_stub.sent)} (noch die reiche Bubble-Kette). "
                "send_trip_report muss bei telegram_style='kurzform' den SMS-Text "
                "statt der Bubbles senden."
            )
            payload = tg_stub.sent[0]

            # (b) parse_mode NICHT gesetzt (Redirect sendet unescapten SMS-Text).
            assert "parse_mode" not in payload, (
                "RED: Kurzstil-Redirect muss parse_mode=None nutzen; gefunden: "
                f"parse_mode={payload.get('parse_mode')!r} (HTML-Bubble-Pfad)."
            )

            # (c) Keine Inline-Knöpfe.
            assert "reply_markup" not in payload, (
                "RED: Kurzstil darf keine Inline-Knöpfe (reply_markup) mitsenden."
            )

            # (d) Byte-identisch zum parallel erzeugten SMS-Text.
            assert len(sms_stub.received) == 1, (
                "Setup: die SMS-Referenz muss genau einmal am Stub angekommen sein."
            )
            sms_text = sms_stub.received[0]["text"]
            assert sms_text, "Setup: SMS-Text darf nicht leer sein."
            assert payload.get("text") == sms_text, (
                "RED: Telegram-Body im Kurzstil ist nicht byte-identisch zum "
                f"SMS-Text.\n  Telegram={payload.get('text')!r}\n  SMS={sms_text!r}"
            )
        finally:
            tg_stub.stop()
            sms_stub.stop()


# ---------------------------------------------------------------------------
# AC-1 — Default/rich: Telegram bekommt weiterhin die reiche Bubble-Liste (HTML)
# ---------------------------------------------------------------------------

class TestAC1RichRemainsBubbleList:
    def test_rich_style_still_sends_html_bubbles(self, monkeypatch) -> None:
        tg_stub = _TelegramStub()
        try:
            monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", tg_stub.base_url)

            settings = _settings(tg_stub.port, _free_port())
            svc = NotificationService(settings=settings, user_id="tdd-1260-briefing")

            # RED: TripReportConfig(telegram_style="rich") wirft hier TypeError,
            # solange das Feld noch nicht existiert.
            trip = _make_trip(telegram_style="rich")
            request = _make_request(trip, send_sms=False)

            svc.send_trip_report(request)

            assert len(tg_stub.sent) >= 1, (
                "Rich-Default muss mindestens eine Telegram-Bubble senden."
            )
            # Reiche Bubbles werden mit parse_mode=HTML gerendert — der
            # Fingerabdruck, der sie vom Kurzstil-Plaintext unterscheidet.
            assert all(p.get("parse_mode") == "HTML" for p in tg_stub.sent), (
                "Regression: rich/Default muss die HTML-Bubbles unverändert senden "
                f"(parse_mode='HTML'); gefunden: "
                f"{[p.get('parse_mode') for p in tg_stub.sent]!r}."
            )
        finally:
            tg_stub.stop()
