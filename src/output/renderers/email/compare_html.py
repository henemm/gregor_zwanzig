"""Compare-Email HTML-Renderer (Issue #253).

Pure Function ``render_compare_html()`` — analog zu ``html.py``.

Bietet einen profil-bewussten HTML-Renderer fuer ``ComparisonResult``:
- Inline-CSS only (Outlook-kompatibel)
- ``@media (max-width: 480px)`` Block fuer Mobile-Layout
- Profil-Eyebrow ueber ``profile_signature()``
- Winner-Card mit G_SUCCESS-Border + Score-Badge
- Warnungs-Banner (orange, G_WARNING) — kein String-Replace mehr
- Vergleichsmatrix mit primary/secondary Spalten je ``ActivityProfile``
- Stunden-Verlauf fuer Top-N Locations
- Dunkler Footer (G_INK)

SPEC: docs/specs/modules/issue_253_compare_email.md
"""
from __future__ import annotations

import html as _html
from datetime import datetime
from typing import Optional

from app.profile import ActivityProfile
from app.user import ComparisonResult, LocationResult
from output.renderers.email.design_tokens import (
    FONT_DATA, FONT_UI, G_ACCENT, G_BOX_WARNING_BG, G_INK,
    G_INK_FAINT, G_INK_MUTED, G_PAPER, G_SUCCESS, G_SURFACE_1, G_WARNING,
    WEB_FONT_LINK,
)
from output.renderers.email.profile_signature import profile_signature
from src.output.renderers.alert.official_alerts import render_official_alerts_html


# ---------------------------------------------------------------------------
# Modul-Konstanten
# ---------------------------------------------------------------------------

CE_PROFILES: dict[ActivityProfile, dict] = {
    ActivityProfile.WINTERSPORT: {
        "primary":   ["snow_depth_cm", "snow_new_cm", "sunny_hours"],
        "secondary": ["wind_max", "cloud_avg", "score"],
    },
    ActivityProfile.WANDERN: {
        "primary":   ["sunny_hours", "wind_max", "cloud_avg"],
        "secondary": ["snow_depth_cm", "temp_max", "score"],
    },
    ActivityProfile.SUMMER_TREKKING: {
        "primary":   ["sunny_hours", "cloud_avg", "wind_max"],
        "secondary": ["gust_max", "temp_max", "score"],
    },
    ActivityProfile.ALLGEMEIN: {
        "primary":   ["score", "sunny_hours", "wind_max"],
        "secondary": ["snow_depth_cm", "cloud_avg", "temp_max"],
    },
}

METRIC_DIRECTION = {
    "score": "max",
    "sunny_hours": "max",
    "snow_depth_cm": "max",
    "snow_new_cm": "max",
    "temp_max": "max",
    "wind_max": "min",
    "gust_max": "min",
    "cloud_avg": "min",
}

METRIC_LABELS = {
    "score": "Score",
    "snow_depth_cm": "Schneehöhe",
    "snow_new_cm": "Neuschnee",
    "sunny_hours": "Sonne",
    "wind_max": "Wind",
    "gust_max": "Böen",
    "cloud_avg": "Wolken",
    "temp_max": "Temp. max",
}

METRIC_UNITS = {
    "score": "",
    "snow_depth_cm": "cm",
    "snow_new_cm": "cm",
    "sunny_hours": "h",
    "wind_max": "km/h",
    "gust_max": "km/h",
    "cloud_avg": "%",
    "temp_max": "°C",
}

# Issue #460 — Tag-Farben und Wochentag-Abkuerzungen
_TAG_COLORS = {
    "good": {"bg": "#dcf2e1", "fg": "#14532d", "border": "#86c89a"},
    "warn": {"bg": "#fde6cc", "fg": "#7c2d12", "border": "#f0a060"},
    "info": {"bg": "#dde8f3", "fg": "#1e3a5f", "border": "#8aacd0"},
}
_WEEKDAY_ABBR = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_metric_value(loc: LocationResult, metric_id: str):
    """Liest Metrik-Wert aus LocationResult; Fallback None."""
    return getattr(loc, metric_id, None)


