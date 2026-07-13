"""Kanonischer ID-Resolver: Frontend `active_metrics`-IDs -> Renderer/CE_PROFILES-IDs.

Loest NUR Vokabular 3 -> Vokabular 2 (siehe docs/context/fix-1094-compare-config.md,
Abschnitt "Vier inkompatible Metrik-Vokabulare"). Vokabular 1 (Katalog) und 4
(Step4Layout Channel-Layout) sind nicht Teil dieses Slices.

Spec: docs/specs/modules/issue_1104_compare_config_foundation.md
"""
from __future__ import annotations

FRONTEND_TO_RENDERER_METRIC_ID: dict[str, str] = {
    "snow_depth_cm": "snow_depth_cm",
    "snow_new_sum_cm": "snow_new_cm",
    "sunny_hours_h": "sunny_hours",
    "wind_max_kmh": "wind_max",
    "cloud_avg_pct": "cloud_avg",
    "temp_max_c": "temp_max",
    # visibility_min_m, precip_sum_mm, uv_index_max, thunder_level_max: kein
    # ComparisonResult-Feld -> bewusst nicht gemappt (Folge-Scope, s. Known Limitations).
}


# Issue #1231, Slice 7: gleicher vergleich-Namensraum wie oben, aber Ziel
# sind die Stundentabellen-Spalten (HOUR_METRICS-Keys in compare_html.py)
# statt der Uebersichtszeilen -- eigene Zielmenge, weil nicht jede
# Uebersichts-Metrik eine Stundenspalte hat (und umgekehrt). Nur die
# Schnittmenge ist gemappt; gebraucht von der Korridor-mark-Markierung
# (render_compare_html(corridors=...)), NICHT von resolve_enabled_metrics.
#
# Adversary F003 (Fix-Loop): NUR echte 1:1-Stundenmetriken -- ein Korridor
# auf ein TAGES-Aggregat (z.B. `precip_sum_mm`, `uv_index_max`,
# `visibility_min_m`) gegen einen EINZELNEN Stundenwert zu matchen waere
# fachlich falsch (28mm Tagessumme != 3,5mm Stundenwert). Diese drei Metriken
# werden bewusst NICHT hier gemappt -- ihre Markierung passiert korrekt in
# der UEBERSICHTS-Zeile (dort steht das Tages-Aggregat, s.
# FRONTEND_TO_RENDERER_METRIC_ID). Nur Metriken, deren Stundenwert UND
# Tages-Kennzahl dieselbe physikalische Groesse sind (Momentanwert bzw.
# Extremum), bleiben hier: Temperatur, Wind, Boeen, Gewitter-Ordinal.
CORRIDOR_METRIC_TO_HOUR_KEY: dict[str, str] = {
    "temp_max_c": "t2m_c",
    "wind_max_kmh": "wind10m_kmh",
    "gust_max_kmh": "gust_kmh",
    "thunder_level_max": "thunder_level",
}


def resolve_enabled_metrics(active_metrics: list[str] | None) -> set[str] | None:
    """Rueckgabe None (= kein Filter, alle Metriken sichtbar) wenn active_metrics
    leer/None ist -- rueckwaertskompatibler Default (AC-2/AC-4). Nicht mappbare
    IDs werden verworfen statt zum Absturz zu fuehren; bildet die Auswahl komplett
    auf nichts Mappbares ab -> ebenfalls None (kein leeres Matrix-Rendering).

    Nicht-Listen-Input (dict/str/int) wird ebenfalls defensiv zu None -- kein
    TypeError, kein fehlerhaftes Iterieren ueber String-Zeichen oder Dict-Keys."""
    if not active_metrics:
        return None
    if not isinstance(active_metrics, list):
        return None
    resolved = {
        FRONTEND_TO_RENDERER_METRIC_ID[m]
        for m in active_metrics
        if m in FRONTEND_TO_RENDERER_METRIC_ID
    }
    return resolved or None
