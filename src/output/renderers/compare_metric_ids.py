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


# Issue #1278/#2992: Vergleichs-Zeilen (Renderer-IDs) des Zusammenfassungssatzes,
# Reihenfolge = Satz-Reihenfolge des geteilten Bausteins (CompactSummaryFormatter).
# Nur Groessen mit _format_*-Zweig im Baustein -- uv_max/visibility_min/
# sunny_hours/snow_* erscheinen bewusst nicht im Satz. Die Trip-Metrik-ID je
# Zeile steht NICHT hier, sondern kommt aus dem Vergleichs-Katalog
# (``renderer_to_trip_metric_id``).
SUMMARY_SENTENCE_RENDERER_IDS: tuple[str, ...] = (
    "temp_max",
    "cloud_avg",
    "precip_sum",
    "pop_max",
    "wind_max",
    "thunder_max",
)


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


def _non_selectable_keys() -> frozenset[str]:
    """Compare-Schluessel, deren zentrale Groesse nicht waehlbar ist (#1585).

    Abgeleitet aus `MetricDefinition.selectable`, NICHT aus einer getippten
    Kennungsliste -- die naechste `selectable=False`-Groesse verschwindet damit
    ohne weiteren Eingriff auch aus einer gespeicherten Auswahl.

    Import in der Funktion aus demselben Grund wie in `_to_key`: auf
    Modulebene waere es ein Zyklus."""
    from app.metric_catalog import get_metric
    from output.renderers.compare_metric_catalog import COMPARE_METRIC_CATALOG

    return frozenset(
        entry["key"]
        for entry in COMPARE_METRIC_CATALOG
        if not get_metric(entry["metric_id"]).selectable
    )


def _non_selectable_names() -> frozenset[str]:
    """Alle Namensformen zentral nicht waehlbarer Groessen (#710/#1405 S3):
    Katalog-Kennung, Datenfeld, Spaltenschluessel und Tagesfelder -- z. B.
    ``confidence``/``confidence_pct``. Eine gespeicherte Auswahl mit einer
    dieser Formen ist KEINE Luecke (Art b), sondern bleibt still (nur Log)."""
    from app.metric_catalog import _METRICS

    names: set[str] = set(_non_selectable_keys())
    shared: set[str] = set()
    for m in _METRICS:
        forms = {m.id, m.dp_field, m.col_key, *m.summary_fields.values()}
        (shared if m.selectable else names).update(forms)
    # Namensformen, die auch eine WAEHLBARE Groesse traegt (z. B. `t2m_c`),
    # bleiben meldepflichtig -- sonst verschwaende eine echte Luecke still.
    return frozenset(n for n in names - shared if n)


def _unresolved_name(item: object, key: str | None) -> str:
    """Stabile Kennung eines unaufloesbaren Eintrags (Dedup ueber Listen)."""
    if key is not None:
        return key
    if isinstance(item, dict):
        return str(item.get("metric_id"))
    return repr(item)


def resolve_enabled_metrics_report(
    active_metrics: list[str | dict] | None,
) -> tuple[list[str] | None, tuple[str, ...]]:
    """Wie ``resolve_enabled_metrics``, liefert zusaetzlich die Kennungen der
    gewaehlten Eintraege OHNE Renderer-Zuordnung (Issue #1405 S3, Art a).

    Zentral nicht waehlbare Groessen (Art b, z. B. ``confidence_pct``, #710)
    zaehlen NICHT dazu -- sie duerfen nie sichtbar werden, auch nicht als
    Zahl. Die Log-Zeile bleibt unveraendert fuer beide Arten erhalten."""
    resolved = resolve_enabled_metrics(active_metrics)
    if resolved is None:
        return None, ()
    silent = _non_selectable_names()
    unresolved: dict[str, None] = {}
    for item in active_metrics:
        key = _to_key(item)
        if key is not None and key in FRONTEND_TO_RENDERER_METRIC_ID:
            continue
        name = _unresolved_name(item, key)
        if name in silent:
            continue
        unresolved[name] = None
    return resolved, tuple(unresolved)


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
    non_selectable = _non_selectable_keys()

    def _resolvable(key: str | None) -> bool:
        return (
            key is not None
            and key in FRONTEND_TO_RENDERER_METRIC_ID
            and key not in non_selectable
        )

    unmapped = [item for item, key in normalized if not _resolvable(key)]
    if unmapped:
        # Issue #1296: struktureller Guard (AC-6) -- sichtbares Signal statt
        # stiller Verwerfung, damit sich der #1285/#1296-Bug-Typ nicht ein
        # drittes Mal wiederholt.
        logger.warning(
            "resolve_enabled_metrics: %s ohne Renderer-Mapping oder zentral "  # i18n-log
            "nicht waehlbar — Auswahl wird ignoriert statt angezeigt "
            "(vgl. #1285/#1296, #1585)", unmapped,
        )
    resolved = list(dict.fromkeys(
        FRONTEND_TO_RENDERER_METRIC_ID[key]
        for _item, key in normalized
        if _resolvable(key)
    ))
    return resolved


