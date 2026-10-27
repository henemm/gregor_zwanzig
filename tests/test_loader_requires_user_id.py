"""Kern-Schicht: ``save_trip``/``get_snapshots_dir`` verlangen ``user_id`` als
Pflichtargument statt still auf ``"default"`` zurueckzufallen; ``load_trip``
bleibt auf dem Dict-/Datei-Pfad ohne ``user_id`` funktionsfaehig (Legacy-CLI),
scheitert aber fail-closed, sobald es ueber ``data_dir`` eine Nutzerkennung
fuer den Dateipfad braucht (#2151 Scheibe C).

Spec: docs/specs/modules/fix_2151_default_fallbacks_scheibe_c.md (Test 4/5/6,
AC-3, AC-4)

Heute (RED):
  * ``save_trip(trip)`` ohne ``user_id`` schreibt heute klaglos unter
    ``users/default/`` -- kein ``TypeError``.
  * ``get_snapshots_dir()`` ohne ``user_id`` liefert heute klaglos den Pfad
    fuer ``users/default/`` -- kein ``TypeError``.
  * ``load_trip(trip_id, data_dir=...)`` ohne ``user_id`` liest heute still
    ``users/default/briefings/<id>.json`` statt fail-closed mit
    ``ValueError`` zu scheitern (Nachweis: eine Falle unter ``users/default``
    platziert, deren Inhalt sonst zurueckkaeme).

Nachweisform (kein Mock-Theater): echtes, isoliertes Dateisystem (die
autouse-Fixture ``tests/conftest.py::_isolate_data_root`` leitet
``app.loader._DATA_ROOT`` je Testfunktion auf eine Wegwerf-Wurzel um), echte
``Trip``/``Stage``/``Waypoint``-Objekte, Zusicherung genau an der Stelle, an
der sie wirkt (kein Zugriff unter ``users/default/`` als Nebenwirkung).
"""
from __future__ import annotations

from datetime import date, time
from pathlib import Path

import pytest

from app.loader import get_data_dir, get_snapshots_dir, save_trip
from app.trip import Stage, TimeWindow, Trip, Waypoint

LAT, LON = 47.2692, 11.4041


def _minimaler_trip(trip_id: str = "t-leck") -> Trip:
    wps = [
        Waypoint(
            id="G1", name="Start", lat=LAT, lon=LON, elevation_m=600,
            time_window=TimeWindow(start=time(0, 0), end=time(0, 0)),
        ),
    ]
    stage = Stage(id="T1", name="Etappe", date=date.today(), start_time=time(8, 0), waypoints=wps)
    return Trip(id=trip_id, name="Leck-Trip", stages=[stage])


# ═══════════════════════════ AC-3 (Test 4) ═══════════════════════════════════


def test_ac3_save_trip_ohne_user_id_wirft_typeerror_und_schreibt_nichts_unter_default():
    """AC-3 / Test 4: ``save_trip(trip)`` ohne ``user_id`` scheitert mit
    ``TypeError``, BEVOR irgendeine Datei unter ``users/default/`` entsteht.

    RED heute: der Default ``user_id="default"`` laesst den Aufruf klaglos
    durchlaufen und schreibt ``users/default/briefings/t-leck.json``.
    """
    trip = _minimaler_trip("t-leck")

    with pytest.raises(TypeError):
        save_trip(trip)  # type: ignore[call-arg]  -- Pflichtargument fehlt absichtlich

    default_briefing = get_data_dir("default") / "briefings" / "t-leck.json"
    assert not default_briefing.exists(), (
        "AC-3: save_trip(trip) ohne user_id hat trotz (erwartetem) TypeError "
        f"eine Datei unter users/default/ hinterlassen: {default_briefing}"
    )


