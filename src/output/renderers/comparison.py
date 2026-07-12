"""
Comparison Renderers — extracted from the former NiceGUI compare page (Epic #129 Phase A.1; the source module was removed in Phase A.3).

Pure-function renderers that turn ComparisonResult into HTML / Plain-Text for
email delivery. No NiceGUI dependency.

``render_comparison_html()`` war seit Issue #253 ein bestaetigter toter
Alt-Renderer (Score/Winner-Vertrag, nie vom echten Versandpfad aufgerufen --
``render_compare_email()`` nutzt ausschliesslich ``output.renderers.email.
compare_html.render_compare_html()``) und wurde mit Issue #1110 ENTFERNT
(koordiniert mit #1108). ``render_comparison_text()`` wurde im selben Zug auf
den v2-Vertrag umgestellt: kein Score/🏆 mehr, stattdessen Uebersicht +
amtliche Warnungen je Ort, Stundentabellen fuer alle Orte.

SPEC: docs/specs/epic_129a_1_compare_helpers.md
SPEC (v2): docs/specs/modules/issue_1110_compare_mail_v2.md
"""
from __future__ import annotations

from typing import Optional

from app.profile import ActivityProfile
from app.user import ComparisonResult
from output.renderers.email.compare_html import sort_locations_alphabetically
from src.output.metric_format import format_value
from src.output.renderers.alert.official_alerts import render_official_alerts_plain


def render_comparison_text(
    result: ComparisonResult,
    profile: Optional[ActivityProfile] = None,
    enabled_metrics: set | None = None,
) -> str:
    """
    Render ComparisonResult als Klartext (v2, Issue #1110).

    Kein Score/🏆 mehr. Je Ort: Uebersichtswerte + amtliche Warnungen (via
    ``render_official_alerts_plain()``, kein Copy-Paste, ADR-0011). Danach
    kompakte Stundentabellen fuer ALLE Orte (kein Rang-Praefix, keine
    Top-N-Beschraenkung mehr).

    Args:
        result: ComparisonResult aus ComparisonEngine.
        profile: Optional ActivityProfile (aktuell ohne Einfluss auf den
            Klartext-Inhalt, akzeptiert fuer API-Konsistenz mit
            ``render_compare_html``).
        enabled_metrics: Issue #1125. Filtert die sechs Uebersichts-Zeilen
            je Ort auf die enthaltenen Renderer-Metrik-IDs (z.B.
            "temp_max", "wind_max"). ``None`` = kein Filter (alle Zeilen,
            Rueckwaertskompatibilitaet). Spiegelt exakt die Semantik von
            ``_visible_metrics()`` im HTML-Pfad
            (``output.renderers.email.compare_html``). Amtliche Warnungen
            bleiben davon unabhaengig immer sichtbar.

    Returns:
        Klartext-String fuer die E-Mail.
    """
    _ = profile  # akzeptiert fuer API-Konsistenz, aktuell ohne Wirkung

    time_window = result.time_window
    target_date = result.target_date
    created_at = result.created_at
    # Zentraler Sortier-Helfer (PO-Update 2026-07-08): alphabetisch, case-
    # insensitiv, identisch zu render_compare_html() -- keine Doppel-Logik.
    locations = sort_locations_alphabetically(result.locations)
    if not locations:
        return "Keine Vergleichsdaten verfügbar."

    lines: list[str] = []
    lines.append("ORTS-VERGLEICH")
    lines.append("=" * 24)
    lines.append(f"Datum: {target_date.strftime('%A, %d.%m.%Y')}")
    lines.append(f"Zeitfenster: {time_window[0]:02d}:00 - {time_window[1]:02d}:00")
    lines.append(f"Erstellt: {created_at.strftime('%d.%m.%Y %H:%M')}")
    lines.append("")
    lines.append("-" * 50)

    for loc_result in locations:
        loc = loc_result.location
        lines.append(loc.name)
        if loc_result.error is not None:
            lines.append(f"   Fehler: {loc_result.error}")
            lines.append("")
            continue

        def _metric_visible(metric_id: str) -> bool:
            return enabled_metrics is None or metric_id in enabled_metrics

        if _metric_visible("temp_max"):
            temp_max = loc_result.temp_max
            lines.append(f"   Temp max: {format_value('temperature', temp_max, style='plain')}" if temp_max is not None else "   Temp max: -")
        if _metric_visible("wind_max"):
            wind_max = loc_result.wind_max
            lines.append(f"   Wind: {format_value('wind', wind_max, style='plain')}" if wind_max is not None else "   Wind: -")
        if _metric_visible("sunny_hours"):
            # Issue #1214 Scheibe 6: sunshine.decimals=1 im Katalog (vormals
            # F001-Ausnahme in Scheibe 5, s. Spec) macht die Migration jetzt
            # beweisbar verhaltensneutral: calculate_sunny_hours liefert immer
            # round(x, 1) als float, also str(4.7) == "4.7" == f"{4.7:.1f}".
            sunny_h = loc_result.sunny_hours
            lines.append(
                f"   Sonne: {format_value('sunshine', sunny_h, style='bare')}h"
                if sunny_h is not None else "   Sonne: -"
            )
        if _metric_visible("cloud_avg"):
            cloud = loc_result.cloud_avg
            lines.append(f"   Wolken: {format_value('cloud_total', cloud, style='plain')}" if cloud is not None else "   Wolken: -")
        if _metric_visible("snow_depth_cm"):
            snow_depth = loc_result.snow_depth_cm
            lines.append(f"   Schneehöhe: {format_value('snow_depth', snow_depth, style='plain')}" if snow_depth is not None else "   Schneehöhe: -")
        if _metric_visible("snow_new_cm"):
            snow_new = loc_result.snow_new_cm
            lines.append(f"   Neuschnee: {snow_new:.0f} cm" if snow_new is not None else "   Neuschnee: -")

        # Amtliche Warnungen, eine Zeile pro Warnung (Epic #1073 Punkt 6,
        # gemeinsamer Renderer statt Copy-Paste).
        for line in render_official_alerts_plain([(loc.name, loc_result.official_alerts)]):
            lines.append(f"   ⚠️ {line}")

        lines.append("")

    # Stundentabellen fuer ALLE Orte (kompakt, kein Rang-Praefix)
    valid = [loc for loc in locations if loc.error is None and loc.hourly_data]
    if valid:
        lines.append("STUNDENVERLAUF")
        lines.append("-" * 15)
        for loc_result in valid:
            lines.append(loc_result.location.name)
            for dp in loc_result.hourly_data:
                ts = dp.ts.strftime("%H:%M") if hasattr(dp.ts, "strftime") else str(dp.ts)
                temp = f"{dp.t2m_c:.0f}°" if dp.t2m_c is not None else "-"
                gef = f"{dp.wind_chill_c:.0f}°" if dp.wind_chill_c is not None else "-"
                wind = f"{dp.wind10m_kmh:.0f}" if dp.wind10m_kmh is not None else "-"
                cloud_pct = f"{dp.cloud_total_pct}%" if dp.cloud_total_pct is not None else "-"
                lines.append(f"   {ts}  Temp {temp}  Gef. {gef}  Wind {wind}  Wolken {cloud_pct}")
            lines.append("")

    lines.append("---")
    lines.append("Gregor Zwanzig")

    return "\n".join(lines)


