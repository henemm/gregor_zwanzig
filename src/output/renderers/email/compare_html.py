"""Compare-Email HTML-Renderer v2 (Issue #1110).

Pure Function ``render_compare_html()`` — analog zu ``html.py`` (Trip-Mail).

v2-Layout (loest Score/Winner-Vertrag aus #253 ab, s. #1108):
- Kein Score/Ranking/Winner-Card mehr — Orte alphabetisch nach Ortsname
  sortiert (case-insensitiv, PO-Update 2026-07-08, `sort_locations_alphabetically`).
- Uebersichtstabelle: Metriken als Zeilen x Orte als Spalten, inkl. Warn-Zeile
  mit Kuerzel-Chips je Ort (``CV2_METRICS``). KEIN Best-Wert-Highlight (Adversary
  F001, PO-Entscheidung) -- Zellfaerbung ausschliesslich ueber die Risk-Skala.
- Warn-Lead-Block (Akzent-Bar) nur wenn mindestens ein Ort eine amtliche
  Warnung hat.
- Stundentabellen fuer ALLE Orte (nicht nur Top-N), mit Langform-Warn-Streifen
  (wiederverwendet ``render_official_alerts_html``, ADR-0011).
- Inline-CSS only (Outlook-kompatibel), kein CSS-Grid/Flexbox.
- ``@media (max-width: 480px)`` Block fuer Mobile-Layout (Header-Stats).

SPEC: docs/specs/modules/issue_1110_compare_mail_v2.md
"""
from __future__ import annotations

import html as _html
from datetime import date, datetime, timedelta
from typing import Optional

from app.models import Corridor, ThunderLevel
from app.profile import ActivityProfile
from app.user import ComparisonResult, LocationResult
from output.renderers.compare_metric_ids import (
    CORRIDOR_METRIC_TO_HOUR_KEY, FRONTEND_TO_RENDERER_METRIC_ID,
)
from output.renderers.email.design_tokens import (
    FONT_DATA, FONT_UI, G_ACCENT, G_ALERT_L2, G_ALERT_L3, G_ALERT_L4,
    G_BOX_WARNING_BG, G_INK, G_INK_FAINT, G_INK_MUTED, G_PAPER, G_SUCCESS,
    G_WARNING, WEB_FONT_LINK, tone_css,
)
from output.renderers.email.outlook import build_outlook_row, render_outlook_table
from output.renderers.email.profile_signature import profile_signature
from services.corridor_match import corridor_inside
from output.metric_format import severity_for, thunder_ordinal
from output.renderers.alert.official_alerts import (
    _LEVEL_WORDS, OfficialAlertNotice, official_alert_source_label,
    render_official_alerts_html, render_warn_block,
)


# ---------------------------------------------------------------------------
# Risk-Skala + Metrik-Katalog (1:1 aus docs/design-requests/compare_mail_v2/
# screen-compare-email-v2.jsx uebernommen)
# ---------------------------------------------------------------------------

# Issue #1214 Scheibe 2: Compare-lokales Ampel-Vokabular (ok/caution/warn/danger)
# ist 1:1 kompatibel zum kanonischen (green/yellow/orange/red). severity_for()
# liefert kanonisch; die Uebersetzung erfolgt hier an der Aufrufstelle (Compare-
# Vokabular bleibt lokal, wird nicht global umbenannt).
_CANONICAL_TO_COMPARE = {"green": "ok", "yellow": "caution", "orange": "warn", "red": "danger"}
_COMPARE_TO_CANONICAL = {v: k for k, v in _CANONICAL_TO_COMPARE.items()}

# Issue #1214 Scheibe 2: Zell-Toenung stammt aus der zentralen tone_css-Palette
# (design_tokens), nicht mehr aus einem lokal duplizierten Mapping. _RISK_CELL
# bleibt als abgeleiteter Kompat-Alias erhalten (registrierte Konsumenten +
# Regressionstest test_official_alert_badge_color.py locken diese Werte); es ist
# ab jetzt nur noch eine Ableitung von tone_css, keine eigene Farbquelle mehr.
_RISK_CELL = {
    "caution": tone_css("yellow"),
    "warn": tone_css("orange"),
    "danger": tone_css("red"),
}
_INFO_CELL = ("#dde8f3", "#1e3a5f")

# Issue #1056 v2.0: Warn-Chip-Zellfarbe je amtlicher Warnstufe (bg-Tint, fg) --
# eigene Map, harmonisch zu den Badge-Rand-Farben, NICHT die Metrik-Palette
# _RISK_CELL (die bleibt fuer Temp/Wind/etc. unveraendert).
_ALERT_LEVEL_CELL = {
    1: ("#dbeadd", G_SUCCESS),
    2: ("#f2e4b0", G_ALERT_L2),
    3: ("#f4d3c6", G_ALERT_L3),
    4: ("#e4d7f5", G_ALERT_L4),
}


def _sev_temp(v: float) -> str:
    return "danger" if v >= 34 else "warn" if v >= 31 else "caution" if v >= 28 else "ok"


def _sev_wind(v: float) -> str:
    # Issue #1214 Scheibe 2 (Wind-Schwellen-Angleichung, AC-3): nutzt die
    # Katalog-Schwellen (wind.display_thresholds={yellow:30,orange:50,red:70})
    # via severity_for statt der bislang hartcodierten >40/>30/>20. Sichtbare,
    # bewusst gewollte Folge: 45 km/h zeigt jetzt gelb (caution) statt rot
    # (danger) — identisch zum Trip-Briefing (helpers.ampel_level).
    return _CANONICAL_TO_COMPARE.get(severity_for("wind", v), "ok")


def _sev_gust(v: float) -> str:
    return "danger" if v > 60 else "warn" if v > 45 else "caution" if v > 30 else "ok"


def _sev_rain(v: float) -> str:
    return "danger" if v > 8 else "warn" if v > 4 else "caution" if v > 1 else "ok"


def _sev_uv(v: float) -> str:
    return "danger" if v >= 8 else "warn" if v >= 6 else "caution" if v >= 3 else "ok"


def _sev_pop(v: float) -> str:
    return "danger" if v >= 80 else "warn" if v >= 60 else "caution" if v >= 40 else "ok"


def _sev_visibility(v: float) -> str:
    """v in Metern -- niedrige Sicht ist kritischer."""
    return "danger" if v < 1000 else "warn" if v < 3000 else "caution" if v < 5000 else "ok"


def _sev_cape(v: float) -> str:
    return _CANONICAL_TO_COMPARE.get(severity_for("cape", v), "ok")


_WEEKDAY_ABBR = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

# Format-Vorbild html.py:1160-1161 -- lokale Kopie statt Import (eigenstaendiges
# Compare-Vokabular, s. Spec-Modul-Docstring), NONE rendert als "—" (kein Wert).
_THUNDER_LEVEL_LABEL = {"NONE": "—", "MED": "mittel", "HIGH": "hoch"}
_THUNDER_SEV = {"MED": "warn", "HIGH": "danger"}


def _fmt_deg(v) -> str:
    return f"{v:.0f}°" if v is not None else "—"


def _fmt_kmh(v) -> str:
    return f"{v:.0f}" if v is not None else "—"


def _fmt_rain(v) -> str:
    return f"{v:.1f}" if v else "·"


def _fmt_uv(v) -> str:
    return f"{v:.0f}" if v is not None else "—"


