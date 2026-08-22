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


def outlook_grundauswahl_ids(metric_ids: object) -> list[str]:
    """Grundauswahl-Kennungen -> die davon im Ausblick DARSTELLBAREN (#1848 A3).

    Reihenfolge der Eingabe, jede Kennung hoechstens einmal. Groessen ohne
    Tagesauswertung (kein Compare-Katalog-Paar mit ``SegmentWeatherSummary``-
    Feld, z. B. ``confidence``) fallen heraus: sie haetten in der Tagestabelle
    keinen darstellbaren Wert und stehen deshalb auch nicht in der
    "Aus"-Gruppe (Spec "Known Limitations").
    """
    gesehen: set[str] = set()
    ergebnis: list[str] = []
    for metric_id in metric_ids or ():
        if metric_id in gesehen or not derived_aggregations(metric_id):
            continue
        gesehen.add(metric_id)
        ergebnis.append(metric_id)
    return ergebnis


def _erbe_grundauswahl(
    gespeichert: list[str] | None, grundauswahl: list[str] | None, herkunft: str,
) -> list[str] | None:
    """ADR-0050 Regeln 1/2/4 auf die Ausgabeflaeche "Ausblick" (#1848 A3).

    EINE Umsetzung fuer beide Flaechen -- Trip und Ortsvergleich reichen nur
    ihre je eigene Grundauswahl herein (Trip/Compare-Teilungs-Invariante).
    Der Ausblick verhaelt sich damit wie ein Kanal: die Grundauswahl ist die
    Ausgangsmenge, die gespeicherte Auswahl darf davon nur ABWAEHLEN.

    * ``gespeichert == []`` -- bewusst geleert, der Block entfaellt ganz
      (AC-11, unveraendert).
    * ``grundauswahl`` leer/``None`` -- kein Maximum definiert (ADR-0050 D4):
      kein Schnitt, Altverhalten. ``None`` faellt weiterhin auf die sieben
      festen Spalten zurueck.
    * ``gespeichert is None`` -- nie etwas eingestellt heisst "nichts
      abgewaehlt": die GANZE Grundauswahl (AC-3), nicht die frueheren sieben
      festen Spalten.
    * sonst der Schnitt: eine in der Grundauswahl abgewaehlte Groesse
      erscheint nie, egal was gespeichert ist (AC-4/AC-6).

    🔴 Bleibt nach dem Schnitt NICHTS uebrig, ist das NICHT ``[]`` (AC-10):
    ``[]`` heisst "bewusst geleert" und laesst den Block bei
    ``html.py:1356``/``plain.py:314`` kommentarlos verschwinden. Eine
    gespeicherte, aber vollstaendig ausserhalb der Grundauswahl liegende
    Auswahl (Altbestand, geaenderte Grundauswahl) faellt stattdessen auf die
    volle Grundauswahl zurueck -- sichtbar protokolliert. "Unaufloesbar" und
    "bewusst geleert" duerfen nie denselben Zustand erzeugen.
    """
    if gespeichert == []:
        return []
    if not grundauswahl:
        return gespeichert
    if gespeichert is None:
        return list(grundauswahl)
    aktiv = [metric_id for metric_id in gespeichert if metric_id in grundauswahl]
    if aktiv:
        return aktiv
    logger.warning(
        "Ausblick: keine Groesse aus %s liegt in der %s (%s) — Rueckfall auf "
        "die volle Grundauswahl statt Block aus (#1848 A3: unaufloesbar ist "
        "NICHT bewusst geleert)", gespeichert, herkunft, grundauswahl,
    )
    return list(grundauswahl)


def resolve_trip_outlook_metrics(dc: object, report_type: str) -> list[str] | None:
    """Trip-Vorschau: die Grundauswahl ist die Ausgangsmenge (#1720 S1/#1848 A3).

    Grundauswahl-Quelle ist dieselbe gemeinsame Funktion wie beim Kanal-Layout:
    ``UnifiedWeatherDisplayConfig.allowed_metric_ids_for_report_type()``
    (ADR-0050 Regel 1/2 auf die Ausgabeflaeche "Vorschau" ausgeweitet,
    PO-Entscheid 2026-08-14; EINE Quelle seit #1848 Scheibe A). ``dc.metrics``
    liefert dazu nur die REIHENFOLGE -- ueber die Zugehoerigkeit entscheidet
    allein die gemeinsame Quelle.

    #1848 A3: ``None`` (nie eingestellt) heisst nicht mehr "sieben feste
    Spalten", sondern "nichts abgewaehlt" -> die ganze Grundauswahl. Die
    Regelanwendung selbst steht in ``_erbe_grundauswahl()``, gemeinsam mit dem
    Ortsvergleich.

    🔴 ``dc`` MUSS der ungekollabierte Stand sein: geschnitten wird gegen die
    kanal-neutrale ``get_metrics_for_report_type()``, denn der Ausblick hat
    bewusst KEINE Kanal-Ebene (AC-17). Ein enges
    ``per_channel_layouts["email"]`` (#429) darf eine global aktive, gewaehlte
    Groesse nicht aus der Vorschau schneiden (Adversary-Finding F001).
    """
    gespeichert = resolve_outlook_metrics(getattr(dc, "outlook_metrics", None))
    allowed = dc.allowed_metric_ids_for_report_type(report_type)
    grundauswahl = None if allowed is None else outlook_grundauswahl_ids(
        [mc.metric_id for mc in getattr(dc, "metrics", None) or ()
         if mc.metric_id in allowed]
    )
    return _erbe_grundauswahl(gespeichert, grundauswahl, "Trip-Grundauswahl")