def render_compare_email(
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
) -> tuple[str, str]:
    """Render both HTML and plain-text parts for a compare email (v2, #1110).

    Single entry point for all compare-email render callers. Keeps the HTML
    renderer (output.renderers.email.compare_html) and the plain-text renderer
    (this module) in one place. Kein Score/Winner mehr -- ``winner_tags``
    entfaellt vollstaendig. ``top_n_details`` (Issue #1104) wird angenommen,
    hat aber AKTUELL KEINE Wirkung: PO 2026-07-08 -- Mail zeigt immer alle
    Orte; die Semantik wird in #1105-#1107 neu definiert. ``enabled_metrics``
    filtert die numerischen Uebersichts-Zeilen (s. ``render_compare_html``).
    ``hourly_metrics`` (Issue #1106) filtert die Wert-Spalten je
    Stundentabelle-Ort-Sektion, analog ``enabled_metrics``. ``hourly_enabled``
    (Issue #1107) schaltet die komplette Stundenverlauf-Sektion ein/aus.

    Returns:
        Tuple of (html_body, text_body).
    """
    from output.renderers.email.compare_html import render_compare_html

    html_body = render_compare_html(
        result,
        profile=profile,
        warnings=warnings,
        top_n_details=top_n_details,
        enabled_metrics=enabled_metrics,
        hourly_metrics=hourly_metrics,
        hourly_enabled=hourly_enabled,
        preset_name=preset_name,
        preset_schedule=preset_schedule,
        preset_weekday=preset_weekday,
    )
    text_body = render_comparison_text(result, profile=profile, enabled_metrics=enabled_metrics)
    return html_body, text_body