def _format_metric(metric_id: str, value) -> str:
    """Formatiert Wert mit Einheit; '—' wenn None."""
    if value is None:
        return "—"
    unit = METRIC_UNITS.get(metric_id, "")
    if isinstance(value, float):
        if metric_id in ("snow_depth_cm", "snow_new_cm", "temp_max"):
            return f"{value:.0f}{unit}"
        if metric_id in ("wind_max", "gust_max"):
            return f"{value:.0f}{unit}"
        return f"{value:.1f}{unit}"
    return f"{value}{unit}"


def _find_best_index(values: list, direction: str) -> int:
    """Index des besten (max/min) Wertes; -1 wenn alle None."""
    indexed = [(i, v) for i, v in enumerate(values) if v is not None]
    if not indexed:
        return -1
    if direction == "max":
        return max(indexed, key=lambda x: x[1])[0]
    return min(indexed, key=lambda x: x[1])[0]


def _render_warning_banner(warning_text: str) -> str:
    """Orange-Banner mit G_WARNING-Akzent."""
    safe = _html.escape(warning_text)
    return (
        f'<div style="background:{G_BOX_WARNING_BG};'
        f'border-left:4px solid {G_WARNING};'
        f'padding:12px 16px;margin:8px 20px;'
        f'border-radius:4px;font-family:{FONT_UI};font-size:14px;'
        f'color:{G_INK};">'
        f'{safe}</div>'
    )


def _render_official_alerts_block(locations: list[LocationResult]) -> str:
    """Issue #1034/#1087 — Badges fuer amtliche Warnungen je Ort.

    Thin-Wrapper um den gemeinsamen Renderer (Epic #1073 Punkt 6, kein
    Copy-Paste) — Byte-Gleichheit zum vorherigen Compare-only-Code Pflicht
    (AC-2).
    """
    entries = [(loc.location.name, loc.official_alerts) for loc in locations]
    return render_official_alerts_html(entries)


def _generate_winner_tags(
    winner: LocationResult,
    profile: Optional[ActivityProfile],
) -> list[dict[str, str]]:
    """Erzeugt bis zu 4 Tag-Dicts (`{"tone", "label"}`) aus Winner-Metriken.

    Profilspezifisch (WINTERSPORT / WANDERN / sonst). Sortierung good > warn > info.
    Leere Liste wenn winner oder profile None ist. SPEC: issue_457 §1.
    """
    if winner is None or profile is None:
        return []

    if winner.error is not None:
        return []

    tags: list[tuple[str, str]] = []

    if profile == ActivityProfile.WINTERSPORT:
        sd = winner.snow_depth_cm
        if sd is not None and sd >= 100:
            tags.append(("good", f"Schneehöhe {sd:.0f} cm"))
        elif sd is not None and 50 <= sd < 100:
            tags.append(("info", f"Schneehöhe {sd:.0f} cm"))
        sn = winner.snow_new_cm
        if sn is not None and sn >= 10:
            tags.append(("good", f"+{sn:.0f} cm Neuschnee"))
        elif sn is not None and 3 <= sn < 10:
            tags.append(("info", f"+{sn:.0f} cm Neuschnee"))
        if winner.above_low_clouds is True:
            tags.append(("good", "Über den Wolken"))
        sh = winner.sunny_hours
        if sh is not None and sh >= 6:
            tags.append(("good", f"{sh} h Sonne"))
        wm = winner.wind_max
        if wm is not None and wm > 40:
            tags.append(("warn", f"Wind {wm:.0f} km/h"))
        gm = winner.gust_max
        if gm is not None and gm > 60:
            tags.append(("warn", f"Böen {gm:.0f} km/h"))
    elif profile == ActivityProfile.WANDERN:
        sh = winner.sunny_hours
        if sh is not None and sh >= 7:
            tags.append(("good", f"{sh} h Sonne"))
        elif sh is not None and 4 <= sh < 7:
            tags.append(("info", f"{sh} h Sonne"))
        wm = winner.wind_max
        if wm is not None and wm > 40:
            tags.append(("warn", f"Wind {wm:.0f} km/h"))
        ca = winner.cloud_avg
        if ca is not None and ca >= 80:
            tags.append(("warn", "Stark bewölkt"))
        tm = winner.temp_max
        if tm is not None and 5 <= tm <= 22:
            tags.append(("good", f"Temp. {tm:.0f}°C"))
    else:
        sh = winner.sunny_hours
        if sh is not None and sh >= 6:
            tags.append(("good", f"{sh} h Sonne"))
        wm = winner.wind_max
        if wm is not None and wm > 30:
            tags.append(("warn", f"Wind {wm:.0f} km/h"))
        ca = winner.cloud_avg
        if ca is not None and ca < 30:
            tags.append(("good", "Gering bewölkt"))

    good_tags = [t for t in tags if t[0] == "good"]
    warn_tags = [t for t in tags if t[0] == "warn"]
    info_tags = [t for t in tags if t[0] == "info"]

    if warn_tags and len(good_tags) >= 4:
        # Mindestens 1 Warn-Tag reservieren — max 3 Good + 1 Warn
        result = good_tags[:3] + warn_tags[:1]
    else:
        result = good_tags + warn_tags
        result = result + info_tags
        result = result[:4]
    return [{"tone": t, "label": label} for t, label in result]


