"""
Bug #744 — Telegram-Inbound erkennt bare Keywords kanalübergreifend (Folge aus #731 F001).

Treibt echte bare Textnachrichten durch die komplette Telegram-Pipeline
(Webhook → _process_update → _parse_command → echter TripCommandProcessor → echter
TelegramOutput) und beweist das ausgehende sendMessage-Verhalten am Boundary.
Keine Mocks für den Befehls-Dispatch.

ACs (Spec: docs/specs/modules/bug_744_telegram_bare_keywords.md):
  - AC-1: bare `weiter` → Versand reaktiviert (enabled=True persistiert),
          sendMessage NICHT "Unbekannter Befehl". Rot vor Fix.
  - AC-2: bare `stop` → Trip abgemeldet (enabled=False persistiert),
          sendMessage NICHT "Unbekannter Befehl". Rot vor Fix.
  - AC-3: bare `help`/`jetzt`/`gewitter` → kanalgleich aufgelöst,
          NICHT "Unbekannter Befehl". Rot vor Fix.
  - AC-4: unbekannter Befehl → Fehlermeldung nennt den AKTUELLEN Befehlssatz
          (heute/morgen/jetzt/gewitter/ruhetag/status/stop/weiter/hilfe). Rot vor Fix.
  - AC-5: Regression — Slash-Shortcut `/h` und `### key: value` bleiben gültig
          (NICHT "Unbekannter Befehl"). Grün vor und nach Fix.

GitHub Issue: #744
"""
from __future__ import annotations

import http.server
import json
import socketserver
import threading
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.loader import load_all_trips, save_trip
from app.models import (
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    TripReportConfig,
    TripSegment,
)
from app.trip import Stage, Trip, Waypoint
from services.weather_snapshot import WeatherSnapshotService

WEBHOOK_PATH = "/api/internal/telegram-webhook"
_TODAY = date.today()
_NOW = datetime.now(tz=timezone.utc).replace(minute=0, second=0, microsecond=0)
_TRIP_ID = "test-744-keywords"
_TRIP_NAME = "Keyword-Test-Tour"
_CHAT_ID = 744744


# ---------------------------------------------------------------------------
# Echte Objekte — keine Mocks
# ---------------------------------------------------------------------------

def _make_trip(enabled: bool) -> Trip:
    """Aktiver Trip (Etappe an HEUTE) mit Telegram-Report-Config."""
    return Trip(
        id=_TRIP_ID,
        name=_TRIP_NAME,
        stages=[
            Stage(
                id="S1",
                name="Heute-Etappe",
                date=_TODAY,
                waypoints=[
                    Waypoint(id="W1", name="Start", lat=42.1, lon=9.0, elevation_m=800),
                    Waypoint(id="W2", name="Ziel", lat=42.2, lon=9.1, elevation_m=600),
                ],
            ),
        ],
        report_config=TripReportConfig(
            trip_id=_TRIP_ID, enabled=enabled, send_telegram=True,
        ),
    )


def _make_snapshot_segments() -> list[SegmentWeatherData]:
    """24 Stundenpunkte ab JETZT — deckt Nowcast/Gewitter-Sicht ohne Netzwerk ab."""
    provider = Provider.OPENMETEO
    meta = ForecastMeta(provider=provider, model="test", grid_res_km=0.0)
    points = [
        ForecastDataPoint(
            ts=_NOW + timedelta(hours=i),
            thunder_level=ThunderLevel.HIGH if i % 3 == 0 else ThunderLevel.NONE,
            wind10m_kmh=float(20 + i),
            precip_1h_mm=float(i) * 0.2,
        )
        for i in range(24)
    ]
    segment = TripSegment(
        segment_id="seg-744",
        start_point=GPXPoint(lat=42.1, lon=9.0, elevation_m=800),
        end_point=GPXPoint(lat=42.2, lon=9.1, elevation_m=600),
        start_time=_NOW,
        end_time=_NOW + timedelta(hours=23),
        duration_hours=23.0,
        distance_km=15.0,
        ascent_m=200.0,
        descent_m=400.0,
    )
    summary = SegmentWeatherSummary(
        thunder_level_max=ThunderLevel.HIGH, wind_max_kmh=44.0, precip_sum_mm=4.6,
    )
    return [
        SegmentWeatherData(
            segment=segment, timeseries=NormalizedTimeseries(meta=meta, data=points),
            aggregated=summary, fetched_at=_NOW, provider=provider.value,
        )
    ]