def _fmt_pop(v) -> str:
    return f"{v:.0f}%" if v is not None else "—"


def _fmt_visibility(v) -> str:
    # Issue #1237 (AC-2): nur der Zahlenwert -- die Einheit steht in der
    # Einheiten-Legende unter den Stundentabellen (analog Trip-Briefing).
    return f"{v / 1000:.1f}" if v is not None else "—"


def _fmt_thunder(v) -> str:
    if v is None:
        return "—"
    key = v.value if hasattr(v, "value") else str(v)
    return _THUNDER_LEVEL_LABEL.get(key, "—")


def _sev_thunder(v):
    if v is None:
        return None
    key = v.value if hasattr(v, "value") else str(v)
    return _THUNDER_SEV.get(key)


def _sev_rain_safe(v) -> str:
    return _sev_rain(v or 0.0)


_PRECIP_TYPE_LABEL = {
    "RAIN": "Regen",
    "SNOW": "Schnee",
    "MIXED": "Mischniederschlag",
    "FREEZING_RAIN": "Eisregen",
}


def _fmt_precip_type(v) -> str:
    """Niederschlagsart-TAGESWERT (Issue #1324): PrecipType-Enum -> deutsches
    Label, analog ``_fmt_thunder``."""
    if v is None:
        return "—"
    key = v.value if hasattr(v, "value") else str(v)
    return _PRECIP_TYPE_LABEL.get(key, "—")


def _fmt_visibility_overview(v) -> str:
    """Sicht-TAGESWERT der Uebersichts-Matrix (Issue #1285).

    Nutzt die bestehende Compare-Darstellung (`_fmt_visibility`: Meter -> km,
    eine Nachkommastelle) und haengt die Einheit an -- anders als die
    Stundentabelle hat die Uebersicht keine Einheiten-Legende unter sich, in
    der "km" sonst stuende. Der zugrundeliegende Wert bleibt der Trip-Wert in
    Metern (AC-15), nur die Anzeige ist compare-typisch.
    """
    return f"{_fmt_visibility(v)} km" if v is not None else "—"


# Issue #1214 Scheibe 2: "metric_id" verweist auf den Katalog-Eintrag
# (metric_catalog._METRICS) und ist die dokumentierte Verbindung fuer die
# Konsolidierung. In dieser Scheibe wird nur wind ueber severity_for/Katalog
# gefahren (Wind-45-Fix); die uebrigen Severity-/Format-Helfer bleiben lokal,
# weil der Katalog fuer sie KEINE aequivalenten display_thresholds/decimals
# bereitstellt (s. Report-Auffaelligkeit) und ein Umstellen sonst still das
# Rendering aendern wuerde. Die metric_id-Felder bereiten Scheibe 3+ vor.
#
# Issue #1285: precip_sum/pop_max/thunder_max/visibility_min sind NEU -- ihre
# Auswahl wurde bis 2026-07-16 STILL verworfen, weil es die Zeile gar nicht
# gab. "fmt" (optional) ersetzt die Zahl+Einheit-Standardformatierung
# `_fmt_metric` -- noetig fuer Nicht-Zahlwerte (Gewitter ist ein
# ThunderLevel-Enum und kracht in `f"{value:.0f}"` mit TypeError) und fuer die
# m->km-Umrechnung der Sicht. Zeilen OHNE "fmt" verhalten sich unveraendert.
CV2_METRICS = [
    {"key": "warn", "label": "Amtliche Warnungen", "kind": "warn"},
    {"key": "temp_max", "metric_id": "temperature", "label": "Temp max", "unit": "°C", "sev": _sev_temp},
    {"key": "wind_max", "metric_id": "wind", "label": "Wind", "unit": "km/h", "sev": _sev_wind},
    {"key": "precip_sum", "metric_id": "precipitation", "label": "Regen", "unit": "mm",
     "decimals": 1, "sev": _sev_rain},
    {"key": "pop_max", "metric_id": "rain_probability", "label": "Regenwahrscheinlichkeit",
     "unit": "%", "sev": _sev_pop},
    {"key": "thunder_max", "metric_id": "thunder", "label": "Gewitter",
     "fmt": _fmt_thunder, "sev": _sev_thunder},
    {"key": "sunny_hours", "metric_id": "sunshine", "label": "Sonne", "unit": "h", "decimals": 1},
    {"key": "cloud_avg", "metric_id": "cloud_total", "label": "Wolken", "unit": "%"},
    {"key": "uv_max", "metric_id": "uv_index", "label": "UV max", "unit": "", "sev": _sev_uv},
    {"key": "visibility_min", "metric_id": "visibility", "label": "Sicht min",
     "fmt": _fmt_visibility_overview, "sev": _sev_visibility},
    {"key": "snow_depth_cm", "metric_id": "snow_depth", "label": "Schneehöhe", "unit": "cm"},
    {"key": "snow_new_cm", "metric_id": "fresh_snow", "label": "Neuschnee", "unit": "cm"},
    # Issue #1296: vier weitere bis 2026-07-17 STILL verworfene Zeilen (analog
    # #1285). temp_min ohne "sev" (_sev_temp ist eine Hitze-Schwelle, fachlich
    # falsch fuer eine Kaelte-Kennzahl); freezing_level ebenfalls ohne "sev"
    # (kein AC verlangt Faerbung, s. Spec Known Limitations). cape_max bekam
    # mit Issue #1298 (B2) eine Ampel-Faerbung ueber _sev_cape.
    {"key": "temp_min", "label": "Temp min", "unit": "°C"},
    {"key": "gust_max", "label": "Böen", "unit": "km/h", "sev": _sev_gust},
    {"key": "cape_max", "label": "CAPE", "unit": "J/kg", "sev": _sev_cape},
    {"key": "freezing_level", "label": "Nullgradgrenze", "unit": "m"},
    # Issue #1324: zehn weitere additive Zeilen (keine Severity-Faerbung, s.
    # Spec Known Limitations). Klasse A (Renderer-ID = LocationResult-Feld):
    {"key": "wind_direction_avg", "label": "Windrichtung", "unit": "°"},
    {"key": "wind_chill_min", "label": "Gefühlte Temp. min", "unit": "°C"},
    {"key": "cloud_low_avg", "label": "Wolken tief", "unit": "%"},
    {"key": "cloud_mid_avg", "label": "Wolken mittel", "unit": "%"},
    {"key": "cloud_high_avg", "label": "Wolken hoch", "unit": "%"},
    # Klasse B (Live-Aggregat ueber _DAILY_AGGREGATE_FIELD):
    {"key": "humidity_avg", "label": "Luftfeuchtigkeit Ø", "unit": "%"},
    {"key": "dewpoint_avg", "label": "Taupunkt Ø", "unit": "°C"},
    {"key": "pressure_avg", "label": "Luftdruck Ø", "unit": "hPa"},
    {"key": "precip_type", "label": "Niederschlagsart", "fmt": _fmt_precip_type},
    {"key": "snowfall_limit", "label": "Schneefallgrenze", "unit": "m"},
]


