"""
TDD RED tests for Issue #637 — Telegram Inbound Webhook-Migration (Python-Seite).

Diese Tests MÜSSEN fehlschlagen bis der interne Webhook-Endpoint
POST /api/internal/telegram-webhook existiert und die bestehende
Befehlsverarbeitung (InboundTelegramReader._process_update) wiederverwendet.

Kein Mock der Logik unter Test:
- AC-2/AC-5 fahren echte HTTP-POSTs gegen die reale FastAPI-App (TestClient).
- AC-3 legt zwei ECHTE temporäre Nutzer mit user.json an und nutzt die reale
  lookup_user_by_telegram_chat_id-Dateiauflösung (kein Mock des Routings).
Der ausgehende Telegram-Netzwerk-Send wird an der Grenze beobachtet
(TelegramOutput.send) — das ist Boundary-Capture, kein Mock der Verarbeitung.

SPEC: docs/specs/modules/telegram_webhook_inbound.md
"""
from __future__ import annotations

import json
import shutil
from datetime import date, datetime, timedelta, timezone
from pathlib import Path



def _make_active_trip():
    from app.trip import Trip, Stage, Waypoint
    today = date.today()
    return Trip(
        id="gr20",
        name="GR20",
        stages=[
            Stage(
                id="T1", name="Tag 1", date=today - timedelta(days=1),
                waypoints=[Waypoint(id="G1", name="Start", lat=39.71, lon=2.62, elevation_m=400)],
            ),
            Stage(
                id="T2", name="Tag 2", date=today + timedelta(days=1),
                waypoints=[Waypoint(id="G2", name="Ziel", lat=39.75, lon=2.65, elevation_m=150)],
            ),
        ],
    )


# =============================================================================
# AC-2 (Vorbedingung): Webhook-Router ist in der FastAPI-App registriert
# =============================================================================

def test_webhook_router_registered():
    """
    GIVEN: Die FastAPI-App mit allen Routern
    WHEN: Die registrierten Routen geprüft werden
    THEN: POST /api/internal/telegram-webhook existiert
    """
    from api.main import app

    routes = [r.path for r in app.routes if hasattr(r, "path")]
    assert "/api/internal/telegram-webhook" in routes, (
        f"POST /api/internal/telegram-webhook nicht in Routen gefunden: {routes}"
    )


# =============================================================================
# AC-2: Nahtlose Befehls-Weiterleitung — 'status' wird verarbeitet
# =============================================================================

def test_webhook_processes_status_command(monkeypatch):
    """
    GIVEN: Ein gültiges Telegram-Update mit Befehl 'status' und aktivem Trip
    WHEN: Es per HTTP an /api/internal/telegram-webhook gepostet wird
    THEN: Der bestehende TripCommandProcessor verarbeitet den Befehl
          (channel='telegram', body enthält 'status'), Antwort ist 200 OK
    """
    from fastapi.testclient import TestClient
    from api.main import app

    trip = _make_active_trip()
    captured: dict = {}

    def fake_process(self, msg):
        captured["channel"] = msg.channel
        captured["body"] = msg.body
        from services.trip_command_processor import CommandResult
        return CommandResult(
            success=True, command="status",
            confirmation_subject="Status", confirmation_body="OK",
            trip_name=trip.name,
        )

    monkeypatch.setattr(
        "services.inbound_telegram_reader.load_all_trips",
        lambda user_id="default": [trip],
    )
    monkeypatch.setattr(
        "services.trip_command_processor.TripCommandProcessor.process",
        fake_process,
    )
    monkeypatch.setattr(
        "services.notification_service.TelegramOutput.send",
        lambda self, subject, body: None,
    )

    client = TestClient(app)
    update = {
        "update_id": 100,
        "message": {
            "chat": {"id": 12345},
            "text": "status",
            "date": int(datetime.now(tz=timezone.utc).timestamp()),
        },
    }
    resp = client.post("/api/internal/telegram-webhook", json=update)

    assert resp.status_code == 200, f"Erwartet 200, bekam {resp.status_code}: {resp.text}"
    assert captured.get("channel") == "telegram"
    assert "status" in (captured.get("body") or ""), (
        f"Befehl 'status' nicht an Processor durchgereicht: {captured}"
    )


# =============================================================================
# AC-3: Multi-User-Integrität — chat_id → korrekte user_id, kein Cross-User-Leak
# =============================================================================