def _render_tag(tone: str, label: str) -> str:
    """Rendert einen Tag als Inline-CSS-Pill (Outlook-kompatibel)."""
    colors = _TAG_COLORS.get(tone, _TAG_COLORS["info"])
    safe = _html.escape(label)
    return (
        f'<span style="display:inline-block;padding:2px 8px;'
        f'border-radius:12px;font-size:12px;font-weight:600;'
        f'background:{colors["bg"]};color:{colors["fg"]};'
        f'border:1px solid {colors["border"]};">{safe}</span>'
    )


def _render_winner_card(
    winner: LocationResult,
    tags: Optional[list[tuple[str, str]]] = None,
) -> str:
    """Winner-Card mit border-left + Score-Badge + optional Tag-Pills."""
    name = _html.escape(winner.location.name)
    score = winner.score if winner.score is not None else 0
    badge_bg = G_SUCCESS if winner.error is None else G_WARNING
    tags_html = ""
    if tags:
        pieces = []
        for t in tags:
            if isinstance(t, dict):
                tone, label = t.get("tone", "info"), t.get("label", "")
            else:
                tone, label = t[0], t[1]
            pieces.append(_render_tag(tone, label))
        tags_html = (
            f'<div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:8px;">'
            f'{"".join(pieces)}</div>'
        )
    return (
        f'<div style="background:{G_SURFACE_1};'
        f'border-left:4px solid {G_SUCCESS};'
        f'padding:16px 20px;margin:16px 20px;'
        f'border-radius:4px;font-family:{FONT_UI};">'
        f'<div style="font-size:11px;color:{G_INK_MUTED};'
        f'text-transform:uppercase;letter-spacing:0.08em;'
        f'margin-bottom:4px;">Bester Standort</div>'
        f'<h2 style="margin:0 0 8px 0;font-size:22px;color:{G_INK};">{name}</h2>'
        f'<span style="display:inline-block;background:{badge_bg};'
        f'color:#ffffff;padding:4px 12px;border-radius:12px;'
        f'font-size:13px;font-weight:600;">Score {score}</span>'
        f'{tags_html}'
        f'</div>'
    )


def _render_winner_tags(tags: list[dict]) -> str:
    """Issue #460 — Pill-Tags unter der Winner-Card.

    - Leere Liste -> "" (kein Container).
    - Unbekannte Tones werden uebersprungen.
    """
    if not tags:
        return ""

    pills: list[str] = []
    for tag in tags:
        tone = tag.get("tone")
        colors = _TAG_COLORS.get(tone)
        if colors is None:
            continue
        label = _html.escape(str(tag.get("label", "")))
        pill_style = (
            f"display:inline-flex;align-items:center;"
            f"padding:4px 10px;"
            f"background:{colors['bg']};color:{colors['fg']};"
            f"border:1px solid {colors['border']};border-radius:99px;"
            f"font-family:{FONT_DATA};font-size:11px;font-weight:600;"
            f"white-space:nowrap;"
        )
        pills.append(f'<span style="{pill_style}">{label}</span>')

    if not pills:
        return ""

    container_style = (
        "display:flex;flex-wrap:wrap;gap:6px;"
        "margin:0 20px;padding-top:12px;"
    )
    return f'<div style="{container_style}">{"".join(pills)}</div>'


