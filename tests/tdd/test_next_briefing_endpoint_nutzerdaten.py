"""#1969 (Adversary F003/F004): ``GET /api/_internal/next-briefings`` liest
Vermerke und Orte des RICHTIGEN Nutzers, filtert per ``trip_id``/``preset_id``
und isoliert ein kaputtes Objekt.

Spec: docs/specs/modules/feat_1969_naechstes_briefing.md (AC-14, AC-19)

Zwei Nutzer mit GLEICHEN Kennungen (Trip-ID, Orts-ID, Preset-ID), aber
verschiedenen Daten: wuerde der Endpoint Vermerk-Speicher oder Ortsliste eines
anderen Nutzers (oder von ``"default"``) lesen, kippt die Antwort. Echte Dateien
im isolierten Daten-Root (autouse ``_isolate_data_root``), echte FastAPI-App,
Zeit per ``freeze_time`` (der Endpoint liest die Uhr selbst).
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from freezegun import freeze_time

PFAD = "/api/_internal/next-briefings"
USER_A, USER_B = "nbd-user-a", "nbd-user-b"
TRIP_ID, PRESET_ID, ORT_ID = "geteilte-trip-id", "geteilte-preset-id", "ort-1"
D23, D24 = date(2026, 10, 23), date(2026, 10, 24)
PARIS_TZ = ZoneInfo("Europe/Paris")
# Fr 23.10.2026 08:00 Paris (CEST): Morgen-Slot 07:00 im Nachholfenster.
JETZT = datetime(2026, 10, 23, 8, tzinfo=PARIS_TZ).astimezone(timezone.utc)
PARIS = (42.30, 8.93)
AUCKLAND = (-36.85, 174.76)


def _trip_json(trip_id: str) -> dict:
    return {
        "id": trip_id, "name": f"Trip {trip_id}",
        "stages": [
            {"id": f"{trip_id}-s{i}", "name": f"Etappe {i}", "date": d.isoformat(),
             "waypoints": [
                 {"id": f"{trip_id}-w{i}a", "name": "Start", "lat": PARIS[0],
                  "lon": PARIS[1], "elevation_m": 800},
                 {"id": f"{trip_id}-w{i}b", "name": "Ziel", "lat": PARIS[0] + 0.05,
                  "lon": PARIS[1] + 0.05, "elevation_m": 1200},
             ]}
            for i, d in enumerate((D23, D24))
        ],
        "report_config": {"enabled": True, "morning_time": "07:00:00",
                          "evening_time": "18:00:00"},
    }


def _preset_json(preset_id: str, location_ids: list) -> dict:
    return {
        "id": preset_id, "kind": "vergleich", "name": f"Vergleich {preset_id}",
        "schedule": "daily", "weekday": None, "location_ids": location_ids,
        "morning_enabled": True, "morning_time": "07:00:00",
        "evening_enabled": True, "evening_time": "18:00:00",
    }


def _schreibe(user_id: str, objekt: dict) -> None:
    from app.loader import get_briefings_dir

    ordner = get_briefings_dir(user_id)
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / f"{objekt['id']}.json").write_text(json.dumps(objekt), encoding="utf-8")


def _ort(user_id: str, coords) -> None:
    from app.loader import save_location
    from app.user import SavedLocation

    save_location(SavedLocation(id=ORT_ID, name="Ort", lat=coords[0], lon=coords[1],
                                elevation_m=100), user_id)


def _hole(**params) -> dict:
    from api.main import app

    with freeze_time(JETZT):
        resp = TestClient(app).get(PFAD, params=params)
    assert resp.status_code == 200, f"{resp.status_code}: {resp.text[:300]}"
    return resp.json()


# ═══════════════════════════════ F003 ═══════════════════════════════


def test_vermerk_kommt_aus_dem_speicher_des_anfragenden_nutzers():
    """A hat den heutigen Morgen-Slot vermerkt, B (gleiche Trip-ID) nicht ⇒
    A: naechster Termin 18:00; B: 07:00 ueberfaellig. Liest der Endpoint den
    Speicher eines anderen Nutzers (oder "default"), kippt mindestens eine Seite."""
    from services.briefing_slots import BriefingSlotStore

    for uid in (USER_A, USER_B):
        _schreibe(uid, _trip_json(TRIP_ID))
    BriefingSlotStore(USER_A).record_outcome(TRIP_ID, "morning", D23, "sent")

    a = _hole(user_id=USER_A)["trips"][TRIP_ID]
    b = _hole(user_id=USER_B)["trips"][TRIP_ID]

    assert (a["local_date"], a["local_time"], a.get("overdue")) == ("2026-10-23", "18:00", None), (
        f"A: eigener Vermerk wurde nicht gelesen: {a!r}"
    )
    assert (b["local_date"], b["local_time"], b.get("overdue")) == ("2026-10-23", "07:00", True), (
        f"B: fremder Vermerk (von A) wurde gelesen: {b!r}"
    )


def test_orte_kommen_aus_der_ortsliste_des_anfragenden_nutzers():
    """Gleiche Orts-ID ``ort-1``: bei A in Auckland, bei B in Paris ⇒ der
    Vergleich von A traegt Pacific/Auckland, der von B Europe/Paris. Eine
    fremde oder leere Ortsliste ergaebe die falsche Zone bzw. UTC."""
    _ort(USER_A, AUCKLAND)
    _ort(USER_B, PARIS)
    for uid in (USER_A, USER_B):
        _schreibe(uid, _preset_json(PRESET_ID, [ORT_ID]))

    a = _hole(user_id=USER_A)["compare"][PRESET_ID]
    b = _hole(user_id=USER_B)["compare"][PRESET_ID]

    assert a["tz"] == "Pacific/Auckland", f"A: Zone nicht aus A's Orten: {a!r}"
    assert b["tz"] == "Europe/Paris", f"B: Zone nicht aus B's Orten: {b!r}"


# ═══════════════════════════════ F004 ═══════════════════════════════


def _zwei_von_jedem() -> None:
    _ort(USER_A, PARIS)
    for tid in ("trip-1", "trip-2"):
        _schreibe(USER_A, _trip_json(tid))
    for pid in ("preset-1", "preset-2"):
        _schreibe(USER_A, _preset_json(pid, [ORT_ID]))


def test_trip_id_filter_liefert_genau_diesen_trip_und_keine_vergleiche():
    _zwei_von_jedem()
    ohne = _hole(user_id=USER_A)
    assert set(ohne["trips"]) == {"trip-1", "trip-2"}, ohne  # Positiv-Kontrolle
    assert set(ohne["compare"]) == {"preset-1", "preset-2"}, ohne

    body = _hole(user_id=USER_A, trip_id="trip-2")

    assert set(body["trips"]) == {"trip-2"}, body
    assert body["compare"] == {}, body


def test_preset_id_filter_liefert_genau_diesen_vergleich_und_keine_trips():
    _zwei_von_jedem()

    body = _hole(user_id=USER_A, preset_id="preset-1")

    assert set(body["compare"]) == {"preset-1"}, body
    assert body["trips"] == {}, body


def test_kaputtes_objekt_wirft_die_uebrigen_nicht_aus_der_antwort():
    """Ein Vergleich mit unbrauchbarer Orts-Kennung (Liste statt String) laesst
    seine Ableitung scheitern -- der intakte Vergleich und der Trip bleiben in
    der Antwort, statt dass der ganze Endpoint 500 liefert."""
    _ort(USER_A, PARIS)
    _schreibe(USER_A, _trip_json("trip-ok"))
    _schreibe(USER_A, _preset_json("preset-ok", [ORT_ID]))
    _schreibe(USER_A, _preset_json("preset-kaputt", [["keine-gueltige-id"]]))

    body = _hole(user_id=USER_A)

    assert "preset-ok" in body["compare"], body
    assert "trip-ok" in body["trips"], body
    assert "preset-kaputt" not in body["compare"], body
