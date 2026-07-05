"""
Telegram E2E-Pipeline-Tests (Issue #672).

Schließt die Test-Lücke im Telegram-Kanal: Treibt echte Text-Befehle durch die
komplette Pipeline (Webhook → _process_update → _parse_command → _find_active_trip
→ echter Processor → echter TelegramOutput) und beweist ausgehende Calls
mit Inhalt und Inline-Keyboard.

ACs:
  - AC-1: Text `/s` → eine Loading-sendMessage (⏳) gefolgt von editMessageText
          mit Glance-Inhalt (heute + morgen) und reply_markup.inline_keyboard ≥1 Button.
  - AC-2: Text `/th` → Loading-sendMessage gefolgt von editMessageText mit Timeline-Inhalt
          und ≥1 Button (dd_ oder tl_/glance).
  - AC-3: Jeder BOT_COMMANDS-Eintrag mit führendem Slash → sendMessage NICHT
          mit "Unbekannter Befehl" (behebt #671; rot vor Fix, grün nach Fix).
  - AC-4: Alle callback_data aus der Glance editMessageText-Antwort → _callback_to_body ≠ None
          (kein toter Button).
  - AC-5: Live-Staging-Bot-Smoke (gated: GZ_TELEGRAM_BOT_TOKEN + GZ_TELEGRAM_TEST_CHAT_ID).

Realer Flow (#697/#704): sendMessage(⏳ Loading) → on-demand Wetter holen →
editMessageText(Inhalt + Buttons). Fixture liefert message_id damit der echte
Edit-Pfad ausgeübt wird (nicht der Fallback-sendMessage).

Spec: docs/specs/modules/issue_672_telegram_e2e_pipeline.md
GitHub Issue: #672
"""
from __future__ import annotations

import http.server
import json
import os
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

from tests.tdd._telegram_live_fixture import live_telegram_enabled

WEBHOOK_PATH = "/api/internal/telegram-webhook"

_TODAY = date.today()
_NOW = datetime.now(tz=timezone.utc).replace(minute=0, second=0, microsecond=0)

# Unique trip ID for this test file — no collision with #655/#637
_TRIP_ID = "test-672-pipeline"
_TRIP_NAME = "Pipeline-Test-Tour"


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
        segment_id="seg-672",
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


