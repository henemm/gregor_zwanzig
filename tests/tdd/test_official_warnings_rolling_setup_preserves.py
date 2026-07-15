"""TDD — Issue #1258 Fix-Loop 1, Finding F001 (CRITICAL).

`scripts/setup_staging_validator_trip.py::_build_rolling_trip()` konstruiert
bei JEDEM Lauf einen frischen `Trip(...)` ohne `official_warnings`-Kwarg.
Der bare Dataclass-Konstruktor liefert dafuer per Default
`{"enabled": False}` (Neuanlage-Semantik, s. `app/trip.py`). Da das Skript
idempotent gedacht ist (rollender Cronjob, s. Docstring des Skripts) und
`save_trip()` per RMW-Merge ("overlay wins" bei Key-Konflikten,
`app/loader._deep_merge_preserve_unknown`) arbeitet, wuerde ein bereits auf
der Platte persistierter `official_warnings.enabled = True`-Wert bei jedem
wiederkehrenden Lauf STILL auf `False` zurueckgesetzt — der Test-Trip
verlöre den amtlichen-Warnungen-Zustand ohne dass irgendjemand ihn
absichtlich geaendert haette.

RED vor dem Fix: der zweite `_build_rolling_trip()`/`save_trip()`-Durchlauf
ueberschreibt `official_warnings.enabled` von True auf False.
GREEN nach dem Fix: `_build_rolling_trip()` gibt `official_warnings=None`
an den Konstruktor, `_trip_to_dict()` laesst den Schluessel dann weg,
der RMW-Merge fasst den bestehenden Wert nicht an.

Keine Mocks — echter `save_trip()`/`load_trip()`-Roundtrip auf einem
isolierten `tmp_path`-Datenverzeichnis (Muster test_issue_1258_*).
"""
from __future__ import annotations

from pathlib import Path


def test_rolling_setup_rerun_preserves_existing_official_warnings_enabled(tmp_path: Path):
    from app.loader import load_trip, save_trip
    from scripts.setup_staging_validator_trip import TRIP_ID, USER_ID, _build_rolling_trip

    data_dir = tmp_path / "data"

    # Erster Lauf: Trip existiert noch nicht -> Neuanlage-Default enabled=False.
    trip = _build_rolling_trip()
    save_trip(trip, user_id=USER_ID, data_dir=data_dir)

    # Simuliert einen Nutzer/Operator, der amtliche Warnungen fuer den
    # Test-Trip manuell aktiviert (z.B. ueber den Alarme-Tab).
    persisted = load_trip(TRIP_ID, data_dir=str(data_dir), user_id=USER_ID)
    persisted.official_warnings = {"enabled": True, "sources": ["meteofrance_vigilance"]}
    save_trip(persisted, user_id=USER_ID, data_dir=data_dir)

    reloaded = load_trip(TRIP_ID, data_dir=str(data_dir), user_id=USER_ID)
    assert reloaded.official_warnings == {
        "enabled": True,
        "sources": ["meteofrance_vigilance"],
    }, "Vorbedingung verletzt: manuelle Aktivierung wurde nicht persistiert"

    # Zweiter Lauf: das Skript baut den Trip-Objektgraph erneut (rollender
    # Cronjob) und speichert ihn wieder — der amtliche-Warnungen-Zustand
    # darf dabei NICHT zurueckgesetzt werden.
    rerun_trip = _build_rolling_trip()
    save_trip(rerun_trip, user_id=USER_ID, data_dir=data_dir)

    final = load_trip(TRIP_ID, data_dir=str(data_dir), user_id=USER_ID)
    assert final.official_warnings == {
        "enabled": True,
        "sources": ["meteofrance_vigilance"],
    }, (
        "F001: wiederholter Skript-Lauf hat official_warnings ueberschrieben, "
        f"erhalten: {final.official_warnings!r}"
    )
