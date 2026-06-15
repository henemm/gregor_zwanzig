"""
TDD RED — Issue #817: Alerts-Tab auf Δ-Schwellen umstellen.

AC-4: Cross-Lang-Wertekontrakt zwischen
  Go DefaultDeltaThreshold (internal/model/trip.go) und
  Python metric_catalog.default_change_threshold.

  Implementierung: Go-Test TestEmitDefaultDeltaThresholdJSON schreibt echte
  Laufzeitwerte als JSON in GZ_DELTA_JSON_OUT (subprocess-Aufruf, kein read_text).
  Damit #765-konform — kein Produkt-Quelltext-Read.

AC-5: Regression-Guard für from_alert_rules — δ-Regeln setzen Threshold direkt
  (im Gegensatz zu absoluten Regeln, die den MetricCatalog-Default per setdefault nutzen).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parents[2]  # .../gregor_zwanzig/


def _go_binary() -> str:
    """Lokalisiert die go-Binary. Wirft pytest.skip wenn nicht vorhanden."""
    candidate = shutil.which("go")
    if candidate:
        return candidate
    fallback = "/usr/local/go/bin/go"
    if os.path.isfile(fallback):
        return fallback
    pytest.skip("go binary not found — skipping Go-runtime cross-lang check")


def _emit_default_delta_threshold() -> dict[str, float]:
    """
    Führt TestEmitDefaultDeltaThresholdJSON via subprocess aus und liest die
    emittierten Laufzeitwerte als JSON zurück.

    Liest echte Go-Map-Werte zur Laufzeit — kein read_text auf Quelltext (#765-konform).
    """
    go = _go_binary()
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        env = {**os.environ, "GZ_DELTA_JSON_OUT": tmp_path}
        result = subprocess.run(
            [go, "test", "-run", "TestEmitDefaultDeltaThresholdJSON", "-count=1",
             "./internal/model/"],
            env=env,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"go test TestEmitDefaultDeltaThresholdJSON failed (exit {result.returncode}):\n"
                f"stdout: {result.stdout}\nstderr: {result.stderr}"
            )
        out_path = Path(tmp_path)
        if not out_path.exists() or out_path.stat().st_size == 0:
            raise RuntimeError(
                "TestEmitDefaultDeltaThresholdJSON did not write output file — "
                "check GZ_DELTA_JSON_OUT handling in the Go test."
            )
        return json.loads(out_path.read_text())
    finally:
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass


# ---------------------------------------------------------------------------
# AC-4 -- Cross-Lang-Wertekontrakt
# ---------------------------------------------------------------------------


def test_817_ac4_cross_lang_contract_go_block_exists():
    """
    AC-4 RED-Treiber: DefaultDeltaThreshold in trip.go muss existieren und
    alle 6 Metriken enthalten.

    Schlägt fehl wenn TestEmitDefaultDeltaThresholdJSON kein gültiges JSON
    mit mindestens 6 Einträgen emittiert.
    """
    go_thresholds = _emit_default_delta_threshold()
    assert go_thresholds, (
        "DefaultDeltaThreshold emittiert leeres JSON -- Implementierungsfehler"
    )
    assert len(go_thresholds) >= 6, (
        f"DefaultDeltaThreshold muss mind. 6 Einträge haben, got {len(go_thresholds)}: {go_thresholds}"
    )


def test_817_ac4_cross_lang_contract_values():
    """
    AC-4: Go DefaultDeltaThreshold stimmt mit Python metric_catalog exakt überein.

    Mapping Go-Constant-Suffix -> Python metric_catalog summary_field -> Erwartungswert:
      WindGust         -> gust_max_kmh            -> 20.0
      PrecipitationSum -> precip_sum_mm            -> 10.0
      TemperatureMin   -> temp_min_c              -> 5.0
      TemperatureMax   -> temp_max_c              -> 5.0
      ThunderLevel     -> thunder_level_max       -> 1.0
      SnowLine         -> freezing_level_m        -> 200.0
    """
    from src.app.metric_catalog import get_change_detection_map  # type: ignore[import]

    go_thresholds = _emit_default_delta_threshold()
    catalog = get_change_detection_map()

    # Erwartete Übereinstimmungen: (Go-Suffix, Python-summary-field, Wert)
    expected_pairs = [
        ("WindGust", "gust_max_kmh", 20.0),
        ("PrecipitationSum", "precip_sum_mm", 10.0),
        ("TemperatureMin", "temp_min_c", 5.0),
        ("TemperatureMax", "temp_max_c", 5.0),
        ("ThunderLevel", "thunder_level_max", 1.0),
        ("SnowLine", "freezing_level_m", 200.0),
    ]

    for go_suffix, py_field, expected in expected_pairs:
        # Go-Seite (echte Laufzeitwerte)
        assert go_suffix in go_thresholds, (
            f"Go DefaultDeltaThreshold: fehlender Eintrag fuer AlertMetric{go_suffix}"
        )
        go_val = go_thresholds[go_suffix]
        assert go_val == expected, (
            f"Go DefaultDeltaThreshold[{go_suffix}]: want {expected}, got {go_val}"
        )
        # Python-Seite
        assert py_field in catalog, (
            f"Python metric_catalog.get_change_detection_map(): fehlender Eintrag fuer {py_field!r}"
        )
        py_val = catalog[py_field]
        assert py_val == expected, (
            f"Cross-Lang-Kontrakt verletzt: Go[{go_suffix}]={go_val} != Python[{py_field}]={py_val} "
            f"(erwartet: {expected})"
        )


# ---------------------------------------------------------------------------
# AC-5 -- Regression-Guard: from_alert_rules Delta-vs-Absolut-Kontrast
# ---------------------------------------------------------------------------
# HINWEIS: AC-5 ist ein REGRESSION-GUARD -- kein RED-Treiber.
# from_alert_rules verarbeitet kind="delta" bereits korrekt (Slice 1 / #816).
# Dieser Test ist heute GRUEN und dokumentiert die Kern-Motivation fuer #817:
#
#   Delta-Regel  -> threshold fliesst DIREKT in _thresholds[field] (Z. 234-235)
#   Absolute-Regel -> threshold wird IGNORIERT, MetricCatalog-Default via setdefault (Z. 222-223)
#
# Das beweist, warum absolute Regeln den Nutzerwert nie an die Auswertung uebergeben.


def test_817_ac5_delta_rule_threshold_flows_through():
    """
    AC-5 Regression-Guard: from_alert_rules mit kind="delta" fuer WIND_GUST
    (Basis-Metrik, seit #817 von SyncAlertRules erzeugt) setzt
    _thresholds["gust_max_kmh"] direkt auf rule.threshold.

    Kein Mock. Echter from_alert_rules-Aufruf.

    REGRESSION-GUARD: Schlaegt fehl wenn from_alert_rules aufhoert, Delta-Regeln
    fuer Basis-Metriken via _ALERT_METRIC_TO_SUMMARY_FIELD zu routen (F001-Fix).
    """
    from src.app.models import AlertMetric, AlertRule, AlertRuleKind, AlertSeverity  # type: ignore[import]
    from src.services.weather_change_detection import WeatherChangeDetectionService  # type: ignore[import]

    rule = AlertRule(
        id="test-delta",
        kind=AlertRuleKind.DELTA,
        metric=AlertMetric.WIND_GUST,  # echte Spec-Aussage AC-5: Basis-Metrik als delta
        threshold=30.0,
        severity=AlertSeverity.WARNING,
        enabled=True,
    )
    service = WeatherChangeDetectionService.from_alert_rules([rule])
    # gust_max_kmh ist in _ALERT_METRIC_TO_SUMMARY_FIELD[WIND_GUST] (F001-Fallback-Pfad)
    assert "gust_max_kmh" in service._thresholds, (
        "AC-5/guard: from_alert_rules(delta WIND_GUST) muss gust_max_kmh in _thresholds setzen"
    )
    assert service._thresholds["gust_max_kmh"] == 30.0, (
        f"AC-5/guard: Delta-Threshold 30.0 muss direkt fliessen, got {service._thresholds['gust_max_kmh']}"
    )


def test_817_ac5_contrast_absolute_rule_ignores_threshold():
    """
    AC-5 Kontrast-Test (Regression-Guard, heute GRUEN):
    from_alert_rules mit kind="absolute" fuer wind_gust IGNORIERT rule.threshold.
    Stattdessen greift setdefault mit MetricCatalog-Default (20.0).

    Dies ist die KERN-ERKENNTNIS von #817:
      Absolute Regeln -> threshold nie alert-wirksam -> Migration auf Delta noetig.

    Kein Mock. Echter from_alert_rules-Aufruf.
    """
    from src.app.metric_catalog import get_change_detection_map  # type: ignore[import]
    from src.app.models import AlertMetric, AlertRule, AlertRuleKind, AlertSeverity  # type: ignore[import]
    from src.services.weather_change_detection import WeatherChangeDetectionService  # type: ignore[import]

    # Absolut-Regel mit absichtlich anderem Threshold als MetricCatalog-Default
    rule = AlertRule(
        id="test-absolute",
        kind=AlertRuleKind.ABSOLUTE,
        metric=AlertMetric.WIND_GUST,
        threshold=999.0,  # weit von Default entfernt
        severity=AlertSeverity.WARNING,
        enabled=True,
    )
    service = WeatherChangeDetectionService.from_alert_rules([rule])

    catalog_default = get_change_detection_map().get("gust_max_kmh")
    assert catalog_default is not None, "MetricCatalog muss Default fuer gust_max_kmh haben"

    # Kontrast-Assert: threshold=999 kommt NICHT durch -- MetricCatalog-Default greift.
    if "gust_max_kmh" in service._thresholds:
        actual = service._thresholds["gust_max_kmh"]
        assert actual == catalog_default, (
            f"AC-5/kontrast: Absolute-Regel threshold=999 darf NICHT durchfliessen. "
            f"Erwartet MetricCatalog-Default {catalog_default}, got {actual}. "
            f"Dies beweist: absolute Regeln sind nie alert-wirksam."
        )
        assert actual != 999.0, (
            "AC-5/kontrast: Absolute threshold=999 ist durchgeflossen -- "
            "das ist ein Fehler (from_alert_rules Z. 222-223 setdefault wird verletzt)."
        )
