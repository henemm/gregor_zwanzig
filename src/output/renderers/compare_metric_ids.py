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
    "wind_chill_max_c": "wind_chill_max",
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


def _to_key(item: object) -> str | None:
    """Normalisiert EIN Element der gespeicherten Metrik-Auswahl auf den
    Compare-Auswahl-Schluessel (#1373 Scheibe B).

    * Zeichenkette (Altformat) bleibt unveraendert -- ob sie mappbar ist,
      entscheidet wie bisher `FRONTEND_TO_RENDERER_METRIC_ID`.
    * Objekt (Neuformat) wird ueber den Umkehr-Index des Vergleichs-Katalogs
      aufgeloest: `{"metric_id": ..., "aggregation": ...}` -> Schluessel.
    * Alles andere (falscher Typ, unvollstaendiges/unbekanntes Paar) -> None,
      wird also wie eine nicht mappbare Zeichenkette verworfen.

    Der Import liegt bewusst IN der Funktion: `compare_metric_catalog`
    importiert seinerseits `FRONTEND_TO_RENDERER_METRIC_ID` aus diesem Modul
    (Drift-Waechter beim Modul-Import), ein Import auf Modulebene waere ein
    Zyklus."""
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        from output.renderers.compare_metric_catalog import key_for

        return key_for(item.get("metric_id"), item.get("aggregation"))
    return None


def resolve_enabled_metrics(
    active_metrics: list[str | dict] | None,
) -> list[str] | None:
    """Rueckgabe None (= kein Filter, alle Metriken sichtbar) nur wenn das Feld
    fehlt (`active_metrics is None`) -- rueckwaertskompatibler Default fuer
    Altbestand (AC-3). Eine bewusst leere oder komplett unauflösbare Auswahl
    liefert `[]` zurueck, nicht None (Issue #1366, AC-1/AC-2) -- "leer heisst
    leer" statt "leer heisst alle". Nicht mappbare IDs werden verworfen statt
    zum Absturz zu fuehren.

    Nicht-Listen-Input (dict/str/int) wird ebenfalls defensiv zu None -- kein
    TypeError, kein fehlerhaftes Iterieren ueber String-Zeichen oder Dict-Keys.

    Issue #1335 Scheibe 1: Rueckgabetyp ist eine reihenfolge-erhaltende,
    deduplizierte Liste (erste-Vorkommen-Reihenfolge von ``active_metrics``)
    statt eines ungeordneten ``set`` -- die Nutzer-Reihenfolge der Config
    erreicht so den Renderer (AC-1).

    Issue #1373 Scheibe B: die Auswahl darf beide Speicherformate enthalten --
    Zeichenketten (Altformat) UND `{"metric_id": ..., "aggregation": ...}`
    (Neuformat), auch gemischt in derselben Liste (Restrisiko R1: stehen-
    gebliebene Browser-Sitzung). Die Normalisierung laeuft PRO ELEMENT und VOR
    dem Dedup; Dedup-Schluessel bleibt die Renderer-Kennung, die Reihenfolge
    (#1335/#1359) bleibt damit unveraendert erhalten."""
    if active_metrics is None:
        return None
    if not isinstance(active_metrics, list):
        return None
    normalized = [(item, _to_key(item)) for item in active_metrics]
    unmapped = [
        item
        for item, key in normalized
        if key is None or key not in FRONTEND_TO_RENDERER_METRIC_ID
    ]
    if unmapped:
        # Issue #1296: struktureller Guard (AC-6) -- sichtbares Signal statt
        # stiller Verwerfung, damit sich der #1285/#1296-Bug-Typ nicht ein
        # drittes Mal wiederholt.
        logger.warning(
            "resolve_enabled_metrics: %s ohne Renderer-Mapping — Auswahl "
            "wird ignoriert statt angezeigt (vgl. #1285/#1296)", unmapped,
        )
    resolved = list(dict.fromkeys(
        FRONTEND_TO_RENDERER_METRIC_ID[key]
        for _item, key in normalized
        if key is not None and key in FRONTEND_TO_RENDERER_METRIC_ID
    ))
    return resolved