def _render_header(result: ComparisonResult, sig) -> str:
    """Issue #460 — Header-Sektion mit Profil-Label, Datum/Zeitfenster und Stats-Grid."""
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
    date_style = (
        f"font-family:{FONT_DATA};font-size:13px;"
        f"color:{G_INK};margin-top:6px;"
    )

    # Stats-Werte
    profil_val = _html.escape(sig.eyebrow)
    orte_val = str(len(result.valid_locations))
    horizont_val = "+48h"
    erstellt_val = datetime.now().strftime("%H:%M")

    cell_label_style = (
        f"font-family:{FONT_DATA};font-size:9px;"
        f"color:{G_INK_FAINT};text-transform:uppercase;"
        f"letter-spacing:0.08em;padding-bottom:2px;"
    )
    cell_value_style = (
        f"font-family:{FONT_UI};font-size:14px;"
        f"color:{G_INK};font-weight:600;"
    )

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
        f'<tr>{desktop_cells}</tr>'
        f'</table>'
    )

    mobile_row1 = _cell("Profil", profil_val, "50%") + _cell("Orte", orte_val, "50%")
    mobile_row2 = _cell("Horizont", horizont_val, "50%") + _cell("Erstellt", erstellt_val, "50%")
    mobile_table = (
        f'<table class="header-stats-mobile" cellspacing="0" cellpadding="0" '
        f'style="display:none;width:100%;margin-top:14px;border-collapse:collapse;">'
        f'<tr>{mobile_row1}</tr>'
        f'<tr>{mobile_row2}</tr>'
        f'</table>'
    )

    wrapper_style = (
        f"background:{G_PAPER};padding:22px;"
        f"border-bottom:1px solid #e6e1d3;"
    )
    return (
        f'<div class="header-wrapper" style="{wrapper_style}">'
        f'<div style="{label_style}">{label_text}</div>'
        f'<div style="{date_style}">{date_line}</div>'
        f'{desktop_table}'
        f'{mobile_table}'
        f'</div>'
    )


def _render_matrix(
    result: ComparisonResult,
    profile: Optional[ActivityProfile],
    enabled_metrics: Optional[set],
) -> str:
    """Vergleichsmatrix als <table>."""
    locs = result.locations
    if not locs:
        return ""

    effective_profile = profile or ActivityProfile.ALLGEMEIN
    profile_cfg = CE_PROFILES.get(effective_profile, CE_PROFILES[ActivityProfile.ALLGEMEIN])
    primary_metrics = list(profile_cfg["primary"])
    secondary_metrics = list(profile_cfg["secondary"])

    if enabled_metrics is not None:
        primary_metrics = [m for m in primary_metrics if m in enabled_metrics]
        secondary_metrics = [m for m in secondary_metrics if m in enabled_metrics]

    # Header-Zeile
    header_cells = ['<th style="text-align:left;padding:8px 12px;">Metrik</th>']
    for loc in locs:
        name = _html.escape(loc.location.name)
        header_cells.append(
            f'<th style="text-align:right;padding:8px 12px;">{name}</th>'
        )

    # Daten-Zeilen
    body_rows = []
    for metric_id in primary_metrics + secondary_metrics:
        is_secondary = metric_id in secondary_metrics
        label = METRIC_LABELS.get(metric_id, metric_id)
        direction = METRIC_DIRECTION.get(metric_id, "max")
        values = [
            None if loc.error is not None else _get_metric_value(loc, metric_id)
            for loc in locs
        ]
        best_idx = _find_best_index(values, direction)

        row_class = ' class="secondary-col"' if is_secondary else ""
        cells = [
            f'<th{row_class} style="text-align:left;padding:6px 12px;'
            f'font-weight:500;color:{G_INK_MUTED};">{label}</th>'
        ]
        for i, (loc, val) in enumerate(zip(locs, values)):
            if loc.error is not None:
                cell_text = "—"
                bg = f"background:{G_WARNING};" if metric_id == "score" else ""
            else:
                cell_text = _format_metric(metric_id, val)
                bg = ""
                if i == best_idx and val is not None:
                    bg = "background:rgba(58, 125, 68, 0.15);"
            cells.append(
                f'<td{row_class} style="text-align:right;padding:6px 12px;'
                f'{bg}color:{G_INK};">{cell_text}</td>'
            )
        body_rows.append(f'<tr>{"".join(cells)}</tr>')

    # Mobile-Karten: eine Karte pro Location, nur primary metrics
    cards = []
    for loc in locs:
        rows = []
        for m in primary_metrics:
            label = METRIC_LABELS.get(m, m)
            val = None if loc.error is not None else _get_metric_value(loc, m)
            cell = "—" if loc.error is not None else _format_metric(m, val)
            rows.append(
                f'<div class="card-row" style="display:flex;justify-content:space-between;'
                f'padding:4px 0;border-bottom:1px solid {G_SURFACE_1};font-family:{FONT_UI};'
                f'font-size:14px;color:{G_INK};">'
                f'<span style="color:{G_INK_MUTED};">{label}</span>'
                f'<span>{cell}</span>'
                f'</div>'
            )
        name = _html.escape(loc.location.name)
        score_bg = G_WARNING if loc.error is not None else G_SUCCESS
        score_val = loc.score if loc.score is not None else 0
        cards.append(
            f'<div class="location-card" style="background:{G_SURFACE_1};'
            f'border-radius:4px;padding:12px 16px;margin-bottom:12px;">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">'
            f'<strong style="font-family:{FONT_UI};font-size:15px;color:{G_INK};">{name}</strong>'
            f'<span style="background:{score_bg};color:#ffffff;padding:2px 10px;'
            f'border-radius:10px;font-size:12px;font-family:{FONT_UI};">Score {score_val}</span>'
            f'</div>'
            f'{"".join(rows)}'
            f'</div>'
        )

    mobile_cards_html = (
        f'<div class="mobile-cards" style="display:none;margin:16px 20px;">'
        f'{"".join(cards)}'
        f'</div>'
    )

    return (
        f'<div style="margin:16px 20px;">'
        f'<table class="matrix-table" cellspacing="0" cellpadding="0" '
        f'style="width:100%;max-width:640px;border-collapse:collapse;'
        f'font-family:{FONT_UI};font-size:14px;background:{G_PAPER};">'
        f'<thead><tr>{"".join(header_cells)}</tr></thead>'
        f'<tbody>{"".join(body_rows)}</tbody>'
        f'</table>'
        f'</div>'
        f'{mobile_cards_html}'
    )


