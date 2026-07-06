"""
Issue #697 — On-demand Wetter-Fetch für Telegram-Abfragebefehle.

Beweist: kein Snapshot vorhanden → Befehl → echte Wetterdaten (kein "Kein Wetter-Snapshot").
Kein Snapshot vorab anlegen — echter User-Flow.

Spec: docs/specs/modules/issue_697_telegram_on_demand_fetch.md
"""
from __future__ import annotations

import http.server
import json
import os
import socketserver
import threading
from datetime import date, timedelta
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
WEATHER_MARKERS = ("°C", "km/h", "mm", "🌤", "⛈", "🌧", "🌨", "☀", "🌥", "⚡",
                   "%", "Temp", "Wind", "Regen", "Schnee", "Gewitter")

REQUIRES_CHAT_ID = pytest.mark.skipif(
    not os.environ.get("GZ_TELEGRAM_TEST_CHAT_ID"),
    reason="GZ_TELEGRAM_TEST_CHAT_ID nicht gesetzt",
)


# ---------------------------------------------------------------------------
# Fixture: User mit aktivem Trip, OHNE Wetter-Snapshot
# ---------------------------------------------------------------------------

@pytest.fixture()
def user_with_trip_no_snapshot(tmp_path):
    """User + aktiver Trip in tmp_path, kein Snapshot vorhanden."""
    import sys
    sys.path.insert(0, str(REPO / "src"))
    sys.path.insert(0, str(REPO / "tests"))

    from tdd._telegram_live_fixture import _create_active_trip, TEST_USER_ID
    import json as _json

    user_id = TEST_USER_ID
    user_dir = tmp_path / "users" / user_id
    user_dir.mkdir(parents=True)

    chat_id = "8346977700"
    (user_dir / "user.json").write_text(_json.dumps({
        "id": user_id,
        "password_hash": "$2a$10$placeholder000000000000000000000000000000000",
        "created_at": "2026-01-01T00:00:00+00:00",
        "mail_to": "",
        "telegram_chat_id": chat_id,
    }), encoding="utf-8")

    _create_active_trip(user_id=user_id, data_dir=str(tmp_path))

    snap_dir = tmp_path / "users" / user_id / "weather_snapshots"
    existing = list(snap_dir.glob("*.json")) if snap_dir.exists() else []
    assert not existing, "Fixture darf keinen Snapshot anlegen"

    return {"user_id": user_id, "chat_id": chat_id, "data_dir": str(tmp_path)}


# ---------------------------------------------------------------------------
# AC-1 — /heute ohne Snapshot liefert echte Wetterdaten
# ---------------------------------------------------------------------------

@REQUIRES_CHAT_ID
def test_ac1_heute_without_snapshot_returns_weather(user_with_trip_no_snapshot):
    """
    GIVEN: User mit aktivem Trip, kein Snapshot vorhanden
    WHEN: /heute durch die Pipeline läuft
    THEN: Antwort enthält echte Wetterdaten (°C, km/h oder mm) — kein Fehler-Text.
    """
    import sys
    sys.path.insert(0, str(REPO / "src"))
    sys.path.insert(0, str(REPO / "tests"))

    from tdd._telegram_live_fixture import run_command_through_pipeline

    body = run_command_through_pipeline(
        command="heute",
        chat_id=user_with_trip_no_snapshot["chat_id"],
        data_dir=user_with_trip_no_snapshot["data_dir"],
    )

    assert "Kein Wetter-Snapshot" not in body, f"Fehler statt Wetterdaten: {body!r}"
    assert "Keine Etappe geplant" not in body, f"Keine Etappe: {body!r}"
    assert any(m in body for m in WEATHER_MARKERS), \
        f"Keine Wetterdaten in Antwort: {body!r}"


# ---------------------------------------------------------------------------
# AC-2 — /morgen ohne Snapshot liefert echte Wetterdaten für morgen
# ---------------------------------------------------------------------------

@REQUIRES_CHAT_ID
def test_ac2_morgen_without_snapshot_returns_weather(user_with_trip_no_snapshot):
    """
    GIVEN: User mit aktivem Trip, kein Snapshot vorhanden
    WHEN: /morgen durch die Pipeline läuft
    THEN: Antwort enthält echte Wetterdaten für morgen.
    """
    import sys
    sys.path.insert(0, str(REPO / "src"))
    sys.path.insert(0, str(REPO / "tests"))

    from tdd._telegram_live_fixture import run_command_through_pipeline

    body = run_command_through_pipeline(
        command="morgen",
        chat_id=user_with_trip_no_snapshot["chat_id"],
        data_dir=user_with_trip_no_snapshot["data_dir"],
    )

    assert "Kein Wetter-Snapshot" not in body, f"Fehler statt Wetterdaten: {body!r}"
    assert "Keine Etappe geplant" not in body, f"Keine Etappe: {body!r}"
    assert any(m in body for m in WEATHER_MARKERS), \
        f"Keine Wetterdaten für morgen: {body!r}"