# Issue #1106: ersetzt _HOUR_COLUMNS -- 9 konfigurierbare Wert-Spalten,
# kanonische Reihenfolge (AC-8). "Zeit" ist keine Metrik hier, sondern fest
# verdrahtete erste Spalte in _render_hour_row/_render_hour_table.
HOUR_METRICS = [
    {"key": "t2m_c", "metric_id": "temperature", "label": "Temp", "fmt": _fmt_deg, "sev": _sev_temp},
    {"key": "wind_chill_c", "metric_id": "wind_chill", "label": "Gef.", "fmt": _fmt_deg},
    {"key": "wind10m_kmh", "metric_id": "wind", "label": "Wind", "fmt": _fmt_kmh, "sev": _sev_wind},
    {"key": "gust_kmh", "metric_id": "gust", "label": "Böen", "fmt": _fmt_kmh, "sev": _sev_gust},
    {"key": "precip_1h_mm", "metric_id": "precipitation", "label": "Regen", "fmt": _fmt_rain, "sev": _sev_rain_safe},
    {"key": "uv_index", "metric_id": "uv_index", "label": "UV", "fmt": _fmt_uv, "sev": _sev_uv},
    {"key": "thunder_level", "metric_id": "thunder", "label": "Gew.", "fmt": _fmt_thunder, "sev": _sev_thunder},
    {"key": "pop_pct", "metric_id": "rain_probability", "label": "Regen-W.", "fmt": _fmt_pop, "sev": _sev_pop},
    {"key": "visibility_m", "metric_id": "visibility", "label": "Sicht", "fmt": _fmt_visibility, "sev": _sev_visibility},
]


# ---------------------------------------------------------------------------
# Korridor-mark-Markierung (Issue #1231, Slice 7, AC-19) — rein additive
# Anzeige-Signatur neben der bestehenden Severity-Faerbung. AC-20: wirkt
# ausschliesslich hier im Renderer, calculate_score() bleibt unberuehrt.
# ---------------------------------------------------------------------------

def _mark_lookup(corridors: list[Corridor] | None, id_map: dict[str, str]) -> dict[str, Corridor]:
    """`corridors` (nur mark=True) ueber `id_map` (vergleich-Namensraum ->
    Renderer-Zeilen-Key) aufgeloest. notify-only-Corridors (mark=False) und
    nicht mappbare Metriken fallen raus."""
    if not corridors:
        return {}
    return {id_map[c.metric]: c for c in corridors if c.mark and c.metric in id_map}


def _is_marked(corridor: Optional[Corridor], value) -> bool:
    """corridor_inside() (C5, src/services/corridor_match.py) ist die
    einzige Match-Quelle. Gewitter-Werte (ThunderLevel-Enum) werden vorab per
    thunder_ordinal() in ihr Ordinal uebersetzt -- Corridor.range traegt fuer
    diese Metrik Ordinalwerte, keine Enum-Instanzen."""
    if corridor is None:
        return False
    v = thunder_ordinal(value) if isinstance(value, ThunderLevel) else value
    return bool(corridor_inside(v, corridor.range[0], corridor.range[1]))


# Adversary F001 (Fix-Loop): class="corridor-mark" allein ist unsichtbar (keine
# <style>-Regel referenziert sie) -- die eigentliche Sichtbarkeits-Signatur ist
# ein additiver gruener Border-Balken (Inline-Style, E-Mail-tauglich). Der
# gruene Hintergrund-Tint (tone_css("green")) wird NUR gesetzt, wenn die Zelle
# noch keinen eigenen Severity-Hintergrund traegt -- sonst wuerde er die
# Severity-Farbe verdecken (Design-Prinzip Lesbarkeit, CLAUDE.md).
_MARK_BORDER = f"border-left:3px solid {G_SUCCESS};"


def _mark_cell_style(bg: str, marked: bool) -> tuple[str, str]:
    """(bg, extra_style) fuer eine Zelle -- `extra_style` wird VOR `background:`
    in den style-String eingefuegt, `bg` ist ggf. auf den gruenen Tint
    umgeschrieben (nur wenn zuvor transparent, s.o.)."""
    if not marked:
        return bg, ""
    mark_bg = tone_css("green")[0] if bg == "transparent" else bg
    return mark_bg, _MARK_BORDER


# ---------------------------------------------------------------------------
# Warn-Kürzel-Mapping (dünner Anzeige-Layer über OfficialAlert.hazard)
# ---------------------------------------------------------------------------

def _warn_short(alert) -> tuple[str, str]:
    """(Kuerzel-Text, Severity) je hazard. Fallback: alert.label ungekuerzt."""
    if alert.hazard == "extreme_heat":
        return "Hitze", "warn"
    if alert.hazard == "wildfire_risk":
        sev = {2: "caution", 3: "warn", 4: "danger"}.get(alert.level, "warn")
        return f"Brand · {alert.level}", sev
    if alert.hazard == "access_ban":
        return "Zugang", "caution"
    return alert.label, "info"


def _dedup_alerts(alerts: list) -> list:
    """Duenner Wrapper um die kanonische Dedup-Quelle `dedupe_official_alerts`
    (Issue #1217/#1218): Uebersichts-Chip und Pro-Ort-Streifen nutzen dieselbe
    Gruppierung `(region_label or label, hazard)` + hoechste Stufe."""
    from output.renderers.alert.official_alerts import dedupe_official_alerts

    return [a for a, _ in dedupe_official_alerts([(a, []) for a in alerts])]


def _render_warn_cell(alerts: list) -> str:
    """Warn-Zellen-Inhalt: gestapelte Kuerzel-Chips oder '—' bei keiner Warnung.

    Block-Divs statt Flexbox (Outlook-fest, AC-8) -- stapeln sich von selbst.
    """
    if not alerts:
        return '<span style="color:#b8b4a8;font-size:12px;">—</span>'
    chips = []
    for alert in alerts:
        short, _sev = _warn_short(alert)
        bg, fg = _ALERT_LEVEL_CELL.get(alert.level, _ALERT_LEVEL_CELL[4])
        chips.append(
            f'<div style="display:inline-block;font-size:9.5px;font-weight:700;'
            f'letter-spacing:0.01em;padding:2px 6px;margin:1px auto;white-space:nowrap;'
            f'background:{bg};color:{fg};border:1px solid {fg}22;">{_html.escape(short)}</div>'
        )
    return "".join(chips)


# ---------------------------------------------------------------------------
# Uebersichtstabelle (Metriken x Orte)
# ---------------------------------------------------------------------------

# Issue #1285: Uebersichts-Zeilen, deren Tageswert NICHT als gleichnamiges
# LocationResult-Feld vorliegt. (Renderer-Zeilen-Key -> LocationResult-Feld /
# SegmentWeatherSummary-Feld). Beide Quellen tragen denselben Namen, weil das
# LocationResult-Feld exakt das Trip-Aggregat spiegelt.
_DAILY_AGGREGATE_FIELD: dict[str, str] = {
    "precip_sum": "precip_sum_mm",
    "pop_max": "pop_max_pct",
    "thunder_max": "thunder_level_max",
    "uv_max": "uv_index_max",
    "visibility_min": "visibility_min_m",
    # Issue #1296, Klasse B: cape_max/freezing_level haben KEIN LocationResult-
    # Feld (anders als temp_min/gust_max, die ueber den field-is-None-Zweig von
    # _metric_value direkt per getattr(loc, key) gelesen werden) -- der Wert
    # kommt ausschliesslich aus der Live-Ableitung (_daily_summary).
    "cape_max": "cape_max_jkg",
    "freezing_level": "freezing_level_m",
    # Issue #1324, Klasse B: kein LocationResult-Feld, Wert kommt aus der
    # Live-Ableitung (_daily_summary -> SegmentWeatherSummary).
    "humidity_avg": "humidity_avg_pct",
    "dewpoint_avg": "dewpoint_avg_c",
    "pressure_avg": "pressure_avg_hpa",
    "precip_type": "precip_type_dominant",
    "snowfall_limit": "snowfall_limit_m",
}