def test_webhook_multi_user_routing_no_cross_leak(monkeypatch):
    """
    GIVEN: Zwei echte Nutzer (alice chat=111, bob chat=222) mit eigener user.json
    WHEN: Ein Webhook-Update von alice's chat_id eingeht
    THEN: Es werden ausschließlich alice's Trips geladen (load_all_trips('alice')),
          niemals bob's; ein unbekannter chat_id fällt auf 'default' zurück,
          nicht auf einen fremden Nutzer.
    """
    from fastapi.testclient import TestClient
    from api.main import app

    data_users = Path("data/users")
    alice_dir = data_users / "zz_test637_alice"
    bob_dir = data_users / "zz_test637_bob"
    try:
        for d, chat in ((alice_dir, "111"), (bob_dir, "222")):
            d.mkdir(parents=True, exist_ok=True)
            (d / "user.json").write_text(
                json.dumps({"id": d.name, "telegram_chat_id": chat}),
                encoding="utf-8",
            )

        loaded_for: list[str] = []

        def capture_load(user_id="default"):
            loaded_for.append(user_id)
            return []  # keine Trips → Verarbeitung endet nach "kein aktiver Trip"

        monkeypatch.setattr(
            "services.inbound_telegram_reader.load_all_trips", capture_load
        )
        monkeypatch.setattr(
            "services.notification_service.TelegramOutput.send",
            lambda self, subject, body: None,
        )

        client = TestClient(app)

        # Update von alice
        client.post("/api/internal/telegram-webhook", json={
            "update_id": 301,
            "message": {"chat": {"id": 111}, "text": "status"},
        })
        assert "zz_test637_alice" in loaded_for, (
            f"alice's chat_id wurde nicht auf alice geroutet: {loaded_for}"
        )
        assert "zz_test637_bob" not in loaded_for, (
            f"Cross-User-Leak: bob's Daten bei alice-Update geladen: {loaded_for}"
        )

        # Unbekannter chat_id → default, kein fremder Nutzer
        loaded_for.clear()
        client.post("/api/internal/telegram-webhook", json={
            "update_id": 302,
            "message": {"chat": {"id": 999999}, "text": "status"},
        })
        assert loaded_for and all(u == "default" for u in loaded_for), (
            f"Unbekannter chat_id darf nur 'default' laden, nicht: {loaded_for}"
        )
    finally:
        shutil.rmtree(alice_dir, ignore_errors=True)
        shutil.rmtree(bob_dir, ignore_errors=True)


# =============================================================================
# AC-5: Idempotenz — doppelt zugestelltes Update wird nur einmal verarbeitet
# =============================================================================

def test_webhook_idempotent_duplicate_update(monkeypatch):
    """
    GIVEN: Ein Update (update_id=200) das bereits verarbeitet wurde
    WHEN: Dasselbe Update ein zweites Mal zugestellt wird
    THEN: Der Befehl wird nur EINMAL verarbeitet (eine Processor-Ausführung),
          beide Antworten sind 200 OK.
    """
    from fastapi.testclient import TestClient
    from api.main import app

    trip = _make_active_trip()
    process_calls: list[str] = []

    def fake_process(self, msg):
        process_calls.append(msg.body)
        from services.trip_command_processor import CommandResult
        return CommandResult(
            success=True, command="ruhetag",
            confirmation_subject="OK", confirmation_body="OK",
            trip_name=trip.name,
        )

    monkeypatch.setattr(
        "services.inbound_telegram_reader.load_all_trips",
        lambda user_id="default": [trip],
    )
    monkeypatch.setattr(
        "services.trip_command_processor.TripCommandProcessor.process",
        fake_process,
    )
    monkeypatch.setattr(
        "services.notification_service.TelegramOutput.send",
        lambda self, subject, body: None,
    )

    client = TestClient(app)
    update = {
        "update_id": 200,
        "message": {"chat": {"id": 12345}, "text": "ruhetag 2"},
    }

    r1 = client.post("/api/internal/telegram-webhook", json=update)
    r2 = client.post("/api/internal/telegram-webhook", json=update)

    assert r1.status_code == 200 and r2.status_code == 200
    assert len(process_calls) == 1, (
        f"Doppel-Zustellung muss nur EINMAL verarbeiten, war: {len(process_calls)}x"
    )