# ---------------------------------------------------------------------------
# AC-3 — /glance ohne Snapshot liefert heute + morgen
# ---------------------------------------------------------------------------

@REQUIRES_CHAT_ID
def test_ac3_glance_without_snapshot_returns_both_days(user_with_trip_no_snapshot):
    """
    GIVEN: User mit aktivem Trip, kein Snapshot vorhanden
    WHEN: /glance durch die Pipeline läuft
    THEN: Antwort enthält Wetterdaten für BEIDE Tage (heute + morgen).
    """
    import sys
    sys.path.insert(0, str(REPO / "src"))
    sys.path.insert(0, str(REPO / "tests"))

    from tdd._telegram_live_fixture import run_command_through_pipeline

    today = date.today()
    tomorrow = today + timedelta(days=1)

    body = run_command_through_pipeline(
        command="glance",
        chat_id=user_with_trip_no_snapshot["chat_id"],
        data_dir=user_with_trip_no_snapshot["data_dir"],
    )

    assert "Kein Wetter-Snapshot" not in body, f"Fehler statt Wetterdaten: {body!r}"
    assert f"heute ({today:%d.%m}): Keine Etappe geplant" not in body, \
        f"Heute hat keine Etappe: {body!r}"
    assert f"morgen ({tomorrow:%d.%m}): Keine Etappe geplant" not in body, \
        f"Morgen hat keine Etappe: {body!r}"
    assert any(m in body for m in WEATHER_MARKERS), \
        f"Keine Wetterdaten in Glance: {body!r}"


# ---------------------------------------------------------------------------
# AC-4 — Loading-Message wird gesendet, dann durch echte Daten ersetzt
# ---------------------------------------------------------------------------

