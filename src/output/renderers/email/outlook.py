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
import re as _re
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from datetime import tzinfo
    from app.models import SegmentWeatherSummary, ForecastDataPoint

from app.metric_catalog import get_metric
from output.renderers.email.helpers import format_trend_tokens
from output.renderers.email.design_tokens import FONT_DATA
from utils.geo import degrees_to_compass


_THUNDER_TOKEN_RE = _re.compile(
    r"^([a-zA-Zäöü]+)@(\d+)(?:\(([a-zA-Zäöü]+)@(\d+)\))?"
)


def _thunder_token_parts(token: Optional[str]):
    """Zerlegt einen Gewitter-Token in (Erst-Wort, Erst-Stunde, Peak-Zusatz).

    Issue #1653 (F005): ``render_threshold_peak_value`` haengt den
    Spitzenwert als ``leicht@5(hoch@15)`` an, wenn Erst-Ueberschreitung und
    Spitze im selben Fenster auseinanderfallen -- der meteorologische
    Normalfall eines ueber den Nachmittag eskalierenden Gewitters. Wer nur
    die erste Gruppe liest, unterschlaegt genau die Stufe, vor der der
    Report warnen soll. Der Peak-Zusatz ist "" (leer), wenn Erst == Peak.
    """
    if not token or token == "-":
        return None
    m = _THUNDER_TOKEN_RE.match(token)
    if not m:
        return None
    peak_suffix = f" ({m.group(3)} @{m.group(4)})" if m.group(3) else ""
    return m.group(1), m.group(2), peak_suffix


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
        if d is not None and v >= d:
            return "background:#f6c5bf;"
        if w is not None and v >= w:
            return "background:#fad6b8;"
        if c is not None and v >= c:
            return "background:#fbeeb8;"
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
    def _acc_dot(conf_pct) -> str:
        if conf_pct is None:
            return "–"
        try:
            v = float(conf_pct)
        except (TypeError, ValueError):
            return "–"
        if v >= 80:
            color = "#2f8a3e"
        elif v >= 60:
            color = "#e3b008"
        elif v >= 40:
            color = "#e07b1a"
        else:
            color = "#c52a22"
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
    if metrics is not None:
        from output.renderers.compare_outlook_metric_ids import outlook_columns

        columns = outlook_columns(metrics)
        head = "".join(
            f'<th {_oh_style}>{_html.escape(c["label"])}</th>' for c in columns
        )
        body = ""
        for stage in rows:
            cells = stage.get("cells") or []
            body += (
                '<tr>' + _otd(stage.get("weekday", "–"))
                + "".join(
                    _otd(_html.escape(cells[i] if i < len(cells) else "–"))
                    for i in range(len(columns))
                )
                + '</tr>'
            )
        return (
            '<table cellpadding="0" cellspacing="0" '
            'style="border-collapse:collapse;width:100%;'
            'border-top:2px solid #1d1c1a;">'
            f'<thead><tr><th {_oh_style}>Tag</th>{head}</tr></thead>'
            f'<tbody>{body}</tbody></table>'
        )

    _acc_th = f'<th {_oh_style}>ACC</th>' if show_acc else ""
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

    # Issue #1474: LOW ("leicht") ergaenzt -- Wort aus der geteilten Quelle
    # (metric_format.THUNDER_LABEL_DE, "geteilte Quelle statt Kopien").
    # Str-Enum-Hash-Aequivalenz (s. metric_format.py): der rohe String-Key
    # findet denselben Eintrag wie die ThunderLevel-Instanz.
    from output.metric_format import THUNDER_LABEL_DE as _THUNDER_LABEL_DE
    from output.metric_format import format_hail_note as _format_hail_note
    _THUNDER_LEVEL_LABEL = {
        "LOW": _THUNDER_LABEL_DE["LOW"],
        "MED": _THUNDER_LABEL_DE["MED"],
        "HIGH": _THUNDER_LABEL_DE["HIGH"],
    }
    _THUNDER_LEVEL_BG = {
        "LOW": "background:#fbe6c3;",
        "MED": "background:#fad6b8;",
        "HIGH": "background:#f6c5bf;",
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
        # F002: Gew = Stufe + Uhrzeit (kein Fake-%), Hintergrund nach Level
        thunder_level = (stage.get("thunder", "NONE") or "NONE").upper()
        # Issue #1653: Tag- und Nachtanteil getrennt, damit ein Nachtgewitter
        # nicht mehr hinter dem staerkeren Tageswert verschwindet -- oder
        # umgekehrt. Wort UND Uhrzeit des Tagesteils stammen aus demselben
        # Token und damit aus demselben Fenster; vorher kam das Wort aus
        # `stage["thunder"]` (auf die Gehzeit geklemmtes Aggregat) und nur die
        # Uhrzeit aus dem Tagesfenster -- zwei Rechnungen, die nur meist
        # uebereinstimmten: sagte das Aggregat "NONE", waehrend im Tagesfenster
        # ein Gewitter lag, verschwand der Tagesteil ganz.
        day_part = None
        d_tok = tokens.get("thunder_day_token", "-")
        _d = _thunder_token_parts(d_tok)
        if _d:
            day_part = f"{_d[0]} @{_d[1]}{_d[2]}"
            # Issue #1680 S5a: die tragende Zutat unmittelbar hinter der
            # Uhrzeit des Tagesteils -- vor Nacht- und Hagel-Zusatz (AC-1/AC-5).
            _origin = tokens.get("thunder_day_origin")
            if _origin:
                day_part += f" · {_origin}"
        elif not (stage.get("hourly_thunder") or ()) and thunder_level in (
            "LOW", "MED", "HIGH",
        ):
            # Ohne jede Stundenreihe kann der Split nichts sagen -- dann wie
            # bisher die Stufe des Aggregats ohne Uhrzeit (Alt-Fixtures).
            day_part = _THUNDER_LEVEL_LABEL[thunder_level]

        night_part = None
        n_tok = tokens.get("thunder_night_token", "-")
        _m = _thunder_token_parts(n_tok)
        if _m:
            night_part = f"nachts {_m[0]} @{_m[1]}{_m[2]}"

        if day_part and night_part:
            gew_str = f"{day_part} · {night_part}"
        elif day_part:
            gew_str = day_part
        elif night_part:
            gew_str = night_part
        else:
            gew_str = "–"

        if gew_str != "–":
            # Issue #1475 Nachbesserung (Punkt 4b): rein deskriptiver
            # Hagel-Zusatz an der Gewitter-Zelle (ADR-0007, kein Rat).
            _hail_note = _format_hail_note(stage.get("hail"))
            if _hail_note:
                gew_str += f" · {_hail_note}"

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

    ``show_acc`` existiert fuer Signatur-Symmetrie mit
    ``render_outlook_table``; der Klartext-Ausblick zeigte schon im
    Ist-Zustand keine ACC-Spalte, daher ohne Effekt.

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

            cells = stage.get("cells") or []
            values = "  ".join(
                f"{c['label']} {cells[i] if i < len(cells) else '–'}"
                for i, c in enumerate(outlook_columns(metrics))
            )
            lines.append(f"{weekday:<3} {values}".rstrip())
            continue

        tok = format_trend_tokens(stage)
        name = stage.get("name", "")
        # Precip str — zero decision from format_trend_tokens
        precip_str = tok["precip_str"]

        # Issue #1653: das Tageswort stammt aus derselben Quelle wie in der
        # HTML-Zelle -- `thunder_day_token` (nach Tagesfenster gefilterte
        # Stundenreihe), nicht mehr aus `stage["thunder"]` ueber
        # `tok['thunder_plain']` (auf die Gehzeit geklemmtes Aggregat). Zwei
        # Rechnungen, die nur meist uebereinstimmten: sagte das Aggregat
        # "NONE", waehrend im Tagesfenster ein Gewitter lag, verschwand es
        # hier ganz -- und umgekehrt behauptete die Zeile ein Tagesgewitter,
        # wenn das Aggregat eine Stufe trug, die Stundenreihe im Tagesfenster
        # aber leer war.
        from output.renderers.email.helpers import _THUNDER_MAP
        thunder_word = tok["thunder_plain"]
        _d_tok = tok.get("thunder_day_token", "-")
        _dm = _thunder_token_parts(_d_tok)
        if _dm:
            thunder_word = f"⚡{_dm[0]}{_dm[2]}"
            # Issue #1680 S5a: derselbe Zusatz wie in der HTML-Zelle, aus
            # demselben Token -- der Klartext fuehrt wie bisher keine
            # Tagesuhrzeit (AC-2).
            _origin = tok.get("thunder_day_origin")
            if _origin:
                thunder_word += f" · {_origin}"
        elif stage.get("hourly_thunder"):
            # Stundenreihe da, im Tagesfenster aber kein Gewitter.
            thunder_word = _THUNDER_MAP["NONE"]["plain"]
        # Ohne jede Stundenreihe (Alt-Aufrufer, Compare) bleibt es beim
        # Aggregatwort -- der Split kann dort nichts sagen.

        name_field = f"{name:<26} " if show_name else ""
        line = (
            f"{weekday:<3} {name_field}{tok['temp_str']:<8} "
            f"{precip_str:<5} {tok['wind_str']:<5} {thunder_word}"
        )
        # Issue #1653: Nacht-Zusatz mit Uhrzeit -- die Klartext-Zeile zeigte
        # bisher ausschliesslich das Tageswort, ein Nachtgewitter erschien
        # dort nie.
        _n_tok = tok.get("thunder_night_token", "-")
        _nm = _thunder_token_parts(_n_tok)
        if _nm:
            line += f" · nachts {_nm[0]} @{_nm[1]}{_nm[2]}"
        # Issue #1475 Nachbesserung (Punkt 4b): derselbe deskriptive
        # Hagel-Zusatz wie in der HTML-Ausblick-Tabelle (geteilte Quelle).
        from output.metric_format import format_hail_note
        _note = format_hail_note(stage.get("hail"))
        if _note:
            line = f"{line} · {_note}"
        lines.append(line)

        note = stage.get("note")
        if note:
            lines.append(f"    ↳ {note}")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# build_outlook_row — extrahiert aus trip_report_scheduler.py (Z.1460-1488, AC-3)
# ---------------------------------------------------------------------------

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
    """
    if metrics is None and trip_display_config is not None:
        from output.renderers.compare_outlook_metric_ids import (
            resolve_trip_outlook_metrics,
        )

        metrics = resolve_trip_outlook_metrics(trip_display_config, report_type)
    from output.metric_format import thunder_label_value
    from output.tokens.dto import HourlyValue
    from utils.timezone import local_hour as _lh

    temp_lo = int(summary.temp_min_c) if summary.temp_min_c is not None else None
    temp_hi = int(summary.temp_max_c) if summary.temp_max_c is not None else None
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
            format_outlook_value, outlook_columns,
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
        row["cells"] = [
            format_outlook_value(
                getattr(summary, col["field"], None),
                {**col, "hail": _hail, "signals": _signals},
            )
            for col in outlook_columns(metrics)
        ]

    return row
