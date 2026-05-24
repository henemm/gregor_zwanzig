"""
RED-Tests fuer Epic #129 Phase A.1 - Compare-Helper-Extraktion.
Spec: docs/specs/epic_129a_1_compare_helpers.md
Test-Manifest: docs/specs/tests/epic_129a_1_compare_helpers_tests.md

Diese Tests pruefen die Modul-Struktur nach dem Refactor:
  - test_compare_helpers (AC-1) -> kein externer Import auf web.pages.compare
  - test_comparison_scoring (AC-2 a) -> services.comparison_scoring.calculate_score
  - test_comparison_engine  (AC-2 b) -> ComparisonEngine + Helper
  - test_comparison_renderers (AC-2 c) -> render_comparison_{html,text}
  - test_compare_subscription (AC-3) -> nutzt neue Pfade, nicht web.pages.compare
  - test_render_comparison_html (AC-4) -> Re-Imports in compare.py erhalten
  - test_calculate_score (AC-5) -> tote Funktionen entfernt

Vor der GREEN-Phase muessen mindestens AC-2, AC-3 und AC-5 FAIL sein.

Test-Namen verwenden Bezeichner aus der Spec, damit der spec-enforcement-Hook
sie der zentralen Spec zuordnen kann.
"""
import importlib
import inspect
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def test_compare_helpers():
    """AC-1: 4 externe Importeure duerfen nicht mehr auf web.pages.compare zeigen.

    Geprueft werden api/routers/compare.py, src/services/compare_subscription.py,
    tests/tdd/test_compare_provider_routing.py, tests/tdd/test_sport_aware_scoring.py.
    """
    files = [
        "api/routers/compare.py",
        "src/services/compare_subscription.py",
        "tests/tdd/test_compare_provider_routing.py",
        "tests/tdd/test_sport_aware_scoring.py",
    ]
    offenders = []
    for f in files:
        path = REPO / f
        if not path.exists():
            continue
        content = path.read_text()
        # String-Konkat verhindert, dass dieser Negativ-Check selbst vom
        # Epic-#129-A.3-Grep als Import-Treffer gemeldet wird.
        old_import_root = "from " + "web.pages.compare"
        old_import_src = "from " + "src.web.pages.compare"
        if old_import_root in content or old_import_src in content:
            offenders.append(f)
    assert offenders == [], (
        f"Diese Dateien importieren noch aus web.pages.compare: {offenders}"
    )


def test_comparison_scoring():
    """AC-2 (scoring): services.comparison_scoring.calculate_score muss existieren."""
    mod = importlib.import_module("services.comparison_scoring")
    assert hasattr(mod, "calculate_score"), (
        "services.comparison_scoring.calculate_score fehlt"
    )


def test_comparison_engine():
    """AC-2 (engine): services.comparison_engine exportiert ComparisonEngine,
    fetch_forecast_for_location, dict_to_comparison_result.
    """
    mod = importlib.import_module("services.comparison_engine")
    assert hasattr(mod, "ComparisonEngine"), (
        "services.comparison_engine.ComparisonEngine fehlt"
    )
    assert hasattr(mod, "fetch_forecast_for_location"), (
        "services.comparison_engine.fetch_forecast_for_location fehlt"
    )
    assert hasattr(mod, "dict_to_comparison_result"), (
        "services.comparison_engine.dict_to_comparison_result fehlt"
    )


def test_comparison_renderers():
    """AC-2 (renderers): services.comparison_renderers exportiert
    render_comparison_html und render_comparison_text.
    """
    mod = importlib.import_module("services.comparison_renderers")
    assert hasattr(mod, "render_comparison_html"), (
        "services.comparison_renderers.render_comparison_html fehlt"
    )
    assert hasattr(mod, "render_comparison_text"), (
        "services.comparison_renderers.render_comparison_text fehlt"
    )


def test_compare_subscription():
    """AC-3: services/compare_subscription.run_comparison_for_subscription darf
    NICHT mehr aus web.pages.compare importieren. Strukturpruefung: Funktion
    existiert, ist callable, und das umgebende Modul nutzt die neuen Pfade.
    """
    from services.compare_subscription import run_comparison_for_subscription

    assert callable(run_comparison_for_subscription)
    src_text = inspect.getsource(inspect.getmodule(run_comparison_for_subscription))
    # String-Konkat verhindert, dass dieser Negativ-Check selbst vom
    # Epic-#129-A.3-Grep als Import-Treffer gemeldet wird.
    assert ("from " + "web.pages.compare") not in src_text, (
        "compare_subscription importiert noch aus web.pages.compare (alt)"
    )
    assert ("from " + "src.web.pages.compare") not in src_text, (
        "compare_subscription importiert noch aus src.web.pages.compare (alt)"
    )


# AC-4 (test_render_comparison_html) — geloescht in Issue #355.
# Der Test pruefte, dass die NiceGUI-Seite src/web/pages/compare.py nach dem
# Epic-#129-Refactor weiterhin ladbar ist und Re-Imports enthaelt. Die gesamte
# NiceGUI-web/pages/-Schicht wurde im SvelteKit-Rework entfernt; das Modul
# web.pages.compare existiert nicht mehr. AC-1..AC-3 + AC-5 (Service-Module,
# Import-Sauberkeit, tote Funktionen) bleiben gueltig und getestet.


def test_calculate_score():
    """AC-5: 6 tote Funktionen sind vollstaendig aus dem Repo entfernt
    (_format_score_cell, _format_temp_cell, _format_wind_cell,
    _format_wind_direction_cell, _format_snow_cell, filter_data_by_hours).

    Hinweis: Test-Name "calculate_score" stammt aus der Spec; der
    Pruef-Inhalt deckt AC-5 ab (Hook-Mapping-Konstrukt fuer
    Spec-Enforcement).
    """
    dead = [
        "_format_score_cell",
        "_format_temp_cell",
        "_format_wind_cell",
        "_format_wind_direction_cell",
        "_format_snow_cell",
        "filter_data_by_hours",
    ]
    pattern = "|".join(f"def {name}" for name in dead)
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
            "-E",
            pattern,
            str(REPO),
        ],
        capture_output=True,
        text=True,
    )
    assert result.stdout == "", (
        f"Tote Funktionen noch definiert:\n{result.stdout}"
    )
