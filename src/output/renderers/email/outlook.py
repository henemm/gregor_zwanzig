"""Geteilter Ausblick-Baustein (Trip UND Compare) — Epic #1301 B4.

Extrahiert aus ``html.py`` (Ausblick-Tabelle), ``plain.py`` (Klartext-Block)
und ``trip_report_scheduler.py`` (Zeilenbau), damit Compare denselben
Renderer/Zeilenbau ruft statt einer eigenen Kopie (Trip/Compare-Teilungs-
Invariante, CLAUDE.md; Anti-Pattern-Referenz #1170).

SPEC: docs/specs/modules/epic_1301_b4_compare_outlook.md AC-1..AC-3, AC-6, AC-8

``render_outlook_table(rows, show_acc=True)`` und
``render_outlook_plain(rows, show_acc=True)`` sind fuer ``show_acc=True``
byte-/zeichengleich zum bisherigen Inline-Verhalten (Trip-Default) --
``show_acc=False`` laesst NUR die ACC-Kopfzelle/-Datenzelle strukturell
entfallen (Compare-Ausblick, ADR-0005/#710: Confidence keine per-Ort-Metrik).

``build_outlook_row(summary, points, weekday, tz, *, sms_thresholds=None)``
ist eine reine Funktion (kein Netz-/Fetch-Aufruf) -- ``summary`` ist eine
``SegmentWeatherSummary``, geliefert von ``aggregate_stage`` (Trip) ODER
``summarize_points`` (Compare); ``points`` die flache Stundenpunktliste fuer
die @-time-Hourly-Samples.
"""
from __future__ import annotations

import html as _html
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from datetime import tzinfo
    from app.models import SegmentWeatherSummary, ForecastDataPoint

from app.metric_catalog import get_metric
from output.renderers.email.helpers import format_trend_tokens
from output.renderers.email.thunder_branch import (
    resolve_thunder_day_branch, thunder_cell_html, thunder_cell_plain,
    thunder_column_index,
)
from output.renderers.email.design_tokens import FONT_DATA, tone_css
from utils.geo import degrees_to_compass


# ---------------------------------------------------------------------------
# ACC-Stufen — EINE Quelle fuer Farbpunkt (HTML) und Wort (Klartext)
# ---------------------------------------------------------------------------

# Issue #2098 Befund C: der Farbpunkt ist im HTML der einzige Informations-
# traeger, im Klartext braucht dieselbe Aussage ein Wort ("HTML=Normalfassung,
# Farbe im HTML ⇒ WORT im Klartext"). Beide lesen dieselben vier Untergrenzen,
# damit Wort und Punkt nicht auseinanderdriften koennen.
# (Untergrenze | None = Restfall, Farbe, Klartext-Wort)
_ACC_STUFEN = (
    (80, "#2f8a3e", "hoch"),
    (60, "#e3b008", "mittel"),
    (40, "#e07b1a", "niedrig"),
    (None, "#c52a22", "sehr niedrig"),
)
_ACC_KEIN_WERT = "–"
ACC_LABEL = "ACC"


def _acc_stufe(conf_pct) -> tuple[str, str] | None:
    """(Farbe, Klartext-Wort) zu einer Prognose-Genauigkeit; ``None`` ohne Wert."""
    try:
        v = float(conf_pct)
    except (TypeError, ValueError):
        return None
    for grenze, farbe, wort in _ACC_STUFEN:
        if grenze is None or v >= grenze:
            return farbe, wort
    return None


def _acc_wort(conf_pct) -> str:
    """Klartext-Entsprechung des ACC-Farbpunkts (#2098 AC-6/AC-11/AC-12)."""
    stufe = _acc_stufe(conf_pct)
    return stufe[1] if stufe else _ACC_KEIN_WERT


# ---------------------------------------------------------------------------
# render_outlook_table — extrahiert aus html.py (Z.1116-1271, AC-1/AC-2)
# ---------------------------------------------------------------------------

