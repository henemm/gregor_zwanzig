"""TDD RED: Issue #1895 Schritt 4 — toten Code rund um alert_rules entfernen.

Spec: docs/specs/modules/feat_1895_s4_alert_rules_rueckbau.md (AC-3, AC-4)

RED-Grund: `expand_preset` existiert noch (kein produktiver Aufrufer, ADR-0043),
der Import gelingt daher noch. Nach der Löschung wirft er ImportError.

Die übrigen Tests sichern den produktiven Ersatz `expand_per_metric_levels`
ab — sie sind schon grün und bleiben es (Regressionswächter für die
Zusicherung „keine HUMIDITY-Regel", die bisher an expand_preset hing).
Echte Funktionen, keine Mocks.
"""
from __future__ import annotations

import importlib

import pytest

from app.models import AlertMetric


def test_ac4_expand_preset_ist_nicht_mehr_importierbar():
    """AC-4: GIVEN der tote Code ist entfernt
    WHEN `from services.alert_preset import expand_preset` läuft
    THEN wirft der Import ImportError."""
    with pytest.raises(ImportError):
        from services.alert_preset import expand_preset  # noqa: F401


def test_ac4_expand_per_metric_levels_bleibt_importierbar():
    """AC-4: der produktive Nachbar bleibt erhalten."""
    mod = importlib.import_module("services.alert_preset")
    assert callable(getattr(mod, "expand_per_metric_levels", None))


@pytest.mark.parametrize("level", ["entspannt", "standard", "sensibel"])
def test_ac3_feuchte_stufe_erzeugt_keine_humidity_regel(level):
    """AC-3 (#889/ADR-0010): GIVEN eine Feuchte-Metrik mit Stufe
    WHEN die Stufen über expand_per_metric_levels expandiert werden
    THEN entsteht keine HUMIDITY-Regel."""
    from services.alert_preset import expand_per_metric_levels

    rules = expand_per_metric_levels({"humidity": level, "wind_gust": level})
    assert all(r.metric != AlertMetric.HUMIDITY for r in rules), (
        f"Stufe '{level}' erzeugt eine HUMIDITY-Regel"
    )
    # Gegenprobe: die Expansion arbeitet überhaupt (sonst wäre der Test leer-grün).
    assert any(r.metric == AlertMetric.WIND_GUST for r in rules)


def test_ac3_off_stufe_erzeugt_keine_regel():
    """AC-3 (#846, vormals Preset 'deaktiviert'): Stufe 'off' → keine Regel."""
    from services.alert_preset import expand_per_metric_levels

    assert expand_per_metric_levels({"wind_gust": "off", "cape": "off"}) == []
