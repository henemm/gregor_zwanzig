"""Feature #1260 (AC-10): Zwei-Nutzer-Isolation des Telegram-Kurzstils.

Sperrt fest: der Kurzstil-Schalter ist strikt pro Nutzer/Trip. Zwei getrennte
Nutzer mit eigenem ``NotificationService(user_id=...)`` und eigenem Trip

- Nutzer A: ``telegram_style="kurzform"``
- Nutzer B: ``telegram_style="rich"``

erhalten unabhängig ein Trip-Briefing. Erwartet:

- A bekommt GENAU EINE Kurzstil-Nachricht (``parse_mode`` NICHT gesetzt, keine
  Inline-Knöpfe),
- B bekommt die reiche Bubble-Kette (jede Bubble ``parse_mode="HTML"``),
- KEINE Vermischung: keine A-Nachricht im HTML-Stil, keine B-Nachricht ohne
  ``parse_mode``,
- KEIN ``user_id="default"``-Fallback im Pfad (beide Services tragen ihre echte
  ``user_id``).

Getrennte Beobachtbarkeit über verschiedene ``telegram_chat_id`` je Nutzer: EIN
echter lokaler Telegram-Stub zeichnet alle Nutzlasten auf, die Partitionierung
erfolgt über die ``chat_id`` — so ist beweisbar, dass jede Nachricht im richtigen
Chat mit dem richtigen Stil landet.

KEINE Mocks als Verhaltensbeweis: ``TELEGRAM_API_BASE`` wird per monkeypatch auf
den lokalen Stub umgelenkt (Transport-Umlenkung, kein ``Mock``/``patch`` des
Verhaltens — bewiesen wird die real gesendete HTTP-Nutzlast).
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
    Nutzlast (chat_id/text/parse_mode/reply_markup) auf und antwortet ok:true."""

    def __init__(self) -> None:
        self.sent: list[dict] = []
        sent = self.sent
        counter = {"mid": 4000}

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


def _make_trip(trip_id: str, telegram_style: str) -> Trip:
    stage = Stage(
        id="S1", name="Etappe 1", date=datetime(2026, 5, 1).date(),
        waypoints=[
            Waypoint(id="W1", name="Start", lat=42.2, lon=9.05, elevation_m=400),
            Waypoint(id="W2", name="Ziel", lat=42.25, lon=9.09, elevation_m=1200),
        ],
    )
    return Trip(
        id=trip_id, name=f"Trip-{trip_id}", stages=[stage],
        report_config=TripReportConfig(
            trip_id=trip_id, send_email=False, send_sms=False,
            send_telegram=True, telegram_style=telegram_style,
        ),
    )


def _settings(chat_id: str) -> Settings:
    return Settings(
        telegram_bot_token=f"bot-{chat_id}",
        telegram_chat_id=chat_id,
    )


def _make_request(trip: Trip) -> TripReportRequest:
    return TripReportRequest(
        trip=trip,
        report_type="evening",
        segment_weather=[_make_segment_data()],
        trip_tz=ZoneInfo("Europe/Vienna"),
        report_config=trip.report_config,
        send_email=False,
        send_sms=False,
        send_telegram=True,
    )


# ---------------------------------------------------------------------------
# AC-10 — Zwei Nutzer, getrennte Schalter-Zustände, keine Vermischung
# ---------------------------------------------------------------------------

class TestAC10MultiUserIsolation:
    def test_two_users_keep_independent_telegram_styles(self, monkeypatch) -> None:
        tg_stub = _TelegramStub()
        try:
            monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", tg_stub.base_url)

            chat_a, chat_b = "1111-userA", "2222-userB"

            # Zwei ECHTE, getrennte Nutzer-Kontexte — explizite user_id, KEIN
            # "default"-Fallback; getrennte Settings (eigene chat_id).
            svc_a = NotificationService(
                settings=_settings(chat_a), user_id="user-a-1260",
            )
            svc_b = NotificationService(
                settings=_settings(chat_b), user_id="user-b-1260",
            )

            trip_a = _make_trip("A", telegram_style="kurzform")
            trip_b = _make_trip("B", telegram_style="rich")

            # Unabhängiger Versand je Nutzer.
            svc_a.send_trip_report(_make_request(trip_a))
            svc_b.send_trip_report(_make_request(trip_b))

            # Getrennt beobachtbar: Partition nach chat_id.
            a_msgs = [p for p in tg_stub.sent if p.get("chat_id") == chat_a]
            b_msgs = [p for p in tg_stub.sent if p.get("chat_id") == chat_b]

            # (1) Kein Streuverlust: jede aufgezeichnete Nachricht gehört genau
            #     einem der beiden Chats.
            assert len(a_msgs) + len(b_msgs) == len(tg_stub.sent), (
                "Fremde chat_id im Stub — Settings-Isolation verletzt: "
                f"{[p.get('chat_id') for p in tg_stub.sent]!r}"
            )

            # (2) Nutzer A: GENAU EINE Kurzstil-Nachricht, parse_mode nicht gesetzt.
            assert len(a_msgs) == 1, (
                "Kurzstil-Nutzer A muss GENAU EINE Telegram-Nachricht bekommen; "
                f"gefunden {len(a_msgs)}."
            )
            assert "parse_mode" not in a_msgs[0], (
                "RED: A-Kurzstil muss parse_mode=None nutzen; gefunden "
                f"parse_mode={a_msgs[0].get('parse_mode')!r}."
            )
            assert "reply_markup" not in a_msgs[0], (
                "A-Kurzstil darf keine Inline-Knöpfe mitsenden."
            )

            # (3) Nutzer B: reiche Bubble-Kette, jede Bubble parse_mode=HTML.
            assert len(b_msgs) >= 1, (
                "Rich-Nutzer B muss mindestens eine HTML-Bubble bekommen."
            )
            assert all(p.get("parse_mode") == "HTML" for p in b_msgs), (
                "Regression/Vermischung: B (rich) muss die HTML-Bubbles behalten; "
                f"gefunden {[p.get('parse_mode') for p in b_msgs]!r}."
            )

            # (4) Keine Vermischung in der Gegenrichtung: keine A-Nachricht im
            #     HTML-Stil, keine B-Nachricht ohne parse_mode.
            assert all("parse_mode" not in p for p in a_msgs), (
                "Vermischung: A (kurzform) enthält eine HTML-Nachricht."
            )
            assert all("parse_mode" in p for p in b_msgs), (
                "Vermischung: B (rich) enthält eine Nachricht ohne parse_mode."
            )

            # (5) Kein "default"-Fallback: beide Services tragen ihre echte user_id.
            assert svc_a._user_id == "user-a-1260" != "default"
            assert svc_b._user_id == "user-b-1260" != "default"
        finally:
            tg_stub.stop()
