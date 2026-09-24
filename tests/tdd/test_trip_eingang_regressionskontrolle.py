"""Positive Regressionskontrolle — Issue #2282 Scheibe S1, AC-1, AC-3, AC-13.

SPEC: docs/specs/modules/feat_2282_ortsvergleich_eingangskanaele.md

BEWUSST SCHON IN DER RED-PHASE GRÜN: Diese Datei hält das heutige Trip-Verhalten
fest, das die neue Auswahl (`resolve_active_target`) und die Vergleichs-Weiche in
`process()` NICHT verändern dürfen. Sie ist kein TDD-Nachweis für neue Funktion,
sondern die Gegenprobe, dass die Änderung nicht zu breit greift (AC-13 verlangt
ausdrücklich eine eigene positive Assertion, nicht nur „bestehende Tests grün").

Dazu gehört auch: ein ARCHIVIERTER oder ABGELAUFENER Vergleich neben einem aktiven
Trip darf keine Rückfrage auslösen (Mutation 1 der Spec, Gegenrichtung).
"""
from __future__ import annotations

import json
import shutil
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from app.config import Settings  # noqa: E402
from app.loader import get_briefings_dir, get_data_dir, load_all_trips, save_trip  # noqa: E402
from app.models import TripReportConfig  # noqa: E402
from app.trip import Stage, Trip, Waypoint  # noqa: E402
from services.trip_command_processor import (  # noqa: E402
    InboundMessage,
    TripCommandProcessor,
)

TRIP_PAUSE_HINWEIS = "Zum Fortsetzen: STOP (dauerhaft) oder warte bis die Pause abläuft"


@pytest.fixture
def uid():
    u = f"tdd-2282-reg-{uuid.uuid4().hex[:8]}"
    yield u
    shutil.rmtree(get_briefings_dir(u).parent, ignore_errors=True)


def _nutzer_mit_tier(uid: str, tier: str = "premium") -> None:
    """Nachbesserung #2412 S4a: `send_command_reply_premium_sms` (via
    `_via_premium_sms`) hatte vor dem SMS-Tageslimit-Gate keinen Tier-Check
    -- ohne `user.json` faellt `user_tier._tier()` auf "free" zurueck (Cap
    0). Premium-SMS ist laut #1676 D7 ein Premium-Merkmal, diese Tests
    stehen fuer einen Premium-Nutzer. Muster `test_sms_tageslimit.py::
    _nutzer_anlegen`."""
    d = get_data_dir(uid)
    d.mkdir(parents=True, exist_ok=True)
    (d / "user.json").write_text(json.dumps({"id": uid, "tier": tier}))


def _trip(user_id: str, name: str, start_offset_days: int) -> Trip:
    today = date.today()
    tid = f"trip-{uuid.uuid4().hex[:8]}"
    trip = Trip(
        id=tid, name=name,
        stages=[
            Stage(id=f"S{i}", name=f"Tag {i + 1}",
                  date=today + timedelta(days=start_offset_days + i),
                  waypoints=[Waypoint(id=f"W{i}", name="A", lat=47.0, lon=11.0, elevation_m=800)])
            for i in range(3)
        ],
        report_config=TripReportConfig(trip_id=tid),
    )
    save_trip(trip, user_id)
    return trip


def _preset(user_id: str, name: str, **felder) -> dict:
    pid = f"cmp-{uuid.uuid4().hex[:8]}"
    entry = {"id": pid, "name": name, "kind": "vergleich", "user_id": user_id,
             "location_ids": ["loc-a"], "schedule": "daily", "previous_schedule": "",
             "created_at": "2026-09-01T08:00:00Z"}
    entry.update(felder)
    d = get_briefings_dir(user_id)
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{pid}.json").write_text(json.dumps(entry), encoding="utf-8")
    return entry


def _geladen(user_id: str, trip_id: str) -> Trip:
    return next(t for t in load_all_trips(user_id) if t.id == trip_id)


def _via_telegram(monkeypatch, user_id: str, text: str) -> list[str]:
    sent: list[str] = []
    monkeypatch.setattr("app.loader.lookup_user_by_telegram_chat_id",
                        lambda chat_id, data_dir="data": user_id)
    monkeypatch.setattr("services.notification_service.TelegramOutput.send",
                        lambda self, subject, body, **kw: sent.append(body) or 1)
    from services.inbound_telegram_reader import InboundTelegramReader

    InboundTelegramReader()._process_update(
        {"update_id": 1, "message": {"chat": {"id": 12345}, "text": text,
                                     "date": int(datetime.now(tz=timezone.utc).timestamp())}},
        Settings(telegram_bot_token="fake:token", telegram_chat_id="12345"),
    )
    return sent


class _LernAntwort:
    def __init__(self, user_id: str):
        self._uid = user_id

    def json(self):
        return {"user_id": self._uid}


def _via_premium_sms(monkeypatch, user_id: str, text: str) -> list[str]:
    sent: list[str] = []
    from output.channels.premium_sms import PremiumSmsOutput

    monkeypatch.setattr(PremiumSmsOutput, "__init__", lambda self, settings: None)
    monkeypatch.setattr(PremiumSmsOutput, "send",
                        lambda self, subject, body, **kw: sent.append(body))
    from services.inbound_sms_reader import InboundSmsReader

    InboundSmsReader()._verarbeite_befehl(Settings(), text, "+491701234567", _LernAntwort(user_id))
    return sent


_KANAELE = {"telegram": _via_telegram, "premium_sms": _via_premium_sms}


@pytest.mark.parametrize("kanal", ["telegram", "premium_sms"])
@pytest.mark.parametrize("vergleich", [None, "archiviert", "abgelaufen"])
def test_ac1_ein_trip_ohne_aktiven_vergleich_pausiert_trip(monkeypatch, uid, kanal, vergleich):
    _nutzer_mit_tier(uid)
    trip = _trip(uid, "Korsika", start_offset_days=-1)
    if vergleich == "archiviert":
        _preset(uid, "Alpenblick", archived_at="2026-09-01T00:00:00Z")
    elif vergleich == "abgelaufen":
        _preset(uid, "Alpenblick", end_date=(date.today() - timedelta(days=3)).isoformat())

    sent = _KANAELE[kanal](monkeypatch, uid, "pause 2d")

    assert _geladen(uid, trip.id).report_config.paused_until is not None
    assert sent and TRIP_PAUSE_HINWEIS in sent[-1], sent


@pytest.mark.parametrize("kanal", ["telegram", "premium_sms"])
def test_ac3_mehrere_trips_ohne_vergleich_pick_active_trip_entscheidet(monkeypatch, uid, kanal):
    _nutzer_mit_tier(uid)
    aktuell = _trip(uid, "Korsika", start_offset_days=-1)
    zukunft = _trip(uid, "Dolomiten", start_offset_days=20)

    sent = _KANAELE[kanal](monkeypatch, uid, "pause 2d")

    assert _geladen(uid, aktuell.id).report_config.paused_until is not None
    assert _geladen(uid, zukunft.id).report_config.paused_until is None
    assert sent and "Mehrdeutig" not in sent[-1]


def test_ac13_trip_pause_text_und_wirkung_unveraendert(uid):
    trip = _trip(uid, "Korsika", start_offset_days=-1)
    res = TripCommandProcessor().process(InboundMessage(
        trip_name="Korsika", body="pause 2d", sender="a@example.com", channel="email",
        received_at=datetime.now(tz=timezone.utc), user_id=uid,
    ))
    assert res.success is True
    assert TRIP_PAUSE_HINWEIS in res.confirmation_body
    assert _geladen(uid, trip.id).report_config.paused_until is not None
