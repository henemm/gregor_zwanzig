"""
Tests fuer Epic #129 Phase A.2 - GPX-Helper + Coordinates-Extraktion.
Spec: docs/specs/epic_129a_2_gpx_helpers.md
Test-Manifest: docs/specs/tests/epic_129a_2_gpx_helpers_tests.md

Diese Tests pruefen die neue Modul-Struktur nach dem (abgeschlossenen) Refactor
über echte Imports, das Vorhandensein der Helper-Funktionen und einen stabilen
API-Contract:
  - test_gpx_processing_module (AC-2 b) -> 6 Funktionen in services.gpx_processing
  - test_gpx_to_stage_data_signature (AC-3) -> API-Contract stabil
  - test_web_utils_file_removed (AC-5 b) -> src/web/utils.py existiert nicht mehr

#765-Hinweis: Die früheren Quelltext-Greps (Datei-Inhalt-Asserts auf
api/routers/gpx.py via read_text und grep --include=*.py für tote Funktionen)
wurden entfernt — Datei-Inhalt-Anti-Pattern (CLAUDE.md). Die neue Struktur ist
über echte Imports/Signaturen bewiesen; AC-1/AC-5(dead-fn) sind implizit erfüllt:
die alten web.pages-Module existieren nicht mehr (SvelteKit-Rework, Issue #355).
"""
import importlib
import inspect
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


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
      content, filename, stage_date, start_hour, upload_dir

    api/routers/gpx.py importiert diese Funktion fuer Production-Endpoint
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

    assert len(params) == len(expected_params), (
        f"Parameter-Anzahl von gpx_to_stage_data hat sich geaendert. "
        f"Erwartet: {expected_params}, Tatsaechlich: {params}"
    )


def test_web_utils_file_removed():
    """AC-5 (utils-file): src/web/utils.py existiert nicht mehr.

    Reine Existenz-Prüfung (kein Quelltext-Read): die NiceGUI-web/-Schicht wurde
    im SvelteKit-Rework (Issue #355) vollständig entfernt.
    """
    utils_path = REPO / "src" / "web" / "utils.py"
    assert not utils_path.exists(), (
        f"src/web/utils.py existiert noch ({utils_path}) — sollte mit der "
        f"NiceGUI-web/-Schicht entfernt sein"
    )
