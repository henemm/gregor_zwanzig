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
    FONT_UI, G_ACCENT, G_BOX_WARNING_BG, G_INK, G_INK_FAINT, G_INK_MUTED,
    G_PAPER, G_SUCCESS, G_SURFACE_1, G_WARNING, WEB_FONT_LINK,
)
from output.renderers.email.profile_signature import profile_signature


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


def _render_winner_card(winner: LocationResult) -> str:
    """Winner-Card mit border-left + Score-Badge."""
    name = _html.escape(winner.location.name)
    score = winner.score if winner.score is not None else 0
    badge_bg = G_SUCCESS if winner.error is None else G_WARNING
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
        key=lambda l: l.score if l.score is not None else -1,
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
) -> str:
    """Rendert ComparisonResult als HTML-Mail.

    Pure Function — keine Seiteneffekte, kein Netzwerk.

    Args:
        result: ComparisonResult aus ComparisonEngine.
        profile: ActivityProfile fuer Eyebrow + Spaltenauswahl. Default ALLGEMEIN.
        warnings: Liste von Warnungs-Texten; je Eintrag ein orange-Banner.
        top_n_details: Anzahl Locations mit Stunden-Verlauf (0 = keiner).
        enabled_metrics: Optionaler Set-Filter fuer Metrik-Zeilen.

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

    winner_html = ""
    if result.winner is not None:
        winner_html = _render_winner_card(result.winner)

    warnings_html = "".join(_render_warning_banner(w) for w in warnings)

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
{winner_html}
{warnings_html}
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
