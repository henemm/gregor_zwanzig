"""
RED-Tests fuer Epic #129 Phase A.2 - GPX-Helper + Coordinates-Extraktion.
Spec: docs/specs/epic_129a_2_gpx_helpers.md
Test-Manifest: docs/specs/tests/epic_129a_2_gpx_helpers_tests.md

Diese Tests pruefen die Modul-Struktur nach dem Refactor:
  - test_gpx_helpers_externals_clean (AC-1) -> kein externer Import auf web.pages.{trips,gpx_upload} / web.utils
  - test_coordinates_module (AC-2 a) -> services.coordinates.parse_dms_coordinates
  - test_gpx_processing_module (AC-2 b) -> 6 Funktionen in services.gpx_processing
  - test_gpx_to_stage_data_signature (AC-3) -> API-Contract stabil
  - test_pages_loadable (AC-4) -> Re-Imports in gpx_upload.py + trips.py erhalten
  - test_dead_format_decimal_to_dms_removed (AC-5 a) -> tote Funktion entfernt
  - test_web_utils_file_removed (AC-5 b) -> src/web/utils.py geloescht oder leer

Vor der GREEN-Phase muessen mindestens AC-2, AC-3 und AC-5 FAIL sein.

Test-Namen verwenden Bezeichner aus der Spec, damit der spec-enforcement-Hook
sie der zentralen Spec zuordnen kann.
"""
import importlib
import inspect
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def test_gpx_helpers_externals_clean():
    """AC-1: 5 externe Importeure duerfen nicht mehr auf web.pages.{trips,gpx_upload}
    oder web.utils zeigen.

    Geprueft werden api/routers/gpx.py und 4 Test-Files.
    """
    files = [
        "api/routers/gpx.py",
        "tests/unit/test_gpx_upload_page.py",
        "tests/unit/test_gpx_import_in_trip_dialog.py",
        "tests/unit/test_etappen_config.py",
        "tests/unit/test_trips_time_window_bugfix.py",
    ]
    forbidden_patterns = [
        "from web.pages.gpx_upload",
        "from web.pages.trips",
        "from web.utils",
        "from src.web.pages.gpx_upload",
        "from src.web.pages.trips",
        "from src.web.utils",
    ]
    offenders = []
    for f in files:
        path = REPO / f
        if not path.exists():
            continue
        content = path.read_text()
        for pattern in forbidden_patterns:
            if pattern in content:
                offenders.append(f"{f}: '{pattern}'")
    assert offenders == [], (
        "Diese Dateien importieren noch aus web.pages.{trips,gpx_upload} "
        f"oder web.utils:\n  - " + "\n  - ".join(offenders)
    )


def test_coordinates_module():
    """AC-2 (coordinates): services.coordinates.parse_dms_coordinates muss existieren."""
    mod = importlib.import_module("services.coordinates")
    assert hasattr(mod, "parse_dms_coordinates"), (
        "services.coordinates.parse_dms_coordinates fehlt"
    )


def test_gpx_processing_module():
    """AC-2 (gpx_processing): services.gpx_processing exportiert alle 6 Helper-Funktionen."""
    mod = importlib.import_module("services.gpx_processing")
    expected = [
        "process_gpx_upload",
        "compute_full_segmentation",
        "segments_to_trip",
        "gpx_to_stage_data",
        "process_bulk_gpx_uploads",
        "compute_default_start_date",
    ]
    missing = [name for name in expected if not hasattr(mod, name)]
    assert missing == [], (
        f"services.gpx_processing exportiert nicht alle erwarteten Funktionen. "
        f"Fehlend: {missing}"
    )


