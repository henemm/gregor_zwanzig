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

from i18n import Lang
from output.metric_format import NO_VALUE

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
            "resolve_outlook_metrics: kein Eintrag von %s war aufloesbar — "  # i18n-log
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
    * ``grundauswahl is None`` -- kein Maximum definiert (Altbestand ohne
      Grundauswahl): kein Schnitt, Altverhalten. ``None`` faellt weiterhin auf
      die sieben festen Spalten zurueck.
    * ``grundauswahl == []`` -- bewusst leere Grundauswahl: die Liste nimmt
      nur aus den Metriken oben, ist also leer, der Block entfaellt (#3047 N2,
      Konzept §5.8; hebt "leer = kein Maximum" (ADR-0050 D4) fuer den Ausblick
      auf -- Trip und Ortsvergleich gleich).
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
    if gespeichert == [] or grundauswahl == []:
        return []
    if grundauswahl is None:
        return gespeichert
    if gespeichert is None:
        return list(grundauswahl)
    aktiv = [metric_id for metric_id in gespeichert if metric_id in grundauswahl]
    if aktiv:
        return aktiv
    logger.warning(
        "Ausblick: keine Groesse aus %s liegt in der %s (%s) — Rueckfall auf "  # i18n-log
        "die volle Grundauswahl statt Block aus (#1848 A3: unaufloesbar ist "
        "NICHT bewusst geleert)", gespeichert, herkunft, grundauswahl,
    )
    return list(grundauswahl)


def _kennungen_aus_renderer_ids(renderer_ids: list[str]) -> list[str]:
    """Renderer-Kennungen der Uebersicht -> Katalog-Kennungen des Ausblicks.

    Der Umkehr-Index wird aus dem Compare-Katalog GERECHNET (``key`` ->
    ``metric_id``) statt getippt -- eine zweite Uebersetzungstabelle waere
    genau das vierte Vokabular, das ``compare_metric_ids`` vermeidet. Mehrere
    Auswertungen derselben Groesse fallen dabei auf dieselbe Kennung zusammen;
    die Reihenfolge des ersten Vorkommens bleibt erhalten.
    """
    from output.renderers.compare_metric_ids import katalog_paar

    paare = [katalog_paar(r) for r in renderer_ids]
    return [p[0] for p in paare if p is not None]


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

    ``label`` kommt seit #2136/ADR-0068 aus ``MetricDefinition.col_label``
    (dieselbe Quelle, aus der die Stunden-/Etappentabelle derselben Mail ihre
    Spaltenkoepfe zieht, ``get_col_defs()`` -> ``visible_cols()``), NICHT mehr
    aus dem deutschen Langnamen des Compare-Katalogs. Der fruehere Einwand
    (ADR-0037, 2026-07-27: ``temperature`` liefert fuer min/max/avg identisch
    "Temp") ist durch die seither gebaute Merge-/Dedup-Mechanik entkraeftet --
    ``_merge_min_max_pairs()`` fuehrt Tief+Hoch zu einer Spannen-Spalte
    zusammen, die Duplikat-Suffix-Schleife unten haengt einem verbleibenden
    Restkollisionsfall (z. B. zusaetzliches Avg) ``aggregation_label_de()``
    an -- beide Mechaniken arbeiten generisch auf ``column["label"]``,
    unabhaengig von dessen Quelle.

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
                "label": catalog["col_label"],
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


def _friendly_outlook_text(
    metric_id: object, number: float, lang: Lang = "de",
) -> str | None:
    """Einfach-Form eines TAGESwerts (Ausblick, Orte-Uebersicht) oder ``None``
    (= die Groesse hat dort keine Einfach-Form, Issue #2049).

    Seit #3260 S1b (ADR-0127 Nr. 2) kommen Form und Wort allein aus
    ``metric_format.darstellung`` (Katalog ``form``/``WORTSKALA``, Wertart
    ``tag``: Niederschlag nach der Tagessummen-Skala); die if-Kette je Kennung
    ist entfallen. Textfassung (Klartext/Telegram)."""
    from output.metric_format import darstellung

    if not isinstance(metric_id, str):
        return None
    zelle = darstellung(metric_id, number, stelle="outlook", ausgabeart="text",
                        fmt="simplified", ampel=None, wertart="tag", lang=lang)
    return None if zelle.form == "zahl" else zelle.text


