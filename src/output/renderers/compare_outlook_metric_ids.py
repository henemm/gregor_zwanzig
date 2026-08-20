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
    # #1401 A1: der angereicherte Katalog (Name aus dem zentralen Register,
    # `aggregation_label` daneben) statt der rohen Tabelle -- der Name steht
    # dort nicht mehr getippt.
    from output.renderers.compare_metric_catalog import (
        get_compare_metric_catalog, key_for,
    )

    key = key_for(metric_id, aggregation)
    if key is None:
        return None
    return next((e for e in get_compare_metric_catalog() if e["key"] == key), None)


def _summary_field(metric_id: object, aggregation: object) -> str | None:
    """``SegmentWeatherSummary``-Feldname der Tagesauswertung (oder ``None``).

    #1357: reiner Delegat auf die gehobene Katalog-Funktion -- EINE Quelle
    fuer Ausblick (hier) und Trip-Kachel (email/helpers.py), keine zweite
    Kopie der Aufloesungsregel."""
    from app.metric_catalog import summary_field_for

    return summary_field_for(metric_id, aggregation)


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


def resolve_trip_outlook_metrics(dc: object, report_type: str) -> list[dict] | None:
    """Trip-Vorschau (#1720 S1): aufgeloest UND gegen die Grundauswahl
    geschnitten. Der Ortsvergleich ruft weiterhin ``resolve_outlook_metrics()``
    direkt -- er kennt bewusst kein globales Maximum (ADR-0053).

    Geschnitten wird gegen dieselbe gemeinsame Quelle wie das Kanal-Layout:
    ``UnifiedWeatherDisplayConfig.allowed_metric_ids_for_report_type()``
    (ADR-0050 Regel 1/2 auf die Ausgabeflaeche "Vorschau" ausgeweitet,
    PO-Entscheid 2026-08-14; EINE Quelle seit #1848 Scheibe A -- vorher trug
    diese Funktion eine eigene Nachbildung der Regeln). Hier bleibt nur die
    Anwendung auf das ``{metric_id, aggregation}``-Vokabular: ``None`` von der
    gemeinsamen Quelle heisst "kein Maximum definiert" (D4) -> kein Schnitt,
    die Reihenfolge der Auswahl bleibt erhalten.

    Die Drei-Werte-Semantik von ``resolve_outlook_metrics()`` bleibt
    unberuehrt: ``None`` (Feld fehlt) bleibt ``None``, ``[]`` (bewusst
    geleert) bleibt ``[]`` -- der Schnitt wirkt nur auf einer bereits
    aufgeloesten, nicht-leeren Liste.

    🔴 ``dc`` MUSS der ungekollabierte Stand sein: geschnitten wird gegen die
    kanal-neutrale ``get_metrics_for_report_type()``, denn der Ausblick hat
    bewusst KEINE Kanal-Ebene (AC-17). Ein enges
    ``per_channel_layouts["email"]`` (#429) darf eine global aktive, gewaehlte
    Groesse nicht aus der Vorschau schneiden (Adversary-Finding F001).
    """
    resolved = resolve_outlook_metrics(getattr(dc, "outlook_metrics", None))
    if not resolved:
        return resolved
    allowed = dc.allowed_metric_ids_for_report_type(report_type)
    if allowed is None:
        return resolved
    return [e for e in resolved if e.get("metric_id") in allowed]


def outlook_columns(metrics: object) -> list[dict]:
    """Auswahl -> geordnete Spalten-Beschreibung fuer den Ausblick-Renderer.

    ``label`` kommt aus dem Compare-Katalog (deutsch, seit #1401 A1 der Name
    des zentralen Registers), NICHT aus ``MetricDefinition.col_label``: dessen
    Kuerzel sind englisch ("Rain"/"Thdr"/"PType") und fuer temperature
    min/max/avg IDENTISCH ("Temp") -- zwei gewaehlte Temperatur-Auswertungen
    ergaeben zwei gleich beschriftete Spalten (Abweichung zur Spec,
    PO-Entscheidung 2026-07-27).

    #1401 A1: die Auswertung ist kein Namensbestandteil mehr. Eine Tabellen-
    spalte traegt aber genau EINEN String -- waehlt der Nutzer dieselbe Groesse
    zweimal (Temperatur max UND min), bekommen genau diese Spalten die
    Auswertung angehaengt, damit die PO-Vorgabe "keine zwei gleich
    beschrifteten Spalten" erhalten bleibt."""
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
            "metric_id": metric_id,
            "aggregation": aggregation,
            "field": field,
            "unit": catalog.get("unit", ""),
            "decimals": catalog.get("decimals", 0),
            "kind": catalog.get("kind", "range"),
            "aggregation_label": catalog.get("aggregation_label", ""),
        })
    columns = _merge_min_max_pairs(columns)
    mehrfach = {c["label"] for c in columns
                if sum(1 for other in columns if other["label"] == c["label"]) > 1}
    for column in columns:
        if column["label"] in mehrfach and column.get("aggregation_label"):
            column["label"] = f"{column['label']} {column['aggregation_label']}"
    return columns


