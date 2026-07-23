"""Kanonischer ID-Resolver: Frontend-IDs -> Stundenverlauf-Renderer-Metrik-IDs.

Eigenstaendiges Vokabular fuer die Stundentabellen-Spalten je Ort-Sektion in
der Compare-Mail (Issue #1106) -- bewusst KEIN Reuse von
``compare_metric_ids.py::FRONTEND_TO_RENDERER_METRIC_ID`` (Rohwerte pro
Stunde != Aggregate der Uebersichtstabelle).

Spec: docs/specs/modules/issue_1106_hourly_metrics_config.md
"""
from __future__ import annotations

FRONTEND_TO_HOURLY_METRIC_ID: dict[str, str] = {
    "temp_c": "t2m_c",
    "wind_chill_c": "wind_chill_c",
    "wind_kmh": "wind10m_kmh",
    "gust_kmh": "gust_kmh",
    "precip_mm": "precip_1h_mm",
    "uv_index": "uv_index",
    "thunder_level": "thunder_level",
    "pop_pct": "pop_pct",
    "visibility_m": "visibility_m",
    # Issue #1335 Scheibe 1: reines Merge-Signal, KEIN Eintrag in HOUR_METRICS
    # (compare_html.py) -- erzeugt keine eigene Spalte, sondern wird beim
    # Rendern in die Wind-Zelle gemergt (Kompass-Text), analog Trip-Muster
    # `should_merge_wind_dir()`. Rechte Seite = ForecastDataPoint-Feldname.
    "wind_dir_deg": "wind_direction_deg",
}


def resolve_hourly_metrics(hourly_metrics: list[str] | None) -> list[str] | None:
    """Rueckgabe None (= kein Filter, alle 9 Spalten sichtbar) wenn
    hourly_metrics leer/None ist -- rueckwaertskompatibler Default (AC-1).
    Nicht mappbare IDs werden verworfen statt zum Absturz zu fuehren; bildet
    die Auswahl komplett auf nichts Mappbares ab -> ebenfalls None (keine
    leere Stundentabelle).

    Nicht-Listen-Input (dict/str/int) wird defensiv zu None -- kein
    TypeError, kein fehlerhaftes Iterieren ueber String-Zeichen oder
    Dict-Keys (Adversary-Analogie F001, #1104).

    Issue #1335 Scheibe 1: Rueckgabetyp ist eine reihenfolge-erhaltende,
    deduplizierte Liste (erste-Vorkommen-Reihenfolge von ``hourly_metrics``)
    statt eines ungeordneten ``set`` (AC-2)."""
    if not hourly_metrics:
        return None
    if not isinstance(hourly_metrics, list):
        return None
    resolved = list(dict.fromkeys(
        FRONTEND_TO_HOURLY_METRIC_ID[m]
        for m in hourly_metrics
        if m in FRONTEND_TO_HOURLY_METRIC_ID
    ))
    return resolved or None


__all__ = ["resolve_hourly_metrics", "FRONTEND_TO_HOURLY_METRIC_ID"]