def render_outlook_table(
    rows: list[dict], *, show_acc: bool = True, metrics: Optional[list] = None,
) -> str:
    """Rendert die HTML-Ausblick-Tabelle.

    ``show_acc=True`` (Trip-Default) ist byte-identisch zum bisherigen
    Inline-Block in ``render_html``. ``show_acc=False`` (Compare) laesst
    die ACC-<th>-Kopfzelle und die ``_acc_dot``-<td>-Zellen vollstaendig
    entfallen -- alle uebrigen Spalten bleiben unveraendert.

    ``metrics`` (#1361/#1368, nur Compare): gesetzte Auswahl im Neuformat
    ersetzt die festen sieben Spalten durch die gewaehlten, in Auswahl-
    Reihenfolge und mit lesbaren Katalog-Beschriftungen. ``None`` (Trip und
    Compare-Altbestand) laesst die Ausgabe byte-identisch.
    """

    def _outlook_cell_bg(val, thresholds: tuple) -> str:
        """Bestimmt Zell-BG aus Schwellwert-Tupel (caution, warn, danger)."""
        if val is None:
            return ""
        try:
            v = float(val)
        except (TypeError, ValueError):
            return ""
        c, w, d = thresholds
        # Fix #1801 S1: Hex-Werte aus der EINEN Quelle tone_css() statt
        # dreier lokaler Kopien.
        if d is not None and v >= d:
            return f"background:{tone_css('red')[0]};"
        if w is not None and v >= w:
            return f"background:{tone_css('orange')[0]};"
        if c is not None and v >= c:
            return f"background:{tone_css('yellow')[0]};"
        return ""

    def _catalog_thresholds(metric_id: str) -> tuple:
        """Issue #1377 Scheibe B: (caution, warn, danger)-Tupel aus dem
        zentralen Katalog statt hartcodierter Zahlen — derselbe Renderer
        rendert Trip UND Ortsvergleich, diese eine Umstellung schliesst die
        Ausblick-Luecke zwischen beiden Mail-Arten in einem Schritt."""
        t = get_metric(metric_id).display_thresholds
        return (t.get("yellow"), t.get("orange"), t.get("red"))

    def _otd(content: str, *, bg: str = "", align: str = "center") -> str:
        """Outlook-Table-Datenzelle (kompakte inline-styles für Outlook).

        fix-911-table-jsx AC-3: MONO-Font (FONT_DATA) auf Data-Cells.
        """
        return (
            f'<td style="{bg}padding:6px 4px;text-align:{align};'
            f'font-family:{FONT_DATA};'
            f'font-size:11px;border-right:1px solid #f0ece1;'
            f'border-bottom:1px solid #f0ece1;">'
            f'{content}</td>'
        )

    # 4-stufiger ACC-Dot aus confidence_pct
    # hoch>=80=ok, mittel>=60=caution, niedrig>=40=warn, sehr_niedrig<40=danger
    # #2098: Stufen aus `_ACC_STUFEN` -- dieselbe Quelle wie das Klartext-Wort.
    def _acc_dot(conf_pct) -> str:
        stufe = _acc_stufe(conf_pct)
        if stufe is None:
            return _ACC_KEIN_WERT
        color = stufe[0]
        return (
            f'<span style="display:inline-block;width:10px;height:10px;'
            f'border-radius:50%;background:{color};"></span>'
        )

    # thead
    _oh_style = (
        f'style="background:#fff;border-bottom:1px solid #e6e1d3;'
        f'padding:6px 4px;text-align:center;font-family:{FONT_DATA};'
        f'font-size:10px;font-weight:600;color:#3a3835;white-space:nowrap;"'
    )
    # #2098 Befund B: die ACC-Kopfzelle gilt fuer BEIDE Zweige -- der Trip
    # laeuft seit #1848 A3 praktisch immer ueber den konfigurierbaren.
    _acc_th = f'<th {_oh_style}>{ACC_LABEL}</th>' if show_acc else ""
    if metrics is not None:
        from output.renderers.compare_outlook_metric_ids import outlook_columns

        columns = outlook_columns(metrics)
        head = "".join(
            f'<th {_oh_style}>{_html.escape(c["label"])}</th>' for c in columns
        )
        # #1848 A3: die Gewitter-Zelle entsteht aus DEMSELBEN Zellenbau wie im
        # festen Zweig darunter (thunder_cell_html) -- `cells` traegt dort nur
        # das Stufenwort, ohne Onset-Uhrzeit, Nachtanteil, Herkunft und Hagel.
        gew_index = thunder_column_index(columns)
        body = ""
        for stage in rows:
            cells = stage.get("cells") or []
            # Issue #1849: Ampel-Hintergruende parallel zu den Zellentexten.
            cell_bg = stage.get("cell_bg") or []
            texte = [cells[i] if i < len(cells) else "–" for i in range(len(columns))]
            if gew_index is not None:
                texte[gew_index] = thunder_cell_html(format_trend_tokens(stage), stage)
            # #2098 Befund B: ACC HINTER den gewaehlten Spalten -- am
            # `outlook_columns()`/`cells`-Mechanismus vorbei, damit
            # `confidence` nie eine waehlbare Metrik wird (ADR-0005/#710).
            # Kopf- und Datenzelle haengen an DEMSELBEN `show_acc`, ein
            # Auseinanderlaufen von Beschriftung und Wert ist damit
            # ausgeschlossen (AC-10).
            acc_td = (
                _otd(_acc_dot(stage.get("confidence_pct"))) if show_acc else ""
            )
            body += (
                '<tr>' + _otd(stage.get("weekday", "–"))
                + "".join(
                    _otd(_html.escape(text),
                         bg=cell_bg[i] if i < len(cell_bg) else "")
                    for i, text in enumerate(texte)
                )
                + acc_td
                + '</tr>'
            )
        return (
            '<table cellpadding="0" cellspacing="0" '
            'style="border-collapse:collapse;width:100%;'
            'border-top:2px solid #1d1c1a;">'
            f'<thead><tr><th {_oh_style}>Tag</th>{head}{_acc_th}</tr></thead>'
            f'<tbody>{body}</tbody></table>'
        )

    outlook_thead = (
        f'<thead><tr>'
        f'<th {_oh_style}>Tag</th>'
        f'<th {_oh_style}>N</th>'
        f'<th {_oh_style}>D</th>'
        f'<th {_oh_style}>R</th>'
        f'<th {_oh_style}>PR</th>'
        f'<th {_oh_style}>Wind</th>'
        f'<th {_oh_style}>Böen</th>'
        f'<th {_oh_style}>Gew</th>'
        f'{_acc_th}'
        f'</tr></thead>'
    )

    # Fix #1801 S1: MED/HIGH aus tone_css() (EINE Quelle); LOW bleibt bewusst
    # ein abweichender, eigener Gelbton ausserhalb des Ampel-Vokabulars
    # (Spec „Nicht-Ziele").
    _THUNDER_LEVEL_BG = {
        "LOW": "background:#fbe6c3;",
        "MED": f"background:{tone_css('orange')[0]};",
        "HIGH": f"background:{tone_css('red')[0]};",
    }

    outlook_rows = ""
    for stage in rows:
        tokens = format_trend_tokens(stage)
        weekday = stage.get("weekday", "–")
        # F005 (#911): Scheduler schreibt temp_lo/temp_hi (trip_report_scheduler
        # _build_stage_trend). temp_min_c/temp_max_c nur Fallback (Alt-Fixtures).
        # Ohne temp_lo/temp_hi zeigten N/D in der echten Produktionsmail immer „–".
        temp_min = stage.get("temp_lo", stage.get("temp_min_c"))
        temp_max = stage.get("temp_hi", stage.get("temp_max_c"))
        precip_mm = stage.get("precip_mm")
        wind_kmh = stage.get("wind_kmh")
        pr_pct = stage.get("rain_probability_pct")
        conf_pct = stage.get("confidence_pct")
        # Gust aus hourly_gust wenn vorhanden
        hourly_gust = stage.get("hourly_gust") or ()
        gust_kmh = max((float(g.value) if hasattr(g, "value") else float(g)
                        for g in hourly_gust if g is not None), default=None)
        # F002: Gew = Stufe + Uhrzeit (kein Fake-%), Hintergrund nach Level.
        # #1848 A3: der Zellenbau (Tag/Nacht-Split #1653, Onset-Uhrzeit,
        # Herkunft #1680 S5a, Hagel-Zusatz #1475) steht jetzt in
        # `thunder_cell_html()` -- DIESELBE Quelle, die auch der
        # konfigurierbare Zweig oben ruft.
        thunder_level = (stage.get("thunder", "NONE") or "NONE").upper()
        gew_str = thunder_cell_html(tokens, stage)

        n_str = f"{temp_min:.0f}°" if temp_min is not None else "–"
        d_str = f"{temp_max:.0f}°" if temp_max is not None else "–"
        r_str = f"{precip_mm:.1f}" if precip_mm is not None else "–"
        pr_str = f"{int(pr_pct)}%" if pr_pct is not None else "–"
        wind_str = f"{wind_kmh:.0f}" if wind_kmh is not None else "–"
        gust_str = f"{gust_kmh:.0f}" if gust_kmh is not None else "–"

        tag_bg = ""
        n_bg = ""
        d_bg = ""
        r_bg = _outlook_cell_bg(precip_mm, _catalog_thresholds("precipitation"))
        pr_bg = _outlook_cell_bg(pr_pct, _catalog_thresholds("rain_probability"))
        wind_bg = _outlook_cell_bg(wind_kmh, _catalog_thresholds("wind"))
        gust_bg = _outlook_cell_bg(gust_kmh, _catalog_thresholds("gust"))
        gew_bg = _THUNDER_LEVEL_BG.get(thunder_level, "")
        acc_bg = ""

        acc_td = _otd(_acc_dot(conf_pct), bg=acc_bg) if show_acc else ""

        outlook_rows += (
            '<tr>'
            + _otd(weekday, bg=tag_bg)
            + _otd(n_str, bg=n_bg)
            + _otd(d_str, bg=d_bg)
            + _otd(r_str, bg=r_bg)
            + _otd(pr_str, bg=pr_bg)
            + _otd(wind_str, bg=wind_bg)
            + _otd(gust_str, bg=gust_bg)
            + _otd(gew_str, bg=gew_bg)
            + acc_td
            + '</tr>'
        )

    outlook_table = (
        '<table cellpadding="0" cellspacing="0" '
        'style="border-collapse:collapse;width:100%;'
        'border-top:2px solid #1d1c1a;">'
        + outlook_thead
        + f'<tbody>{outlook_rows}</tbody>'
        + '</table>'
    )

    return outlook_table