def _msg_update(update_id: int, text: str) -> dict:
    return {
        "update_id": update_id,
        "message": {
            "chat": {"id": _CHAT_ID},
            "text": text,
            "date": int(datetime.now(tz=timezone.utc).timestamp()),
        },
    }


def _sent_texts(records: list[tuple[str, dict]]) -> list[str]:
    return [p.get("text", "") for (m, p) in records if m == "sendMessage"]


def _last_send(records: list[tuple[str, dict]]) -> str:
    texts = _sent_texts(records)
    assert texts, f"Kein sendMessage ausgegangen. Calls: {[m for m, _ in records]}"
    return texts[-1]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def capture(monkeypatch):
    """Echter lokaler HTTP-Server fängt ausgehende Bot-API-Calls (Boundary-Capture)."""
    records: list[tuple[str, dict]] = []

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            n = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(n) if n else b""
            try:
                payload = json.loads(raw) if raw else {}
            except ValueError:
                payload = {}
            method = self.path.rstrip("/").split("/")[-1]
            records.append((method, payload))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true,"result":{"message_id":1}}')

        def log_message(self, *args):
            return

    srv = socketserver.TCPServer(("127.0.0.1", 0), _Handler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setattr("output.channels.telegram.TELEGRAM_API_BASE", f"http://127.0.0.1:{port}")
    try:
        yield records
    finally:
        srv.shutdown()
        srv.server_close()


@pytest.fixture
def env(tmp_path: Path, monkeypatch):
    """Lenkt Daten-I/O auf tmp_path; gibt einen Seeder zurück."""
    redirect = lambda user_id="default": tmp_path / user_id  # noqa: E731
    monkeypatch.setattr("app.loader.get_data_dir", redirect)
    monkeypatch.setattr("services.trip_command_processor.get_data_dir", redirect)

    def seed(enabled: bool = True) -> None:
        save_trip(_make_trip(enabled), "default")
        WeatherSnapshotService("default").save(_TRIP_ID, _make_snapshot_segments(), _TODAY)

    return seed


@pytest.fixture
def client():
    from api.main import app
    return TestClient(app)


def _reload_enabled() -> bool:
    trips = load_all_trips("default")
    trip = next(t for t in trips if t.id == _TRIP_ID)
    return trip.report_config.enabled


# ---------------------------------------------------------------------------
# AC-1: bare `weiter` reaktiviert
# ---------------------------------------------------------------------------

def test_ac1_bare_weiter_reactivates(env, capture, client):
    """
    GIVEN: aktiver Trip mit deaktiviertem Versand (enabled=False)
    WHEN: bare Textnachricht 'weiter' (ohne Slash) an den Telegram-Webhook
    THEN: Versand reaktiviert (enabled=True persistiert), Bot bestätigt,
          KEIN "Unbekannter Befehl".
    """
    env(enabled=False)
    resp = client.post(WEBHOOK_PATH, json=_msg_update(74401, "weiter"))
    assert resp.status_code == 200, resp.text

    text = _last_send(capture)
    assert "Unbekannter Befehl" not in text, (
        f"bare 'weiter' wurde abgelehnt statt reaktiviert: {text!r}"
    )
    assert "reaktiviert" in text.lower() or "wieder aktiviert" in text.lower(), text
    assert _reload_enabled() is True, "Versand nicht reaktiviert (enabled blieb False)"


# ---------------------------------------------------------------------------
# AC-2: bare `stop` meldet ab
# ---------------------------------------------------------------------------

def test_ac2_bare_stop_cancels(env, capture, client):
    """
    GIVEN: aktiver Trip mit aktivem Versand (enabled=True)
    WHEN: bare Textnachricht 'stop' (ohne Slash) an den Telegram-Webhook
    THEN: Versand abgemeldet (enabled=False persistiert), Bot bestätigt,
          KEIN "Unbekannter Befehl".
    """
    env(enabled=True)
    resp = client.post(WEBHOOK_PATH, json=_msg_update(74402, "stop"))
    assert resp.status_code == 200, resp.text

    text = _last_send(capture)
    assert "Unbekannter Befehl" not in text, (
        f"bare 'stop' wurde abgelehnt statt abgemeldet: {text!r}"
    )
    assert "beendet" in text.lower() or "deaktiviert" in text.lower(), text
    assert _reload_enabled() is False, "Versand nicht abgemeldet (enabled blieb True)"


# ---------------------------------------------------------------------------
# AC-3: bare `help` / `jetzt` / `gewitter` kanalgleich aufgelöst
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("update_id,keyword", [
    (74411, "help"), (74412, "jetzt"), (74413, "gewitter"),
])
def test_ac3_shared_bare_keywords_recognized(env, capture, client, update_id, keyword):
    """
    GIVEN: aktiver Trip + Wetter-Snapshot
    WHEN: ein per E-Mail gültiges bare Keyword an den Telegram-Webhook geht
    THEN: es wird erkannt (kein "Unbekannter Befehl") — kanalübergreifend identisch.
          Eigene update_id je Keyword (sonst Webhook-Dedup → vakuum-grün).
    """
    env(enabled=True)
    resp = client.post(WEBHOOK_PATH, json=_msg_update(update_id, keyword))
    assert resp.status_code == 200, resp.text

    texts = " ".join(_sent_texts(capture))
    assert "Unbekannter Befehl" not in texts, (
        f"bare {keyword!r} wurde auf Telegram abgelehnt (E-Mail kennt es): {texts!r}"
    )


# ---------------------------------------------------------------------------
# AC-4: aktualisierte Fehlermeldung für echte Unbekannte
# ---------------------------------------------------------------------------

def test_ac4_unknown_command_lists_current_set(env, capture, client):
    """
    GIVEN: aktiver Trip
    WHEN: ein echter Unsinn-Befehl 'quatsch' an den Telegram-Webhook
    THEN: "Unbekannter Befehl" + Fehlermeldung nennt den aktuellen Befehlssatz
          (mind. 'weiter' und 'stop' und 'jetzt' — die nach #731 hinzukamen).
    """
    env(enabled=True)
    resp = client.post(WEBHOOK_PATH, json=_msg_update(74403, "quatsch"))
    assert resp.status_code == 200, resp.text

    text = _last_send(capture)
    assert "Unbekannter Befehl" in text, f"Unsinn sollte abgelehnt werden: {text!r}"
    low = text.lower()
    for kw in ("weiter", "stop", "jetzt"):
        assert kw in low, (
            f"Fehlermeldung nennt '{kw}' nicht — veralteter Befehlssatz: {text!r}"
        )


# ---------------------------------------------------------------------------
# AC-5: Regression — Slash-Shortcut + ###-Format bleiben gültig
# ---------------------------------------------------------------------------

def test_ac5_slash_shortcut_still_works(env, capture, client):
    """Regression: '/h' (Slash-Shortcut heute) bleibt gültig — kein 'Unbekannter Befehl'."""
    env(enabled=True)
    resp = client.post(WEBHOOK_PATH, json=_msg_update(74404, "/h"))
    assert resp.status_code == 200, resp.text
    texts = " ".join(_sent_texts(capture))
    assert "Unbekannter Befehl" not in texts, texts


def test_ac5_known_bare_command_still_works(env, capture, client):
    """Regression: bare 'status' (schon vor Fix gültig) bleibt gültig — kein 'Unbekannter Befehl'."""
    env(enabled=True)
    resp = client.post(WEBHOOK_PATH, json=_msg_update(74405, "status"))
    assert resp.status_code == 200, resp.text
    texts = " ".join(_sent_texts(capture))
    assert "Unbekannter Befehl" not in texts, texts