def resolve_compare_outlook_metrics(
    outlook_metrics: object, enabled_metrics: list[str] | None,
) -> list[str] | None:
    """Ortsvergleich-Ausblick: dieselbe Kopplung wie im Trip (#1848 A3, AC-6).

    ``enabled_metrics`` ist die bereits aufgeloeste Grundauswahl der
    Uebersichtstabelle (``resolve_enabled_metrics(active_metrics)``, Renderer-
    Kennungen) -- dieselbe Menge, die seit #1703 Scheibe 8 schon als MAXIMUM
    fuer die Kanal-Auswahl dient. ``None`` (Feld fehlt, Altbestand) heisst
    weiterhin "kein Maximum definiert" und schneidet nicht.

    Loest ADR-0053 Punkt 1 ab ("Ausblick bleibt bewusst ohne Kaskadenbindung"):
    die Bindung gilt ab dieser Scheibe in BEIDEN Flaechen gleich.
    """
    gespeichert = resolve_outlook_metrics(outlook_metrics)
    grundauswahl = None if enabled_metrics is None else outlook_grundauswahl_ids(
        _kennungen_aus_renderer_ids(enabled_metrics)
    )
    return _erbe_grundauswahl(gespeichert, grundauswahl, "Ortsvergleich-Grundauswahl")


def _kennungen_aus_renderer_ids(renderer_ids: list[str]) -> list[str]:
    """Renderer-Kennungen der Uebersicht -> Katalog-Kennungen des Ausblicks.

    Der Umkehr-Index wird aus dem Compare-Katalog GERECHNET (``key`` ->
    ``metric_id``) statt getippt -- eine zweite Uebersetzungstabelle waere
    genau das vierte Vokabular, das ``compare_metric_ids`` vermeidet. Mehrere
    Auswertungen derselben Groesse fallen dabei auf dieselbe Kennung zusammen;
    die Reihenfolge des ersten Vorkommens bleibt erhalten.
    """
    from output.renderers.compare_metric_catalog import get_compare_metric_catalog
    from output.renderers.compare_metric_ids import FRONTEND_TO_RENDERER_METRIC_ID

    umkehr: dict[str, str] = {}
    for eintrag in get_compare_metric_catalog():
        renderer_id = FRONTEND_TO_RENDERER_METRIC_ID.get(eintrag["key"])
        if renderer_id is not None:
            umkehr.setdefault(renderer_id, eintrag["metric_id"])
    return [umkehr[r] for r in renderer_ids if r in umkehr]


def resolve_trip_outlook_formats(dc: object) -> dict[str, bool] | None:
    """Trip-Vorschau: die Roh/Einfach-Zuordnung je Groesse (#2049).

    Bewusst eine EIGENE Funktion neben ``resolve_trip_outlook_metrics()``
    statt eines zweiten Rueckgabewerts: jene Funktion hat mehrere Aufrufer
    (Renderer wie Zeilenbau), die ausschliesslich die Kennungsliste brauchen.

    Der Ausblick hat keine Kanal-Ebene (ADR-0055 Punkt 2) und keinen
    Report-Typ-Bezug -- die Zuordnung gilt global je Flaeche, es gibt also
    nichts zu kaskadieren. ``None`` (nie eingestellt) heisst "alles Roh".
    """
    from app.metric_catalog import normalize_outlook_metric_formats

    return normalize_outlook_metric_formats(
        getattr(dc, "outlook_metric_formats", None))


def resolve_compare_outlook_formats(
    outlook_metric_formats: object,
) -> dict[str, bool] | None:
    """Ortsvergleich-Ausblick: dieselbe Regel wie im Trip (#2049).

    Die Ortsvergleichs-Konfiguration ist ein roher ``display_config``-Dict
    (kein Dataclass wie beim Trip) -- deshalb nimmt diese Funktion den
    gespeicherten Wert direkt entgegen statt ein Traegerobjekt. Die Regel
    selbst ist EINE (``normalize_outlook_metric_formats``), damit die beiden
    Flaechen nicht auseinanderlaufen koennen.
    """
    from app.metric_catalog import normalize_outlook_metric_formats

    return normalize_outlook_metric_formats(outlook_metric_formats)