# ---------------------------------------------------------------------------
# render_outlook_plain — extrahiert aus plain.py (ab Z.242, AC-6)
# ---------------------------------------------------------------------------

def render_outlook_plain(
    rows: list[dict],
    *,
    show_acc: bool = True,
    metrics: Optional[list] = None,
    heading: str = "Nächste Etappen",
    show_name: bool = True,
) -> str:
    """Rendert den Klartext-Ausblick-Block.

    ``show_acc`` haengt im konfigurierbaren Zweig (``metrics`` gesetzt) das
    ACC-Wort hinter die gewaehlten Spalten -- die Klartext-Entsprechung des
    HTML-Farbpunkts (#2098 Befund C). Der Altform-Zweig zeigte ACC noch nie
    und bleibt unveraendert; ``show_acc=False`` (Ortsvergleich) laesst die
    Spalte in beiden Zweigen entfallen.

    ``metrics`` (#1361): gesetzte Auswahl ersetzt die festen Wert-Tokens
    durch die gewaehlten Groessen. ``heading`` (#1368): Compare schreibt
    "3-Tages-Ausblick" -- im Ortsvergleich gibt es keine Etappen.
    ``show_name=False`` (#1368): laesst das feste 26-Zeichen-Etappennamen-
    Feld entfallen, das der Ortsvergleich nie befuellt. Alle drei sind per
    Default abgeschirmt -- der Trip-Aufruf bleibt byte-identisch.
    """
    lines: list[str] = []
    lines.append("")
    lines.append(heading)
    for stage in rows:
        weekday = stage.get("weekday", "")
        if metrics is not None:
            from output.renderers.compare_outlook_metric_ids import outlook_columns

            columns = outlook_columns(metrics)
            cells = stage.get("cells") or []
            texte = [cells[i] if i < len(cells) else "–" for i in range(len(columns))]
            # #1848 A3: Gewitterfeld aus DEMSELBEN Zellenbau wie der feste
            # Zweig darunter -- mit Onset-Uhrzeit, Nachtanteil, Herkunft und
            # Hagel statt bloss dem Stufenwort aus `cells`.
            gew_index = thunder_column_index(columns)
            if gew_index is not None:
                texte[gew_index] = thunder_cell_plain(format_trend_tokens(stage), stage)
            values = "  ".join(
                [f"{c['label']} {texte[i]}" for i, c in enumerate(columns)]
                # #2098 Befund C: der ACC-Farbpunkt des HTML ist fuer
                # Klartext-Leser unsichtbar -- dieselbe Aussage als Wort,
                # aus derselben Stufenquelle, an derselben Position
                # (hinter den gewaehlten Spalten) wie im HTML.
                + ([f"{ACC_LABEL} {_acc_wort(stage.get('confidence_pct'))}"]
                   if show_acc else [])
            )
            # #1848 A3: Etappenname und Notiz stehen auch hier -- der feste
            # Zweig darunter fuehrt beide seit jeher, und seit A3 laeuft JEDE
            # Tour ueber diesen Zweig. Ohne sie verloere der Klartext-Ausblick
            # die Zuordnung Zeile -> Etappe. `show_name=False` (Ortsvergleich,
            # #1368) laesst das Feld wie bisher entfallen.
            name_field = f"{stage.get('name', ''):<26} " if show_name else ""
            lines.append(f"{weekday:<3} {name_field}{values}".rstrip())
            note = stage.get("note")
            if note:
                lines.append(f"    ↳ {note}")
            continue

        tok = format_trend_tokens(stage)
        name = stage.get("name", "")
        # Precip str — zero decision from format_trend_tokens
        precip_str = tok["precip_str"]

        # Issue #1653/#1493/#1680 S5a/#1475: Tageswort aus dem Tagesfenster
        # mit Onset-Uhrzeit, Herkunft, Nacht- und Hagel-Zusatz. #1848 A3: der
        # Zellenbau steht in `thunder_cell_plain()` -- DIESELBE Quelle, die
        # auch der konfigurierbare Zweig oben ruft.
        thunder_word = thunder_cell_plain(tok, stage)

        name_field = f"{name:<26} " if show_name else ""
        line = (
            f"{weekday:<3} {name_field}{tok['temp_str']:<8} "
            f"{precip_str:<5} {tok['wind_str']:<5} {thunder_word}"
        )
        lines.append(line)

        note = stage.get("note")
        if note:
            lines.append(f"    ↳ {note}")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# build_outlook_row — extrahiert aus trip_report_scheduler.py (Z.1460-1488, AC-3)
