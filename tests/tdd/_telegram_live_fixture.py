"""
Test-Fixture-Helper für echte Telegram-Live-Tests (Issue #686).

Stellt idempotent Staging-Test-User + aktiven Trip + Wetter-Snapshot sicher.
KEINE Mocks — echte Pipeline, echte API.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Konstanten
# ---------------------------------------------------------------------------

TEST_USER_ID = "tg-live-e2e"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def ensure_test_user_with_active_trip(
    chat_id: str,
    data_dir: str = "data",
) -> str:
    """Legt idempotent einen dedizierten Test-User mit aktivem Trip + Snapshot an.

    Regeln:
    - user_id ist immer TEST_USER_ID ("tg-live-e2e") — nicht "default"
    - user.json wird read-modify-write: vorhandene Felder bleiben erhalten,
      nur telegram_chat_id wird auf chat_id gesetzt
    - Ein gültiger Trip wird nur angelegt, wenn noch kein aktiver Trip existiert
    - Ein Wetter-Snapshot wird nur geholt, wenn noch keiner existiert (idempotent)

    Returns:
        user_id (immer TEST_USER_ID)
    """
    user_id = TEST_USER_ID
    user_dir = Path(data_dir) / "users" / user_id
    user_dir.mkdir(parents=True, exist_ok=True)

    # user.json: read-modify-write
    user_file = user_dir / "user.json"
    if user_file.exists():
        profile = json.loads(user_file.read_text(encoding="utf-8"))
    else:
        profile = {
            "id": user_id,
            "password_hash": "$2a$10$placeholder000000000000000000000000000000000",
            "created_at": datetime.now(tz=timezone.utc).isoformat(),
            "mail_to": "",
        }
    profile["telegram_chat_id"] = str(chat_id)
    user_file.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")

    # Trip anlegen falls noch kein aktiver Trip existiert
    trip = active_trip_for(user_id=user_id, data_dir=data_dir)
    if trip is None:
        _create_active_trip(user_id=user_id, data_dir=data_dir)
        trip = active_trip_for(user_id=user_id, data_dir=data_dir)

    # Wetter-Snapshot sicherstellen (F002: ohne Snapshot → "Kein Wetter-Snapshot verfügbar")
    if trip is not None and data_dir == "data":
        _ensure_weather_snapshot(trip=trip, user_id=user_id)

    return user_id


def active_trip_for(user_id: str, data_dir: str = "data") -> Optional[object]:
    """Gibt den heute-aktiven Trip des Users zurück, sonst None.

    Liest direkt aus {data_dir}/users/{user_id}/trips/*.json via load_trip(path).
    Nicht load_all_trips (CWD-relativ, ignoriert data_dir).
    """
    from app.loader import load_trip

    trips_dir = Path(data_dir) / "users" / user_id / "trips"
    if not trips_dir.exists():
        return None

    today = date.today()
    for trip_file in trips_dir.glob("*.json"):
        try:
            trip = load_trip(str(trip_file))
            if trip is None:
                continue
            if trip.start_date <= today <= trip.end_date:
                return trip
        except Exception:
            continue
    return None


def run_command_through_pipeline(
    command: str,
    chat_id: str,
    data_dir: str = "data",
) -> str:
    """Fährt die echte Pipeline für einen Menü-Befehl ohne an Telegram zu senden.

    Replicates the body-encoding from inbound_telegram_reader._process_update
    (Z.164-182): query-keys → "### query: <key>", sonst "### <key>" / "### <key>: <value>".

    Returns:
        CommandResult.confirmation_body (echter Pipeline-Output)
    """
    from datetime import datetime, timezone

    from services.inbound_telegram_reader import InboundTelegramReader
    from services.trip_command_processor import (
        InboundMessage,
        TripCommandProcessor,
        _QUERY_KEYS,
    )

    # Führenden Slash entfernen
    cmd = command.lstrip("/")

    reader = InboundTelegramReader()
    from app.loader import lookup_user_by_telegram_chat_id

    user_id = lookup_user_by_telegram_chat_id(chat_id) or "default"
    trip = reader._find_active_trip(user_id)
    if trip is None:
        return "Kein aktiver Trip"

    key, value = reader._parse_command(cmd)
    if key is None:
        return "Unbekannter Befehl"

    # Body kodieren (exakt wie _process_update)
    if key in _QUERY_KEYS:
        body = f"### query: {key}"
    elif value:
        body = f"### {key}: {value}"
    else:
        body = f"### {key}"

    inbound = InboundMessage(
        channel="telegram",
        trip_name=trip.name,
        body=body,
        sender=chat_id,
        received_at=datetime.now(tz=timezone.utc),
        user_id=user_id,
    )
    result = TripCommandProcessor().process(inbound)
    return result.confirmation_body


def deliver_and_cleanup(
    command: str,
    chat_id: str,
    data_dir: str = "data",
) -> tuple:
    """Echter Live-Pfad durch _process_update: sendet via echten Webhook-Eintrittspunkt.

    Baut ein echtes Telegram-Update-dict und ruft den ECHTEN
    InboundTelegramReader._process_update auf. Dieser sendet an den Test-Chat
    (weil user.json telegram_chat_id=chat_id hat → with_user_profile → user_settings).
    Danach reader.sent_message_ids auslesen und alle Nachrichten löschen.

    Keine Mocks — echter Webhook-Eintrittspunkt, echte Telegram-API.

    Returns:
        (last_message_id: int | None, all_deleted_ok: bool)
    """
    from app.config import Settings
    from outputs.telegram import TelegramOutput
    from services.inbound_telegram_reader import InboundTelegramReader

    settings = Settings()

    # Echtes Update-Dict wie Telegram es senden würde (message-Typ)
    cmd_text = f"/{command}" if not command.startswith("/") else command
    update = {
        "update_id": 1,
        "message": {
            "message_id": 1,
            "from": {"id": int(chat_id), "is_bot": False, "first_name": "Test"},
            "chat": {"id": int(chat_id), "type": "private"},
            "date": int(datetime.now(tz=timezone.utc).timestamp()),
            "text": cmd_text,
        },
    }

    reader = InboundTelegramReader()
    try:
        reader._process_update(update, settings)
    except Exception:
        return (None, False)

    if not reader.sent_message_ids:
        return (None, False)

    last_mid = reader.sent_message_ids[-1]
    out = TelegramOutput(settings.model_copy(update={"telegram_chat_id": str(chat_id)}))
    all_deleted = True
    for mid in reader.sent_message_ids:
        try:
            ok = out.delete_message(chat_id=chat_id, message_id=mid)
            if not ok:
                all_deleted = False
        except Exception:
            all_deleted = False

    return (last_mid, all_deleted)


# ---------------------------------------------------------------------------
# Interne Helper
# ---------------------------------------------------------------------------


def _ensure_weather_snapshot(trip, user_id: str) -> None:
    """Holt einen echten Wetter-Snapshot falls noch keiner existiert.

    Nutzt TripReportSchedulerService._convert_trip_to_segments + _fetch_weather
    + WeatherSnapshotService.save — exakt wie der Scheduler nach dem Report-Versand.
    Idempotent: existiert schon ein Snapshot, wird nichts gemacht.
    """
    from services.weather_snapshot import WeatherSnapshotService

    svc = WeatherSnapshotService(user_id)
    if svc.load(trip.id) is not None:
        return  # Snapshot existiert bereits — nichts zu tun

    # target_date = heute falls Stage vorhanden, sonst erster Stage-Tag
    today = date.today()
    stage = trip.get_stage_for_date(today)
    if stage is None:
        # Ersten Stage im aktiven Fenster nehmen
        active_stages = [s for s in trip.stages if trip.start_date <= s.date <= trip.end_date]
        if not active_stages:
            return
        target_date = active_stages[0].date
    else:
        target_date = today

    from services.trip_report_scheduler import TripReportSchedulerService
    scheduler = TripReportSchedulerService(user_id=user_id)
    segments = scheduler._convert_trip_to_segments(trip, target_date)
    if not segments:
        return

    try:
        segment_weather = scheduler._fetch_weather(segments)
        if segment_weather:
            svc.save(trip.id, segment_weather, target_date)
    except Exception:
        pass  # fail-soft: Snapshot-Fehler verhindert den Test nicht


def _create_active_trip(user_id: str, data_dir: str) -> None:
    """Erstellt einen gültigen Trip mit start_date=heute-1, end_date=heute+2.

    Koordinaten: Korsika (GR20-Region) — echte Wetterdaten verfügbar.
    """
    today = date.today()
    start = today - timedelta(days=1)
    end = today + timedelta(days=2)

    trips_dir = Path(data_dir) / "users" / user_id / "trips"
    trips_dir.mkdir(parents=True, exist_ok=True)

    trip_id = "tg-live-e2e-trip"
    trip_data = {
        "id": trip_id,
        "name": "TG Live E2E Test",
        "stages": [
            {
                "id": "s1",
                "name": "Stage 1",
                "date": str(start),
                "waypoints": [
                    {
                        "id": "w0",
                        "name": "Vizzavona",
                        "lat": 42.12,
                        "lon": 9.12,
                        "elevation_m": 910,
                        "arrival_calculated": "08:00",
                    },
                    {
                        "id": "w1",
                        "name": "Bocca Palmente",
                        "lat": 42.15,
                        "lon": 9.13,
                        "elevation_m": 1640,
                        "arrival_calculated": "12:00",
                    },
                ],
                "start_time": "08:00",
            },
            {
                "id": "s2",
                "name": "Stage 2",
                "date": str(today),
                "waypoints": [
                    {
                        "id": "w2",
                        "name": "Bocca Palmente",
                        "lat": 42.15,
                        "lon": 9.13,
                        "elevation_m": 1640,
                        "arrival_calculated": "08:00",
                    },
                    {
                        "id": "w3",
                        "name": "Refuge de Pietra Piana",
                        "lat": 42.20,
                        "lon": 9.17,
                        "elevation_m": 1842,
                        "arrival_calculated": "14:00",
                    },
                ],
                "start_time": "08:00",
            },
            {
                "id": "s3",
                "name": "Stage 3",
                "date": str(end),
                "waypoints": [
                    {
                        "id": "w4",
                        "name": "Refuge de Pietra Piana",
                        "lat": 42.20,
                        "lon": 9.17,
                        "elevation_m": 1842,
                        "arrival_calculated": "08:00",
                    },
                    {
                        "id": "w5",
                        "name": "Corte",
                        "lat": 42.30,
                        "lon": 9.15,
                        "elevation_m": 396,
                        "arrival_calculated": "13:00",
                    },
                ],
                "start_time": "08:00",
            },
        ],
        "alert_rules": [],
        "region": "Korsika",
    }

    trip_file = trips_dir / f"{trip_id}.json"
    trip_file.write_text(json.dumps(trip_data, ensure_ascii=False, indent=2), encoding="utf-8")
