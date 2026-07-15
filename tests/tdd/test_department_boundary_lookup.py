"""TDD — Département-Grenzen für lookup_department (Issue #1254).

SPEC: docs/specs/modules/issue_1254_department_boundaries.md
AC-1 bis AC-7.

KEINE Mocks für das Kernverhalten (CLAUDE.md-Projektkonvention): alle Tests
rufen die echte `lookup_department(lat, lon)` gegen die (zukuenftig)
gebuendelte `department_polygons.json` auf. Heute (vor dem Fix) loest die
Funktion ausschliesslich per Naechster-Nachbar-Zentroid auf — Draguignan und
Fréjus werden deshalb falsch dem entfernten Nachbar-Département zugeordnet
(RED-Beweis fuer AC-1/AC-2, im Subset von AC-3).
"""
from __future__ import annotations

import logging

import pytest

from services.official_alerts import department_mapper
from services.official_alerts.department_mapper import lookup_department


def test_draguignan_maps_to_var_83():
    """AC-1: Draguignan liegt real im Département Var (83), nicht in 04
    (Alpes-de-Haute-Provence), obwohl dessen Praefektur-Zentroid (Digne)
    naeher liegt als die Praefektur von 83 (Toulon)."""
    assert lookup_department(43.5402, 6.4665) == "83"


def test_frejus_maps_to_var_83():
    """AC-2: Fréjus liegt real im Département Var (83), nicht in 06
    (Alpes-Maritimes), obwohl dessen Praefektur-Zentroid (Nice) naeher liegt
    als die Praefektur von 83 (Toulon)."""
    assert lookup_department(43.4332, 6.7370) == "83"


@pytest.mark.parametrize(
    "lat,lon,expected",
    [
        (43.5402, 6.4665, "83"),  # Draguignan
        (43.4332, 6.7370, "83"),  # Fréjus
        (43.4055, 6.0619, "83"),  # Brignoles
        (43.1258, 5.9304, "83"),  # Toulon
        (43.8339, 5.7870, "04"),  # Manosque
        (43.8470, 6.5127, "04"),  # Castellane
        (44.3866, 6.6521, "04"),  # Barcelonnette
        (43.7765, 7.5027, "06"),  # Menton
    ],
)
def test_border_towns_resolve_to_true_department(lat, lon, expected):
    """AC-3: eine Referenzliste echter Grenzorte muss jeweils im
    tatsaechlichen Département ihrer realen Lage landen, nicht im Département
    des naechstgelegenen Praefektur-Zentroids."""
    assert lookup_department(lat, lon) == expected


def test_corsica_contract_preserved():
    """AC-4 (Regressionsschutz, kein RED-Beweis noetig): Korsika bleibt als
    zwei normale Codes "2A"/"2B" aufgeloest, kein Sonderfall-Zweig."""
    assert lookup_department(41.9192, 8.7386) == "2A"  # Ajaccio
    assert lookup_department(42.6979, 9.4508) == "2B"  # Bastia


def test_point_outside_all_polygons_falls_back_to_plausible_code():
    """AC-5: eine Koordinate innerhalb der Frankreich-Bounding-Box, die in
    keinem (vereinfachten) Département-Polygon liegt (hier: ein Punkt im
    Mittelmeer nahe der Provence-Kueste, vor Toulon), muss ueber den
    Nearest-Centroid-Fallback einen plausiblen, nicht-leeren Département-Code
    liefern — kein None, keine Exception."""
    result = lookup_department(43.00, 6.30)
    assert result is not None
    assert isinstance(result, str)
    assert result in department_mapper.DEPARTMENT_CENTROIDS


def test_missing_polygon_file_falls_back_failsoft(tmp_path, caplog):
    """AC-6: fehlende/kaputte Polygondatei darf den Import von
    `services.official_alerts` NICHT reissen und `lookup_department` muss
    fail-soft auf die bestehende Nearest-Centroid-Logik zurueckfallen, dabei
    eine Warnung loggen.

    Erwartetes Ziel-Interface (analog `massif_zones._load_massifs` /
    `massif_zones._DATA_PATH`, Issue #1037-Muster), das die Implementierung
    in `department_mapper.py` bereitstellen MUSS:

    - Modul-Attribut `_DATA_PATH: Path` — Standardpfad der gebuendelten
      `department_polygons.json`.
    - Funktion `_load_department_polygons(path: Path = _DATA_PATH) -> list`
      — laedt die Polygondaten, faengt fehlende/kaputte Dateien fail-soft ab
      (loggt `logger.warning(...)`, liefert `[]`, wirft NIE eine Exception).

    Solange dieses Interface in `department_mapper.py` noch nicht existiert,
    ist dieser Test RED (AttributeError) — das ist im TDD-RED-Schritt
    ausdruecklich erwuenscht (Zielverhalten, nicht Ist-Zustand).
    """
    missing = tmp_path / "nonexistent_department_polygons.json"
    with caplog.at_level(logging.WARNING):
        result = department_mapper._load_department_polygons(missing)
    assert result == [], "fehlende Datei muss [] liefern, kein Crash"
    assert any(r.levelno >= logging.WARNING for r in caplog.records), (
        "fehlende Datei muss eine Warnung loggen"
    )

    broken = tmp_path / "broken_department_polygons.json"
    broken.write_text("{ das ist kein json ]")
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        result_broken = department_mapper._load_department_polygons(broken)
    assert result_broken == [], "kaputte Datei muss [] liefern, kein Crash"

    # Import bleibt intakt + fail-soft Fallback: bereits heute korrekt
    # aufgeloeste Orte (Nearest-Centroid) bleiben unveraendert korrekt.
    assert lookup_department(43.1258, 5.9304) == "83"  # Toulon


def test_previously_correct_towns_no_regression():
    """AC-7: bereits vorher korrekt aufgeloeste Orte bleiben nach dem Fix
    unveraendert korrekt (keine Regression)."""
    assert lookup_department(43.1258, 5.9304) == "83"  # Toulon
    assert lookup_department(43.8339, 5.7870) == "04"  # Manosque
    assert lookup_department(43.7765, 7.5027) == "06"  # Menton
    assert lookup_department(43.4055, 6.0619) == "83"  # Brignoles


@pytest.mark.parametrize(
    "lat,lon",
    [
        (44.3796, 4.9895),  # Valréas
        (44.3311, 4.9291),  # Visan
        (44.3626, 4.9455),  # Grillon
    ],
)
def test_enclave_des_papes_maps_to_vaucluse_84(lat, lon):
    """AC-8: die Enclave des Papes (Valréas/Visan/Grillon) ist eine Exklave
    des Départements Vaucluse (84), vollstaendig vom Département Drôme (26)
    umschlossen. Ohne Loch-Behandlung im 26-Polygon liefert die einfache
    Exterior-Ring-Pruefung faelschlich "26", weil das 26-Aussenpolygon die
    Enklave mit-abdeckt."""
    assert lookup_department(lat, lon) == "84"
