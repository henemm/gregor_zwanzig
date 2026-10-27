"""
Bewachungstest #2239: `load_all_trips` deckt sich mit `load_trip`.

Spec: docs/specs/modules/fix_2239_loader_konsistenz.md
Workflow: fix-2239-loader-divergenz

Kein Bug-Reproduktionstest: gegen den unveraenderten Loader ist dieser Test
gruen. Sein Wert wird durch Mutationen von `load_all_trips` belegt (M1-M4 in
der Spec). Keine Mocks -- echte JSON-Dateien unter tmp_path, echte Loader.

Hinweis zu `glob("*.json")`: die Lesereihenfolge ist Dateisystem-abhaengig,
nicht sortiert. Damit ein Abbruch im except-Zweig (Mutation M3) sicher
auffaellt, liegen mehrere kaputte Dateien zwischen vielen gueltigen Trips.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

USER_A = "tdd-2239-nutzer-a"
USER_B = "tdd-2239-nutzer-b"

# (id, archiviert?)
ROUTES_A = [
    ("a-route-01", False),
    ("a-route-02", True),
    ("a-route-03", False),
    ("a-route-04", True),
    ("a-route-05", False),
    ("a-route-06", False),
    ("a-route-07", False),
    ("a-route-08", True),
]
VERGLEICH_A = "a-vergleich-01"
KAPUTT_A = ["a-kaputt-01", "a-kaputt-02", "a-kaputt-03", "a-kaputt-04"]
ROUTES_B = [("b-route-01", False), ("b-route-02", True), ("b-route-03", False)]


def _trip_json(trip_id: str, archived: bool = False, stage_date: str = "2026-07-01") -> dict:
    data: dict = {
        "id": trip_id,
        "kind": "route",
        "name": f"Trip {trip_id}",
        "stages": [
            {
                "id": f"stage-{trip_id}-1",
                "name": "Etappe 1",
                "date": stage_date,
                "waypoints": [
                    {"id": f"wp-{trip_id}-1", "name": "Start",
                     "lat": 42.0, "lon": 9.0, "elevation_m": 800}
                ],
            }
        ],
    }
    if archived:
        data["archived_at"] = "2026-01-15T10:00:00Z"
    return data


def _write(directory: Path, trip_id: str, payload: dict) -> Path:
    path = directory / f"{trip_id}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


@pytest.fixture()
def env(tmp_path, monkeypatch):
    """Isolierter Daten-Root mit zwei Nutzern (gleiche Mechanik wie conftest)."""
    from app import loader

    monkeypatch.setattr(loader, "_DATA_ROOT", str(tmp_path))
    dir_a = loader.get_briefings_dir(USER_A)
    dir_b = loader.get_briefings_dir(USER_B)
    dir_a.mkdir(parents=True, exist_ok=True)
    dir_b.mkdir(parents=True, exist_ok=True)

    for trip_id, archived in ROUTES_A:
        _write(dir_a, trip_id, _trip_json(trip_id, archived))
    vergleich = {"id": VERGLEICH_A, "kind": "vergleich", "name": "Ortsvergleich"}
    _write(dir_a, VERGLEICH_A, vergleich)
    for trip_id in KAPUTT_A:
        _write(dir_a, trip_id, _trip_json(trip_id, stage_date="kein-datum"))
    for trip_id, archived in ROUTES_B:
        _write(dir_b, trip_id, _trip_json(trip_id, archived))
    return dir_a


def _einzeln_ladbar(directory: Path) -> dict:
    """Referenz: pro kind=route-Datei `load_trip(<Pfad>)`; Erfolge {id: Trip}."""
    from app.loader import load_trip

    ergebnis = {}
    for path in sorted(directory.glob("*.json")):
        if json.loads(path.read_text(encoding="utf-8")).get("kind") != "route":
            continue
        try:
            trip = load_trip(path, user_id=USER_A)
        except Exception:
            continue
        ergebnis[trip.id] = trip
    return ergebnis


def _ids(trips) -> set:
    return {t.id for t in trips}


def test_ac1_include_archived_deckt_sich_mit_load_trip(env):
    """GIVEN Nutzer A mit route-Dateien (teils archiviert) und kaputten Dateien
    WHEN load_all_trips(A, include_archived=True)
    THEN identisch mit der Menge, die load_trip einzeln fehlerfrei laedt."""
    from app.loader import load_all_trips

    referenz = _einzeln_ladbar(env)
    assert set(referenz) == {i for i, _ in ROUTES_A}, "Fixture-Annahme verletzt"
    assert _ids(load_all_trips(USER_A, include_archived=True)) == set(referenz)


def test_ac2_default_blendet_genau_die_archivierten_aus(env):
    """GIVEN dasselbe Szenario
    WHEN load_all_trips(A) ohne Flag
    THEN Referenzmenge abzueglich archived_at, und nicht leer."""
    from app.loader import load_all_trips

    erwartet = {i for i, t in _einzeln_ladbar(env).items() if t.archived_at is None}
    ergebnis = _ids(load_all_trips(USER_A))
    assert erwartet, "Fixture-Annahme verletzt: es muss nicht archivierte Trips geben"
    assert ergebnis, "load_all_trips ohne Flag darf nicht leer sein"
    assert ergebnis == erwartet


def test_ac3_vergleich_datei_taucht_nirgends_auf(env):
    """GIVEN eine kind=vergleich-Datei im selben briefings/-Verzeichnis
    WHEN load_all_trips mit und ohne include_archived
    THEN deren ID steht in keinem Ergebnis."""
    from app.loader import load_all_trips

    assert VERGLEICH_A not in _ids(load_all_trips(USER_A))
    assert VERGLEICH_A not in _ids(load_all_trips(USER_A, include_archived=True))


def test_ac4_kaputte_datei_bricht_nicht_ab_und_wird_geloggt(env, caplog):
    """GIVEN kaputte kind=route-Dateien (ungueltiges Datum) neben gueltigen Trips
    WHEN load_all_trips(A, include_archived=True)
    THEN fehlen nur die kaputten, alle gueltigen sind da (kein Abbruch), und
    je kaputter Datei steht ein ERROR 'Skipping corrupt trip <Dateiname>' im Log."""
    from app.loader import load_all_trips

    with caplog.at_level(logging.ERROR):
        ergebnis = _ids(load_all_trips(USER_A, include_archived=True))

    assert ergebnis == {i for i, _ in ROUTES_A}
    fehler = [r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR]
    for kaputt in KAPUTT_A:
        assert any(
            "Skipping corrupt trip" in m and f"{kaputt}.json" in m for m in fehler
        ), f"kein ERROR-Log fuer {kaputt}.json: {fehler}"


def test_ac5_nutzer_sind_getrennt(env):
    """GIVEN Nutzer A und B mit disjunkten Trip-IDs im selben Daten-Root
    WHEN load_all_trips je Nutzer
    THEN enthaelt keines Trips des anderen."""
    from app.loader import load_all_trips

    ids_a = {i for i, _ in ROUTES_A}
    ids_b = {i for i, _ in ROUTES_B}
    assert ids_a.isdisjoint(ids_b)
    res_a = _ids(load_all_trips(USER_A, include_archived=True))
    res_b = _ids(load_all_trips(USER_B, include_archived=True))
    assert res_a == ids_a and not (res_a & ids_b)
    assert res_b == ids_b and not (res_b & ids_a)