# ---------------------------------------------------------------------------

def _metric_column_bg(col: dict, raw: object) -> str:
    """Zell-Hintergrund einer Ausblick-Metrikspalte (#1849).

    Ampelband aus den SSoT-Helfern (``severity_for``/``thunder_ampel_band``),
    Hex-Wert aus ``tone_css`` -- dieselben Quellen wie der Altpfad. ``green``
    faerbt bewusst NICHT (Altpfad-Paritaet, kein gruener Teppich), und die
    Gewitterstufe LOW traegt den abweichenden Altpfad-Hellgelbton
    (``_THUNDER_LEVEL_BG``), nicht ``tone_css('yellow')``.
    """
    from output.metric_format import severity_for, thunder_ampel_band

    kind = col.get("kind")
    if kind == "enum":
        return ""
    if kind == "ordinal":
        band = thunder_ampel_band(raw)
        if band == "yellow":
            return "background:#fbe6c3;"
    else:
        band = severity_for(col.get("metric_id"), raw)
    if band in (None, "green"):
        return ""
    return f"background:{tone_css(band)[0]};"



# #1848 A1 (AC-1/AC-2/AC-3): Gehzeit-Fenster-Override je Summary-Feld.
# `hiking_extrema` ist ein bereits fertiges hiking_field_min_max()-Mapping
# (Vorbild sms_thresholds) -- dieselben Funktionen, die sms_trip.py fuer
# D/FD nutzt (Issue #1417). Fail-soft: fehlt der Key oder ist
# `hiking_extrema` None, bleibt das Etappenaggregat (AC-2). Berechnet wird
# es entweder vom Aufrufer selbst UEBERGEBEN oder HIER aus `segments`
# abgeleitet (s. `_resolve_hiking_extrema`) -- `trip_report_scheduler.py`
# darf `output.renderers.day_window` nicht selbst importieren
# (Architektur-Wache `test_scheduler_has_no_output_imports`), reicht daher
# die rohen Segmente durch statt das Ergebnis vorzurechnen.
_HIKING_FIELD_MAP = {
    "temp_min_c": ("t2m_c", 0),
    "temp_max_c": ("t2m_c", 1),
    "wind_chill_min_c": ("wind_chill_c", 0),
    "wind_chill_max_c": ("wind_chill_c", 1),
}