def _daily_summary(loc: LocationResult):
    """Tages-Aggregat eines Ortes aus ``hourly_data`` (kanonische Trip-Regeln).

    Der Renderer darf sich NICHT darauf verlassen, dass die ComparisonEngine
    gelaufen ist: ``dict_to_comparison_result()`` und der Validator-Render-Pfad
    fuettern denselben Renderer ohne Engine. Genau dieses Live-Ableiten aus
    ``hourly_data`` macht ``uv_max`` heute schon (Issue #1110); die vier neuen
    Zeilen folgen demselben Muster.
    """
    from services.weather_metrics import summarize_points

    return summarize_points(loc.hourly_data)


def _metric_value(loc: LocationResult, key: str, summary=None):
    field = _DAILY_AGGREGATE_FIELD.get(key)
    if field is None:
        return getattr(loc, key, None)
    # Engine-Wert hat Vorrang; fehlt er (kein Engine-Lauf), live ableiten.
    value = getattr(loc, field, None)
    if value is not None:
        return value
    if summary is None:
        summary = _daily_summary(loc)
    return getattr(summary, field, None) if summary is not None else None


def _fmt_metric(value, decimals, unit: str) -> str:
    if value is None:
        return "—"
    text = f"{value:.{decimals if decimals is not None else 0}f}"
    if not unit:
        return text
    return f"{text}{unit}" if unit in ("°C", "%") else f"{text} {unit}"


def _render_overview_row(
    m: dict, locations: list[LocationResult], marks: dict | None = None,
    summaries: dict | None = None,
) -> str:
    marks = marks or {}
    summaries = summaries or {}
    label_cell = (
        f'<td style="text-align:left;padding:8px 5px;font-family:{FONT_UI};'
        f'color:{G_INK_MUTED};font-weight:500;font-size:12px;'
        f'border-right:1px solid #f0ece1;">{_html.escape(m["label"])}</td>'
    )
    cells = [label_cell]
    for loc in locations:
        if m["key"] == "warn":
            content = "—" if loc.error is not None else _render_warn_cell(_dedup_alerts(loc.official_alerts))
            cells.append(
                f'<td style="text-align:center;padding:7px 5px;vertical-align:middle;'
                f'border-right:1px solid #f0ece1;">{content}</td>'
            )
            continue
        value = (
            None if loc.error is not None
            else _metric_value(loc, m["key"], summaries.get(id(loc)))
        )
        sev_fn = m.get("sev")
        sev_level = sev_fn(value) if (sev_fn and value is not None) else None
        bg, fg, weight = "transparent", G_INK, "500"
        if sev_level and sev_level != "ok":
            # Issue #1214 Scheibe 2: Zell-Toenung ueber die zentrale tone_css-
            # Palette (kanonisches Vokabular), Compare-lokal -> kanonisch.
            bg, fg = tone_css(_COMPARE_TO_CANONICAL[sev_level])
            weight = "700"
        fmt_fn = m.get("fmt")
        text = fmt_fn(value) if fmt_fn else _fmt_metric(value, m.get("decimals"), m.get("unit", ""))
        marked = _is_marked(marks.get(m["key"]), value)
        cls = ' class="corridor-mark"' if marked else ""
        bg, extra_style = _mark_cell_style(bg, marked)
        cells.append(
            f'<td{cls} style="text-align:center;padding:8px 5px;font-family:{FONT_DATA};'
            f'font-size:12.5px;{extra_style}background:{bg};color:{fg};font-weight:{weight};'
            f'border-right:1px solid #f0ece1;">{text}</td>'
        )
    return f'<tr style="border-bottom:1px solid #f0ece1;">{"".join(cells)}</tr>'


def _visible_metrics(enabled_metrics: set | None) -> list[dict]:
    """Issue #1104: filtert die NUMERISCHEN Uebersichts-Zeilen auf
    ``enabled_metrics`` (Set von Renderer-Metrik-IDs wie "wind_max"). Die
    Warn-Zeile ("Amtliche Warnungen") ist immer sichtbar. ``None`` = kein
    Filter (alle Zeilen, Rueckwaertskompatibilitaet)."""
    if enabled_metrics is None:
        return CV2_METRICS
    return [m for m in CV2_METRICS if m["key"] == "warn" or m["key"] in enabled_metrics]


def _render_overview_table(
    locations: list[LocationResult],
    enabled_metrics: set | None = None,
    corridors: list[Corridor] | None = None,
) -> str:
    header_cells = [
        f'<th style="text-align:left;padding:9px 5px;font-size:10px;'
        f'color:{G_INK_FAINT};border-right:1px solid #f0ece1;">Metrik</th>'
    ]
    for loc in locations:
        name = _html.escape(loc.location.name)
        header_cells.append(
            f'<th style="text-align:center;padding:9px 5px;font-size:11px;'
            f'font-family:{FONT_UI};font-weight:600;color:{G_INK};'
            f'border-right:1px solid #f0ece1;">{name}</th>'
        )
    header_row = (
        f'<tr style="background:{G_PAPER};border-bottom:1px solid #e6e1d3;">'
        f'{"".join(header_cells)}</tr>'
    )
    marks = _mark_lookup(corridors, FRONTEND_TO_RENDERER_METRIC_ID)
    visible = _visible_metrics(enabled_metrics)
    # Tages-Aggregate EINMAL je Ort ableiten (nicht je Zeile x Ort) -- nur wenn
    # ueberhaupt eine Zeile davon lebt.
    summaries: dict = {}
    if any(m["key"] in _DAILY_AGGREGATE_FIELD for m in visible):
        summaries = {
            id(loc): _daily_summary(loc)
            for loc in locations if loc.error is None and loc.hourly_data
        }
    rows = "".join(_render_overview_row(m, locations, marks, summaries) for m in visible)
    table = (
        f'<table cellspacing="0" cellpadding="0" style="width:100%;min-width:760px;'
        f'border-collapse:collapse;font-family:{FONT_DATA};'
        f'font-variant-numeric:tabular-nums;">'
        f'<thead>{header_row}</thead><tbody>{rows}</tbody></table>'
    )
    return (
        f'<div style="overflow-x:auto;-webkit-overflow-scrolling:touch;'
        f'margin-top:12px;border:1px solid #e6e1d3;">{table}</div>'
    )