def outlook_columns(metrics: object, formats: object = None) -> list[dict]:
    """Auswahl -> geordnete Spalten-Beschreibung fuer den Ausblick-Renderer.

    ``formats`` (#2049): Roh/Einfach-Zuordnung ``{kennung: bool}``. Jede Spalte
    einer auf Einfach gestellten UND ausblick-faehigen Groesse traegt
    ``"friendly": True``; ``format_outlook_value()`` verzweigt daran. Der
    Default ist hart Roh -- ohne ``formats`` (oder ohne Eintrag) entsteht das
    Feld gar nicht erst, die Spalten bleiben damit zeichengleich zum bisherigen
    Stand (AC-2/AC-12). Eine nicht-faehige Kennung bekommt das Feld NIE, auch
    wenn ein Flag gespeichert ist (AC-4: Sichtbarkeit und Wirkung haengen an
    derselben Faehigkeitsliste).

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
    from app.metric_catalog import (
        normalize_outlook_metric_formats, normalize_outlook_metric_ids,
    )

    # Die Normalisierung filtert nicht-faehige Kennungen bereits heraus --
    # derselbe Ladepfad-Helfer wie in `loader.py`, keine zweite Regel hier.
    friendly_ids = normalize_outlook_metric_formats(formats) or {}
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
                # Rein additiv: nur die auf Einfach gestellten Spalten
                # bekommen ueberhaupt einen Schluessel (AC-12).
                **({"friendly": True} if friendly_ids.get(metric_id) else {}),
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
            # #2049 (AC-11): diese Funktion baut ein NEUES Dict und kopiert nur
            # die hier gelisteten Schluessel -- ohne diese Zeile ginge das
            # Roh/Einfach-Flag beim Zusammenfuehren still verloren. Additiv wie
            # oben: fehlt es, entsteht der Schluessel nicht.
            **({"friendly": True} if col.get("friendly") else {}),
        })
    return merged


_FRIENDLY_CLOUD_IDS = ("cloud_total", "cloud_low", "cloud_mid", "cloud_high")


def _friendly_outlook_text(metric_id: object, number: float) -> str | None:
    """Wort-/Symbolform einer Ausblick-Groesse oder ``None`` (Issue #2049).

    Wiederverwendung statt Parallel-Logik (AC-10): Himmelsrichtung, Wolken-
    symbol und Wind-/Boeen-Wortstufe kommen aus den bestehenden Helfern, die
    dieselbe Aussage anderswo im Produkt schon treffen. Neu sind allein die
    drei Skalen, fuer die es bisher gar keine Wortform gab -- und die
    Niederschlags-Skala ist bewusst die TAGESSUMMEN-Skala, nicht die
    Stundenskala ``format_precip_intensity`` (AC-9).

    Die Schluesselmenge dieser Verzweigung ist ``OUTLOOK_FRIENDLY_CAPABLE``
    (app.metric_catalog) -- dieselbe Liste, an der das Frontend die
    Sichtbarkeit des Umschalters festmacht (AC-4).
    """
    from output.metric_format import cloud_emoji
    from services.weather_metrics import (
        format_precip_daily_sum, format_rain_probability_scale,
        format_sunshine_scale, format_wind_strength,
    )
    from utils.geo import degrees_to_compass

    if metric_id == "wind_direction":
        return degrees_to_compass(number)
    if metric_id in _FRIENDLY_CLOUD_IDS:
        return cloud_emoji(number)
    if metric_id in ("wind", "gust"):
        return format_wind_strength(number)
    if metric_id == "precipitation":
        return format_precip_daily_sum(number)
    if metric_id == "rain_probability":
        return format_rain_probability_scale(number)
    if metric_id == "sunshine":
        return format_sunshine_scale(number)
    return None


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
    # #2049: "Einfach" heisst im Ausblick DIESELBE Zeichenkette in allen vier
    # Ausgabeorten -- `stage["cells"]` ist ein geteilter Kanal fuer HTML und
    # Text, ein HTML-Ampelpunkt erschiene in Klartext und Telegram als
    # Quelltext (AC-6). Die Ampel traegt die HTML-Zelle ohnehin als
    # Hintergrundtoenung (`_metric_column_bg`, unabhaengig von diesem Flag).
    if column.get("friendly") is True:
        friendly = _friendly_outlook_text(column.get("metric_id"), number)
        if friendly is not None:
            return friendly
        logger.warning(
            "format_outlook_value: %r ist als Einfach markiert, hat hier aber "
            "keine Wortform — Rueckfall auf die Rohzahl. Faehigkeitsliste "
            "(metric_catalog.OUTLOOK_FRIENDLY_CAPABLE) und Verzweigung "
            "(_friendly_outlook_text) sind auseinandergelaufen (#2049 AC-4).",
            column.get("metric_id"),
        )
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
    "outlook_grundauswahl_ids",
    "resolve_outlook_metrics",
    "resolve_compare_outlook_metrics",
    "resolve_compare_outlook_formats",
    "resolve_trip_outlook_metrics",
    "resolve_trip_outlook_formats",
    "outlook_columns",
    "format_outlook_value",
    "format_outlook_range_cell",
]
