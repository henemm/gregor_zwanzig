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

import re as _re
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from datetime import tzinfo
    from app.models import SegmentWeatherSummary, ForecastDataPoint

from src.output.renderers.email.helpers import format_trend_tokens
from src.output.renderers.email.design_tokens import FONT_DATA
from utils.geo import degrees_to_compass


# ---------------------------------------------------------------------------
# render_outlook_table — extrahiert aus html.py (Z.1116-1271, AC-1/AC-2)
# ---------------------------------------------------------------------------

def render_outlook_table(rows: list[dict], *, show_acc: bool = True) -> str:
    """Rendert die HTML-Ausblick-Tabelle.

    ``show_acc=True`` (Trip-Default) ist byte-identisch zum bisherigen
    Inline-Block in ``render_html``. ``show_acc=False`` (Compare) laesst
    die ACC-<th>-Kopfzelle und die ``_acc_dot``-<td>-Zellen vollstaendig
    entfallen -- alle uebrigen Spalten bleiben unveraendert.
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

    _THUNDER_LEVEL_LABEL = {"MED": "mittel", "HIGH": "hoch"}
    _THUNDER_LEVEL_BG = {"MED": "background:#fad6b8;", "HIGH": "background:#f6c5bf;"}

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
        if thunder_level in ("MED", "HIGH"):
            gew_str = _THUNDER_LEVEL_LABEL[thunder_level]
            t_tok = tokens.get("thunder_token", "-")
            _at = _re.search(r"@(\d+)", t_tok) if t_tok and t_tok != "-" else None
            if _at:
                gew_str += f" @{_at.group(1)}"
        else:
            gew_str = "–"

        n_str = f"{temp_min:.0f}°" if temp_min is not None else "–"
        d_str = f"{temp_max:.0f}°" if temp_max is not None else "–"
        r_str = f"{precip_mm:.1f}" if precip_mm is not None else "–"
        pr_str = f"{int(pr_pct)}%" if pr_pct is not None else "–"
        wind_str = f"{wind_kmh:.0f}" if wind_kmh is not None else "–"
        gust_str = f"{gust_kmh:.0f}" if gust_kmh is not None else "–"

        tag_bg = ""
        n_bg = ""
        d_bg = ""
        r_bg = _outlook_cell_bg(precip_mm, (2, 5, 8))
        pr_bg = _outlook_cell_bg(pr_pct, (50, 70, 85))
        wind_bg = _outlook_cell_bg(wind_kmh, (20, 30, None))
        gust_bg = _outlook_cell_bg(gust_kmh, (30, 45, 60))
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

def render_outlook_plain(rows: list[dict], *, show_acc: bool = True) -> str:
    """Rendert den Klartext-Ausblick-Block.

    ``show_acc`` existiert fuer Signatur-Symmetrie mit
    ``render_outlook_table``; der Klartext-Ausblick zeigte schon im
    Ist-Zustand keine ACC-Spalte, daher ohne Effekt.
    """
    lines: list[str] = []
    lines.append("")
    lines.append("Nächste Etappen")
    for stage in rows:
        tok = format_trend_tokens(stage)
        weekday = stage.get("weekday", "")
        name = stage.get("name", "")
        # Precip str — zero decision from format_trend_tokens
        precip_str = tok["precip_str"]

        line = (
            f"{weekday:<3} {name:<26} {tok['temp_str']:<8} "
            f"{precip_str:<5} {tok['wind_str']:<5} {tok['thunder_plain']}"
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

def build_outlook_row(
    summary: "SegmentWeatherSummary",
    points: list["ForecastDataPoint"],
    weekday: str,
    tz,
    *,
    sms_thresholds: Optional[dict] = None,
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
    """
    from app.models import ThunderLevel as _TL
    from src.output.tokens.dto import HourlyValue
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
    _THUNDER_NUM = {_TL.NONE: 0, _TL.MED: 1, _TL.HIGH: 2}
    for dp in points:
        lh = _lh(dp.ts, tz)
        if dp.precip_1h_mm is not None:
            _hourly_precip.append(HourlyValue(hour=lh, value=dp.precip_1h_mm))
        if dp.wind10m_kmh is not None:
            _hourly_wind.append(HourlyValue(hour=lh, value=dp.wind10m_kmh))
        if dp.gust_kmh is not None:
            _hourly_gust.append(HourlyValue(hour=lh, value=dp.gust_kmh))
        if dp.thunder_level is not None:
            _hourly_thunder.append(HourlyValue(
                hour=lh, value=float(_THUNDER_NUM.get(dp.thunder_level, 0))
            ))

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
        "confidence_pct": _conf_pct,
        "rain_probability_pct": getattr(summary, "pop_max_pct", None),
        "sms_threshold_precip": _sms.get("precipitation"),
        "sms_threshold_wind": _sms.get("wind"),
        "sms_threshold_gust": _sms.get("gust"),
        "sms_threshold_thunder": _sms.get("thunder"),
    }
    row.update({k: v for k, v in optional.items() if v is not None})

    return row
