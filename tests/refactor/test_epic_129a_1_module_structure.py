"""
Tests fuer Epic #129 Phase A.1 - Compare-Helper-Extraktion.
Spec: docs/specs/epic_129a_1_compare_helpers.md
Test-Manifest: docs/specs/tests/epic_129a_1_compare_helpers_tests.md

Diese Tests pruefen die neue Modul-Struktur nach dem (abgeschlossenen) Refactor
über echte Imports und das Vorhandensein der öffentlichen Symbole:
  - test_comparison_scoring (AC-2 a) -> services.comparison_scoring.calculate_score
  - test_comparison_engine  (AC-2 b) -> ComparisonEngine + Helper
  - test_comparison_renderers (AC-2 c) -> render_comparison_{html,text}

Issue #1250 Scheibe 0: test_compare_subscription (AC-3) entfernt — Legacy-
Drittstack CompareSubscription stillgelegt (#1131).

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
    render_comparison_text.

    Issue #1110: render_comparison_html() war ein bestaetigter toter
    Alt-Renderer (Score/Winner-Vertrag, nie vom echten Versandpfad
    aufgerufen) und wurde ENTFERNT (koordiniert mit #1108) -- der echte
    HTML-Renderer lebt in output.renderers.email.compare_html.
    """
    mod = importlib.import_module("output.renderers.comparison")
    assert not hasattr(mod, "render_comparison_html"), (
        "output.renderers.comparison.render_comparison_html haette mit "
        "Issue #1110 entfernt werden muessen (toter Alt-Renderer)"
    )
    assert hasattr(mod, "render_comparison_text"), (
        "output.renderers.comparison.render_comparison_text fehlt"
    )


# Issue #1250 Scheibe 0: test_compare_subscription (AC-3) entfernt — Legacy-
# Drittstack CompareSubscription stillgelegt (#1131),
# services.compare_subscription existiert nicht mehr.
