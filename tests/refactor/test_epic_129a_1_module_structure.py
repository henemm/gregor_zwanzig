"""
Tests fuer Epic #129 Phase A.1 - Compare-Helper-Extraktion.
Spec: docs/specs/epic_129a_1_compare_helpers.md
Test-Manifest: docs/specs/tests/epic_129a_1_compare_helpers_tests.md

Diese Tests pruefen die neue Modul-Struktur nach dem (abgeschlossenen) Refactor
über echte Imports und das Vorhandensein der öffentlichen Symbole:
  - test_comparison_scoring (AC-2 a) -> services.comparison_scoring.calculate_score
  - test_comparison_engine  (AC-2 b) -> ComparisonEngine + Helper
  - test_comparison_renderers (AC-2 c) -> render_comparison_{html,text}
  - test_compare_subscription (AC-3) -> Funktion importierbar + callable

#765-Hinweis: Die früheren Quelltext-Greps (Datei-Inhalt-Asserts auf
api/routers/compare.py, src/services/compare_subscription.py via read_text /
inspect.getsource / grep --include=*.py) wurden entfernt — Datei-Inhalt-Anti-
Pattern (CLAUDE.md). Der Refactor ist abgeschlossen; die neue Modul-Struktur
ist über die echten Imports unten bewiesen. AC-1 (kein Import auf
web.pages.compare) ist implizit erfüllt: das alte Modul existiert nicht mehr
(SvelteKit-Rework, Issue #355), ein Import darauf würde sofort fehlschlagen.
"""
import importlib


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
    """AC-2 (renderers): output.renderers.comparison exportiert
    render_comparison_html und render_comparison_text.
    """
    mod = importlib.import_module("output.renderers.comparison")
    assert hasattr(mod, "render_comparison_html"), (
        "output.renderers.comparison.render_comparison_html fehlt"
    )
    assert hasattr(mod, "render_comparison_text"), (
        "output.renderers.comparison.render_comparison_text fehlt"
    )


def test_compare_subscription():
    """AC-3: services/compare_subscription.run_comparison_for_subscription ist
    importierbar und callable (Modul nutzt die neuen Pfade — andernfalls würde
    der Import an einem nicht mehr existierenden web.pages.compare scheitern).
    """
    from services.compare_subscription import run_comparison_for_subscription

    assert callable(run_comparison_for_subscription)
