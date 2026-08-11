"""RED — Issue #1701 (#1676 Scheibe S2b): Kanal-Schwelle (ADR-0046) fuer
Premium-SMS.

Spec: docs/specs/modules/feat_1701_alarm_premium_sms.md
Abgedeckt: AC-8.

WICHTIGER BEFUND BEIM SCHREIBEN DIESES TESTS (D6 der Spec): ``services.
alert_channel_threshold.split_by_threshold()`` ist BEREITS kanal-agnostisch
-- ein reiner Aufruf mit ``channels={"premium_sms"}`` ist schon HEUTE
korrekt und damit KEIN legitimer RED-Treiber (ein isolierter Funktionstest
waere bereits gruen, siehe Kontrollmessung unten). Die tatsaechlich fehlende
Funktionalitaet liegt bei ``_effective_alert_channels()``
(``trip_alert.py:1492-1494``): Premium-SMS wird dort HEUTE ueberhaupt nicht
als Kanal erkannt, unabhaengig von jeder Schwelle. Der RED-Nachweis muss
deshalb END-ZU-ENDE laufen und BEIDE Seiten zeigen (Vorbild: die uebrige
Testsuite dieses Projekts verlangt fuer genau diese Faelle immer die
Gegenprobe, s. ``tests/tdd/test_compare_alert_channel_delivery.py``
Modul-Docstring): die HIGH-Schwelle unterdrueckt (heute trivial gruen, weil
der Kanal noch gar nicht existiert) UND die Gegenprobe ohne Schwelle liefert
tatsaechlich zu (heute ROT, weil der Kanal fehlt). Erst das Paar beweist,
dass die SCHWELLE entscheidet -- nicht die (noch fehlende)
Kanal-Erkennung selbst.

TESTPOLITIK (CLAUDE.md "Test-Politik: Zwei Schichten", Kern-Schicht): kein
Mock-Theater, echter lokaler HTTP-Stub (Vorbild
``tests/unit/test_alert_channel_premium_sms.py``).
"""
from __future__ import annotations

import http.server
import socket
import threading
import urllib.parse
import uuid
from datetime import date, datetime, timedelta, timezone

from app.config import Settings
from app.models import (
    ChangeSeverity,
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    TripReportConfig,
    TripSegment,
    WeatherChange,
)
from app.trip import Stage, Trip, Waypoint
from services import alert_channel_threshold

LEARNED_REPLY_TO = "+4915799912345"
LAT, LON = 47.0, 11.0


def _free_port() -> int:
    s = socket.socket()
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class _SevenIoStub:
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

    def to(self, number: str) -> list[dict]:
        return [e for e in self.received if e.get("to") == number]


def _uid(prefix: str) -> str:
    return f"tdd-1701-thr-{prefix}-{uuid.uuid4().hex[:6]}"


def _write_profile(user_id: str, *, tier: str, reply_to: str) -> None:
    import json

    from app.loader import get_data_dir

    path = get_data_dir(user_id)
    path.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc) - timedelta(minutes=5)
    profile = {
        "id": user_id, "tier": tier,
        "premium_sms_reply_to": reply_to,
        "premium_sms_reply_at": stamp.isoformat().replace("+00:00", "Z"),
    }
    (path / "user.json").write_text(json.dumps(profile), encoding="utf-8")


def _settings(port: int, user_id: str) -> Settings:
    update = {
        "sms_gateway_url": f"http://127.0.0.1:{port}/api/sms",
        "seven_api_key": "test-stub-key",
        "seven_sandbox_key": "test-stub-key",
        "sms_to": "+49000000111",
        "sms_from": None,
    }
    return Settings().with_user_profile(user_id).model_copy(update=update)


def _weather_segment(segment_id: int | str = 1, **summary_kwargs) -> SegmentWeatherData:
    now = datetime.now(timezone.utc)
    seg = TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=LAT, lon=LON, elevation_m=1000),
        end_point=GPXPoint(lat=LAT + 0.1, lon=LON + 0.1, elevation_m=1500),
        start_time=now - timedelta(hours=1), end_time=now + timedelta(hours=3),
        duration_hours=4.0, distance_km=6.0, ascent_m=500, descent_m=0,
    )
    return SegmentWeatherData(
        segment=seg,
        timeseries=NormalizedTimeseries(
            meta=ForecastMeta(provider=Provider.OPENMETEO, model="test", grid_res_km=1.0),
            data=[],
        ),
        aggregated=SegmentWeatherSummary(**summary_kwargs),
        fetched_at=now, provider="openmeteo",
    )