def _render_hourly_section(
    result: ComparisonResult,
    top_n_details: int,
) -> str:
    """Stunden-Verlauf-Tabellen fuer Top-N Locations."""
    if top_n_details <= 0:
        return ""
    valid = sorted(
        result.valid_locations,
        key=lambda loc: loc.score if loc.score is not None else -1,
        reverse=True,
    )[:top_n_details]

    sections = []
    for loc in valid:
        if not loc.hourly_data:
            continue
        name = _html.escape(loc.location.name)
        rows = []
        for dp in loc.hourly_data:
            ts = dp.ts.strftime("%H:%M") if hasattr(dp.ts, "strftime") else str(dp.ts)
            temp = f"{dp.t2m_c:.0f}°" if dp.t2m_c is not None else "—"
            wind = f"{dp.wind10m_kmh:.0f}" if dp.wind10m_kmh is not None else "—"
            cloud = f"{dp.cloud_total_pct}%" if dp.cloud_total_pct is not None else "—"
            rows.append(
                f'<tr>'
                f'<td style="padding:4px 8px;color:{G_INK_MUTED};">{ts}</td>'
                f'<td style="padding:4px 8px;text-align:right;">{temp}</td>'
                f'<td style="padding:4px 8px;text-align:right;">{wind}</td>'
                f'<td style="padding:4px 8px;text-align:right;">{cloud}</td>'
                f'</tr>'
            )
        sections.append(
            f'<div style="margin:16px 20px;">'
            f'<h3 style="margin:0 0 8px 0;font-size:16px;color:{G_INK};'
            f'font-family:{FONT_UI};">{name} — Stundenverlauf</h3>'
            f'<table cellspacing="0" cellpadding="0" '
            f'style="width:100%;max-width:640px;border-collapse:collapse;'
            f'font-family:{FONT_UI};font-size:13px;background:{G_PAPER};">'
            f'<thead><tr>'
            f'<th style="text-align:left;padding:4px 8px;color:{G_INK_FAINT};">Zeit</th>'
            f'<th style="text-align:right;padding:4px 8px;color:{G_INK_FAINT};">Temp</th>'
            f'<th style="text-align:right;padding:4px 8px;color:{G_INK_FAINT};">Wind</th>'
            f'<th style="text-align:right;padding:4px 8px;color:{G_INK_FAINT};">Wolken</th>'
            f'</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody>'
            f'</table></div>'
        )
    return "".join(sections)