def resolve_hourly_metric_formats(stored: object) -> dict[str, bool] | None:
    """Orte-Stundenverlauf: ``display_config.hourly_metric_formats`` (#3097,
    ADR-0121 Nachtrag 3b) -> ``{kennung: bool}``; ``None`` = nie eingestellt.

    Nur boolesche Werte zaehlen (wahr = Einfach, ausdruecklich falsch = Roh),
    und nur fuer Groessen mit zwei Formen an der Stelle ``hourly`` der Quelle
    ``zwei_formen_stellen`` (#3156): Sonnenstunden (gesperrt) und Windrichtung
    (immer Kompass) fallen heraus."""
    from app.metric_catalog import zwei_formen_stellen

    if not isinstance(stored, dict):
        return None
    return {k: v for k, v in stored.items()
            if isinstance(v, bool) and "hourly" in zwei_formen_stellen(k)}


def outlook_zellen(
    value: object, column: dict, *, lang: Lang = "de", ampel: dict,
) -> dict[str, str]:
    """Eine Ausblick-Zelle je Ausgabeart (#3260 S1b, Spec Nr. 4): ``text``
    (Nur-Text, Telegram), ``html`` (fertiger, escapter Zellinhalt, bei Einfach
    ggf. der Ampelpunkt) und ``ascii`` (Kompakt-Mail). Die Form waehlt allein
    ``metric_format.darstellung`` aus dem Katalog."""
    import html as _html

    text = format_outlook_value(value, column, lang=lang)
    aus = {"text": text, "html": _html.escape(text), "ascii": text}
    for art in ("html", "ascii"):
        zelle = _einfach_zelle(value, column, lang=lang, ausgabeart=art, ampel=ampel)
        if zelle is not None:
            aus[art] = zelle.html if art == "html" else zelle.text
    return aus


def format_outlook_value(
    value: object, column: dict, *, lang: Lang = "de",
) -> str:
    """Zellentext (Nur-Text/Telegram) einer Ausblick-Spalte; die HTML- und
    ASCII-Fassung liefert ``outlook_zellen``.

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

    ``lang`` (Issue #2750): Wortskalen, Gewitter- und Niederschlagsart-Wort
    in Nutzersprache; ohne ``lang`` deutsch (byte-gleich zum Bestand).
    """
    zelle = _einfach_zelle(value, column, lang=lang, ausgabeart="text", ampel=None)
    return zelle.text if zelle is not None else _outlook_text(value, column, lang=lang)


def _einfach_zelle(value: object, column: dict, *, lang: Lang, ausgabeart: str,
                   ampel: dict | None):
    """#3260 S1b (loest #2049 AC-6 ab): Einfach waehlt die Form je Ausgabeart
    allein ``darstellung`` -- HTML Ampelpunkt bzw. Symbol, Nur-Text und
    Telegram Wort/Symbol, Kompakt (ASCII) Wort statt Emoji-Kurzname.
    ``None`` = Roh bzw. nicht numerisch (eigene Zellformatierung)."""
    from output.metric_format import darstellung

    metric_id = column.get("metric_id")
    if (value is None or column.get("friendly") is not True
            or column.get("kind") in ("ordinal", "enum") or not isinstance(metric_id, str)):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    zelle = darstellung(metric_id, number, stelle="outlook", ausgabeart=ausgabeart,
                        fmt="simplified", ampel=ampel, wertart="tag", lang=lang)
    if zelle.form != "zahl":
        return zelle
    logger.warning(
        "format_outlook_value: %r ist als Einfach markiert, hat hier aber "  # i18n-log
        "keine Wortform — Rueckfall auf die Rohzahl. Faehigkeitsliste "
        "(metric_catalog.OUTLOOK_FRIENDLY_CAPABLE) und Formtabelle "
        "(metric_catalog.STELLEN_FORMEN) sind auseinandergelaufen (#2049 AC-4).",
        metric_id,
    )
    return None


def _outlook_text(value: object, column: dict, *, lang: Lang) -> str:
    from output.renderers.email.compare_html import _fmt_precip_type, _fmt_thunder

    if value is None:
        return NO_VALUE
    kind = column.get("kind")
    if kind == "ordinal":
        return _fmt_thunder(
            value, column.get("hail"), column.get("signals"), lang=lang)
    if kind == "enum":
        return _fmt_precip_type(value, lang=lang)
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
    "outlook_grundauswahl_ids",
    "resolve_outlook_metrics",
    "resolve_hourly_metric_formats",
    "outlook_columns",
    "format_outlook_value",
    "format_outlook_range_cell",
]
