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

from app.profile import ActivityProfile
from app.user import ComparisonResult, LocationResult
from output.renderers.email.design_tokens import (
    FONT_DATA, FONT_UI, G_ACCENT, G_ALERT_L2, G_ALERT_L3, G_ALERT_L4,
    G_BOX_WARNING_BG, G_INK, G_INK_FAINT, G_INK_MUTED, G_PAPER, G_SUCCESS,
    G_WARNING, WEB_FONT_LINK,
)
from output.renderers.email.profile_signature import profile_signature
from src.output.renderers.alert.official_alerts import render_official_alerts_html


# ---------------------------------------------------------------------------
# Risk-Skala + Metrik-Katalog (1:1 aus docs/design-requests/compare_mail_v2/
# screen-compare-email-v2.jsx uebernommen)
# ---------------------------------------------------------------------------

_RISK_CELL = {
    "caution": ("#fbeeb8", "#5e4a00"),
    "warn": ("#fad6b8", "#8a3506"),
    "danger": ("#f6c5bf", "#8a1009"),
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
    return "danger" if v > 40 else "warn" if v > 30 else "caution" if v > 20 else "ok"


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


CV2_METRICS = [
    {"key": "warn", "label": "Amtliche Warnungen", "kind": "warn"},
    {"key": "temp_max", "label": "Temp max", "unit": "°C", "sev": _sev_temp},
    {"key": "wind_max", "label": "Wind", "unit": "km/h", "sev": _sev_wind},
    {"key": "sunny_hours", "label": "Sonne", "unit": "h", "decimals": 1},
    {"key": "cloud_avg", "label": "Wolken", "unit": "%"},
    {"key": "uv_max", "label": "UV max", "unit": "", "sev": _sev_uv},
    {"key": "snow_depth_cm", "label": "Schneehöhe", "unit": "cm"},
    {"key": "snow_new_cm", "label": "Neuschnee", "unit": "cm"},
]

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
    return f"{v / 1000:.1f} km" if v is not None else "—"


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


# Issue #1106: ersetzt _HOUR_COLUMNS -- 9 konfigurierbare Wert-Spalten,
# kanonische Reihenfolge (AC-8). "Zeit" ist keine Metrik hier, sondern fest
# verdrahtete erste Spalte in _render_hour_row/_render_hour_table.
HOUR_METRICS = [
    {"key": "t2m_c", "label": "Temp", "fmt": _fmt_deg, "sev": _sev_temp},
    {"key": "wind_chill_c", "label": "Gef.", "fmt": _fmt_deg},
    {"key": "wind10m_kmh", "label": "Wind", "fmt": _fmt_kmh, "sev": _sev_wind},
    {"key": "gust_kmh", "label": "Böen", "fmt": _fmt_kmh, "sev": _sev_gust},
    {"key": "precip_1h_mm", "label": "Regen", "fmt": _fmt_rain, "sev": _sev_rain_safe},
    {"key": "uv_index", "label": "UV", "fmt": _fmt_uv, "sev": _sev_uv},
    {"key": "thunder_level", "label": "Gew.", "fmt": _fmt_thunder, "sev": _sev_thunder},
    {"key": "pop_pct", "label": "Regen-W.", "fmt": _fmt_pop, "sev": _sev_pop},
    {"key": "visibility_m", "label": "Sicht", "fmt": _fmt_visibility, "sev": _sev_visibility},
]


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
    """Reduziert auf eindeutige `(hazard, level, label)`-Tupel (Reihenfolge
    erhalten, erstes Vorkommen gewinnt, Issue #1134). Zwei Warnungen mit
    gleichem hazard aber unterschiedlichem `label` bleiben beide erhalten."""
    seen = set()
    out = []
    for a in alerts:
        key = (a.hazard, a.level, a.label)
        if key not in seen:
            seen.add(key)
            out.append(a)
    return out


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

def _metric_value(loc: LocationResult, key: str) -> Optional[float]:
    if key == "uv_max":
        vals = [dp.uv_index for dp in loc.hourly_data if dp.uv_index is not None]
        return max(vals) if vals else None
    return getattr(loc, key, None)


def _fmt_metric(value, decimals, unit: str) -> str:
    if value is None:
        return "—"
    text = f"{value:.{decimals if decimals is not None else 0}f}"
    if not unit:
        return text
    return f"{text}{unit}" if unit in ("°C", "%") else f"{text} {unit}"


def _render_overview_row(m: dict, locations: list[LocationResult]) -> str:
    label_cell = (
        f'<td style="text-align:left;padding:8px 5px;font-family:{FONT_UI};'
        f'color:{G_INK_MUTED};font-weight:500;font-size:12px;'
        f'border-right:1px solid #f0ece1;">{_html.escape(m["label"])}</td>'
    )
    cells = [label_cell]
    for loc in locations:
        if m["key"] == "warn":
            content = "—" if loc.error is not None else _render_warn_cell(loc.official_alerts)
            cells.append(
                f'<td style="text-align:center;padding:7px 5px;vertical-align:middle;'
                f'border-right:1px solid #f0ece1;">{content}</td>'
            )
            continue
        value = None if loc.error is not None else _metric_value(loc, m["key"])
        sev_fn = m.get("sev")
        sev_level = sev_fn(value) if (sev_fn and value is not None) else None
        bg, fg, weight = "transparent", G_INK, "500"
        if sev_level and sev_level != "ok":
            bg, fg = _RISK_CELL[sev_level]
            weight = "700"
        text = _fmt_metric(value, m.get("decimals"), m.get("unit", ""))
        cells.append(
            f'<td style="text-align:center;padding:8px 5px;font-family:{FONT_DATA};'
            f'font-size:12.5px;background:{bg};color:{fg};font-weight:{weight};'
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


def _render_overview_table(locations: list[LocationResult], enabled_metrics: set | None = None) -> str:
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
    rows = "".join(_render_overview_row(m, locations) for m in _visible_metrics(enabled_metrics))
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


# ---------------------------------------------------------------------------
# Warn-Lead-Block (Akzent-Bar, nur bei >=1 Warnung ueber alle Orte)
# ---------------------------------------------------------------------------

def _lead_tag(bg: str, fg: str, border: str, label: str) -> str:
    return (
        f'<span style="display:inline-block;padding:4px 10px;margin:0 6px 6px 0;'
        f'background:{bg};color:{fg};border:1px solid {border};font-size:11px;'
        f'font-weight:600;font-family:{FONT_DATA};letter-spacing:0.02em;">'
        f'{_html.escape(label)}</span>'
    )


def _render_warn_lead(locations: list[LocationResult]) -> str:
    """Aggregat-Lead ueber alle Orte -- KEINE Ortsnamen (haelt AC-1 alphabetische
    Sortierung ein, da sonst ein spaeterer Ort vor einem frueheren im HTML
    auftauchen koennte)."""
    valid = [loc for loc in locations if loc.error is None]
    if not any(loc.official_alerts for loc in valid):
        return ""

    total = len(valid)
    heat_count = sum(1 for loc in valid if any(a.hazard == "extreme_heat" for a in loc.official_alerts))
    wildfire_levels = [a.level for loc in valid for a in loc.official_alerts if a.hazard == "wildfire_risk"]
    access_count = sum(1 for loc in valid if any(a.hazard == "access_ban" for a in loc.official_alerts))
    max_level = max(wildfire_levels, default=0)

    parts = []
    if heat_count:
        parts.append(f"Für {heat_count} von {total} Orten liegt eine Hitzewarnung vor")
    if access_count:
        parts.append(f"für {access_count} Gebiet(e) gilt ein Zugangsverbot")
    if max_level:
        parts.append(f"höchste Waldbrandstufe {max_level}")
    sentence = ("; ".join(parts) + ".") if parts else "Es liegen amtliche Warnungen vor."

    tags = []
    if heat_count:
        tags.append(_lead_tag("#fde6cc", "#7c2d12", "#f0a060", f"Extreme Hitze · {heat_count} Orte"))
    if max_level:
        tags.append(_lead_tag("#fadcd6", "#7f1d1d", "#e88472", f"Waldbrand Stufe {max_level}"))
    if access_count:
        tags.append(_lead_tag("#fde6cc", "#7c2d12", "#f0a060", f"Zugang gesperrt · {access_count} Gebiete"))

    return (
        f'<div style="padding:18px 24px 16px;">'
        f'<div style="border-left:2px solid {G_ACCENT};padding-left:14px;">'
        f'<span style="font-family:{FONT_DATA};font-size:10px;letter-spacing:0.12em;'
        f'color:{G_ACCENT};font-weight:600;text-transform:uppercase;">'
        f'Amtliche Warnungen · aktiv</span>'
        f'<div style="font-size:16px;line-height:1.5;font-weight:500;margin-top:6px;'
        f'color:{G_INK};">{sentence}</div>'
        f'<div style="margin-top:12px;">{"".join(tags)}</div>'
        f'</div></div>'
    )


# ---------------------------------------------------------------------------
# Stundentabellen (alle Orte)
# ---------------------------------------------------------------------------

def _sev_cell_style(level: Optional[str]) -> tuple[str, str, str]:
    if level is None or level == "ok":
        return "transparent", G_INK, "500"
    bg, fg = _RISK_CELL[level]
    return bg, fg, "700"


def _hour_td(text: str, bg: str = "transparent", fg: str = G_INK, weight: str = "500", align: str = "center") -> str:
    return (
        f'<td style="text-align:{align};padding:8px 4px;font-size:13px;'
        f'background:{bg};color:{fg};font-weight:{weight};'
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


def _render_hour_row(dp, visible: list[dict]) -> str:
    hh = dp.ts.strftime("%H:%M") if hasattr(dp.ts, "strftime") else str(dp.ts)
    cells = _hour_td(hh, fg=G_INK_MUTED, align="left")
    for m in visible:
        value = getattr(dp, m["key"], None)
        text = m["fmt"](value)
        sev_fn = m.get("sev")
        sev_level = sev_fn(value) if (sev_fn and value is not None) else None
        style = _sev_cell_style(sev_level)
        cells += _hour_td(text, *style)
    return f'<tr style="border-bottom:1px solid #f0ece1;">{cells}</tr>'


def _render_hour_table(loc: LocationResult, hourly_metrics: set | None = None) -> str:
    visible = _visible_hour_metrics(hourly_metrics)
    columns = ["Zeit"] + [m["label"] for m in visible]
    ths = "".join(
        f'<th style="text-align:{"left" if col == "Zeit" else "center"};padding:6px 4px;'
        f'font-size:11px;color:{G_INK};font-weight:600;border-right:1px solid #f0ece1;">'
        f'{col}</th>'
        for col in columns
    )
    header = f'<tr style="background:{G_PAPER};border-bottom:1px solid #e6e1d3;">{ths}</tr>'
    rows = "".join(_render_hour_row(dp, visible) for dp in loc.hourly_data)
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


def _render_location_section(loc: LocationResult, index: int, hourly_metrics: set | None = None) -> str:
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
        f'{header}{strip}{_render_hour_table(loc, hourly_metrics)}</div>'
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
    start_h, end_h = result.time_window
    time_str = f"{start_h:02d}:00 – {end_h:02d}:00"
    date_line = f"{weekday}, {date_str}  ·  {time_str}"
    date_style = f"font-family:{FONT_DATA};font-size:13px;color:{G_INK};margin-top:6px;"

    profil_val = _html.escape(sig.eyebrow)
    orte_val = str(len(result.locations))
    horizont_val = "+48h"
    erstellt_val = datetime.now().strftime("%H:%M")

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
        _cell("Profil", profil_val, "25%")
        + _cell("Orte", orte_val, "25%")
        + _cell("Horizont", horizont_val, "25%")
        + _cell("Erstellt", erstellt_val, "25%")
    )
    desktop_table = (
        f'<table class="header-stats-desktop" cellspacing="0" cellpadding="0" '
        f'style="width:100%;margin-top:14px;border-collapse:collapse;">'
        f'<tr>{desktop_cells}</tr></table>'
    )

    mobile_row1 = _cell("Profil", profil_val, "50%") + _cell("Orte", orte_val, "50%")
    mobile_row2 = _cell("Horizont", horizont_val, "50%") + _cell("Erstellt", erstellt_val, "50%")
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


def _render_legend() -> str:
    items = [("#2f8a3e", "unkritisch"), ("#e3b008", "Achtung"), ("#e07b1a", "Warnung"), ("#c52a22", "Gefahr")]
    dots = "".join(
        f'<span style="display:inline-block;margin-right:16px;font-family:{FONT_DATA};'
        f'font-size:10px;color:{G_INK_MUTED};">'
        f'<span style="display:inline-block;width:10px;height:10px;border-radius:50%;'
        f'background:{color};margin-right:6px;vertical-align:middle;"></span>{label}</span>'
        for color, label in items
    )
    return (
        f'<div style="background:{G_PAPER};border-top:1px solid #e6e1d3;padding:18px 24px;'
        f'margin-top:22px;font-family:{FONT_DATA};font-size:10px;color:{G_INK_MUTED};">'
        f'<span style="font-weight:600;color:{G_INK_FAINT};letter-spacing:0.08em;'
        f'text-transform:uppercase;margin-right:16px;">Risk</span>{dots}'
        f'<span style="color:{G_INK_FAINT};">Warn-Kürzel: Hitze · Brand·Stufe · Zugang</span>'
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

    Returns:
        HTML-String (DOCTYPE bis </html>).
    """
    _ = top_n_details  # akzeptiert (Issue #1104), aktuell ohne Wirkung (s. Docstring)
    warnings = warnings or []
    sig = profile_signature(profile)
    locations = sort_locations_alphabetically(result.locations)

    header_html = _render_header(result, sig)
    warnings_html = "".join(_render_warning_banner(w) for w in warnings)
    warn_lead_html = _render_warn_lead(locations)

    overview_html = (
        f'<div style="padding:6px 24px 0;">'
        f'{_render_section_head("ÜBERSICHT", "Alle Orte · gewählte Metriken", "← scrollen")}'
        f'{_render_overview_table(locations, enabled_metrics)}</div>'
    )
    hourly_head_html = (
        f'<div style="padding:26px 24px 0;">'
        f'{_render_section_head("STUNDEN", "Stundenverlauf · alle Orte", "09–16 Uhr")}</div>'
    ) if hourly_enabled else ""
    hourly_sections_html = (
        "".join(_render_location_section(loc, i, hourly_metrics) for i, loc in enumerate(locations))
        if hourly_enabled else ""
    )

    legend_html = _render_legend()
    abo_html = _render_abo_footer(preset_name, preset_schedule, preset_weekday, len(locations), sig)
    app_footer_html = _render_app_footer()

    # Nur nicht-leere Bloecke einreihen (kein Doppel-Newline durch leeren
    # Warn-Lead/keine Warnungen, analog zur Anti-Erosion-Regel aus #1034).
    body_html = "\n".join(
        part for part in (
            header_html, warnings_html, warn_lead_html, overview_html,
            hourly_head_html, hourly_sections_html, legend_html, abo_html,
            app_footer_html,
        ) if part
    )

    style_block = f"""<style>
body {{ margin:0;padding:0;background:{G_PAPER};font-family:{FONT_UI};color:{G_INK}; }}
.container {{ max-width:680px;margin:0 auto;background:#ffffff; }}
table {{ border-collapse:collapse; }}
th, td {{ vertical-align:top; }}
@media (max-width: 480px) {{
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