def test_ac3_get_snapshots_dir_ohne_user_id_wirft_typeerror():
    """AC-3 / Test 4: ``get_snapshots_dir()`` ohne ``user_id`` scheitert mit
    ``TypeError`` -- kein stiller Pfad auf ``users/default/weather_snapshots``.

    RED heute: der Default ``user_id="default"`` liefert klaglos den Pfad.
    """
    with pytest.raises(TypeError):
        get_snapshots_dir()  # type: ignore[call-arg]


# ═══════════════════════════ AC-4 (Test 5) ═══════════════════════════════════
# Regressionssicherung -- muss VOR und NACH der Aenderung gruen bleiben.


def test_ac4_load_trip_aus_dict_ohne_user_id_gelingt_unveraendert():
    """AC-4 / Test 5 (Regression): der Legacy-CLI-Pfad (Dict, kein
    ``data_dir``) laedt einen Trip auch ohne ``user_id`` weiterhin -- die
    Kennung ist auf diesem Zweig inhaltlich bedeutungslos."""
    from app.loader import load_trip

    daten = {
        "id": "t-dict", "name": "Dict-Trip",
        "stages": [{
            "id": "T1", "name": "Etappe", "date": date.today().isoformat(),
            "start_time": "08:00",
            "waypoints": [{
                "id": "G1", "name": "Start", "lat": LAT, "lon": LON,
                "elevation_m": 600,
            }],
        }],
    }

    geladen = load_trip(daten)  # type: ignore[call-arg]  -- user_id bewusst weggelassen

    assert geladen is not None and geladen.id == "t-dict", (
        "AC-4: load_trip(dict) ohne user_id muss weiterhin funktionieren "
        "(Legacy-CLI-Pfad, user_id ist auf diesem Zweig bedeutungslos)"
    )


def test_ac4_load_trip_aus_datei_ohne_user_id_gelingt_unveraendert(tmp_path: Path):
    """AC-4 / Test 5 (Regression): explizite Datei (kein ``data_dir``) laedt
    ebenfalls ohne ``user_id`` -- ``src/app/cli.py:217``-Pfad."""
    from app.loader import load_trip

    datei = tmp_path / "einzeltrip.json"
    datei.write_text(
        '{"id": "t-datei", "name": "Datei-Trip", "stages": []}',
        encoding="utf-8",
    )

    geladen = load_trip(datei)  # type: ignore[call-arg]  -- user_id bewusst weggelassen

    assert geladen is not None and geladen.id == "t-datei", (
        "AC-4: load_trip(pfad) ohne user_id muss weiterhin funktionieren "
        "(Legacy-CLI-Pfad, user_id ist auf diesem Zweig bedeutungslos)"
    )


# ═══════════════════════════ AC-4 (Test 6) ═══════════════════════════════════


def test_ac4_load_trip_mit_data_dir_ohne_user_id_wirft_valueerror_statt_default_zu_lesen(
    tmp_path: Path,
):
    """AC-4 / Test 6: ``load_trip(trip_id, data_dir=...)`` OHNE ``user_id``
    muss ``ValueError`` werfen, BEVOR irgendein Dateizugriff unter
    ``users/`` erfolgt -- insbesondere darf es NICHT still
    ``users/default/briefings/<id>.json`` lesen.

    Nachweis per Falle: unter ``users/default`` liegt ein Trip mit
    unverwechselbarem Namen. Kaeme dieser Name zurueck, haette die Funktion
    still auf 'default' zurueckgegriffen statt fail-closed zu scheitern.

    RED heute: der Default ``user_id="default"`` liest klaglos genau diese
    Falle und liefert den Trip zurueck statt eines ``ValueError``.
    """
    from app.loader import load_trip

    falle = tmp_path / "users" / "default" / "briefings"
    falle.mkdir(parents=True)
    (falle / "t-geheim.json").write_text(
        '{"id": "t-geheim", "name": "Geheim-Trip-Fuer-Default", "stages": []}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        load_trip("t-geheim", data_dir=str(tmp_path))  # type: ignore[call-arg]
