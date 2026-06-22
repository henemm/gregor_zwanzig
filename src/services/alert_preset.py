"""Issue #846 — Alert-Preset-Expansion (Epic #813 Slice 3).

Expandiert einen Preset-Namen in eine Liste von AlertRule-Objekten.

Presets:
- "deaktiviert" → leere Liste (kein Alert-Versand)
- "entspannt"   → lockere Schwellen (13 Regeln)
- "standard"    → empfohlene Schwellen (13 Regeln, Default)
- "sensibel"    → enge Schwellen (13 Regeln)

Schwellwert-Tabelle:
    Metrik                  Art               Entspannt  Standard  Sensibel
    wind_gust               delta ↑              35         20        12
    precipitation_sum       delta ↑              20         10         5
    thunder_level           delta ↑               1          1         1
    snow_line               delta ↓             600        400       200
    temperature_min         delta ↓               8          5         3
    temperature_max         delta ↑              10          6         4
    temperature_change      delta ↑              14         10         6
    wind_change             delta ↑              35         25        15
    precipitation_change    delta ↑              15          7         3
    fresh_snow              delta ↑              20          8         2
    cape                    delta ↑            1200        600       200
    visibility   threshold_crossing ↓           500       1000      3000
    humidity                delta ↑              25         15        10
"""
from __future__ import annotations

import uuid
from typing import Final

from app.models import AlertMetric, AlertRule, AlertRuleKind, AlertSeverity

# ───────────────────────── Schwellwert-Tabelle ──────────────────────────────

# Jede Zeile: (metric, kind, threshold_entspannt, threshold_standard, threshold_sensibel)
_PRESET_TABLE: Final[list[tuple]] = [
    (AlertMetric.WIND_GUST,            AlertRuleKind.DELTA,              35,    20,    12),
    (AlertMetric.PRECIPITATION_SUM,    AlertRuleKind.DELTA,              20,    10,     5),
    (AlertMetric.THUNDER_LEVEL,        AlertRuleKind.DELTA,               1,     1,     1),
    (AlertMetric.SNOW_LINE,            AlertRuleKind.DELTA,             600,   400,   200),
    (AlertMetric.TEMPERATURE_MIN,      AlertRuleKind.DELTA,               8,     5,     3),
    (AlertMetric.TEMPERATURE_MAX,      AlertRuleKind.DELTA,              10,     6,     4),
    (AlertMetric.TEMPERATURE_CHANGE,   AlertRuleKind.DELTA,              14,    10,     6),
    (AlertMetric.WIND_CHANGE,          AlertRuleKind.DELTA,              35,    25,    15),
    (AlertMetric.PRECIPITATION_CHANGE, AlertRuleKind.DELTA,              15,     7,     3),
    (AlertMetric.FRESH_SNOW,           AlertRuleKind.DELTA,              20,     8,     2),
    (AlertMetric.CAPE,                 AlertRuleKind.DELTA,            1200,   600,   200),
    (AlertMetric.VISIBILITY,           AlertRuleKind.THRESHOLD_CROSSING, 500,  1000,  3000),
    (AlertMetric.HUMIDITY,             AlertRuleKind.DELTA,              25,    15,    10),
]

# Spaltenindex in _PRESET_TABLE (2=entspannt, 3=standard, 4=sensibel)
_COL: Final[dict[str, int]] = {
    "entspannt": 2,
    "standard":  3,
    "sensibel":  4,
}


def expand_preset(name: str) -> list[AlertRule]:
    """Expandiert einen Preset-Namen in eine AlertRule-Liste.

    Args:
        name: Preset-Name ("deaktiviert" | "entspannt" | "standard" | "sensibel").
              Unbekannte Namen werden wie "standard" behandelt.

    Returns:
        Liste von AlertRule-Objekten. Leer bei "deaktiviert".
    """
    if name == "deaktiviert":
        return []

    col = _COL.get(name, _COL["standard"])
    rules: list[AlertRule] = []
    for row in _PRESET_TABLE:
        metric, kind, *thresholds = row
        threshold = float(thresholds[col - 2])
        rules.append(AlertRule(
            id=str(uuid.uuid4()),
            kind=kind,
            metric=metric,
            threshold=threshold,
            severity=AlertSeverity.WARNING,
            enabled=True,
        ))
    return rules