def _renderer_ids_for_kennung(kennung: object) -> list[str]:
    """Katalog-Kennung -> die Vergleichs-Zeilen (Renderer-IDs), die sie traegt
    (Issue #3039). Expansion nach dem Muster ``derived_aggregations``: jede
    Zeile des Vergleichs-Katalogs mit dieser Kennung, in Katalog-Reihenfolge
    (z. B. ``temperature`` -> Hoechst-, dann Tiefstwert). Zentral nicht
    waehlbare Groessen (#1585) fallen heraus."""
    if not isinstance(kennung, str):
        return []
    from output.renderers.compare_metric_catalog import COMPARE_METRIC_CATALOG

    non_selectable = _non_selectable_keys()
    return [
        FRONTEND_TO_RENDERER_METRIC_ID[entry["key"]]
        for entry in COMPARE_METRIC_CATALOG
        if entry["metric_id"] == kennung
        and entry["key"] in FRONTEND_TO_RENDERER_METRIC_ID
        and entry["key"] not in non_selectable
    ]


def _katalog_paare() -> dict[tuple[str, str], str]:
    """(Katalog-ID, Aggregation) -> Renderer-Kennung, gerechnet aus
    ``COMPARE_METRIC_CATALOG`` und ``FRONTEND_TO_RENDERER_METRIC_ID`` (Issue
    #3101) -- keine zweite getippte Abbildung. Jeder Katalog-Key hat eine
    Renderer-Kennung (Drift-Waechter in ``compare_metric_catalog``), daher
    ohne Filter. Import in der Funktion (Zyklus, s. ``_to_key``)."""
    from output.renderers.compare_metric_catalog import COMPARE_METRIC_CATALOG

    return {
        (entry["metric_id"], entry["aggregation"]): FRONTEND_TO_RENDERER_METRIC_ID[entry["key"]]
        for entry in COMPARE_METRIC_CATALOG
    }


def renderer_kennung(katalog_id: object, aggregation: object) -> str | None:
    """Adapter vor dem Renderer (Issue #3101): eine Zeile der Orte-Kanallisten
    (Katalog-ID + Aggregation) -> Renderer-Kennung; unbekanntes Paar -> None."""
    return _katalog_paare().get((katalog_id, aggregation))


def katalog_paar(renderer_id: object) -> tuple[str, str] | None:
    """Rueckrichtung zu ``renderer_kennung``: Renderer-Kennung ->
    (Katalog-ID, Aggregation); unbekannt -> None."""
    for paar, rid in _katalog_paare().items():
        if rid == renderer_id:
            return paar
    return None


def renderer_to_trip_metric_id(
    renderer_ids: tuple[str, ...] = SUMMARY_SENTENCE_RENDERER_IDS,
) -> dict[str, str]:
    """Renderer-ID -> Trip-Metrik-ID (``dc.metrics[].metric_id``) fuer den
    Zusammenfassungssatz, abgeleitet aus dem Vergleichs-Katalog (Issue #2992,
    Muster #3101) -- keine zweite getippte Tabelle. Reihenfolge = Eingabe.
    Fehlt ein Katalog-Paar -> ``ValueError`` mit der Renderer-ID (kein stilles
    Entfallen des Satzteils)."""
    result: dict[str, str] = {}
    for rid in renderer_ids:
        paar = katalog_paar(rid)
        if paar is None:
            raise ValueError(f"Satz-Renderer-ID ohne Katalog-Paar: {rid}")  # i18n-log
        result[rid] = paar[0]
    return result


#: Kanaele, die eine Stelle der Tabelle "Was steht wo" sind (#3156).