def _render_warn_banner(locations: list[LocationResult]) -> str:
    """Aggregat-WarnBlock-Banner (Issue #1216): geteilter embedded WarnBlock mit
    Orts-Scope. Nennt die höchste amtliche Stufe + den führenden Ort („höchste
    Stufe ROT · Marseille") und zählt die betroffenen Orte je Gefahr („6 von 7
    Orten"). ADDITIV zum Bestands-Warn-Lead, zur Matrix-Warn-Zeile und zum
    Pro-Ort-Streifen (PO-Entscheidung Frage D, additiver Umbau)."""
    valid = [loc for loc in locations if loc.error is None]
    alerted = [loc for loc in valid if loc.official_alerts]
    if not alerted:
        return ""

    total = len(valid)
    leading_loc = None
    leading_alert = None
    for loc in alerted:
        for a in loc.official_alerts:
            if leading_alert is None or a.level > leading_alert.level:
                leading_alert, leading_loc = a, loc
    word = _LEVEL_WORDS.get(leading_alert.level, ("🔴", "ROT"))[1]
    count_line = f"höchste Stufe {word} · {leading_loc.location.name}"

    # Je Gefahr die höchststufige Warnung, Meter nach Stufe absteigend.
    by_hazard: dict = {}
    for loc in alerted:
        for a in loc.official_alerts:
            cur = by_hazard.get(a.hazard)
            if cur is None or a.level > cur.level:
                by_hazard[a.hazard] = a
    notices = []
    for a in sorted(by_hazard.values(), key=lambda x: -x.level):
        hz_locs = [loc for loc in alerted if any(x.hazard == a.hazard for x in loc.official_alerts)]
        if len(hz_locs) > 1:
            chip = f"{len(hz_locs)} von {total} Orten"
        else:
            chip = hz_locs[0].location.name if hz_locs else ""
        notices.append(OfficialAlertNotice(
            alert=a, scope_label="", sms_scope="",
            affected_chips=[chip] if chip else [], free_chips=[],
        ))

    return render_warn_block(
        notices, variant="embedded",
        source_label=official_alert_source_label(leading_alert.source),
        source_url=getattr(leading_alert, "url", None), count_line=count_line,
    )


# ---------------------------------------------------------------------------
# Stundentabellen (alle Orte)
# ---------------------------------------------------------------------------

def _sev_cell_style(level: Optional[str]) -> tuple[str, str, str]:
    if level is None or level == "ok":
        return "transparent", G_INK, "500"
    # Issue #1214 Scheibe 2: zentrale tone_css-Palette, Compare-lokal -> kanonisch.
    bg, fg = tone_css(_COMPARE_TO_CANONICAL[level])
    return bg, fg, "700"


def _hour_td(
    text: str, bg: str = "transparent", fg: str = G_INK, weight: str = "500",
    align: str = "center", marked: bool = False,
) -> str:
    cls = ' class="corridor-mark"' if marked else ""
    bg, extra_style = _mark_cell_style(bg, marked)
    return (
        f'<td{cls} style="text-align:{align};padding:8px 4px;font-size:13px;'
        f'{extra_style}background:{bg};color:{fg};font-weight:{weight};'
        f'border-right:1px solid #f0ece1;">{text}</td>'
    )


def _visible_hour_metrics(hourly_metrics: set | None) -> list[dict]:
    """Issue #1106: filtert ``HOUR_METRICS`` auf ``hourly_metrics`` (Set von
    Renderer-Metrik-IDs wie "t2m_c"). ``None`` = kein Filter (alle 9 Spalten,
    Default). Kanonische Reihenfolge (Reihenfolge von HOUR_METRICS) bleibt
    unabhaengig von der Set-Konstruktions-Reihenfolge erhalten (AC-8)."""
    if hourly_metrics is None:
        return HOUR_METRICS
    return [m for m in HOUR_METRICS if m["key"] in hourly_metrics]


def _render_hour_row(dp, visible: list[dict], marks: dict) -> str:
    # Issue #1237 (AC-1): nur die Stunde ("07"), kein Minutenanteil -- identisch
    # zur bereits korrekten Trip-Briefing-Formatierung (helpers.dp_to_row).
    hh = dp.ts.strftime("%H") if hasattr(dp.ts, "strftime") else str(dp.ts)
    cells = _hour_td(hh, fg=G_INK_MUTED, align="left")
    for m in visible:
        value = getattr(dp, m["key"], None)
        text = m["fmt"](value)
        sev_fn = m.get("sev")
        sev_level = sev_fn(value) if (sev_fn and value is not None) else None
        style = _sev_cell_style(sev_level)
        marked = _is_marked(marks.get(m["key"]), value)
        cells += _hour_td(text, *style, marked=marked)
    return f'<tr style="border-bottom:1px solid #f0ece1;">{cells}</tr>'


def _render_hour_table(
    loc: LocationResult, hourly_metrics: set | None = None, corridors: list[Corridor] | None = None,
) -> str:
    visible = _visible_hour_metrics(hourly_metrics)
    marks = _mark_lookup(corridors, CORRIDOR_METRIC_TO_HOUR_KEY)
    columns = ["Zeit"] + [m["label"] for m in visible]
    ths = "".join(
        f'<th style="text-align:{"left" if col == "Zeit" else "center"};padding:6px 4px;'
        f'font-size:11px;color:{G_INK};font-weight:600;border-right:1px solid #f0ece1;">'
        f'{col}</th>'
        for col in columns
    )
    header = f'<tr style="background:{G_PAPER};border-bottom:1px solid #e6e1d3;">{ths}</tr>'
    rows = "".join(_render_hour_row(dp, visible, marks) for dp in loc.hourly_data)
    table = (
        f'<table cellspacing="0" cellpadding="0" style="width:100%;'
        f'border-collapse:collapse;margin-top:12px;font-family:{FONT_DATA};'
        f'font-size:12px;font-variant-numeric:tabular-nums;">'
        f'<thead>{header}</thead><tbody>{rows}</tbody></table>'
    )
    return (
        f'<div style="overflow-x:auto;-webkit-overflow-scrolling:touch;'
        f'margin-top:12px;border:1px solid #e6e1d3;">{table}</div>'
    )


def _render_location_section(
    loc: LocationResult, index: int, hourly_metrics: set | None = None,
    corridors: list[Corridor] | None = None,
) -> str:
    """Ort-Kopf + Langform-Warn-Streifen + Stundentabelle. Entfaellt bei Fehler
    bzw. fehlenden Stundendaten (SPEC §4)."""
    if loc.error is not None or not loc.hourly_data:
        return ""
    name = _html.escape(loc.location.name)
    header = (
        f'<div style="padding-bottom:8px;border-bottom:2px solid {G_INK};">'
        f'<span style="font-family:{FONT_DATA};font-size:11px;font-weight:600;'
        f'color:{G_ACCENT};letter-spacing:0.1em;">ORT</span> '
        f'<span style="font-size:15px;font-weight:600;color:{G_INK};">{name}</span>'
        f'</div>'
    )
    strip = ""
    if loc.official_alerts:
        # F002 (Adversary Fix-Runde): kein Ortsnamen-Praefix im Compare-Streifen
        # (der Ort-Kopf direkt darueber nennt den Namen bereits) -- geloest per
        # leerem Gruppen-Label am Compare-Aufruf, das Shared-Modul selbst
        # (ADR-0011, Trip-Pfad) bleibt unveraendert.
        # Issue #1134: Dedup identischer Warnungen. Issue #1056 v2.0: Badge-
        # Farbe ist amtstreu level-basiert (kein severity_fn mehr).
        strip = render_official_alerts_html(
            [("", _dedup_alerts(loc.official_alerts))],
        )
    return (
        f'<div style="padding:{20 if index else 14}px 24px 0;">'
        f'{header}{strip}{_render_hour_table(loc, hourly_metrics, corridors)}</div>'
    )


# ---------------------------------------------------------------------------
# Epic #1301 B4 — 3-Tage-Ausblick je Ort (geteilter Renderer/Zeilenbau)
# ---------------------------------------------------------------------------

_WEEKDAYS_DE_OUTLOOK = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


