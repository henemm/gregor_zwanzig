"""TDD RED — #1969 AC-14: ``GET /api/_internal/next-briefings`` trennt Nutzer
und verlangt ``X-GZ-Core-Auth`` (ADR-0062).

Spec: docs/specs/modules/feat_1969_naechstes_briefing.md (AC-14)

Echte Trip-/Preset-Dateien in ZWEI Nutzerverzeichnissen unter dem per Test
isolierten Daten-Root (autouse ``_isolate_data_root`` in tests/conftest.py,
``app.loader._DATA_ROOT`` -> tmp), echte FastAPI-App über ``TestClient``.
Der ``TestClient`` trägt den gültigen Core-Auth-Header automatisch
(``_patch_testclient_with_core_auth`` in tests/conftest.py); der Negativtest
entfernt ihn aktiv und prüft die Entfernung.

Jeder Negativ-Befund ist mit einer Positiv-Kontrolle im SELBEN Test gekoppelt
— sonst wäre „ohne Header ⇒ 401" schon heute grün (die Middleware weist vor
dem Routing ab) und „fremde ID fehlt" wäre bei einem 404 vakuum-grün.

Die Antwort wird nur auf das Vorhandensein von ``trips`` und ``compare``
geprüft, NICHT auf eine exakte Schlüsselmenge: #2346 ergänzt später ein
Geschwister-Objekt ``last_briefing`` auf oberster Ebene.
"""
from __future__ import annotations

import json
from datetime import date, timedelta

from fastapi.testclient import TestClient

CORE_AUTH_HEADER = "X-GZ-Core-Auth"
PFAD = "/api/_internal/next-briefings"

USER_A = "nb-user-a"
USER_B = "nb-user-b"
TRIP_A, TRIP_B = "trip-von-a", "trip-von-b"
PRESET_A, PRESET_B = "vergleich-von-a", "vergleich-von-b"


def _trip_json(trip_id: str) -> dict:
    """Trip mit Etappen ab heute für eine Woche (Korsika) — hat in jedem Fall
    einen künftigen Termin, unabhängig von der Uhrzeit des Testlaufs."""
    heute = date.today()
    return {
        "id": trip_id,
        "name": f"Trip {trip_id}",
        "stages": [
            {
                "id": f"{trip_id}-s{i}",
                "name": f"Etappe {i}",
                "date": (heute + timedelta(days=i)).isoformat(),
                "waypoints": [
                    {"id": f"{trip_id}-w{i}a", "name": "Start",
                     "lat": 42.30, "lon": 8.93, "elevation_m": 800},
                    {"id": f"{trip_id}-w{i}b", "name": "Ziel",
                     "lat": 42.35, "lon": 8.98, "elevation_m": 1200},
                ],
            }
            for i in range(7)
        ],
        "report_config": {
            "enabled": True, "morning_time": "07:00:00", "evening_time": "18:00:00",
        },
    }


def _preset_json(preset_id: str) -> dict:
    return {
        "id": preset_id,
        "kind": "vergleich",
        "name": f"Vergleich {preset_id}",
        "schedule": "daily",
        "weekday": None,
        "location_ids": [],
        "morning_enabled": True,
        "morning_time": "07:00:00",
        "evening_enabled": True,
        "evening_time": "18:00:00",
    }


def _lege_an(user_id: str, trip_id: str, preset_id: str) -> None:
    from app.loader import get_briefings_dir

    ordner = get_briefings_dir(user_id)
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / f"{trip_id}.json").write_text(json.dumps(_trip_json(trip_id)), encoding="utf-8")
    (ordner / f"{preset_id}.json").write_text(
        json.dumps(_preset_json(preset_id)), encoding="utf-8",
    )


def _zwei_nutzer() -> None:
    _lege_an(USER_A, TRIP_A, PRESET_A)
    _lege_an(USER_B, TRIP_B, PRESET_B)
    # Testaufbau: beide Nutzer liegen wirklich getrennt auf der Platte.
    from app.loader import load_all_trips, load_compare_presets

    assert [t.id for t in load_all_trips(USER_A)] == [TRIP_A]
    assert [t.id for t in load_all_trips(USER_B)] == [TRIP_B]
    assert [p.id for p in load_compare_presets(USER_A)] == [PRESET_A]


def _client() -> TestClient:
    from api.main import app

    return TestClient(app)


