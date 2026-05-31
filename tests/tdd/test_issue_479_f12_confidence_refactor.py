"""
TDD RED: Issue #479 — F12 WL-Block aus Konfidenz-Daten ableiten,
WL-Token aus SMS entfernen.

Parent-Spec: docs/specs/modules/issue_479_f12_confidence_refactor.md
Test-Manifest: docs/specs/tests/issue_479_f12_confidence_refactor_tests.md

Ziel (Issue #479):
- StabilityResult vereinfachen (score/component_scores raus, confidence_pct rein)
- compute_stability(values) — pure Funktion, leitet Label aus
  min(confidence_pct_min) der Folge-Etappen ab
- WL-Token aus SMS-Token-Builder/Render entfernen (E-Mail-Block bleibt)
- _fetch_ensemble_with_z500 aus OpenMeteoProvider entfernen
- WeatherPatternService ohne provider-Parameter

Diese Tests müssen im RED-Phase fehlschlagen.
"""
from __future__ import annotations


# ---------------------------------------------------------------------------
# AC-1: StabilityResult hat kein score-/component_scores-Feld mehr
# ---------------------------------------------------------------------------

def test_stability_result_has_no_score_field():
    from app.models import StabilityResult
    import dataclasses
    fields = {f.name for f in dataclasses.fields(StabilityResult)}
    assert "score" not in fields, (
        f"StabilityResult.score muss entfernt werden, vorhanden: {fields}"
    )
    assert "component_scores" not in fields, (
        f"StabilityResult.component_scores muss entfernt werden, "
        f"vorhanden: {fields}"
    )
    assert "confidence_pct" in fields, (
        f"StabilityResult.confidence_pct fehlt, vorhanden: {fields}"
    )


# ---------------------------------------------------------------------------
# AC-2: StabilityResult aus hohen Konfidenz-Werten → STABIL
# ---------------------------------------------------------------------------

def test_stability_from_high_confidence():
    from services.weather_pattern import compute_stability
    result = compute_stability([80, 90, 75])
    assert result is not None
    assert result.label == "STABIL"
    assert result.confidence_pct == 75  # min()


# ---------------------------------------------------------------------------
# AC-3: Mittlere Konfidenz → WECHSELHAFT
# ---------------------------------------------------------------------------

def test_stability_from_medium_confidence():
    from services.weather_pattern import compute_stability
    result = compute_stability([80, 60, 55])
    assert result is not None
    assert result.label == "WECHSELHAFT"
    assert result.confidence_pct == 55


# ---------------------------------------------------------------------------
# AC-4: Niedrige Konfidenz → FRAGIL
# ---------------------------------------------------------------------------

def test_stability_from_low_confidence():
    from services.weather_pattern import compute_stability
    result = compute_stability([80, 45])
    assert result is not None
    assert result.label == "FRAGIL"
    assert result.confidence_pct == 45


# ---------------------------------------------------------------------------
# AC-5: None-Werte werden ignoriert
# ---------------------------------------------------------------------------

def test_stability_none_values_ignored():
    from services.weather_pattern import compute_stability
    result = compute_stability([None, 80, None])
    assert result is not None
    assert result.label == "STABIL"


# ---------------------------------------------------------------------------
# AC-6: Nur None-Werte → None zurück
# ---------------------------------------------------------------------------

def test_stability_all_none_returns_none():
    from services.weather_pattern import compute_stability
    result = compute_stability([None, None])
    assert result is None


# ---------------------------------------------------------------------------
# AC-7: Leere Liste → None
# ---------------------------------------------------------------------------

def test_stability_empty_list_returns_none():
    from services.weather_pattern import compute_stability
    result = compute_stability([])
    assert result is None


# ---------------------------------------------------------------------------
# AC-8: WL-Token NICHT im SMS-Output
# ---------------------------------------------------------------------------

def test_wl_token_not_in_sms_output():
    from output.tokens.builder import STD_SYMBOLS
    assert "WL" not in STD_SYMBOLS, (
        f"WL darf nicht in STD_SYMBOLS sein, vorhanden: {STD_SYMBOLS}"
    )


# ---------------------------------------------------------------------------
# AC-9: _fetch_ensemble_with_z500 existiert nicht mehr in Provider
# ---------------------------------------------------------------------------

def test_z500_method_removed_from_provider():
    from providers.openmeteo import OpenMeteoProvider
    assert not hasattr(OpenMeteoProvider, "_fetch_ensemble_with_z500"), (
        "OpenMeteoProvider._fetch_ensemble_with_z500 muss entfernt werden"
    )


# ---------------------------------------------------------------------------
# AC-10: WeatherPatternService hat keinen provider-Parameter mehr
# ---------------------------------------------------------------------------

def test_weather_pattern_service_no_provider_param():
    from services.weather_pattern import WeatherPatternService
    import inspect
    sig = inspect.signature(WeatherPatternService.__init__)
    assert "provider" not in sig.parameters, (
        f"WeatherPatternService.__init__ darf keinen provider-Parameter mehr "
        f"haben, vorhanden: {list(sig.parameters)}"
    )
