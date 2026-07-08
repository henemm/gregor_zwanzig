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