def _hiking_or_summary(
    summary: "SegmentWeatherSummary", field: Optional[str], hiking_extrema: Optional[dict],
) -> object:
    """Wert fuer ``field`` aus dem Gehzeit-Fenster, wenn ein Override vorliegt
    -- sonst faellt es fail-soft auf das Etappenaggregat zurueck (AC-2)."""
    if field is None:
        return None
    hit = _HIKING_FIELD_MAP.get(field)
    if hit is not None and hiking_extrema is not None:
        extrema = hiking_extrema.get(hit[0])
        if extrema is not None:
            return extrema[hit[1]]
    return getattr(summary, field, None)


def _resolve_hiking_extrema(
    hiking_extrema: Optional[dict], segments: Optional[list],
) -> Optional[dict]:
    """``hiking_extrema`` hat Vorrang; ohne es aber mit ``segments`` wird das
    Gehzeit-Fenster HIER berechnet (``output.renderers.day_window`` ist ein
    Renderer-Modul, der Import gehoert deshalb in diese Schicht, nicht in den
    Zeitplaner). Segmentlose Teile (kein ``.segment``, nur Zeitreihe --
    Test-Doubles) bleiben aussen vor statt die Berechnung abstuerzen zu
    lassen."""
    if hiking_extrema is not None or not segments:
        return hiking_extrema
    from output.renderers.day_window import (
        collect_hiking_window_points, hiking_field_min_max,
    )

    usable = [s for s in segments if getattr(s, "segment", None) is not None]
    hiking_points = collect_hiking_window_points(usable)
    resolved = {
        field: extrema
        for field, extrema in (
            ("t2m_c", hiking_field_min_max(hiking_points, "t2m_c")),
            ("wind_chill_c", hiking_field_min_max(hiking_points, "wind_chill_c")),
        )
        if extrema is not None
    }
    return resolved or None


