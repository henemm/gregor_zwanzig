"""
TDD RED — Issue #655: Telegram Hybrid-Navigation (callback_query + editMessageText).

Teil 6/6 von Epic #639. Macht die Inline-Buttons aus #651/#653/#654 klickbar.
Beweist aus Nutzerperspektive — KEINE Mocks der Logik unter Test:
  - Echter HTTP-POST gegen die reale FastAPI-App (/api/internal/telegram-webhook)
    mit einem callback_query-Body.
  - Ausgehende Telegram-Bot-API-Calls (editMessageText / answerCallbackQuery /
    sendMessage) werden an einem echten lokalen http.server-Socket beobachtet
    (Boundary-Capture via TELEGRAM_API_BASE-Umlenkung) — kein Mock.
  - Echter TripCommandProcessor, echter Trip + Snapshot, echte User-Auflösung.

ACs:
  - AC-1: tl_today → editMessageText (gleicher chat_id+message_id) mit Timeline,
          Zurück-Button (callback_data=glance); KEIN sendMessage.
  - AC-2: unbekanntes callback_data → answerCallbackQuery trotzdem, kein editMessageText.
  - AC-3: doppelt zugestelltes Update (gleiche update_id) → nur 1 edit, 2. = duplicate.
  - AC-4: dd_thunder_today → editMessageText mit Drilldown + Zurück-Button (tl_today).
  - AC-5: zwei echte Nutzer → editMessageText an eigene chat_id mit eigenem Trip,
          kein Cross-User-Leak, kein default-Fallback bei bekanntem Chat.

Spec: docs/specs/modules/issue_655_telegram_callback_query.md v1.0
Test-Manifest: docs/specs/tests/issue_655_telegram_callback_query_tests.md
GitHub Issue: #655
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

from app.loader import save_trip
from app.models import (
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    TripSegment,
)
from app.trip import Stage, Trip, Waypoint
from services.weather_snapshot import WeatherSnapshotService

WEBHOOK_PATH = "/api/internal/telegram-webhook"

_TODAY = date.today()
_NOW = datetime.now(tz=timezone.utc).replace(minute=0, second=0, microsecond=0)

_TRIP_ID = "test-655-callback"
_TRIP_NAME = "Callback-Test-Tour"


# ---------------------------------------------------------------------------
# Echte Objekte — keine Mocks
# ---------------------------------------------------------------------------

def _make_trip(trip_id: str = _TRIP_ID, name: str = _TRIP_NAME) -> Trip:
    """Trip mit Etappe an HEUTE → als aktiv erkannt."""
    return Trip(
        id=trip_id,
        name=name,
        stages=[
            Stage(
                id="S1",
                name="Heute-Etappe",
                date=_TODAY,
                waypoints=[
                    Waypoint(id="W1", name="Start", lat=42.1, lon=9.0, elevation_m=800),
                ],
            ),
        ],
    )


def _make_snapshot_segments() -> list[SegmentWeatherData]:
    """24 Stundenpunkte ab JETZT — deckt das 12h-today-Drilldown-Fenster ab."""
    provider = Provider.OPENMETEO
    meta = ForecastMeta(provider=provider, model="test", grid_res_km=0.0)
    thunder_seq = [
        ThunderLevel.NONE, ThunderLevel.MED, ThunderLevel.HIGH, ThunderLevel.MED,
        ThunderLevel.NONE, ThunderLevel.HIGH,
    ]
    points = [
        ForecastDataPoint(
            ts=_NOW + timedelta(hours=i),
            thunder_level=thunder_seq[i % len(thunder_seq)],
            wind10m_kmh=float(20 + i * 2),
            precip_1h_mm=float(i) * 0.3,
        )
        for i in range(24)
    ]
    timeseries = NormalizedTimeseries(meta=meta, data=points)
    segment = TripSegment(
        segment_id="seg-655",
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
        thunder_level_max=ThunderLevel.HIGH, wind_max_kmh=66.0, precip_sum_mm=6.9,
    )
    return [
        SegmentWeatherData(
            segment=segment, timeseries=timeseries, aggregated=summary,
            fetched_at=_NOW, provider=provider.value,
        )
    ]


def _cb_update(update_id: int, data: str, chat_id: int = 999999, message_id: int = 555) -> dict:
    """Baut ein echtes Telegram callback_query-Update."""
    return {
        "update_id": update_id,
        "callback_query": {
            "id": f"cbq-{update_id}",
            "from": {"id": chat_id},
            "message": {"message_id": message_id, "chat": {"id": chat_id}},
            "data": data,
        },
    }


def _calls_named(records: list[tuple[str, dict]], method: str) -> list[dict]:
    return [payload for (m, payload) in records if m == method]


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
            method = self.path.rstrip("/").split("/")[-1]  # z.B. editMessageText
            records.append((method, payload))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true,"result":{}}')

        def log_message(self, *args):  # Stille
            return

    srv = socketserver.TCPServer(("127.0.0.1", 0), _Handler)
    port = srv.server_address[1]
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr("outputs.telegram.TELEGRAM_API_BASE", f"http://127.0.0.1:{port}")
    try:
        yield records
    finally:
        srv.shutdown()
        srv.server_close()


@pytest.fixture
def env(tmp_path: Path, monkeypatch) -> Path:
    """Lenkt Daten-I/O auf tmp_path; legt default-Trip + Snapshot an."""
    redirect = lambda user_id="default": tmp_path / user_id  # noqa: E731
    monkeypatch.setattr("app.loader.get_data_dir", redirect)
    monkeypatch.setattr("services.trip_command_processor.get_data_dir", redirect)
    save_trip(_make_trip(), "default")
    WeatherSnapshotService("default").save(_TRIP_ID, _make_snapshot_segments(), _TODAY)
    return tmp_path


@pytest.fixture
def client():
    from api.main import app
    return TestClient(app)


# ---------------------------------------------------------------------------
# AC-1: Zoom-Navigation via editMessageText
# ---------------------------------------------------------------------------

def test_ac1_tl_today_edits_message_to_timeline(env, capture, client):
    """
    GIVEN: aktiver default-Trip + Snapshot
    WHEN: callback_query mit data='tl_today' an den Webhook gepostet wird
    THEN: editMessageText (gleiche chat_id + message_id) ersetzt die Nachricht,
          reply_markup hat Zurück-Button (callback_data='glance'); kein sendMessage.
    """
    resp = client.post(WEBHOOK_PATH, json=_cb_update(7001, "tl_today"))
    assert resp.status_code == 200, resp.text

    edits = _calls_named(capture, "editMessageText")
    assert edits, f"editMessageText nicht aufgerufen. Calls: {[m for m, _ in capture]}"
    e = edits[0]
    assert str(e.get("chat_id")) == "999999", f"falsche chat_id: {e.get('chat_id')!r}"
    assert e.get("message_id") == 555, f"falsche message_id: {e.get('message_id')!r}"

    buttons = [b for row in e.get("reply_markup", {}).get("inline_keyboard", []) for b in row]
    assert any(b.get("callback_data") == "glance" for b in buttons), (
        f"Kein Zurück-Button (callback_data=glance): {buttons}"
    )

    sends = _calls_named(capture, "sendMessage")
    assert not sends, f"Unerwartetes sendMessage (Zoom soll editieren, nicht anhängen): {sends}"


# ---------------------------------------------------------------------------
# AC-2: answerCallbackQuery wird immer aufgerufen
# ---------------------------------------------------------------------------

def test_ac2_answer_callback_query_always_even_unknown(env, capture, client):
    """
    GIVEN: aktiver Trip
    WHEN: callback_query mit UNBEKANNTEM data gepostet wird
    THEN: answerCallbackQuery mit der callback_query.id wird trotzdem aufgerufen
          (kein hängender Spinner); KEIN editMessageText.
    """
    resp = client.post(WEBHOOK_PATH, json=_cb_update(7002, "voellig_unbekannt_xyz"))
    assert resp.status_code == 200, resp.text

    answers = _calls_named(capture, "answerCallbackQuery")
    assert answers, f"answerCallbackQuery fehlt. Calls: {[m for m, _ in capture]}"
    assert answers[0].get("callback_query_id") == "cbq-7002", (
        f"falsche callback_query_id: {answers[0].get('callback_query_id')!r}"
    )

    edits = _calls_named(capture, "editMessageText")
    assert not edits, f"editMessageText bei unbekanntem data unerwartet: {edits}"


# ---------------------------------------------------------------------------
# AC-3: Idempotenz gegen Doppel-Zustellung
# ---------------------------------------------------------------------------

def test_ac3_duplicate_callback_query_idempotent(env, capture, client):
    """
    GIVEN: identischer callback_query (gleiche update_id) zweimal zugestellt
    WHEN: beide an den Webhook gepostet werden
    THEN: erster status=ok, zweiter status=duplicate; nur EIN editMessageText.
    """
    upd = _cb_update(7003, "tl_today")
    r1 = client.post(WEBHOOK_PATH, json=upd)
    r2 = client.post(WEBHOOK_PATH, json=upd)

    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json().get("status") == "ok", r1.text
    assert r2.json().get("status") == "duplicate", (
        f"Zweite Zustellung nicht als Duplikat erkannt: {r2.text}"
    )

    edits = _calls_named(capture, "editMessageText")
    assert len(edits) == 1, f"Erwartet genau 1 editMessageText, bekam {len(edits)}"


# ---------------------------------------------------------------------------
# AC-4: Drilldown-Navigation (Tier 2 → Tier 3 → zurück)
# ---------------------------------------------------------------------------

def test_ac4_drilldown_edits_with_back_to_timeline(env, capture, client):
    """
    GIVEN: aktiver Trip + Snapshot mit stündlichen Gewitter-Daten ab jetzt
    WHEN: callback_query mit data='dd_thunder_today' gepostet wird
    THEN: editMessageText ersetzt die Nachricht durch den Drilldown,
          reply_markup hat Zurück-Button zur Timeline (callback_data='tl_today').
    """
    resp = client.post(WEBHOOK_PATH, json=_cb_update(7004, "dd_thunder_today"))
    assert resp.status_code == 200, resp.text

    edits = _calls_named(capture, "editMessageText")
    assert edits, f"editMessageText nicht aufgerufen. Calls: {[m for m, _ in capture]}"
    e = edits[0]
    buttons = [b for row in e.get("reply_markup", {}).get("inline_keyboard", []) for b in row]
    assert any(b.get("callback_data") == "tl_today" for b in buttons), (
        f"Kein Zurück-Button zur Timeline (callback_data=tl_today): {buttons}"
    )


# ---------------------------------------------------------------------------
# AC-5: Multi-User-Isolation — kein Cross-User-Leak, kein default-Fallback
# ---------------------------------------------------------------------------

def test_ac5_multi_user_isolation_no_cross_leak(tmp_path, monkeypatch, capture, client):
    """
    GIVEN: zwei echte Nutzer (alice chat=111, bob chat=222) mit je eigenem Trip
    WHEN: ein callback_query von alice's chat_id eingeht
    THEN: editMessageText geht an chat_id 111 und enthält alice's Trip-Namen,
          niemals bob's; kein default-Fallback bei bekanntem Chat.
    """
    redirect = lambda user_id="default": tmp_path / user_id  # noqa: E731
    monkeypatch.setattr("app.loader.get_data_dir", redirect)
    monkeypatch.setattr("services.trip_command_processor.get_data_dir", redirect)

    data_users = Path("data/users")
    alice_dir = data_users / "zz655_alice"
    bob_dir = data_users / "zz655_bob"
    try:
        for d, chat in ((alice_dir, "111"), (bob_dir, "222")):
            d.mkdir(parents=True, exist_ok=True)
            (d / "user.json").write_text(
                json.dumps({"id": d.name, "telegram_chat_id": chat}), encoding="utf-8"
            )
        save_trip(_make_trip("alice-trip", "Alice-GR20"), "zz655_alice")
        save_trip(_make_trip("bob-trip", "Bob-Pyrenaeen"), "zz655_bob")

        resp = client.post(WEBHOOK_PATH, json=_cb_update(7005, "tl_today", chat_id=111))
        assert resp.status_code == 200, resp.text

        edits = _calls_named(capture, "editMessageText")
        assert edits, f"editMessageText nicht aufgerufen. Calls: {[m for m, _ in capture]}"
        e = edits[0]
        assert str(e.get("chat_id")) == "111", f"editMessageText an falsche chat_id: {e.get('chat_id')!r}"
        text = e.get("text", "")
        assert "Alice-GR20" in text, f"alice's Trip-Name fehlt im editMessageText: {text!r}"
        assert "Bob-Pyrenaeen" not in text, f"CROSS-USER-LEAK: bob's Trip im edit: {text!r}"
    finally:
        import shutil
        for d in (alice_dir, bob_dir):
            shutil.rmtree(d, ignore_errors=True)