@pytest.fixture()
def _recording_server():
    """Lokaler HTTP-Server der alle POST-Bodies aufzeichnet."""
    calls: list[dict] = []

    class _H(http.server.BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length)
            try:
                calls.append(json.loads(raw))
            except Exception:
                calls.append({"raw": raw.decode(errors="replace")})
            resp = json.dumps({"ok": True, "result": {
                "message_id": len(calls), "date": 0,
                "chat": {"id": 999}, "text": "x",
            }}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(resp)

        def log_message(self, *a):
            return

    srv = socketserver.TCPServer(("127.0.0.1", 0), _H)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{port}", calls
    srv.shutdown()
    srv.server_close()


@REQUIRES_CHAT_ID
def test_ac4_loading_message_sent_before_weather(user_with_trip_no_snapshot, _recording_server, monkeypatch):
    """
    GIVEN: User mit aktivem Trip, kein Snapshot vorhanden
    WHEN: /heute über _process_update verarbeitet wird
    THEN:
      - Erster API-Call ist sendMessage mit '⏳' im Text
      - Letzter API-Call enthält echte Wetterdaten (editMessageText)
    """
    import sys
    sys.path.insert(0, str(REPO / "src"))
    base_url, calls = _recording_server

    import output.channels.telegram as tg
    monkeypatch.setattr(tg, "TELEGRAM_API_BASE", base_url)

    import app.loader as _loader
    from tdd._telegram_live_fixture import TEST_USER_ID
    monkeypatch.setattr(
        _loader,
        "get_data_dir",
        lambda uid="default": Path(user_with_trip_no_snapshot["data_dir"]) / "users" / uid,
    )
    # _resolve_user_for_chat ruft lookup_user_by_telegram_chat_id(data_dir="data") hardcoded auf —
    # ohne Patch sucht es im CWD und findet den Test-User nicht.
    monkeypatch.setattr(
        _loader,
        "lookup_user_by_telegram_chat_id",
        lambda cid, data_dir="data": TEST_USER_ID,
    )

    from app.config import Settings
    from services.inbound_telegram_reader import InboundTelegramReader

    chat_id = user_with_trip_no_snapshot["chat_id"]
    settings = Settings(telegram_bot_token="testtoken", telegram_chat_id=chat_id)
    update = {
        "update_id": 1,
        "message": {
            "message_id": 1,
            "from": {"id": int(chat_id), "is_bot": False, "first_name": "Test"},
            "chat": {"id": int(chat_id), "type": "private"},
            "date": 0,
            "text": "/heute",
        },
    }

    reader = InboundTelegramReader()
    reader._process_update(update, settings)

    assert len(calls) >= 2, \
        f"Erwartet mind. 2 API-Calls (sendMessage + editMessageText), war: {len(calls)}"

    first_text = calls[0].get("text", "")
    assert "⏳" in first_text, \
        f"Erster Call muss Loading-Message (⏳) enthalten, war: {first_text!r}"

    last_text = calls[-1].get("text", "")
    assert any(m in last_text for m in WEATHER_MARKERS), \
        f"Letzter Call muss Wetterdaten enthalten, war: {last_text!r}"


# ---------------------------------------------------------------------------
# AC-5 — Frischer Snapshot wird direkt verwendet (kein Re-Fetch)
# ---------------------------------------------------------------------------

@REQUIRES_CHAT_ID
def test_ac5_fresh_snapshot_used_directly(user_with_trip_no_snapshot):
    """
    GIVEN: User mit aktivem Trip und frischem Snapshot (target_date == heute)
    WHEN: /heute zweimal aufgerufen wird
    THEN: Zweiter Aufruf ist <1s (Cache, kein API-Fetch).
    """
    import sys
    import time
    sys.path.insert(0, str(REPO / "src"))
    sys.path.insert(0, str(REPO / "tests"))

    from tdd._telegram_live_fixture import run_command_through_pipeline

    chat_id = user_with_trip_no_snapshot["chat_id"]
    data_dir = user_with_trip_no_snapshot["data_dir"]

    # Erster Aufruf: on-demand Fetch
    run_command_through_pipeline(command="heute", chat_id=chat_id, data_dir=data_dir)

    # Zweiter Aufruf: muss aus Cache kommen
    t0 = time.monotonic()
    body = run_command_through_pipeline(command="heute", chat_id=chat_id, data_dir=data_dir)
    elapsed = time.monotonic() - t0

    assert any(m in body for m in WEATHER_MARKERS), f"Kein Wetterinhalt: {body!r}"
    assert elapsed < 1.0, f"Zweiter Aufruf zu langsam ({elapsed:.2f}s) — kein Cache-Hit?"


# ---------------------------------------------------------------------------
# AC-6 — E2E: kein Snapshot vorab, alle 7 Befehle liefern echte Daten
# ---------------------------------------------------------------------------

@REQUIRES_CHAT_ID
def test_ac6_e2e_no_preseed_all_commands_return_weather():
    """
    GIVEN: Staging-Umgebung, kein Snapshot vorab angelegt
    WHEN: alle 7 Menü-Befehle durch die echte Pipeline laufen
    THEN: alle Antworten enthalten echte Wetterdaten — kein "Kein Wetter-Snapshot".
    """
    import sys
    sys.path.insert(0, str(REPO / "src"))
    sys.path.insert(0, str(REPO / "tests"))

    from tdd._telegram_live_fixture import (
        ensure_test_user_with_active_trip,
        run_command_through_pipeline,
        TEST_USER_ID,
    )

    chat_id = os.environ["GZ_TELEGRAM_TEST_CHAT_ID"]

    snap = Path("data/users") / TEST_USER_ID / "weather_snapshots" / "tg-live-e2e-trip.json"
    if snap.exists():
        snap.unlink()

    ensure_test_user_with_active_trip(chat_id=chat_id)

    assert not snap.exists(), \
        "Fixture darf keinen Snapshot vorab anlegen — on-demand Fetch muss das übernehmen"

    seven = ["glance", "heute", "morgen", "heute_gewitter",
             "timeline_heute", "timeline_morgen", "hilfe"]

    failures = []
    for cmd in seven:
        body = run_command_through_pipeline(command=cmd, chat_id=chat_id)
        if "Kein Wetter-Snapshot" in body:
            failures.append(f"{cmd}: 'Kein Wetter-Snapshot' — on-demand Fetch fehlt")
        elif "Keine Etappe geplant" in body:
            failures.append(f"{cmd}: 'Keine Etappe geplant'")
        elif cmd != "hilfe" and not any(m in body for m in WEATHER_MARKERS):
            failures.append(f"{cmd}: keine Wetterdaten: {body[:80]!r}")

    assert not failures, "Befehle ohne Wetterdaten: " + "; ".join(failures)