def build_outlook_row(
    summary: "SegmentWeatherSummary",
    points: list["ForecastDataPoint"],
    weekday: str,
    tz,
    *,
    sms_thresholds: Optional[dict] = None,
    metrics: Optional[list] = None,
    trip_display_config: object = None,
    report_type: Optional[str] = None,
    day_window_start_hour: Optional[int] = None,
    day_window_end_hour: Optional[int] = None,
    hiking_extrema: Optional[dict] = None,
    segments: Optional[list] = None,
    outlook_metric_formats: Optional[dict] = None,
) -> dict:
    """Baut ein Ausblick-Row-Dict aus einer SegmentWeatherSummary + Punktliste.

    Reine Funktion, kein Netz-/Fetch-Aufruf: ``summary`` kommt von
    ``aggregate_stage`` (Trip) oder ``summarize_points`` (Compare) --
    geteilte Naht (CLAUDE.md Trip/Compare-Teilungs-Invariante). Hourly-
    Samples (hourly_gust/hourly_thunder/hourly_precip/hourly_wind) werden
    intern aus der flachen Punktliste ``points`` abgeleitet (wie im
    Ist-Zustand), damit die Tabelle weiterhin ``hourly_gust`` (nicht
    ``summary.gust_max_kmh``) liest.

    ``sms_thresholds``: optionales Mapping metric_id -> Schwellwert
    (``precipitation``/``wind``/``gust``/``thunder``), wird auf
    ``sms_threshold_precip``/``sms_threshold_wind``/``sms_threshold_gust``/
    ``sms_threshold_thunder`` abgebildet; ``None``-Werte werden gefiltert
    (analog ``trip_report_scheduler._build_stage_trend``).

    ``metrics`` (#1361, Compare): gesetzte Auswahl im Neuformat
    (``{"metric_id", "aggregation"}``) ergaenzt das Dict um ``cells`` -- die
    fertig formatierten Zellentexte der gewaehlten Groessen in Auswahl-
    Reihenfolge, datengetrieben aus ``summary`` ueber
    ``MetricDefinition.summary_fields``. ``None`` laesst das Dict
    unveraendert (rein additiv, AC-11).

    ``trip_display_config``/``report_type`` (#1720 S1, Trip): statt einer
    fertigen Auswahl reicht der Zeitplaner die UNGEKOLLABIERTE
    ``display_config`` durch -- die Aufloesung (``resolve_trip_outlook_metrics``)
    passiert dann hier, in derselben Schicht wie der Spaltenbau und nach
    derselben Regel. So braucht der Zeitplaner kein Renderer-Vokabular
    (Architektur-Wache ``test_scheduler_has_no_output_imports``), und die
    Zellen dieser Zeile koennen nicht nach einer anderen Regel entstehen als
    die Ueberschriften darueber. Ein ausdrueckliches ``metrics`` hat Vorrang
    (Compare-Pfad unveraendert).

    ``hiking_extrema`` (#1848 A1, AC-1/AC-2/AC-3): optionales Mapping
    ``{"t2m_c": (min, max, max_ts), "wind_chill_c": (...)}`` --
    ``hiking_field_min_max()``-Ergebnisse aus dem Gehzeit-Fenster
    (``collect_hiking_window_points()``), das der Aufrufer SELBST berechnet
    (er kennt Segmente, diese Funktion nicht). Wirkt an BEIDEN Wertequellen:
    ``temp_lo``/``temp_hi`` des festen Altform-Pfads UND ``getattr(summary,
    col["field"])`` der ``cells``-Schleife des konfigurierbaren Pfads.
    Fehlender Key/``None`` faellt fail-soft auf das Etappenaggregat zurueck.

    ``outlook_metric_formats`` (#2049): Roh/Einfach je Ausblick-Groesse
    (``{kennung: bool}``). Wie bei ``metrics`` hat die ausdrueckliche Uebergabe
    Vorrang; ohne sie wird die Zuordnung aus ``trip_display_config``
    aufgeloest, damit der Zeitplaner auch dafuer kein Renderer-Vokabular
    braucht. Die ZELLEN entstehen hier genau einmal und speisen alle vier
    Ausgabeorte -- deshalb ist dies die einzige Stelle, an der das Flag
    ankommen muss (die Kopfzeilen der Renderer brauchen es nicht, ihre
    Beschriftung aendert sich nicht).

    ``segments`` (#1848 A1, Alternative zu ``hiking_extrema``): der Aufrufer
    (``trip_report_scheduler.py``) hat ``seg_weather`` bereits vorliegen,
    darf aber ``output.renderers.day_window`` selbst nicht importieren
    (Architektur-Wache ``test_scheduler_has_no_output_imports``) -- reicht
    daher die rohen Segmente durch, die Ableitung passiert HIER
    (``_resolve_hiking_extrema``). Ein explizites ``hiking_extrema`` hat
    Vorrang vor ``segments``.
    """
    hiking_extrema = _resolve_hiking_extrema(hiking_extrema, segments)
    if metrics is None and trip_display_config is not None:
        from output.renderers.compare_outlook_metric_ids import (
            resolve_trip_outlook_metrics,
        )

        metrics = resolve_trip_outlook_metrics(trip_display_config, report_type)
    if outlook_metric_formats is None and trip_display_config is not None:
        # #2049: dieselbe Bauart wie `metrics` eine Zeile darueber -- der
        # Zeitplaner reicht die ungekollabierte Konfiguration durch, die
        # Aufloesung passiert in der Ausgabeschicht.
        from output.renderers.compare_outlook_metric_ids import (
            resolve_trip_outlook_formats,
        )

        outlook_metric_formats = resolve_trip_outlook_formats(trip_display_config)
    from output.metric_format import thunder_label_value
    from output.tokens.dto import HourlyValue
    from utils.timezone import local_hour as _lh

    _temp_lo_raw = _hiking_or_summary(summary, "temp_min_c", hiking_extrema)
    _temp_hi_raw = _hiking_or_summary(summary, "temp_max_c", hiking_extrema)
    temp_lo = int(_temp_lo_raw) if _temp_lo_raw is not None else None
    temp_hi = int(_temp_hi_raw) if _temp_hi_raw is not None else None
    precip_mm = float(summary.precip_sum_mm or 0.0)
    wind_kmh = int(summary.wind_max_kmh or 0)
    wind_dir = degrees_to_compass(getattr(summary, "wind_direction_avg_deg", None))
    thunder_level = summary.thunder_level_max
    thunder = thunder_level.name if thunder_level is not None else "NONE"

    # Issue #640: Build HourlyValue samples from the flat point list for
    # @-time tokens. Uses local hours (Bug #398/#401: tz required). No
    # extra API call.
    _hourly_precip: list = []
    _hourly_wind: list = []
    _hourly_gust: list = []
    _hourly_thunder: list = []
    # Issue #1680 S5a: die tragenden Zutaten je Stunde REICHEN nur durch --
    # gefiltert und vereinigt wird erst in `format_trend_tokens()`, an
    # derselben Stelle und mit demselben Fenster wie `thunder_day_token`
    # (eine Fensterauflösung, nicht zwei; Spec AC-9).
    _thunder_signals: list = []
    _hat_signale = False
    for dp in points:
        lh = _lh(dp.ts, tz)
        if dp.precip_1h_mm is not None:
            _hourly_precip.append(HourlyValue(hour=lh, value=dp.precip_1h_mm))
        if dp.wind10m_kmh is not None:
            _hourly_wind.append(HourlyValue(hour=lh, value=dp.wind10m_kmh))
        if dp.gust_kmh is not None:
            _hourly_gust.append(HourlyValue(hour=lh, value=dp.gust_kmh))
        if dp.thunder_level is not None:
            # Issue #1474: geteilte Render-Skala statt lokaler Kopie -- eine
            # lokale {NONE:0,MED:1,HIGH:2}-Kopie waere nach der LOW-Erweiterung
            # (Skala jetzt {0,1,2,3}) fuer MED/HIGH stillschweigend falsch.
            _hourly_thunder.append(HourlyValue(
                hour=lh, value=float(thunder_label_value(dp.thunder_level))
            ))
            _signale = getattr(dp, "thunder_level_signals", None)
            if _signale is not None:
                _hat_signale = True
            _thunder_signals.append(
                (lh, dp.thunder_level, list(_signale or ()))
            )

    row = dict(
        weekday=weekday,
        temp_lo=temp_lo,
        temp_hi=temp_hi,
        precip_mm=precip_mm,
        wind_dir=wind_dir,
        wind_kmh=wind_kmh,
        thunder=thunder,
        hourly_precip=tuple(_hourly_precip),
        hourly_wind=tuple(_hourly_wind),
        hourly_gust=tuple(_hourly_gust),
        hourly_thunder=tuple(_hourly_thunder),
    )

    _conf_pct_raw = getattr(summary, "confidence_pct_min", None)
    _conf_pct = round(_conf_pct_raw) if _conf_pct_raw is not None else None

    _sms = sms_thresholds or {}
    optional = {
        # Issue #1475 Nachbesserung (Punkt 4b): Hagel-Kennzeichen der Etappe —
        # Quelle fuer den Textzusatz in der Gewitter-Zelle von
        # render_outlook_table()/render_outlook_plain(). Steht bewusst im
        # None-gefilterten `optional`-Block: ohne bestaetigten Hagel bleibt das
        # Row-Dict zeichengleich zum Stand vor dieser Spec (Paritaets-Test
        # tests/tdd/test_trip_outlook_parity.py). `thunder` bleibt unberuehrt
        # (AC-10).
        "hail": getattr(summary, "hail_flag", None),
        "confidence_pct": _conf_pct,
        "rain_probability_pct": getattr(summary, "pop_max_pct", None),
        "sms_threshold_precip": _sms.get("precipitation"),
        "sms_threshold_wind": _sms.get("wind"),
        "sms_threshold_gust": _sms.get("gust"),
        "sms_threshold_thunder": _sms.get("thunder"),
        # Issue #1653: konfiguriertes Tagesfenster fuer die Tag/Nacht-Trennung
        # der Gewitter-Zelle. Ebenfalls None-gefiltert -- Aufrufer ohne Fenster
        # (Compare, Bestandstests) erhalten ein zeichengleiches Row-Dict.
        "day_window_start_hour": day_window_start_hour,
        "day_window_end_hour": day_window_end_hour,
        # Issue #1680 S5a: (Stunde, Stufe, Traegerliste) je Stunde mit
        # Gewitterstufe. Steht bewusst im None-gefilterten `optional`-Block:
        # fuehrt KEIN Punkt eine Traegerliste (Alt-Schnappschuss vor Scheibe 1,
        # Bestandsfixturen), bleibt das Row-Dict zeichengleich (AC-8/AC-10,
        # Paritaets-Test tests/tdd/test_trip_outlook_parity.py).
        "hourly_thunder_signals": (
            tuple(_thunder_signals) if _hat_signale else None
        ),
    }
    row.update({k: v for k, v in optional.items() if v is not None})

    if metrics is not None:
        from output.renderers.compare_outlook_metric_ids import (
            format_outlook_range_cell, format_outlook_value, outlook_columns,
        )

        # Issue #1475 Nachbesserung (Punkt 5b, Aufrufstelle 4): der Hagel-Wert
        # der Etappe/des Tages reist als Spalten-Eigenschaft mit, damit die
        # Gewitter-Zelle des Ausblicks denselben Zusatz zeigt wie die
        # Uebersichtstabelle derselben Mail.
        _hail = getattr(summary, "hail_flag", None)
        # Issue #1680 S5a (AC-11b): dieselbe Bauart wie der Hagel-Wert oben --
        # die tragenden Zutaten reisen als Spalten-Eigenschaft mit. Quelle ist
        # bewusst das TAGES-Aggregat `summary.thunder_level_max_signals`, also
        # DIESELBE Rechnung wie die hier gezeigte Stufe (`col["field"]`), nicht
        # das Tagesfenster -- eine Herkunft, die nicht zur gezeigten Stufe
        # gehoert, waere der AC-12-Fehler aus Scheibe 1.
        _signals = getattr(summary, "thunder_level_max_signals", None)
        # Issue #1841: im TRIP-Fall (trip_display_config gesetzt) liest die
        # Gewitterspalte (kind == "ordinal") das konfigurierte TAGESFENSTER
        # statt des gehzeit-geklemmten Aggregats -- derselbe geteilte Helfer
        # wie Kompaktmail/Klartext-Altpfad/Telegram (#1671). Diskriminator ist
        # `trip_display_config`, NICHT `report_type` (beim Trip immer gesetzt,
        # sagt nichts ueber den Pfad) und NICHT die Fensterpraesenz (Falle:
        # test_outlook_day_night_thunder_split.py:665, gilt fuer Compare mit
        # gesetztem Fenster). Der Ortsvergleich (trip_display_config is None)
        # bleibt unveraendert (AC-5).
        _thunder_value = summary.thunder_level_max
        _thunder_signals = _signals
        if trip_display_config is not None:
            from app.models import ThunderLevel as _ThunderLevel

            _tok = format_trend_tokens(row)
            _zweig = resolve_thunder_day_branch(_tok, row)
            if _zweig == "day":
                # Stufe UND Herkunft aus DEMSELBEN Fenster (AC-6) -- beide
                # Schluessel speisen sich aus derselben, in
                # format_trend_tokens() EINMAL berechneten Menge, keine
                # zweite Fensterauflösung hier.
                _thunder_value = _tok.get("thunder_day_level")
                _thunder_signals = _tok.get("thunder_day_carriers")
            elif _zweig == "none":
                _thunder_value = _ThunderLevel.NONE
                _thunder_signals = None
            # "plain": _thunder_value/_thunder_signals bleiben das Aggregat
            # (unveraendert, wie ohne Stundenreihe/AC-4).
        # Issue #1849: Zellentext UND Zell-Hintergrund entstehen aus DEMSELBEN
        # Rohwert -- eine zweite Rohwert-Aufloesung koennte fuer die
        # Gewitterspalte am oben (#1841) aufgeloesten Tagesfenster vorbeigehen.
        cells: list[str] = []
        cell_bg: list[str] = []
        for col in outlook_columns(metrics, outlook_metric_formats):
            ordinal = col.get("kind") == "ordinal"
            # #1848 A1 (AC-4..AC-8): eine zusammengefuehrte Spannen-Spalte
            # traegt `field_min`/`field_max` statt `field` -- BEIDE Seiten
            # gehen (mit demselben Gehzeit-Fenster-Override wie der
            # Einzelwert-Fall) in EINE Zelle "{min}/{max}".
            if "field_min" in col or "field_max" in col:
                raw_min = _hiking_or_summary(summary, col.get("field_min"), hiking_extrema)
                raw_max = _hiking_or_summary(summary, col.get("field_max"), hiking_extrema)
                cells.append(format_outlook_range_cell(raw_min, raw_max, col))
                cell_bg.append(_metric_column_bg(col, raw_max))
                continue
            raw = (
                _thunder_value if ordinal
                else _hiking_or_summary(summary, col.get("field"), hiking_extrema)
            )
            cells.append(format_outlook_value(
                raw,
                {**col, "hail": _hail,
                 "signals": _thunder_signals if ordinal else _signals},
            ))
            cell_bg.append(_metric_column_bg(col, raw))
        row["cells"] = cells
        row["cell_bg"] = cell_bg

    return row
