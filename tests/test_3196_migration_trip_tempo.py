"""TDD RED: Issue #3196 -- Migration ``scripts/migrate_3196_trip_tempo.py`` (AC-10).

Spec: docs/specs/modules/feat_3196_trip_tempo_etappen.md, Abschnitt Backend.
Muster: ``scripts/migrate_2794_preset_horizons.py`` (planen, sichern,
``--execute``; Usage ``--root <data/users> [--backup-dir <p>] [--execute]``).

Gegen eine Kopie der voll besetzten Trip-Fixture (``trip_schema_full.json``)
mit verschiedenen Altwerten in ``activity``:

- Trockenlauf schreibt nichts.
- ``--execute`` setzt ``tempo`` (abgeleitet aus ``activity``) per
  Read-Modify-Write; ``activity`` und alle uebrigen Felder bleiben
  unveraendert (Vorher/Nachher-Vergleich aller Felder ausser ``tempo``).
- Ein schon gesetztes ``tempo`` wird nie ueberschrieben.
- Orts-Vergleiche (``kind = vergleich``) bekommen kein ``tempo``.
- Zweiter Lauf aendert nichts (idempotent).
- Vor dem Schreiben liegt eine Sicherung im Backup-Ordner.

Kern-Schicht, ohne Netz, ohne Mocks.
"""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent
_SKRIPT = _HERE.parent / "scripts" / "migrate_3196_trip_tempo.py"
_FULL = json.loads((_HERE / "fixtures" / "trip_schema_full.json").read_text(encoding="utf-8"))


