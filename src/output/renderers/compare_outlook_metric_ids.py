"""Aufloeser fuer die Ausblick-Spaltenauswahl des Ortsvergleichs (#1361/#1368).

Struktureller Zwilling zu ``compare_hourly_metric_ids.py``. Gespeichert wird
seit #1848 A2 die reine KENNUNG (``"temperature"``) -- dasselbe Vokabular, das
Kanal-An/Aus, Reihenfolge, SMS-Kuerzel und Schwellwerte ohnehin benutzen. Die
Auswertungen leitet der Katalog ab (``derived_aggregations()``); die
Paar-Altform (``{"metric_id": ..., "aggregation": ...}``, ADR-0037) bleibt
dauerhaft lesbar. Kein viertes Vokabular, keine zweite Uebersetzungstabelle:
die Existenzpruefung laeuft ueber ``compare_metric_catalog.key_for()``, der
Feldbezug ueber ``metric_catalog.MetricDefinition.summary_fields``.

SPEC: docs/specs/modules/issue_1361_1368_ausblick_konfigurierbar.md
      docs/specs/modules/feat_1848_a2_ausblick_kennungen.md
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


def derived_aggregations(metric_id: object) -> list[str]:
    """Kennung -> die Auswertungen, die der Ausblick daraus zeigt (#1848 A2).

    Die Ableitungsregel der Spec, an genau EINER Stelle::

        Kennung => alle Auswertungen aus available_aggregations(kennung),
                   die eine Zeile im Compare-Katalog haben (key_for != None),
                   in der Reihenfolge von available_aggregations()

    🔴 Quelle ist ``available_aggregations()``, NICHT ``summary_fields``:
    ``precipitation`` und ``thunder`` fuehren dort zusaetzlich ``onset``, und
    ``summary_field_for('precipitation','onset')`` loest sehr wohl auf --
    ueber ``summary_fields`` abgeleitet entstuenden also ``onset``-Spalten.
    ``available_aggregations()`` filtert gegen ``_AGGREGATION_ORDER`` und
    laesst ``onset`` fallen.

    Streng deterministisch und reihenfolgestabil (kein ``set``, keine
    Dict-Iteration): Kopfzeile und Wertzeilen der vier Renderer entstehen aus
    ZWEI getrennten ``outlook_columns()``-Aufrufen und sind nur ueber den
    Listenindex verbunden -- eine schwankende Reihenfolge verschoebe Werte
    gegen Beschriftungen, still und ohne Ausnahme.
    """
    from app.metric_catalog import available_aggregations

    return [a for a in available_aggregations(metric_id)
            if _catalog_entry(metric_id, a) is not None
            and _summary_field(metric_id, a) is not None]


def resolve_outlook_metrics(outlook_metrics: object) -> list[str] | None:
    """Gespeicherte Auswahl -> geordnete, gueltige Kennungen (#1848 A2).

    Drei-Werte-Semantik (ADR-0037/ADR-0055), jetzt mit sauber getrenntem
    drittem Fall:

    * ``None`` -- Feld fehlt ODER die gespeicherte Auswahl ist zwar gefuellt,
      aber KEIN Eintrag laesst sich aufloesen. Beides heisst "keine
      verwertbare Auswahl" und faellt auf die bisherigen sieben festen
      Spalten zurueck.
    * ``[]`` -- die Auswahl ist ausdruecklich leer ("leer heisst leer", analog
      #1366): der Aufrufer schaltet den Ausblick-Block ab.
    * gefuellt -- die gueltigen Kennungen in Auswahlreihenfolge.

    🔴 Warum der zweite Fall NICHT ``[]`` liefern darf (M5/R-A2-3): ``[]``
    bedeutet "bewusst geleert" und schaltet den Block ab. Eine gefuellte, aber
    unverstandene Auswahl (Altbestand nach Rueckroll, Tippfehler, entfernte
    Groesse) liesse den 3-Tages-Ausblick damit kommentarlos VERSCHWINDEN statt
    auf die Standardspalten zurueckzufallen -- nicht als Fehler sichtbar,
    sondern als stille Abwesenheit. "Unaufloesbar" und "bewusst geleert"
    duerfen nie denselben Zustand erzeugen.

    Verworfene Eintraege werden per ``logger.warning`` sichtbar gemacht
    (#1361 Befund 3); die Reihenfolge bleibt erhalten (kein ``set``).
    """
    from app.metric_catalog import normalize_outlook_metric_ids

    kennungen = normalize_outlook_metric_ids(outlook_metrics)
    if kennungen is None:
        return None

    resolved: list[str] = []
    dropped: list[str] = []
    for metric_id in kennungen:
        (resolved if derived_aggregations(metric_id) else dropped).append(metric_id)

    if dropped:
        logger.warning(
            "resolve_outlook_metrics: %s ohne Katalog-Entsprechung — Eintrag "
            "wird verworfen statt angezeigt (vgl. #1361 Befund 3)", dropped,
        )
    if outlook_metrics and not resolved:
        logger.warning(
            "resolve_outlook_metrics: kein Eintrag von %s war aufloesbar — "
            "Rueckfall auf die sieben festen Ausblick-Spalten statt Block aus "
            "(#1848 A2: unaufloesbar ist NICHT bewusst geleert)",
            outlook_metrics,
        )
        return None
    return resolved


def resolve_trip_outlook_metrics(dc: object, report_type: str) -> list[str] | None:
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
    unberuehrt: ``None`` (Feld fehlt ODER nichts aufloesbar, #1848 A2) bleibt
    ``None``, ``[]`` (bewusst geleert) bleibt ``[]`` -- der Schnitt wirkt nur
    auf einer bereits aufgeloesten, nicht-leeren Liste.

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
    return [metric_id for metric_id in resolved if metric_id in allowed]


def outlook_columns(metrics: object) -> list[dict]:
    """Auswahl -> geordnete Spalten-Beschreibung fuer den Ausblick-Renderer.

    ``label`` kommt aus dem Compare-Katalog (deutsch, seit #1401 A1 der Name
    des zentralen Registers), NICHT aus ``MetricDefinition.col_label``: dessen
    Kuerzel sind englisch ("Rain"/"Thdr"/"PType") und fuer temperature
    min/max/avg IDENTISCH ("Temp") -- zwei gewaehlte Temperatur-Auswertungen
    ergaeben zwei gleich beschriftete Spalten (Abweichung zur Spec,
    PO-Entscheidung 2026-07-27).

    #1401 A1: die Auswertung ist kein Namensbestandteil mehr. Eine Tabellen-
    spalte traegt aber genau EINEN String -- traegt eine Groesse mehr als eine
    darstellbare Auswertung und werden die nicht ohnehin zur Spannen-Spalte
    zusammengefuehrt (z. B. ein kuenftiges ``temperature/avg``, A3), bekommen
    genau diese Spalten die Auswertung angehaengt, damit die PO-Vorgabe "keine
    zwei gleich beschrifteten Spalten" erhalten bleibt.

    #1848 A2: die Eingabe sind KENNUNGEN; welche Auswertungen daraus Spalten
    werden, entscheidet ``derived_aggregations()`` -- der Katalog, nicht die
    gespeicherte Auswahl. Die Paar-Altform wird weiterhin angenommen (auf ihre
    Kennung reduziert), damit ein direkter Aufruf mit Bestandsdaten nicht
    stillschweigend leer laeuft."""
    from app.metric_catalog import normalize_outlook_metric_ids

    columns: list[dict] = []
    dropped: list[str] = []
    for metric_id in normalize_outlook_metric_ids(metrics) or []:
        aggregations = derived_aggregations(metric_id)
        if not aggregations:
            dropped.append(metric_id)
            continue
        for aggregation in aggregations:
            catalog = _catalog_entry(metric_id, aggregation)
            columns.append({
                "label": catalog["label"],
                "metric_id": metric_id,
                "aggregation": aggregation,
                "field": _summary_field(metric_id, aggregation),
                "unit": catalog.get("unit", ""),
                "decimals": catalog.get("decimals", 0),
                "kind": catalog.get("kind", "range"),
                "aggregation_label": catalog.get("aggregation_label", ""),
            })
    if dropped:
        # #1848 A2: die Verwerfung war hier bislang STUMM -- eine Spalte
        # verschwand ohne jede Spur. Sie hat dieselbe Ursache wie die im
        # Aufloeser und gehoert genauso protokolliert.
        logger.warning(
            "outlook_columns: %s ohne Katalog-Entsprechung — Spalte entfaellt "
            "(vgl. #1361 Befund 3)", dropped,
        )
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
    "derived_aggregations",
    "resolve_outlook_metrics",
    "resolve_trip_outlook_metrics",
    "outlook_columns",
    "format_outlook_value",
    "format_outlook_range_cell",
]
