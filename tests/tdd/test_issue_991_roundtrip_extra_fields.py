"""
TDD RED Tests for Issue #991 — Trip-Roundtrip erhält unmodellierte Top-Level-Felder.

Each test maps 1:1 to one AC from
docs/specs/modules/fix_991_trip_roundtrip_fields.md.

These tests reproduce real data loss in the pure model roundtrip
`_trip_to_dict(load_trip_from_dict(d))`: unmodellierte Top-Level-Keys
(z.B. accuracy_pct, headline, briefings_count, alerts_count) werden
verworfen, weil `Trip` keinen generischen `extra`-Auffangmechanismus hat.

NO MOCKS — real dataclasses, real dict roundtrip, real production JSON files.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.loader import _trip_to_dict, load_trip, load_trip_from_dict


def _minimal_trip_dict(**extra_fields) -> dict:
    """Build a minimal valid Trip dict (id, name, one stage with one waypoint)
    plus arbitrary extra top-level fields for roundtrip testing.
    """
    d = {
        "id": "tdd-991-trip",
        "name": "TDD 991 Test Trip",
        "stages": [
            {
                "id": "stage-1",
                "name": "Etappe 1",
                "date": "2026-07-10",
                "waypoints": [
                    {
                        "id": "wp-1",
                        "name": "Start",
                        "lat": 46.0,
                        "lon": 9.0,
                        "elevation_m": 1200,
                    }
                ],
            }
        ],
    }
    d.update(extra_fields)
    return d


# --- AC-1: Vier Metadaten-Felder überleben Roundtrip ----------------------

def test_ac1_four_metadata_fields_survive_roundtrip():
    """AC-1: accuracy_pct/headline/briefings_count/alerts_count bleiben nach
    _trip_to_dict(load_trip_from_dict(d)) unverändert erhalten.
    """
    d = _minimal_trip_dict(
        accuracy_pct=87.5,
        headline="Sonnig mit Wind",
        briefings_count=42,
        alerts_count=3,
    )

    trip = load_trip_from_dict(d)
    rt = _trip_to_dict(trip)

    assert "accuracy_pct" in rt, "accuracy_pct verloren beim Roundtrip"
    assert rt["accuracy_pct"] == 87.5

    assert "headline" in rt, "headline verloren beim Roundtrip"
    assert rt["headline"] == "Sonnig mit Wind"

    assert "briefings_count" in rt, "briefings_count verloren beim Roundtrip"
    assert rt["briefings_count"] == 42

    assert "alerts_count" in rt, "alerts_count verloren beim Roundtrip"
    assert rt["alerts_count"] == 3


# --- AC-2: Produktiv-Trips verlieren die vier Metadaten-Keys nicht ---------

@pytest.mark.real_data_root
def test_ac2_production_trips_roundtrip_contract():
    """AC-2: Über alle data/users/*/trips/*.json — sofern eines der vier
    Metadaten-Felder im Original vorhanden ist, muss es den Roundtrip
    unverändert überstehen (analog test_ac9 in test_alert_rules_model.py,
    aber fokussiert auf die vier #991-Felder).
    """
    metadata_keys = ["accuracy_pct", "headline", "briefings_count", "alerts_count"]

    trip_files = sorted(Path("data/users").glob("*/trips/*.json"))
    assert trip_files, "Es müssen Produktiv-Trips existieren"

    checked_count = 0
    failures: list[str] = []

    for trip_path in trip_files:
        original = json.loads(trip_path.read_text())
        try:
            trip = load_trip(original)
        except Exception:
            # Pre-existing kaputtes Trip-Schema — nicht Scope dieses Fixes.
            continue

        roundtrip = _trip_to_dict(trip)

        for key in metadata_keys:
            if key not in original:
                continue
            checked_count += 1
            if key not in roundtrip:
                failures.append(f"{trip_path.name}: key '{key}' verloren beim Roundtrip")
                continue
            if roundtrip[key] != original[key]:
                failures.append(
                    f"{trip_path.name}: key '{key}' geändert beim Roundtrip "
                    f"({original[key]!r} -> {roundtrip[key]!r})"
                )

    assert checked_count >= 1, (
        "Kein Produktiv-Trip enthält eines der vier #991-Metadaten-Felder — "
        "Test kann den Vertrag nicht prüfen (Skip-Grund, kein grüner Beweis)."
    )
    assert not failures, "Roundtrip-Drift gefunden:\n" + "\n".join(failures)


# --- AC-3: Beliebiger synthetischer Unbekannt-Key überlebt (Generik) -------

def test_ac3_arbitrary_unknown_field_survives():
    """AC-3: Ein nie modellierter, frei erfundener Top-Level-Key
    (future_field_xyz) überlebt den Roundtrip unverändert — beweist, dass
    die Erhaltung generisch ist, nicht auf die vier bekannten Felder
    beschränkt.
    """
    d = _minimal_trip_dict(future_field_xyz={"nested": 42})

    trip = load_trip_from_dict(d)
    rt = _trip_to_dict(trip)

    assert "future_field_xyz" in rt, "future_field_xyz verloren beim Roundtrip"
    assert rt["future_field_xyz"] == {"nested": 42}


# --- AC-4: Modelliertes Feld gewinnt, kein Duplikat/Konflikt ---------------

def test_ac4_modeled_field_wins_no_duplicate():
    """AC-4: Ein modelliertes Feld (region) wird aus dem Modell serialisiert,
    nicht aus einem generischen extra-Mechanismus — genau ein region-Eintrag
    mit korrektem Wert, kein Konflikt.
    """
    d = _minimal_trip_dict(region="GR20")

    trip = load_trip_from_dict(d)
    rt = _trip_to_dict(trip)

    assert rt["region"] == "GR20"
    # Genau ein Eintrag: dict kann pro Key ohnehin nur einen Wert halten,
    # aber wir beweisen explizit, dass es der modellierte (korrekte) Wert ist
    # und kein aus extra überschriebener/kollidierender Wert.
    assert list(rt.keys()).count("region") == 1


# --- AC-5: start_time bleibt kanonisches HH:MM (kein Sekunden-Drift) -------

def test_ac5_start_time_roundtrip_stable():
    """AC-5: Stage-start_time im kanonischen Format "HH:MM" bleibt nach
    _trip_to_dict(load_trip_from_dict(d)) byte-identisch "HH:MM" —
    nicht ".isoformat()" mit Sekunden ("08:00:00").
    """
    d = _minimal_trip_dict()
    d["stages"][0]["start_time"] = "08:00"

    trip = load_trip_from_dict(d)
    rt = _trip_to_dict(trip)

    assert rt["stages"][0]["start_time"] == "08:00"