def _modul():
    spec = importlib.util.spec_from_file_location("migrate_3196_trip_tempo", _SKRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _trip(id_: str, activity: str | None, tempo: dict | None = None) -> dict:
    d = copy.deepcopy(_FULL)
    d.pop("tempo", None)
    d["id"] = id_
    d["kind"] = "route"
    if activity is None:
        d.pop("activity", None)
    else:
        d["activity"] = activity
    if tempo is not None:
        d["tempo"] = tempo
    return d


def _bestand(root: Path) -> dict[Path, dict]:
    dateien = {
        root / "u1" / "briefings" / "rad20.json": _trip("rad20", "fahrrad_20"),
        root / "u1" / "briefings" / "hochtour.json": _trip("hochtour", "hochtour"),
        root / "u1" / "briefings" / "leer.json": _trip("leer", None),
        root / "u2" / "briefings" / "rad15.json": _trip("rad15", "fahrrad_15"),
        root / "u2" / "briefings" / "schon.json": _trip(
            "schon", "fahrrad_20", tempo={"fortbewegung": "mtb", "grundtempo_kmh": 11}),
        root / "u2" / "briefings" / "vergleich.json": {
            "id": "vergleich", "name": "Orte", "kind": "vergleich", "locations": ["a", "b"]},
    }
    for pfad, inhalt in dateien.items():
        pfad.parent.mkdir(parents=True, exist_ok=True)
        pfad.write_text(json.dumps(inhalt, ensure_ascii=False, indent=2), encoding="utf-8")
    return dateien


def _ohne_tempo_und_ankunft(d: dict) -> dict:
    """AC-10: Vergleich aller Felder ausser ``tempo`` und ``arrival_calculated``
    (die Gehzeiten aendern sich mit dem DAV-Modell bewusst, PO 2026-11-20)."""
    d = copy.deepcopy(d)
    d.pop("tempo", None)
    for st in d.get("stages") or []:
        for wp in st.get("waypoints") or []:
            wp.pop("arrival_calculated", None)
    return d


def _lies(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def test_trockenlauf_schreibt_nichts(tmp_path):
    root = tmp_path / "users"
    dateien = _bestand(root)
    vorher = {p: p.read_bytes() for p in dateien}
    rc = _modul().main(["--root", str(root), "--backup-dir", str(tmp_path / "bak")])
    assert rc == 0
    for p, inhalt in vorher.items():
        assert p.read_bytes() == inhalt, f"Trockenlauf hat {p.name} veraendert"
    assert not (tmp_path / "bak").exists() or not any((tmp_path / "bak").iterdir())


def test_execute_setzt_tempo_und_laesst_alles_andere(tmp_path):
    root = tmp_path / "users"
    dateien = _bestand(root)
    rc = _modul().main(["--root", str(root), "--backup-dir", str(tmp_path / "bak"), "--execute"])
    assert rc == 0

    erwartet = {
        "rad20.json": {"fortbewegung": "rad", "grundtempo_kmh": 20},
        "hochtour.json": {"fortbewegung": "fuss", "grundtempo_kmh": 4},
        "leer.json": {"fortbewegung": "fuss", "grundtempo_kmh": 4},
        "rad15.json": {"fortbewegung": "rad", "grundtempo_kmh": 15},
        "schon.json": {"fortbewegung": "mtb", "grundtempo_kmh": 11},
    }
    for pfad, vorher in dateien.items():
        nachher = _lies(pfad)
        if pfad.name == "vergleich.json":
            assert nachher == vorher, "Orts-Vergleich darf nicht angefasst werden"
            continue
        assert nachher.get("tempo") == erwartet[pfad.name], pfad.name
        assert _ohne_tempo_und_ankunft(nachher) == _ohne_tempo_und_ankunft(vorher), \
            f"{pfad.name}: andere Felder veraendert"

    sicherungen = list((tmp_path / "bak").iterdir())
    assert sicherungen, "keine Sicherung vor dem Schreiben"


def test_zweiter_lauf_aendert_nichts(tmp_path):
    root = tmp_path / "users"
    dateien = _bestand(root)
    mod = _modul()
    assert mod.main(["--root", str(root), "--backup-dir", str(tmp_path / "bak"), "--execute"]) == 0
    nach_erstem = {p: p.read_bytes() for p in dateien}
    assert mod.main(["--root", str(root), "--backup-dir", str(tmp_path / "bak2"), "--execute"]) == 0
    for p, inhalt in nach_erstem.items():
        assert p.read_bytes() == inhalt, f"zweiter Lauf hat {p.name} veraendert"


def _mit_alter_ankunft(id_: str, activity: str) -> dict:
    """Etappe 8 km / 600 Hm auf / 600 Hm ab mit Ankunftszeiten nach dem ALTEN
    Summenmodell (zu Fuss 5:12 statt 4:12 nach DAV)."""
    d = _trip(id_, activity)
    d["stages"] = [{
        "id": "S1", "name": "Tag 1", "date": "2026-07-01", "start_time": "08:00",
        "waypoints": [
            {"id": "A", "name": "A", "lat": 47.0, "lon": 11.0, "elevation_m": 1000,
             "distance_from_start_km": 0.0, "arrival_calculated": "08:00"},
            {"id": "B", "name": "B", "lat": 47.0, "lon": 11.0, "elevation_m": 1600,
             "distance_from_start_km": 4.0, "arrival_calculated": "11:00"},
            {"id": "C", "name": "C", "lat": 47.0, "lon": 11.0, "elevation_m": 1000,
             "distance_from_start_km": 8.0, "arrival_calculated": "13:12"},
        ],
    }]
    return d


@pytest.mark.parametrize("activity,erwartet", [
    ("hochtour", ["08:00", "10:30", "12:12"]),    # zu Fuss 4 km/h nach DAV
    ("fahrrad_20", ["08:00", "09:06", "09:48"]),  # Rad 20 km/h nach DAV
])
def test_execute_rechnet_ankuenfte_nach_dav(tmp_path, activity, erwartet):
    """F-A2-3 (AC-10): nach --execute folgen die gespeicherten Ankunftszeiten der
    DAV-Rechnung mit dem migrierten Tempo; alle uebrigen Felder bleiben gleich."""
    root = tmp_path / "users"
    pfad = root / "u1" / "briefings" / "alt.json"
    pfad.parent.mkdir(parents=True)
    vorher = _mit_alter_ankunft("alt", activity)
    pfad.write_text(json.dumps(vorher, ensure_ascii=False, indent=2), encoding="utf-8")
    assert _modul().main(["--root", str(root), "--backup-dir", str(tmp_path / "bak"), "--execute"]) == 0
    nachher = _lies(pfad)
    assert [wp["arrival_calculated"] for wp in nachher["stages"][0]["waypoints"]] == erwartet
    assert _ohne_tempo_und_ankunft(nachher) == _ohne_tempo_und_ankunft(vorher)
