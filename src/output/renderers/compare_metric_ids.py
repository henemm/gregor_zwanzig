"""Kanonischer ID-Resolver: Frontend `active_metrics`-IDs -> Renderer/CE_PROFILES-IDs.

Loest NUR Vokabular 3 -> Vokabular 2 (siehe docs/context/fix-1094-compare-config.md,
Abschnitt "Vier inkompatible Metrik-Vokabulare"). Vokabular 1 (Katalog) und 4
(Step4Layout Channel-Layout) sind nicht Teil dieses Slices.

Spec: docs/specs/modules/issue_1104_compare_config_foundation.md
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

FRONTEND_TO_RENDERER_METRIC_ID: dict[str, str] = {
    "snow_depth_cm": "snow_depth_cm",
    "snow_new_sum_cm": "snow_new_cm",
    "sunny_hours_h": "sunny_hours",
    "wind_max_kmh": "wind_max",
    "cloud_avg_pct": "cloud_avg",
    "temp_max_c": "temp_max",
    # Issue #1285: die folgenden fuenf wurden bis 2026-07-16 STILL verworfen
    # (keine Matrix-Zeile, keine Meldung), weil LocationResult kein
    # Tages-Aggregat dafuer fuehrte. Die Tageswerte werden jetzt aus
    # hourly_data abgeleitet (kanonische Trip-Regeln, s.
    # weather_metrics.summarize_points), damit sind sie mappbar.
    "precip_sum_mm": "precip_sum",
    "thunder_level_max": "thunder_max",
    "visibility_min_m": "visibility_min",
    "uv_index_max": "uv_max",
    "pop_max_pct": "pop_max",
    # Issue #1296: analog #1285 -- die folgenden vier wurden bis 2026-07-17
    # STILL verworfen. Klasse A (temp_min_c/gust_max_kmh) ist reines Mapping
    # (LocationResult.temp_min/.gust_max existieren bereits); Klasse B
    # (cape_max_jkg/freezing_level_m) wird live aus hourly_data abgeleitet
    # (s. weather_metrics.summarize_points).
    "temp_min_c": "temp_min",
    "gust_max_kmh": "gust_max",
    "cape_max_jkg": "cape_max",
    "freezing_level_m": "freezing_level",
    # Issue #1324: zehn weitere additive Metriken. Klasse A (Renderer-ID =
    # bestehendes LocationResult-Feld, gelesen ueber den field-is-None-Zweig
    # von _metric_value, kein _DAILY_AGGREGATE_FIELD-Eintrag noetig):
    "wind_direction_deg": "wind_direction_avg",
    "wind_chill_min_c": "wind_chill_min",
    "cloud_low_avg_pct": "cloud_low_avg",
    "cloud_mid_avg_pct": "cloud_mid_avg",
    "cloud_high_avg_pct": "cloud_high_avg",
    # Klasse B (eigene Renderer-ID -> SegmentWeatherSummary-Feld ueber
    # _DAILY_AGGREGATE_FIELD, Live-Ableitung aus hourly_data):
    "humidity_avg_pct": "humidity_avg",
    "dewpoint_avg_c": "dewpoint_avg",
    "pressure_avg_hpa": "pressure_avg",
    "precip_type_dominant": "precip_type",
    "snowfall_limit_m": "snowfall_limit",
}


# Issue #1278: Compare-Renderer-ID -> Trip-Metrik-ID (`dc.metrics[].metric_id`).
# Dritte Uebersetzungsrichtung neben FRONTEND_TO_RENDERER_METRIC_ID: der
# geteilte Fliesstext-Baustein (CompactSummaryFormatter) spricht das
# TRIP-Vokabular. Nur Compare-Zeilen mit Trip-Pendant stehen hier -- was fehlt,
# erscheint bewusst nicht im Zusammenfassungssatz (uv_max/visibility_min/
# sunny_hours/snow_*: kein _format_*-Zweig im Baustein, s. Spec Known
# Limitations). Reihenfolge = Satz-Reihenfolge des Bausteins.
RENDERER_TO_TRIP_METRIC_ID: dict[str, str] = {
    "temp_max": "temperature",
    "cloud_avg": "cloud_total",
    "precip_sum": "precipitation",
    "pop_max": "rain_probability",
    "wind_max": "wind",
    "thunder_max": "thunder",
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


def resolve_enabled_metrics(active_metrics: list[str] | None) -> list[str] | None:
    """Rueckgabe None (= kein Filter, alle Metriken sichtbar) wenn active_metrics
    leer/None ist -- rueckwaertskompatibler Default (AC-2/AC-4). Nicht mappbare
    IDs werden verworfen statt zum Absturz zu fuehren; bildet die Auswahl komplett
    auf nichts Mappbares ab -> ebenfalls None (kein leeres Matrix-Rendering).

    Nicht-Listen-Input (dict/str/int) wird ebenfalls defensiv zu None -- kein
    TypeError, kein fehlerhaftes Iterieren ueber String-Zeichen oder Dict-Keys.

    Issue #1335 Scheibe 1: Rueckgabetyp ist eine reihenfolge-erhaltende,
    deduplizierte Liste (erste-Vorkommen-Reihenfolge von ``active_metrics``)
    statt eines ungeordneten ``set`` -- die Nutzer-Reihenfolge der Config
    erreicht so den Renderer (AC-1)."""
    if not active_metrics:
        return None
    if not isinstance(active_metrics, list):
        return None
    unmapped = [m for m in active_metrics if m not in FRONTEND_TO_RENDERER_METRIC_ID]
    if unmapped:
        # Issue #1296: struktureller Guard (AC-6) -- sichtbares Signal statt
        # stiller Verwerfung, damit sich der #1285/#1296-Bug-Typ nicht ein
        # drittes Mal wiederholt.
        logger.warning(
            "resolve_enabled_metrics: %s ohne Renderer-Mapping — Auswahl "
            "wird ignoriert statt angezeigt (vgl. #1285/#1296)", unmapped,
        )
    resolved = list(dict.fromkeys(
        FRONTEND_TO_RENDERER_METRIC_ID[m]
        for m in active_metrics
        if m in FRONTEND_TO_RENDERER_METRIC_ID
    ))
    return resolved or None