def _low_urgency_change() -> WeatherChange:
    """MINOR -> Dringlichkeit 'LOW' (``alert_urgency.urgency_from_changes``)."""
    return WeatherChange(
        metric="gust_max_kmh", old_value=20.0, new_value=45.0, delta=25.0,
        threshold=20.0, severity=ChangeSeverity.MINOR, direction="increase",
        segment_id="1",
    )


def _trip(trip_id: str, *, threshold: str | None) -> Trip:
    stage = Stage(
        id="T1", name="Tag 1", date=date.today(),
        waypoints=[Waypoint(id="W1", name="Start", lat=LAT, lon=LON, elevation_m=1000.0)],
    )
    trip = Trip(id=trip_id, name="Schwellen-Trip", stages=[stage], official_warnings=None)
    trip.report_config = TripReportConfig(
        trip_id=trip_id, send_email=False, alert_on_changes=True,
    )
    trip.alert_channels = {"premium_sms": True}
    trip.alert_cooldown_minutes = 0
    trip.official_alert_triggers_enabled = False
    if threshold is not None:
        trip.alert_channel_thresholds = {"premium_sms": threshold}
    return trip


# ═══════════════════════════════ AC-8 ═════════════════════════════════════

def test_premium_sms_suppressed_below_configured_threshold():
    """AC-8: Given ein Nutzer hat fuer Premium-SMS die Schwelle 'HIGH'
    eingestellt UND ein ausgeloester Alarm hat die Dringlichkeit 'LOW' /
    When der Alarm verarbeitet wird / Then bleibt die Premium-SMS aus --
    UND die Gegenprobe OHNE gesetzte Schwelle (Startwert 'LOW') liefert
    denselben Alarm regulaer zu. Nur das Paar beweist, dass die SCHWELLE
    entscheidet.

    Kontrollmessung (kein RED-Treiber, s. Moduldocstring): der reine
    Funktionsaufruf ist schon heute korrekt.
    """
    allowed, suppressed = alert_channel_threshold.split_by_threshold(
        {"premium_sms"}, "MODERATE", {"premium_sms": "HIGH"},
    )
    assert suppressed == {"premium_sms"} and allowed == set(), (
        "Kontrollmessung: split_by_threshold() ist bereits kanal-agnostisch "
        f"korrekt (D6) -- gefunden allowed={allowed!r}, suppressed={suppressed!r}"
    )

    from services.trip_alert import TripAlertService

    uid = _uid("ac8")
    _write_profile(uid, tier="premium", reply_to=LEARNED_REPLY_TO)

    stub = _SevenIoStub()
    try:
        settings = _settings(stub.port, uid)

        # -- HIGH-Schwelle: die gering-dringliche Meldung bleibt aus --
        trip_high = _trip(f"trip-ac8-high-{uuid.uuid4().hex[:6]}", threshold="HIGH")
        TripAlertService(
            settings=settings, user_id=uid, throttle_hours=0,
            mail_sink=lambda subject, body: None,
        )._send_alert(trip_high, [_weather_segment(1)], [_low_urgency_change()])

        assert stub.to(LEARNED_REPLY_TO) == [], (
            "AC-8: bei HIGH-Schwelle und geringer Dringlichkeit darf KEINE "
            f"Premium-SMS gehen, erhalten: {stub.to(LEARNED_REPLY_TO)!r}"
        )

        # -- Gegenprobe: keine gesetzte Schwelle (Startwert 'LOW') -> liefert --
        trip_low = _trip(f"trip-ac8-low-{uuid.uuid4().hex[:6]}", threshold=None)
        assert trip_low.alert_channel_thresholds is None, (
            "Voraussetzung der Gegenprobe: keine Schwelle gesetzt"
        )
        TripAlertService(
            settings=settings, user_id=uid, throttle_hours=0,
            mail_sink=lambda subject, body: None,
        )._send_alert(trip_low, [_weather_segment(1)], [_low_urgency_change()])
    finally:
        stub.stop()

    hits = stub.to(LEARNED_REPLY_TO)
    assert len(hits) == 1, (
        "AC-8 (Gegenprobe): OHNE gesetzte Schwelle (Startwert 'LOW') muss "
        "eine gering-dringliche Meldung Premium-SMS erreichen -- sonst "
        "beweist der erste Teil dieses Tests nur, dass Premium-SMS ueberhaupt "
        f"nicht verdrahtet ist, nicht dass die SCHWELLE entscheidet. "
        f"Erhalten: {hits!r} (voller Stub: {stub.received!r})"
    )
