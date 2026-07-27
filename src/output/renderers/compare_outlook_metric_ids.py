"""Aufloeser fuer die Ausblick-Spaltenauswahl des Ortsvergleichs (#1361/#1368).

Struktureller Zwilling zu ``compare_hourly_metric_ids.py`` -- aber im
NEUFORMAT (``{"metric_id": ..., "aggregation": ...}``, #1373), demselben
Vokabular wie ``display_config.active_metrics``. Kein viertes Vokabular, keine
zweite Uebersetzungstabelle: die Existenzpruefung laeuft ueber
``compare_metric_catalog.key_for()``, der Feldbezug ueber
``metric_catalog.MetricDefinition.summary_fields``.

SPEC: docs/specs/modules/issue_1361_1368_ausblick_konfigurierbar.md
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _catalog_entry(metric_id: object, aggregation: object) -> dict | None:
    """Compare-Katalog-Zeile zu einem Groesse-Auswertung-Paar (oder ``None``)."""
    from output.renderers.compare_metric_catalog import (
        COMPARE_METRIC_CATALOG, key_for,
    )

    key = key_for(metric_id, aggregation)
    if key is None:
        return None
    return next((e for e in COMPARE_METRIC_CATALOG if e["key"] == key), None)


def _summary_field(metric_id: object, aggregation: object) -> str | None:
    """``SegmentWeatherSummary``-Feldname der Tagesauswertung (oder ``None``).

    ``selectable=False`` (``confidence``, ADR-0005/#710; ``temperature_cold``)
    ist hier bewusst nicht aufloesbar -- der Ausblick zeigt nur waehlbare
    Groessen."""
    from app.metric_catalog import _METRICS_BY_ID

    definition = _METRICS_BY_ID.get(metric_id) if isinstance(metric_id, str) else None
    if definition is None or not definition.selectable:
        return None
    if not isinstance(aggregation, str):
        return None
    return definition.summary_fields.get(aggregation)


def resolve_outlook_metrics(outlook_metrics: object) -> list[dict] | None:
    """``None`` nur wenn das Feld fehlt (Altbestand = bisherige sieben Spalten).

    Eine bewusst geleerte oder vollstaendig unaufloesbare Auswahl liefert
    ``[]`` ("leer heisst leer", analog #1366) -- der Aufrufer schaltet den
    Block daraufhin ab. Unbekannte/ungueltige Paare werden verworfen und per
    ``logger.warning`` sichtbar gemacht (#1361 Befund 3), die Auswahl-
    Reihenfolge bleibt erhalten (kein ``set``)."""
    if not isinstance(outlook_metrics, list):
        return None

    resolved: list[dict] = []
    dropped: list = []
    seen: set[tuple] = set()
    for raw in outlook_metrics:
        metric_id = raw.get("metric_id") if isinstance(raw, dict) else None
        aggregation = raw.get("aggregation") if isinstance(raw, dict) else None
        if _catalog_entry(metric_id, aggregation) is None or _summary_field(metric_id, aggregation) is None:
            dropped.append(raw)
            continue
        if (metric_id, aggregation) in seen:
            continue
        seen.add((metric_id, aggregation))
        resolved.append({"metric_id": metric_id, "aggregation": aggregation})

    if dropped:
        logger.warning(
            "resolve_outlook_metrics: %s ohne Katalog-Entsprechung — Eintrag "
            "wird verworfen statt angezeigt (vgl. #1361 Befund 3)", dropped,
        )
    return resolved


def outlook_columns(metrics: object) -> list[dict]:
    """Auswahl -> geordnete Spalten-Beschreibung fuer den Ausblick-Renderer.

    ``label`` kommt aus dem Compare-Katalog (deutsch und eindeutig, z.B.
    "Temperatur max"), NICHT aus ``MetricDefinition.col_label``: dessen
    Kuerzel sind englisch ("Rain"/"Thdr"/"PType") und fuer temperature
    min/max/avg IDENTISCH ("Temp") -- zwei gewaehlte Temperatur-Auswertungen
    ergaeben zwei gleich beschriftete Spalten (Abweichung zur Spec,
    PO-Entscheidung 2026-07-27)."""
    columns: list[dict] = []
    for entry in metrics or []:
        metric_id = entry.get("metric_id") if isinstance(entry, dict) else None
        aggregation = entry.get("aggregation") if isinstance(entry, dict) else None
        catalog = _catalog_entry(metric_id, aggregation)
        field = _summary_field(metric_id, aggregation)
        if catalog is None or field is None:
            continue
        columns.append({
            "label": catalog["label"],
            "field": field,
            "unit": catalog.get("unit", ""),
            "decimals": catalog.get("decimals", 0),
            "kind": catalog.get("kind", "range"),
        })
    return columns


def format_outlook_value(value: object, column: dict) -> str:
    """Zellentext einer Ausblick-Spalte.

    Nicht-numerische Groessen nutzen DIESELBEN deutschen Labels wie die
    Uebersichtstabelle derselben Mail (``_fmt_thunder``/``_fmt_precip_type``)
    -- keine zweite Label-Tabelle. Der Compare-Katalog kennt genau einen
    ordinalen (Gewitter) und genau einen Enum-Eintrag (Niederschlagsart)."""
    from output.renderers.email.compare_html import _fmt_precip_type, _fmt_thunder

    if value is None:
        return "–"
    kind = column.get("kind")
    if kind == "ordinal":
        return _fmt_thunder(value)
    if kind == "enum":
        return _fmt_precip_type(value)
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    decimals = column.get("decimals") or 0
    text = f"{number:.{int(decimals)}f}"
    unit = column.get("unit") or ""
    return f"{text} {unit}".strip()


__all__ = [
    "resolve_outlook_metrics",
    "outlook_columns",
    "format_outlook_value",
]