def _alle_ids(body: dict) -> set[str]:
    return set(body.get("trips", {})) | set(body.get("compare", {}))


def test_ac14_antwort_fuer_a_enthaelt_nur_ids_von_a():
    """AC-14: ``?user_id=A`` liefert A's Trip und Vergleich, keine ID von B."""
    _zwei_nutzer()

    resp = _client().get(PFAD, params={"user_id": USER_A})

    assert resp.status_code == 200, f"{resp.status_code}: {resp.text[:300]}"
    body = resp.json()
    assert "trips" in body and "compare" in body, body
    assert TRIP_A in body["trips"], body
    assert PRESET_A in body["compare"], body
    assert TRIP_B not in _alle_ids(body) and PRESET_B not in _alle_ids(body), (
        f"Cross-User-Leck: Antwort für {USER_A} enthält IDs von {USER_B}: {body}"
    )
    # Je Objekt das Ausgabeformat (Kern: at oder reason).
    eintrag = body["trips"][TRIP_A]
    assert eintrag.get("at") is not None or eintrag.get("reason"), eintrag


def test_ac14_fremde_trip_id_ist_nicht_enthalten():
    """AC-14: ``?trip_id=<B's Trip>`` im Aufruf von A ⇒ nicht enthalten;
    Positiv-Kontrolle: ``?trip_id=<A's Trip>`` liefert genau diesen Trip."""
    _zwei_nutzer()
    client = _client()

    eigen = client.get(PFAD, params={"user_id": USER_A, "trip_id": TRIP_A})
    assert eigen.status_code == 200, f"{eigen.status_code}: {eigen.text[:300]}"
    assert TRIP_A in eigen.json()["trips"], eigen.json()

    fremd = client.get(PFAD, params={"user_id": USER_A, "trip_id": TRIP_B})
    assert fremd.status_code in (200, 404), f"{fremd.status_code}: {fremd.text[:300]}"
    if fremd.status_code == 200:
        body = fremd.json()
        assert TRIP_B not in _alle_ids(body), f"Fremder Trip ausgeliefert: {body}"
        assert PRESET_B not in _alle_ids(body), body
    else:
        assert TRIP_B not in fremd.text


def test_ac14_fremde_preset_id_ist_nicht_enthalten():
    """AC-14: ``?preset_id=<B's Vergleich>`` im Aufruf von A ⇒ nicht enthalten;
    Positiv-Kontrolle mit A's eigenem Vergleich."""
    _zwei_nutzer()
    client = _client()

    eigen = client.get(PFAD, params={"user_id": USER_A, "preset_id": PRESET_A})
    assert eigen.status_code == 200, f"{eigen.status_code}: {eigen.text[:300]}"
    assert PRESET_A in eigen.json()["compare"], eigen.json()

    fremd = client.get(PFAD, params={"user_id": USER_A, "preset_id": PRESET_B})
    assert fremd.status_code in (200, 404), f"{fremd.status_code}: {fremd.text[:300]}"
    assert PRESET_B not in fremd.text, f"Fremder Vergleich ausgeliefert: {fremd.text[:300]}"


def test_ac14_ohne_core_auth_header_abgewiesen_mit_header_beantwortet():
    """AC-14: ohne ``X-GZ-Core-Auth`` ⇒ 401/403 und keine Nutzdaten; mit
    gültigem Header antwortet derselbe Endpoint 200 (Positiv-Kontrolle —
    ohne sie wäre der Negativfall schon vor dem Endpoint grün)."""
    _zwei_nutzer()

    mit = _client().get(PFAD, params={"user_id": USER_A})
    assert mit.status_code == 200, f"{mit.status_code}: {mit.text[:300]}"
    assert TRIP_A in mit.json()["trips"]

    ohne_client = _client()
    ohne_client.headers.pop(CORE_AUTH_HEADER, None)
    assert CORE_AUTH_HEADER not in ohne_client.headers
    ohne = ohne_client.get(PFAD, params={"user_id": USER_A})
    assert ohne.status_code in (401, 403), f"{ohne.status_code}: {ohne.text[:300]}"
    assert TRIP_A not in ohne.text

    falsch = _client().get(
        PFAD, params={"user_id": USER_A}, headers={CORE_AUTH_HEADER: "falsches-geheimnis"},
    )
    assert falsch.status_code in (401, 403), f"{falsch.status_code}: {falsch.text[:300]}"
    assert TRIP_A not in falsch.text