def test_gpx_to_stage_data_signature():
    """AC-3: API-Contract von gpx_to_stage_data bleibt stabil.

    Signatur-Parameter (aus src/web/pages/trips.py vor dem Refactor):
      content: bytes
      filename: str
      stage_date: Optional[date] = None
      start_hour: int = 8
      upload_dir: Path = _GPX_UPLOAD_DIR

    api/routers/gpx.py:16 importiert diese Funktion fuer Production-Endpoint
    POST /api/gpx/parse — Signatur DARF sich nicht aendern.
    """
    from services.gpx_processing import gpx_to_stage_data

    sig = inspect.signature(gpx_to_stage_data)
    params = list(sig.parameters.keys())

    expected_params = ["content", "filename", "stage_date", "start_hour", "upload_dir"]
    for p in expected_params:
        assert p in params, (
            f"Parameter '{p}' fehlt in gpx_to_stage_data — API-Contract verletzt. "
            f"Aktuelle Signatur: {params}"
        )

    # Anzahl der Parameter muss exakt stimmen (kein zusaetzlicher, kein fehlender)
    assert len(params) == len(expected_params), (
        f"Parameter-Anzahl von gpx_to_stage_data hat sich geaendert. "
        f"Erwartet: {expected_params}, Tatsaechlich: {params}"
    )


def test_pages_loadable():
    """AC-4: src/web/pages/{gpx_upload,trips}.py laden weiterhin ohne ImportError
    und enthalten Re-Imports auf die neuen Service-Module.
    """
    try:
        import nicegui  # noqa: F401
    except ImportError:
        pytest.skip("nicegui nicht installiert - kann pages nicht testen")

    # gpx_upload.py
    mod_upload = importlib.import_module("web.pages.gpx_upload")
    assert hasattr(mod_upload, "render_gpx_upload"), (
        "web.pages.gpx_upload.render_gpx_upload verschwand faelschlich"
    )
    # Re-Imports muessen vorhanden sein, damit UI-Funktionen weiterhin laufen
    for name in ("process_gpx_upload", "compute_full_segmentation", "segments_to_trip"):
        assert hasattr(mod_upload, name), (
            f"Re-Import {name} fehlt in web.pages.gpx_upload"
        )

    # trips.py
    mod_trips = importlib.import_module("web.pages.trips")
    assert hasattr(mod_trips, "render_trips"), (
        "web.pages.trips.render_trips verschwand faelschlich"
    )
    for name in (
        "gpx_to_stage_data",
        "process_bulk_gpx_uploads",
        "compute_default_start_date",
        "parse_dms_coordinates",
    ):
        assert hasattr(mod_trips, name), (
            f"Re-Import {name} fehlt in web.pages.trips"
        )


def test_dead_format_decimal_to_dms_removed():
    """AC-5 (dead-fn): Tote Funktion `format_decimal_to_dms` ist im Produktiv-
    Code (src/, api/) nicht mehr definiert.

    Pattern enthaelt literales `(`, damit die grep-Regel sich nicht selbst
    matcht. Tests-Verzeichnis ist ausgeschlossen, weil dieser Test selbst
    den Bezeichner als Doku-Konstante enthaelt.
    """
    result = subprocess.run(
        [
            "grep",
            "-rn",
            "--include=*.py",
            "--exclude-dir=.git",
            "--exclude-dir=.claude",
            "--exclude-dir=node_modules",
            "--exclude-dir=htmlcov",
            "--exclude-dir=.venv",
            "--exclude-dir=tests",
            "-E",
            r"def format_decimal_to_dms\(",
            str(REPO),
        ],
        capture_output=True,
        text=True,
    )
    assert result.stdout == "", (
        f"Tote Funktion format_decimal_to_dms noch definiert:\n{result.stdout}"
    )


def test_web_utils_file_removed():
    """AC-5 (utils-file): src/web/utils.py existiert nicht mehr (oder ist leer)."""
    utils_path = REPO / "src" / "web" / "utils.py"
    if not utils_path.exists():
        return  # Datei geloescht — perfekt
    # Falls die Datei noch da ist, darf sie keinen ausfuehrbaren Code mehr enthalten
    content = utils_path.read_text().strip()
    # Nur leer oder reine Doku/Kommentare/Whitespace erlaubt
    code_lines = [
        line
        for line in content.splitlines()
        if line.strip()
        and not line.strip().startswith("#")
        and not line.strip().startswith('"""')
        and not line.strip().startswith("'''")
    ]
    assert code_lines == [], (
        f"src/web/utils.py existiert noch und enthaelt Code:\n{content}"
    )