# ---------------------------------------------------------------------------
# Oeffentliche API
# ---------------------------------------------------------------------------

def render_compare_html(
    result: ComparisonResult,
    *,
    profile: Optional[ActivityProfile] = None,
    warnings: list[str] | None = None,
    top_n_details: int = 3,
    enabled_metrics: set | None = None,
    winner_tags: list[dict] | None = None,
) -> str:
    """Rendert ComparisonResult als HTML-Mail.

    Pure Function — keine Seiteneffekte, kein Netzwerk.

    Args:
        result: ComparisonResult aus ComparisonEngine.
        profile: ActivityProfile fuer Eyebrow + Spaltenauswahl. Default ALLGEMEIN.
        warnings: Liste von Warnungs-Texten; je Eintrag ein orange-Banner.
        top_n_details: Anzahl Locations mit Stunden-Verlauf (0 = keiner).
        enabled_metrics: Optionaler Set-Filter fuer Metrik-Zeilen.
        winner_tags: Issue #460 — optionale Pill-Tags unter Winner-Card.
            Liste von {"tone": "good"|"warn"|"info", "label": str}.

    Returns:
        HTML-String (DOCTYPE bis </html>).
    """
    warnings = warnings or []
    sig = profile_signature(profile)
    now = datetime.now()
    target_date = result.target_date

    eyebrow_html = (
        f'<div style="background:{sig.accent_hex};color:#ffffff;'
        f'font-family:{FONT_UI};font-size:11px;letter-spacing:0.08em;'
        f'padding:8px 24px;text-transform:uppercase;">'
        f'{sig.icon_html} {_html.escape(sig.eyebrow)}</div>'
    )

    header_html = _render_header(result, sig)

    winner_html = ""
    winner_tags_html = ""
    if result.winner is not None:
        winner_html = _render_winner_card(result.winner)
        winner_tags_html = _render_winner_tags(winner_tags or [])

    warnings_html = "".join(_render_warning_banner(w) for w in warnings)
    official_alerts_html = _render_official_alerts_block(result.locations)

    matrix_html = _render_matrix(result, profile, enabled_metrics)
    hourly_html = _render_hourly_section(result, top_n_details)

    footer_html = (
        f'<div style="background:{G_INK};color:#ffffff;'
        f'padding:16px 24px;font-family:{FONT_UI};font-size:12px;'
        f'margin-top:24px;">'
        f'Wetter-Vergleich für {target_date.strftime("%d.%m.%Y")} · '
        f'generiert {now.strftime("%d.%m.%Y %H:%M")}'
        f'</div>'
    )

    style_block = f"""<style>
body {{ margin: 0; padding: 0; background: {G_PAPER}; font-family: {FONT_UI}; color: {G_INK}; }}
.container {{ max-width: 680px; margin: 0 auto; background: {G_PAPER}; }}
table {{ border-collapse: collapse; }}
th, td {{ vertical-align: top; }}
.secondary-col {{ display: table-cell; }}
@media (max-width: 480px) {{
    .secondary-col {{ display: none !important; }}
    .container {{ max-width: 100% !important; }}
    table {{ font-size: 12px !important; }}
    h2 {{ font-size: 18px !important; }}
    th, td {{ padding: 4px 6px !important; }}
    .matrix-table {{ display: none !important; }}
    .mobile-cards {{ display: block !important; }}
    .header-stats-desktop {{ display: none !important; }}
    .header-stats-mobile {{ display: table !important; }}
    .header-wrapper {{ padding: 18px !important; }}
}}
</style>"""

    html_doc = f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Wetter-Vergleich</title>
{WEB_FONT_LINK}
{style_block}
</head>
<body>
<div class="container">
{eyebrow_html}
{header_html}
{winner_html}
{winner_tags_html}
{warnings_html}{official_alerts_html}
{matrix_html}
{hourly_html}
{footer_html}
</div>
</body>
</html>"""
    return html_doc


__all__ = [
    "render_compare_html",
    "CE_PROFILES",
    "METRIC_DIRECTION",
    "METRIC_LABELS",
]