def _group_by_calendar_day(points: list, cap: int = 3) -> list[tuple]:
    """Gruppiert eine flache Punktliste nach Kalendertag, Cap auf `cap` Tage."""
    by_day: dict = {}
    for dp in points:
        by_day.setdefault(dp.ts.date(), []).append(dp)
    days = sorted(by_day)[:cap]
    return [(d, by_day[d]) for d in days]


def _build_location_outlook_rows(loc: LocationResult) -> list[dict]:
    """AC-5/AC-8: bis zu 3 Tages-Zeilen aus `outlook_hourly_data`, ueber
    denselben Aggregator (`summarize_points`) und denselben Zeilenbau
    (`build_outlook_row`) wie der Trip-Pfad (Trip/Compare-Teilungs-
    Invariante)."""
    from zoneinfo import ZoneInfo

    from services.weather_metrics import summarize_points

    tz_name = getattr(loc.location, "timezone", None) or "UTC"
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("UTC")

    rows = []
    for day, day_points in _group_by_calendar_day(loc.outlook_hourly_data):
        summary = summarize_points(day_points)
        weekday = _WEEKDAYS_DE_OUTLOOK[day.weekday()]
        rows.append(build_outlook_row(summary, day_points, weekday, tz))
    return rows


def _render_location_outlook(loc: LocationResult, index: int) -> str:
    """AC-5/AC-9: Ausblick-Tabelle je Ort; entfaellt fail-soft bei Fehler
    bzw. leerem `outlook_hourly_data` (kein Crash, restliche Mail
    unveraendert)."""
    if loc.error is not None or not loc.outlook_hourly_data:
        return ""
    rows = _build_location_outlook_rows(loc)
    if not rows:
        return ""
    name = _html.escape(loc.location.name)
    header = (
        f'<div style="padding-bottom:8px;border-bottom:2px solid {G_INK};">'
        f'<span style="font-family:{FONT_DATA};font-size:11px;font-weight:600;'
        f'color:{G_ACCENT};letter-spacing:0.1em;">ORT</span> '
        f'<span style="font-size:15px;font-weight:600;color:{G_INK};">{name}</span>'
        f'</div>'
    )
    table = render_outlook_table(rows, show_acc=False)
    return (
        f'<div style="padding:{20 if index else 14}px 24px 0;">'
        f'{header}{table}</div>'
    )


def _render_official_alerts_block(locations: list[LocationResult]) -> str:
    """Badges fuer amtliche Warnungen je Ort (Thin-Wrapper, ADR-0011).

    Nicht mehr Teil des Hauptrenderpfads (v2 nutzt Warn-Chips in der
    Uebersichtstabelle + Langform-Streifen je Ort), aber als generischer
    Baustein erhalten (Byte-Gleichheit zu #1087 fuer registrierte Konsumenten).
    """
    entries = [(loc.location.name, loc.official_alerts) for loc in locations]
    return render_official_alerts_html(entries)


# ---------------------------------------------------------------------------
# Header / Section-Head / Legende / Footer
# ---------------------------------------------------------------------------

def _render_warning_banner(warning_text: str) -> str:
    """Orange-Banner mit G_WARNING-Akzent (allgemeine Betriebswarnungen,
    z.B. nicht verfuegbare Standorte -- unabhaengig von amtlichen Warnungen)."""
    safe = _html.escape(warning_text)
    return (
        f'<div style="background:{G_BOX_WARNING_BG};'
        f'border-left:4px solid {G_WARNING};'
        f'padding:12px 16px;margin:8px 20px;'
        f'border-radius:4px;font-family:{FONT_UI};font-size:14px;'
        f'color:{G_INK};">'
        f'{safe}</div>'
    )


def _render_header(result: ComparisonResult, sig) -> str:
    label_text = f"ORTS-VERGLEICH · {_html.escape(sig.eyebrow)}"
    label_style = (
        f"font-family:{FONT_DATA};font-size:10px;"
        f"color:{G_ACCENT};letter-spacing:0.08em;"
        f"text-transform:uppercase;margin:0 0 6px 0;"
    )

    weekday = _WEEKDAY_ABBR[result.target_date.weekday()]
    date_str = result.target_date.strftime("%d.%m.%Y")
    # Issue #1268: keine Zeitfenster-Angabe mehr in der Kopfzeile — die
    # Bewertung laeuft immer ueber den ganzen Tag, es gibt nichts zu zeigen.
    date_line = f"{weekday}, {date_str}"
    date_style = f"font-family:{FONT_DATA};font-size:13px;color:{G_INK};margin-top:6px;"

    profil_val = _html.escape(sig.eyebrow)
    orte_val = str(len(result.locations))
    erstellt_val = datetime.now().strftime("%H:%M")
    # Issue #1305: keine Horizont-Kachel mehr — analog #1268 (Zeitfenster-Zeile
    # entfiel ersatzlos). Der Wert ist kein Nutzer-relevanter Datenpunkt.

    cell_label_style = (
        f"font-family:{FONT_DATA};font-size:9px;"
        f"color:{G_INK_FAINT};text-transform:uppercase;"
        f"letter-spacing:0.08em;padding-bottom:2px;"
    )
    cell_value_style = f"font-family:{FONT_UI};font-size:14px;color:{G_INK};font-weight:600;"

    def _cell(label: str, value: str, width: str) -> str:
        return (
            f'<td width="{width}" style="vertical-align:top;padding:0 8px 0 0;">'
            f'<div style="{cell_label_style}">{label}</div>'
            f'<div style="{cell_value_style}">{value}</div>'
            f'</td>'
        )

    desktop_cells = (
        _cell("Profil", profil_val, "33%")
        + _cell("Orte", orte_val, "33%")
        + _cell("Erstellt", erstellt_val, "34%")
    )
    desktop_table = (
        f'<table class="header-stats-desktop" cellspacing="0" cellpadding="0" '
        f'style="width:100%;margin-top:14px;border-collapse:collapse;">'
        f'<tr>{desktop_cells}</tr></table>'
    )

    mobile_row1 = _cell("Profil", profil_val, "50%") + _cell("Orte", orte_val, "50%")
    mobile_row2 = _cell("Erstellt", erstellt_val, "100%")
    mobile_table = (
        f'<table class="header-stats-mobile" cellspacing="0" cellpadding="0" '
        f'style="display:none;width:100%;margin-top:14px;border-collapse:collapse;">'
        f'<tr>{mobile_row1}</tr><tr>{mobile_row2}</tr></table>'
    )

    wrapper_style = f"background:{G_PAPER};padding:22px;border-bottom:1px solid #e6e1d3;"
    return (
        f'<div class="header-wrapper" style="{wrapper_style}">'
        f'<div style="{label_style}">{label_text}</div>'
        f'<div style="{date_style}">{date_line}</div>'
        f'{desktop_table}{mobile_table}</div>'
    )


def _render_section_head(accent: str, title: str, hint: str) -> str:
    return (
        f'<table style="width:100%;border-collapse:collapse;"><tr>'
        f'<td style="text-align:left;padding:0 0 8px;border-bottom:2px solid {G_INK};">'
        f'<span style="font-family:{FONT_DATA};font-size:11px;font-weight:600;'
        f'color:{G_ACCENT};letter-spacing:0.1em;">{_html.escape(accent)}</span> '
        f'<span style="font-size:14px;font-weight:600;color:{G_INK};">{_html.escape(title)}</span>'
        f'</td>'
        f'<td style="text-align:right;padding:0 0 8px;border-bottom:2px solid {G_INK};'
        f'font-family:{FONT_DATA};font-size:10px;color:{G_INK_FAINT};">'
        f'{_html.escape(hint)}</td>'
        f'</tr></table>'
    )


