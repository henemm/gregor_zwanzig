"""Issue #342 — Pro-Metrik-Zeithorizont-Filter im Email-Renderer.

Spec:  docs/specs/modules/issue_342_pro_metrik_horizon_backend.md
Tests-Spec: docs/specs/tests/issue_342_pro_metrik_horizon_backend_tests.md
Issue: https://github.com/henemm/gregor_zwanzig/issues/342

Tests gegen AC-1 … AC-3 (Renderer-Filter pro Etappe) und AC-7
(Backward-Compat ohne horizons-Feld) sowie ein direkter Mapping-Test fuer
derive_horizon().

KEINE Mocks (CLAUDE.md-Regel). Echte Imports + echte Dict-Strukturen.
Tests scheitern absichtlich (RED): visible_cols() hat heute die Signatur
visible_cols(rows: list[dict]) und kein horizon-Argument. derive_horizon()
existiert noch gar nicht. Bei `pytest` → TypeError / ImportError.
"""

from __future__ import annotations

from datetime import date

import pytest


# ----------------------------------------------------------------------
# AC-1: today-Filter blendet thunder aus, wind bleibt sichtbar
# ----------------------------------------------------------------------

def test_visible_cols_filters_today_metric():
    """AC-1: horizon='today' + thunder.today=False → thunder fehlt im Ergebnis."""
    from output.renderers.email.helpers import visible_cols

    dc_metrics = [
        {
            "metric_id": "thunder",
            "enabled": True,
            "horizons": {"today": False, "tomorrow": True, "day_after": True},
        },
        {
            "metric_id": "wind",
            "enabled": True,
            "horizons": {"today": True, "tomorrow": True, "day_after": True},
        },
    ]
    cols = visible_cols(dc_metrics, horizon="today")
    assert "thunder" not in cols, f"thunder sollte fuer today gefiltert sein, got {cols}"
    assert "wind" in cols, f"wind muss fuer today sichtbar bleiben, got {cols}"


# ----------------------------------------------------------------------
# AC-2: tomorrow-Filter zeigt thunder (horizons.tomorrow=True)
# ----------------------------------------------------------------------

def test_visible_cols_shows_tomorrow_metric():
    """AC-2: gleiche dc_metrics, horizon='tomorrow' → thunder ist enthalten."""
    from output.renderers.email.helpers import visible_cols

    dc_metrics = [
        {
            "metric_id": "thunder",
            "enabled": True,
            "horizons": {"today": False, "tomorrow": True, "day_after": True},
        },
        {
            "metric_id": "wind",
            "enabled": True,
            "horizons": {"today": True, "tomorrow": True, "day_after": True},
        },
    ]
    cols = visible_cols(dc_metrics, horizon="tomorrow")
    assert "thunder" in cols, f"thunder sollte fuer tomorrow sichtbar sein, got {cols}"
    assert "wind" in cols


# ----------------------------------------------------------------------
# AC-3: horizon=None (Tag 4+) → Filter ignoriert horizons-Flags
# ----------------------------------------------------------------------

def test_visible_cols_ignores_horizon_for_day4():
    """AC-3: horizon=None liefert alle enabled Metriken, auch wenn horizons.* False ist."""
    from output.renderers.email.helpers import visible_cols

    dc_metrics = [
        {
            "metric_id": "thunder",
            "enabled": True,
            "horizons": {"today": False, "tomorrow": False, "day_after": False},
        },
        {
            "metric_id": "wind",
            "enabled": True,
            "horizons": {"today": False, "tomorrow": False, "day_after": False},
        },
        {
            "metric_id": "temperature",
            "enabled": False,
            "horizons": {"today": True, "tomorrow": True, "day_after": True},
        },
    ]
    cols = visible_cols(dc_metrics, horizon=None)
    # Alle enabled Metriken erscheinen, Disabled nicht.
    assert "thunder" in cols
    assert "wind" in cols
    assert "temperature" not in cols, "disabled muss immer gefiltert sein"


# ----------------------------------------------------------------------
# AC-7: Legacy-Trip ohne horizons-Feld → Default greift
# ----------------------------------------------------------------------

def test_visible_cols_legacy_no_horizons_field():
    """AC-7: kein horizons-Schluessel → Default {True,True,True} greift."""
    from output.renderers.email.helpers import visible_cols

    dc_metrics = [
        {"metric_id": "wind", "enabled": True},  # kein horizons-Key
    ]
    cols = visible_cols(dc_metrics, horizon="today")
    assert "wind" in cols, f"Legacy ohne horizons muss alle Horizonte zeigen, got {cols}"


# ----------------------------------------------------------------------
# derive_horizon(): delta-Mapping
# ----------------------------------------------------------------------

def test_derive_horizon_mapping():
    """derive_horizon() liefert today/tomorrow/day_after fuer delta 0/1/2, None fuer >=3."""
    from output.renderers.email.helpers import derive_horizon

    base = date(2026, 5, 23)
    assert derive_horizon(base, date(2026, 5, 23)) == "today"
    assert derive_horizon(base, date(2026, 5, 24)) == "tomorrow"
    assert derive_horizon(base, date(2026, 5, 25)) == "day_after"
    assert derive_horizon(base, date(2026, 5, 26)) is None


# ----------------------------------------------------------------------
# End-to-End: render_html() filtert pro Etappe
# ----------------------------------------------------------------------

def test_render_html_filters_per_stage():
    """E2E: render_html() propagiert horizon pro Etappe.

    Deferred zur /5-implement-Phase, weil ein echtes NormalizedForecast-Fixture
    mit drei Etappen (heute/morgen/uebermorgen) gebaut werden muss. Der dafuer
    erforderliche Datenpfad wird in §5 + §6 der Spec aufgesetzt.
    """
    pytest.skip(
        "E2E: requires real NormalizedForecast fixture, deferred to /5-implement phase"
    )