def _msg_update(update_id: int, text: str, chat_id: int = 999999) -> dict:
    """Baut ein echtes Telegram message-Update (Text-Nachricht)."""
    return {
        "update_id": update_id,
        "message": {
            "chat": {"id": chat_id},
            "text": text,
            "date": int(datetime.now(tz=timezone.utc).timestamp()),
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

    msg_counter = [0]

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            n = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(n) if n else b""
            try:
                payload = json.loads(raw) if raw else {}
            except ValueError:
                payload = {}
            method = self.path.rstrip("/").split("/")[-1]  # z.B. sendMessage
            records.append((method, payload))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            # sendMessage: echtes Telegram liefert immer eine message_id zurück —
            # ohne sie fällt inbound_telegram_reader in den Fallback-sendMessage-Pfad.
            if method == "sendMessage":
                msg_counter[0] += 1
                resp = json.dumps({"ok": True, "result": {"message_id": msg_counter[0]}})
            else:
                resp = json.dumps({"ok": True, "result": {}})
            self.wfile.write(resp.encode())

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
# AC-1: Text-Befehl /s → Loading-sendMessage + editMessageText mit Glance + Buttons
# ---------------------------------------------------------------------------

def test_ac1_glance_text_command_sends_message_with_buttons(env, capture, client):
    """
    GIVEN: aktiver default-Trip + Snapshot; Fixture liefert message_id
    WHEN: Text-Update '/s' an /api/internal/telegram-webhook gepostet wird
    THEN: genau eine Loading-sendMessage (⏳) gefolgt von einem editMessageText
          mit Glance-Inhalt (heute + morgen) und reply_markup.inline_keyboard ≥1 Button.

    Realer On-demand-Flow (#697/#704): sendMessage(Loading) → Wetter holen →
    editMessageText(Inhalt+Buttons). Ohne message_id in der Fixture würde
    inbound_telegram_reader in den Fallback (zweites sendMessage) fallen.
    """
    # Eindeutige update_id (kein Clash mit #655-Tests: 7001-7005)
    resp = client.post(WEBHOOK_PATH, json=_msg_update(8001, "/s"))
    assert resp.status_code == 200, resp.text

    # Schritt 1: Genau eine Loading-sendMessage
    sends = _calls_named(capture, "sendMessage")
    assert len(sends) == 1, (
        f"Erwartet genau 1 Loading-sendMessage, bekam {len(sends)}. "
        f"Calls: {[m for m, _ in capture]}"
    )
    loading_msg = sends[0]
    assert loading_msg.get("chat_id") is not None, "Loading-sendMessage hat keine chat_id"
    loading_text = loading_msg.get("text", "")
    assert "⏳" in loading_text or "wetter" in loading_text.lower(), (
        f"Loading-sendMessage erwartet ⏳-Text, got: {loading_text!r}"
    )

    # Schritt 2: editMessageText liefert den echten Glance-Inhalt
    edits = _calls_named(capture, "editMessageText")
    assert len(edits) == 1, (
        f"Erwartet genau 1 editMessageText (Glance-Ergebnis), bekam {len(edits)}. "
        f"Calls: {[m for m, _ in capture]}"
    )
    e = edits[0]
    edit_text = e.get("text", "")
    assert edit_text, "editMessageText-Text ist leer"
    # Glance-Antwort deckt BEIDE Tage ab (Spec AC-1: heute UND morgen).
    text_lower = edit_text.lower()
    assert "heute" in text_lower and "morgen" in text_lower, (
        f"Glance-Inhalt erwartet (heute UND morgen), editMessageText: {edit_text!r}"
    )

    buttons = [
        b
        for row in e.get("reply_markup", {}).get("inline_keyboard", [])
        for b in row
    ]
    assert buttons, f"reply_markup.inline_keyboard hat keine Buttons: {e.get('reply_markup')!r}"


# ---------------------------------------------------------------------------
# AC-2: Text-Befehl /th → Loading-sendMessage + editMessageText mit Timeline + Drilldown
# ---------------------------------------------------------------------------

def test_ac2_timeline_text_command_sends_message_with_drilldown_button(env, capture, client):
    """
    GIVEN: aktiver default-Trip + Snapshot; Fixture liefert message_id
    WHEN: Text-Update '/th' (timeline_heute) an den Webhook gepostet wird
    THEN: Loading-sendMessage gefolgt von editMessageText mit Timeline-Inhalt
          und ≥1 Button mit callback_data=dd_* oder tl_/glance.
    """
    resp = client.post(WEBHOOK_PATH, json=_msg_update(8002, "/th"))
    assert resp.status_code == 200, resp.text

    # Loading-sendMessage muss vorhanden sein
    sends = _calls_named(capture, "sendMessage")
    assert sends, (
        f"Loading-sendMessage fehlt bei /th. Calls: {[m for m, _ in capture]}"
    )

    # Das Ergebnis kommt per editMessageText
    edits = _calls_named(capture, "editMessageText")
    assert edits, (
        f"editMessageText fehlt bei /th (Timeline-Ergebnis). Calls: {[m for m, _ in capture]}"
    )
    e = edits[0]

    text = e.get("text", "")
    assert text, "editMessageText-Text ist leer"

    buttons = [
        b
        for row in e.get("reply_markup", {}).get("inline_keyboard", [])
        for b in row
    ]
    assert buttons, f"Keine Buttons in Timeline-editMessageText-Antwort: {e.get('reply_markup')!r}"

    # Mindestens ein Button mit dd_ oder Navigations-callback_data
    nav_or_drill = [
        b for b in buttons
        if (b.get("callback_data") or "").startswith("dd_")
        or b.get("callback_data") in ("tl_today", "tl_tomorrow", "glance")
    ]
    assert nav_or_drill, (
        f"Kein Drilldown/Nav-Button in Timeline-Antwort. Buttons: {buttons}"
    )


# ---------------------------------------------------------------------------
# AC-3: Jeder BOT_COMMANDS-Eintrag liefert unterstützte Antwort (behebt #671)
# ---------------------------------------------------------------------------

def test_ac3_every_bot_menu_command_is_supported(env, capture, client):
    """
    GIVEN: aktiver default-Trip + Snapshot
    WHEN: jeder BOT_COMMANDS-Eintrag mit führendem '/' durch den Webhook läuft
    THEN: kein sendMessage enthält "Unbekannter Befehl" (behebt #671).
    RED vor Fix (BOT_COMMANDS enthält /briefing /wetter die _SHORTCUT_MAP nicht kennt),
    GREEN nach Fix von BOT_COMMANDS + _SHORTCUT_MAP.
    """
    from outputs.telegram import BOT_COMMANDS

    failures = []
    for i, cmd_entry in enumerate(BOT_COMMANDS):
        cmd = cmd_entry["command"]
        slash_cmd = f"/{cmd}"
        # Eindeutige update_id ab 8100
        resp = client.post(WEBHOOK_PATH, json=_msg_update(8100 + i, slash_cmd))
        assert resp.status_code == 200, f"{slash_cmd}: HTTP {resp.status_code}"

        sends = _calls_named(capture, "sendMessage")
        if not sends:
            failures.append(f"{slash_cmd}: kein sendMessage")
        else:
            text = sends[-1].get("text", "")
            if "Unbekannter Befehl" in text:
                failures.append(f"{slash_cmd}: sendMessage enthält 'Unbekannter Befehl': {text!r}")
        # Capture für nächste Iteration leeren
        capture.clear()

    assert not failures, (
        f"Folgende Menü-Befehle liefern 'Unbekannter Befehl' (Bug #671):\n"
        + "\n".join(f"  - {f}" for f in failures)
    )


# ---------------------------------------------------------------------------
# AC-4: Alle Glance-Buttons haben gültige callback_data (kein toter Button)
# ---------------------------------------------------------------------------

def test_ac4_glance_buttons_callback_data_all_handled(env, capture, client):
    """
    GIVEN: aktiver default-Trip + Snapshot; Fixture liefert message_id
    WHEN: die Glance-Antwort (editMessageText aus AC-1) abgeholt und jedes callback_data
          gegen InboundTelegramReader._callback_to_body geprüft wird
    THEN: jedes callback_data liefert ≠ None (kein toter Button).

    Inhaltliche Quelle ist das editMessageText (realer On-demand-Flow), nicht sendMessage.
    """
    resp = client.post(WEBHOOK_PATH, json=_msg_update(8200, "/s"))
    assert resp.status_code == 200, resp.text

    edits = _calls_named(capture, "editMessageText")
    assert edits, (
        f"editMessageText fehlt — Glance-Ergebnis nicht via Edit. "
        f"Calls: {[m for m, _ in capture]}"
    )

    buttons = [
        b
        for row in edits[0].get("reply_markup", {}).get("inline_keyboard", [])
        for b in row
    ]
    assert buttons, "Keine Buttons in Glance editMessageText-Antwort"

    from services.inbound_telegram_reader import InboundTelegramReader
    reader = InboundTelegramReader()

    dead_buttons = []
    for b in buttons:
        cd = b.get("callback_data")
        if cd is None:
            continue  # kein callback_data = kein Inline-Button, ok
        result = reader._callback_to_body(cd)
        if result is None:
            dead_buttons.append(f"callback_data={cd!r}, text={b.get('text')!r}")

    assert not dead_buttons, (
        f"Tote Buttons gefunden (_callback_to_body gibt None):\n"
        + "\n".join(f"  - {d}" for d in dead_buttons)
    )


# ---------------------------------------------------------------------------
# AC-5: Live-Staging-Bot-Smoke (gated)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not live_telegram_enabled(),
    reason="GZ_TELEGRAM_LIVE=1 nicht gesetzt — Live-Sends nur opt-in (#1014)",
)
def test_ac5_live_staging_bot_smoke():
    """
    GIVEN: GZ_TELEGRAM_BOT_TOKEN + GZ_TELEGRAM_TEST_CHAT_ID gesetzt
    WHEN: getMe → sendMessage → editMessageText → deleteMessage gegen echte Bot-API
    THEN: jeder Aufruf antwortet ok=True; Nachricht wird sauber gelöscht.
    """
    import httpx

    token = os.environ["GZ_TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["GZ_TELEGRAM_TEST_CHAT_ID"]
    base = "https://api.telegram.org"
    timeout = 15

    # getMe
    r = httpx.get(f"{base}/bot{token}/getMe", timeout=timeout)
    assert r.status_code == 200, f"getMe HTTP {r.status_code}"
    data = r.json()
    assert data.get("ok") is True, f"getMe ok=False: {data}"

    # sendMessage
    r = httpx.post(
        f"{base}/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": "[#672 AC-5 Live-Smoke] Test — wird sofort gelöscht"},
        timeout=timeout,
    )
    assert r.status_code == 200, f"sendMessage HTTP {r.status_code}"
    data = r.json()
    assert data.get("ok") is True, f"sendMessage ok=False: {data}"
    message_id = data["result"]["message_id"]

    # editMessageText
    r = httpx.post(
        f"{base}/bot{token}/editMessageText",
        json={
            "chat_id": chat_id,
            "message_id": message_id,
            "text": "[#672 AC-5 Live-Smoke] Editiert — wird sofort gelöscht",
        },
        timeout=timeout,
    )
    assert r.status_code == 200, f"editMessageText HTTP {r.status_code}"
    data = r.json()
    assert data.get("ok") is True, f"editMessageText ok=False: {data}"

    # deleteMessage
    r = httpx.post(
        f"{base}/bot{token}/deleteMessage",
        json={"chat_id": chat_id, "message_id": message_id},
        timeout=timeout,
    )
    assert r.status_code == 200, f"deleteMessage HTTP {r.status_code}"
    data = r.json()
    assert data.get("ok") is True, f"deleteMessage ok=False: {data}"