def _units_legend_text(visible: list[dict]) -> str:
    """Issue #1237 (AC-2): Einheiten-Zeile fuer die sichtbaren Stunden-Spalten.
    Einheit je Spalte kommt aus dem Metrik-Katalog (`display_unit`, sonst
    `unit`), formatiert vom geteilten Helfer `helpers.format_units_legend` --
    dieselbe Quelle wie die Trip-Briefing-Legende (keine Kopie)."""
    from app.metric_catalog import _METRICS_BY_ID
    from output.renderers.email.helpers import format_units_legend

    pairs: list[tuple[str, str]] = []
    for m in visible:
        mdef = _METRICS_BY_ID.get(m.get("metric_id", ""))
        if mdef is None:
            continue
        pairs.append((m["label"], mdef.display_unit if mdef.display_unit else mdef.unit))
    return format_units_legend(pairs)


def _render_units_legend(hourly_metrics: set | None) -> str:
    """Einheiten-Legende UNTER der Stundentabelle (nicht im Spaltenkopf) --
    die Spaltenkoepfe bleiben 'Zeit'/'Sicht' (AC-2)."""
    text = _units_legend_text(_visible_hour_metrics(hourly_metrics))
    if not text:
        return ""
    return (
        f'<div style="margin-top:8px;font-family:{FONT_DATA};font-size:10px;'
        f'color:{G_INK_MUTED};">{_html.escape(text)}</div>'
    )


def _render_legend(hourly_metrics: set | None = None, hourly_enabled: bool = True) -> str:
    items = [("#2f8a3e", "unkritisch"), ("#e3b008", "Achtung"), ("#e07b1a", "Warnung"), ("#c52a22", "Gefahr")]
    dots = "".join(
        f'<span style="display:inline-block;margin-right:16px;font-family:{FONT_DATA};'
        f'font-size:10px;color:{G_INK_MUTED};">'
        f'<span style="display:inline-block;width:10px;height:10px;border-radius:50%;'
        f'background:{color};margin-right:6px;vertical-align:middle;"></span>{label}</span>'
        for color, label in items
    )
    units = _render_units_legend(hourly_metrics) if hourly_enabled else ""
    return (
        f'<div style="background:{G_PAPER};border-top:1px solid #e6e1d3;padding:18px 24px;'
        f'margin-top:22px;font-family:{FONT_DATA};font-size:10px;color:{G_INK_MUTED};">'
        f'<span style="font-weight:600;color:{G_INK_FAINT};letter-spacing:0.08em;'
        f'text-transform:uppercase;margin-right:16px;">Risk</span>{dots}'
        f'<span style="color:{G_INK_FAINT};">Warn-Kürzel: Hitze · Brand·Stufe · Zugang</span>'
        f'{units}'
        f'</div>'
    )


def _compute_next_send(schedule, weekday) -> Optional[str]:
    """Known Limitation (SPEC): liefert None (-> '—'), wenn schedule nicht
    ermittelbar ist."""
    if not schedule:
        return None
    today = date.today()
    schedule_str = str(schedule).lower()
    if "weekly" in schedule_str and weekday is not None:
        try:
            target_wd = int(weekday)
        except (TypeError, ValueError):
            return None
        days_ahead = (target_wd - today.weekday()) % 7 or 7
        return (today + timedelta(days=days_ahead)).strftime("%d.%m.%Y")
    if "daily" in schedule_str:
        return (today + timedelta(days=1)).strftime("%d.%m.%Y")
    return None


def _render_abo_footer(preset_name, preset_schedule, preset_weekday, location_count: int, sig) -> str:
    name = _html.escape(preset_name) if preset_name else "Ortsvergleich"
    next_send = _compute_next_send(preset_schedule, preset_weekday) or "—"
    return (
        f'<div style="padding:20px 24px;background:{G_PAPER};border-top:1px solid #e6e1d3;">'
        f'<table style="width:100%;border-collapse:collapse;"><tr>'
        f'<td style="vertical-align:top;width:50%;">'
        f'<span style="font-family:{FONT_DATA};font-size:10px;color:{G_INK_FAINT};'
        f'text-transform:uppercase;letter-spacing:0.1em;">Dieses Abo</span>'
        f'<div style="font-size:14px;font-weight:600;margin-top:4px;color:{G_INK};">{name}</div>'
        f'<div style="font-size:11px;color:{G_INK_MUTED};margin-top:4px;'
        f'font-family:{FONT_DATA};line-height:1.6;">'
        f'{location_count} Orte · Profil {_html.escape(sig.eyebrow)}</div>'
        f'</td>'
        f'<td style="vertical-align:top;width:50%;">'
        f'<span style="font-family:{FONT_DATA};font-size:10px;color:{G_INK_FAINT};'
        f'text-transform:uppercase;letter-spacing:0.1em;">Nächster Versand</span>'
        f'<div style="font-size:14px;font-weight:600;margin-top:4px;'
        f'font-family:{FONT_DATA};color:{G_INK};">{next_send}</div>'
        f'</td></tr></table></div>'
    )


def _render_app_footer() -> str:
    # Issue #1241: dezente Herkunfts-Fußzeile (SSoT-Helper).
    from output.renderers.email.helpers import (
        build_origin_footer, render_origin_footer_html,
    )
    origin_html = render_origin_footer_html(build_origin_footer(
        "compare", renderer_name="email/compare_html.py",
    ))
    return (
        f'<div style="padding:16px 24px 20px;background:{G_INK};color:#9a978d;'
        f'font-size:11px;font-family:{FONT_DATA};">'
        f'<span style="color:#ffffff;font-weight:600;letter-spacing:0.06em;">GREGOR ZWANZIG</span>'
        f' <span style="color:#5a5750;">·</span> Orts-Vergleich'
        f'<div style="margin-top:8px;padding-top:8px;border-top:1px solid #3a3835;font-size:10px;">'
        f'<a href="#" style="color:{G_ACCENT};text-decoration:none;margin-right:16px;">'
        f'Vergleich in App öffnen →</a>'
        f'<a href="#" style="color:#9a978d;text-decoration:none;margin-right:16px;">Abo bearbeiten</a>'
        f'<a href="#" style="color:#9a978d;text-decoration:none;margin-right:16px;">Orte ändern</a>'
        f'<a href="#" style="color:#9a978d;text-decoration:none;">Abmelden</a>'
        f'</div></div>'
        + origin_html
    )


def sort_locations_alphabetically(locations: list[LocationResult]) -> list[LocationResult]:
    """Zentraler Sortier-Helfer (PO-Update 2026-07-08): alphabetisch nach
    Ortsname, case-insensitiv -- einheitlich fuer Uebersichts-Spalten,
    Stundentabellen-Abschnitte (hier) UND Klartext (output.renderers.comparison,
    importiert von dort -- keine Doppel-Implementierung)."""
    return sorted(locations, key=lambda loc: loc.location.name.casefold())


# ---------------------------------------------------------------------------
# Oeffentliche API
# ---------------------------------------------------------------------------