def _merge_min_max_pairs(columns: list[dict]) -> list[dict]:
    """#1848 A1 (PO-Entscheid 2026-08-20, AC-4..AC-8): sind fuer dieselbe
    Groesse Tief UND Hoch gewaehlt (``kind == "range"``), werden die beiden
    Spalten zu EINER Spannen-Spalte (``field_min``/``field_max`` statt
    ``field``) zusammengefuehrt -- Schraegstrich-Zelle statt zweier Spalten
    mit Minimum-/Maximum-Suffix. Loest fuer diesen Fall die rein paarbasierte
    Soll-Menge aus Epic #1703 Scheibe 2 ab (Gegenzahl:
    ``tests/helpers/outlook_columns.py::_merge_min_max_soll``, dieselbe
    Regel). Alles andere bleibt additiv unveraendert: nur eine Auswertung
    gewaehlt (AC-5), ordinal/enum-Groessen, oder mehr als zwei Auswertungen
    einer Groesse (z. B. kuenftiges ``avg`` bei Temperatur, A3) -- dann
    greift weiterhin die bestehende Minimum-/Maximum-Disambiguierung
    unveraendert."""
    by_metric: dict[str, dict[str, int]] = {}
    for i, col in enumerate(columns):
        if col.get("kind") == "range" and col.get("aggregation") in ("min", "max"):
            by_metric.setdefault(col["metric_id"], {})[col["aggregation"]] = i

    merge_at: dict[int, int] = {}
    consumed: set[int] = set()
    for aggs in by_metric.values():
        if "min" in aggs and "max" in aggs:
            first_idx, second_idx = sorted((aggs["min"], aggs["max"]))
            merge_at[first_idx] = second_idx
            consumed.add(second_idx)

    merged: list[dict] = []
    for i, col in enumerate(columns):
        if i in consumed:
            continue
        if i not in merge_at:
            merged.append(col)
            continue
        partner = columns[merge_at[i]]
        lo = col if col["aggregation"] == "min" else partner
        hi = col if col["aggregation"] == "max" else partner
        merged.append({
            "label": col["label"],
            "metric_id": col["metric_id"],
            "field_min": lo["field"],
            "field_max": hi["field"],
            "unit": col.get("unit", ""),
            "decimals": col.get("decimals", 0),
            "kind": "range",
            "aggregation_label": "",
        })
    return merged


def format_outlook_value(value: object, column: dict) -> str:
    """Zellentext einer Ausblick-Spalte.

    Nicht-numerische Groessen nutzen DIESELBEN deutschen Labels wie die
    Uebersichtstabelle derselben Mail (``_fmt_thunder``/``_fmt_precip_type``)
    -- keine zweite Label-Tabelle. Der Compare-Katalog kennt genau einen
    ordinalen (Gewitter) und genau einen Enum-Eintrag (Niederschlagsart).

    Issue #1475 Nachbesserung (Punkt 5b, Aufrufstelle 4): traegt ``column``
    den Schluessel ``"hail"``, wird er an ``_fmt_thunder`` durchgereicht --
    ohne den Schluessel bleibt die Zelle zeichengleich zum bisherigen Stand.

    Issue #1680 S5a (AC-11b): ``"signals"`` folgt exakt derselben Bauart --
    dritter Parameter von ``_fmt_thunder``, additiv, ohne den Schluessel
    zeichengleich.
    """
    from output.renderers.email.compare_html import _fmt_precip_type, _fmt_thunder

    if value is None:
        return "–"
    kind = column.get("kind")
    if kind == "ordinal":
        return _fmt_thunder(value, column.get("hail"), column.get("signals"))
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


def format_outlook_range_cell(raw_min: object, raw_max: object, column: dict) -> str:
    """Tief/Hoch-Zelle einer zusammengefuehrten Spannen-Spalte (#1848 A1,
    AC-4/AC-6/AC-7/AC-8) -- ASCII-Schraegstrich, kein Leerzeichen,
    vorhandenes Minuszeichen bleibt an der Trennstelle erhalten
    (``"-12/-4"``). Kein Einheiten-Suffix in der Zelle selbst (anders als
    die feste Altform, AC-9).

    Sind BEIDE Seiten vorhanden, ist die Reihenfolge Tief/Hoch (``"9/27"``).
    Fehlt EINE Seite (Datenluecke, nicht Konfigurationsauswahl -- die bleibt
    Einzelwert, AC-5), zeigt die Zelle PO-Vorgabe-konform die vorhandene
    Seite zuerst und ``"-"`` fuer die fehlende (``"13/-"``, spec-woertlich
    "zeigt die Zelle die vorhandene Seite und '-' fuer die fehlende") --
    NICHT die feste Tief/Hoch-Position mit einer Luecke."""
    decimals = column.get("decimals") or 0

    def _num(value: object) -> str | None:
        if value is None:
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return str(value)
        return f"{number:.{int(decimals)}f}"

    min_str, max_str = _num(raw_min), _num(raw_max)
    if min_str is not None and max_str is not None:
        return f"{min_str}/{max_str}"
    if min_str is not None:
        return f"{min_str}/-"
    if max_str is not None:
        return f"{max_str}/-"
    return "-/-"


__all__ = [
    "resolve_outlook_metrics",
    "resolve_trip_outlook_metrics",
    "outlook_columns",
    "format_outlook_value",
    "format_outlook_range_cell",
]