def render_compare_html(
    result: ComparisonResult,
    *,
    profile: Optional[ActivityProfile] = None,
    warnings: list[str] | None = None,
    top_n_details: Optional[int] = None,
    enabled_metrics: set | None = None,
    hourly_metrics: set | None = None,
    hourly_enabled: bool = True,
    preset_name: Optional[str] = None,
    preset_schedule: Optional[str] = None,
    preset_weekday: Optional[int] = None,
    corridors: list[Corridor] | None = None,
    outlook_enabled: bool = False,
) -> str:
    """Rendert ComparisonResult als HTML-Mail (v2-Layout, Issue #1110).

    Pure Function — keine Seiteneffekte, kein Netzwerk. Kein Score/Winner.

    Args:
        result: ComparisonResult aus ComparisonEngine.
        profile: ActivityProfile fuer Eyebrow. Default ALLGEMEIN.
        warnings: Liste allgemeiner Betriebswarnungen (orange Banner).
        top_n_details: Issue #1104 -- wird angenommen, hat AKTUELL KEINE
            Wirkung (PO 2026-07-08: die Mail zeigt immer alle Orte;
            Stundentabellen-Beschraenkung wird in #1105-#1107 neu definiert).
        enabled_metrics: Optionales Set von Renderer-Metrik-IDs (z.B.
            "wind_max"/"cloud_avg"), filtert die numerischen Uebersichts-
            Zeilen. Die Warn-Zeile "Amtliche Warnungen" ist immer sichtbar.
            ``None`` = alle Metriken (Default, rueckwaertskompatibel).
        hourly_metrics: Optionales Set von Renderer-Metrik-IDs (Issue #1106,
            z.B. "t2m_c"/"thunder_level"), filtert die Wert-Spalten je
            Stundentabelle. "Zeit" bleibt immer erste Spalte. ``None`` = alle
            9 Spalten (Default).
        hourly_enabled: Issue #1107 -- ``False`` laesst die komplette
            Stundenverlauf-Sektion (Kopf "STUNDEN" + alle Orts-
            Stundentabellen) weg. ``hourly_metrics`` (Spalten-Filter,
            #1106) hat dann keine Wirkung mehr, da die Sektion gar nicht
            gerendert wird. Default ``True`` (rueckwaertskompatibel,
            identisch zum Verhalten vor diesem Slice).
        preset_name: Name des Compare-Presets fuer den Abo-Footer.
        preset_schedule: Schedule-Wert (z.B. "daily"/"weekly") fuer "Naechster Versand".
        preset_weekday: Wochentag-Index (0=Mo) fuer weekly-Schedules.
        corridors: Issue #1231, Slice 7 -- Corridor-Liste des Presets. Zellen,
            deren Wert bei einem `mark=True`-Corridor innerhalb dessen `range`
            liegt (`corridor_inside()`, C5), erhalten zusaetzlich
            `class="corridor-mark"` (additiv zur Severity-Faerbung, AC-19).
            `None`/`[]` = kein Korridor konfiguriert, HTML unveraendert.
        outlook_enabled: Epic #1301 B4 -- ``True`` zeigt je Ort einen bis zu
            3-Tage-Ausblick (Tagestabelle ohne ACC-Spalte, `show_acc=False`,
            ADR-0005/#710). Default ``False`` (rueckwaertskompatibel; der
            Aufrufer resolved den tatsaechlichen Default ueber
            `resolve_compare_render_options`, s. `report_config_resolver.py`).

    Returns:
        HTML-String (DOCTYPE bis </html>).
    """
    _ = top_n_details  # akzeptiert (Issue #1104), aktuell ohne Wirkung (s. Docstring)
    warnings = warnings or []
    sig = profile_signature(profile)
    locations = sort_locations_alphabetically(result.locations)

    header_html = _render_header(result, sig)
    warnings_html = "".join(_render_warning_banner(w) for w in warnings)
    warn_banner_html = _render_warn_banner(locations)

    overview_html = (
        f'<div style="padding:6px 24px 0;">'
        f'{_render_section_head("ÜBERSICHT", "Alle Orte · gewählte Metriken", "← scrollen")}'
        f'{_render_overview_table(locations, enabled_metrics, corridors)}</div>'
    )
    # Issue #1278 (Nebenbefund, AC-12): die dritte Angabe war fest "09–16 Uhr" --
    # ein toter Rest des mit #1268 abgeschafften Zeitfensters. Die Bewertung
    # laeuft seit #1268 ueber den ganzen Tag; die Angabe behauptete eine
    # Einschraenkung, die es nicht gibt. Ersatzlos leer (analog zur bereits
    # entfernten Zeitfenster-Zeile im Klartext-Header, comparison.py:77).
    hourly_head_html = (
        f'<div style="padding:26px 24px 0;">'
        f'{_render_section_head("STUNDEN", "Stundenverlauf · alle Orte", "")}</div>'
    ) if hourly_enabled else ""

    # Issue #1323: der 3-Tage-Ausblick je Ort (Epic #1301 B4) steht direkt
    # unter dessen eigener Stundentabelle, statt als Sammelblock hinter
    # allen Orten. Eine Per-Ort-Schleife (Reihenfolge = Uebersichts-Spalten)
    # statt zwei getrennt gejointen Bloecken. Fail-soft je Ort bleibt
    # erhalten (_render_location_section/_render_location_outlook liefern
    # bei fehlenden Daten "").
    per_location_html = "".join(
        (
            (_render_location_section(loc, i, hourly_metrics, corridors) if hourly_enabled else "")
            + (_render_location_outlook(loc, i) if outlook_enabled else "")
        )
        for i, loc in enumerate(locations)
    )

    legend_html = _render_legend(hourly_metrics, hourly_enabled)
    abo_html = _render_abo_footer(preset_name, preset_schedule, preset_weekday, len(locations), sig)
    app_footer_html = _render_app_footer()

    # Nur nicht-leere Bloecke einreihen (kein Doppel-Newline durch leeren
    # Warn-Lead/keine Warnungen, analog zur Anti-Erosion-Regel aus #1034).
    body_html = "\n".join(
        part for part in (
            header_html, warnings_html, warn_banner_html, overview_html,
            hourly_head_html, per_location_html,
            legend_html, abo_html, app_footer_html,
        ) if part
    )

    # Adversary F001(b): zusaetzliche <style>-Regel als Backup fuer Clients,
    # die Klassen respektieren -- nur bei tatsaechlich konfigurierten
    # Korridoren, damit corridors=None/[] das HTML byte-identisch laesst
    # (Baseline-Schutz, s. test_kein_corridor_rendert_wie_bisher).
    mark_css = f".corridor-mark {{ border-left:3px solid {G_SUCCESS} !important; }}\n" if corridors else ""

    style_block = f"""<style>
body {{ margin:0;padding:0;background:{G_PAPER};font-family:{FONT_UI};color:{G_INK}; }}
.container {{ max-width:680px;margin:0 auto;background:#ffffff; }}
table {{ border-collapse:collapse; }}
th, td {{ vertical-align:top; }}
{mark_css}@media (max-width: 480px) {{
    .container {{ max-width:100% !important; }}
    .header-stats-desktop {{ display:none !important; }}
    .header-stats-mobile {{ display:table !important; }}
    table {{ font-size:12px !important; }}
    .header-wrapper {{ padding:18px !important; }}
}}
</style>"""

    return f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Orts-Vergleich</title>
{WEB_FONT_LINK}
{style_block}
</head>
<body>
<div class="container">
{body_html}
</div>
</body>
</html>"""


__all__ = [
    "render_compare_html",
    "CV2_METRICS",
    "HOUR_METRICS",
    "sort_locations_alphabetically",
]
