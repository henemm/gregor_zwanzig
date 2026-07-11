"""Report-Config-Resolver (Scheibe A, Issue #1208).

SPEC: docs/specs/modules/report_config_resolver.md

Zentraler und EINZIGER Ableitungspfad von `TripReportConfig` +
`UnifiedWeatherDisplayConfig` eines Trips in ein explizites
`ReportRenderOptions`-Objekt. Schliesst die Luecke, die Bug #1102
verursacht hat (`email_format`/`show_outlook` wurden im Versandpfad nie
aus `report_config` gelesen).

Keine I/O, keine Mutation der Eingaben — reine Aufloesungsfunktion.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.models import TripReportConfig, UnifiedWeatherDisplayConfig

# Die 7 render-wirksamen TripReportConfig-Felder (Spec v1.1 §Implementation
# Details). PO-Entscheidung 2026-07-10 (GREEN-Review): show_daylight wurde
# hier entfernt und nach RENDER_NEUTRAL verschoben — der Tageslicht-Block
# wurde bereits in #790 aus render_html/render_plain entfernt, der Toggle
# ist strukturell wirkungslos (bestaetigt durch test_issue_790_briefing_simplify.py).
RENDER_EFFECTIVE_FIELDS: tuple[str, ...] = (
    "email_format",
    "show_outlook",
    "show_stage_stats",
    "show_stability",
    "show_compact_summary",
    "show_yesterday_comparison",
    "multi_day_trend_reports",
)

# Die uebrigen 20 TripReportConfig-Felder — begruendet nach Kategorie
# (Spec-Tabelle "RENDER_NEUTRAL — 20 Felder, kategorisiert und begruendet").
RENDER_NEUTRAL: dict[str, str] = {
    # Metadaten
    "trip_id": "Reine Identifikation, keine Render-Wirkung.",
    "updated_at": "Reiner Zeitstempel, keine Render-Wirkung.",
    # Pre-Render-Gate
    "enabled": "Entscheidet VOR dem Rendern, ob ueberhaupt versendet wird.",
    "paused_until": "Entscheidet VOR dem Rendern, ob ueberhaupt versendet wird.",
    "skip_next": "Entscheidet VOR dem Rendern, ob ueberhaupt versendet wird.",
    # Zeitplanung
    "morning_time": "Steuert WANN der Scheduler laeuft, nicht WAS gerendert wird.",
    "evening_time": "Steuert WANN der Scheduler laeuft, nicht WAS gerendert wird.",
    # Kanalwahl
    "send_email": "Steuert WELCHER Kanal versendet wird, nicht den Mail-Inhalt.",
    "send_sms": "Steuert WELCHER Kanal versendet wird, nicht den Mail-Inhalt.",
    "send_telegram": "Steuert WELCHER Kanal versendet wird, nicht den Mail-Inhalt.",
    # Alert-Pfad
    "alert_on_changes": "Gehoert zum separaten Alert-/Deviation-Pfad, nicht zum Briefing-Rendering.",
    "change_threshold_temp_c": "Gehoert zum separaten Alert-/Deviation-Pfad, nicht zum Briefing-Rendering.",
    "change_threshold_wind_kmh": "Gehoert zum separaten Alert-/Deviation-Pfad, nicht zum Briefing-Rendering.",
    "change_threshold_precip_mm": "Gehoert zum separaten Alert-/Deviation-Pfad, nicht zum Briefing-Rendering.",
    # Pre-Renderer-Service
    "wind_exposition_min_elevation_m": "Wird von einem vorgelagerten Exposition-Service konsumiert, kein direktes Render-Flag.",
    # Tote #790-Toggles
    "show_quick_take_tags": "Seit #790 in render_email() **_ignored absorbiert, strukturell wirkungslos.",
    "show_highlights": "Seit #790 in render_email() **_ignored absorbiert, strukturell wirkungslos.",
    "daily_summary_metrics": "Seit #790 in render_email() **_ignored absorbiert, strukturell wirkungslos.",
    "show_metrics_summary": "Seit #790 in render_email() **_ignored absorbiert, strukturell wirkungslos.",
    "show_daylight": (
        "Tote #790-Toggle-Klasse: Tageslicht-Block in #790 aus "
        "render_html/render_plain entfernt; gated im Scheduler nur noch die "
        "(wirkungslose) Vorab-Berechnung. PO 2026-07-10."
    ),
}


@dataclass(frozen=True)
class ReportRenderOptions:
    """Aufgeloeste Optionen fuer einen Briefing-Versand.

    Immutable — ersetzt den frueheren Patch-Hack, der
    `trip.display_config.show_compact_summary` mutiert hat
    (`trip_report_scheduler.py:779`).

    `show_daylight` ist NICHT render-wirksam (PO-Entscheidung 2026-07-10,
    `RENDER_NEUTRAL` — der Tageslicht-Block wurde in #790 aus den Renderern
    entfernt), bleibt aber als Attribut hier, weil der Scheduler damit die
    (teure) Tageslicht-BERECHNUNG vorab gated (Pre-Render-Gate), bevor
    `format_email()` ueberhaupt aufgerufen wird.
    """

    email_format: str
    show_outlook: bool
    show_stage_stats: bool
    show_stability: bool
    show_compact_summary: bool
    show_daylight: bool
    show_multi_day_trend: bool
    show_yesterday_comparison: bool
    display_config: "UnifiedWeatherDisplayConfig"


def resolve_report_render_options(
    report_config: Optional["TripReportConfig"],
    display_config: Optional["UnifiedWeatherDisplayConfig"],
    report_type: str,
) -> ReportRenderOptions:
    """Loest `report_config`/`display_config` VOLLSTAENDIG in `ReportRenderOptions` auf.

    Fallback-Semantik (identisch zum Bestandsverhalten vor #1208):
    - `report_config is None` → alle Toggles an (bisheriges Default-Verhalten),
      `email_format="full"`.
    - `display_config is None` → `build_default_display_config()`.
    - `show_multi_day_trend`: rc.multi_day_trend_reports, wenn rc gesetzt ist,
      sonst dc.multi_day_trend_reports, sonst `["evening"]`
      (Scheduler-Bestandslogik, `trip_report_scheduler.py:744-750`).

    Reine Funktion — mutiert weder `report_config` noch `display_config`.
    """
    from app.metric_catalog import build_default_display_config

    dc = display_config if display_config is not None else build_default_display_config()

    if report_config is None:
        return ReportRenderOptions(
            email_format="full",
            show_outlook=True,
            show_stage_stats=True,
            show_stability=True,
            show_compact_summary=True,
            show_daylight=True,
            show_multi_day_trend=report_type in (dc.multi_day_trend_reports or ["evening"]),
            show_yesterday_comparison=True,
            display_config=dc,
        )

    trend_reports = report_config.multi_day_trend_reports
    return ReportRenderOptions(
        email_format=report_config.email_format,
        show_outlook=report_config.show_outlook,
        show_stage_stats=report_config.show_stage_stats,
        show_stability=report_config.show_stability,
        show_compact_summary=report_config.show_compact_summary,
        show_daylight=report_config.show_daylight,
        show_multi_day_trend=report_type in trend_reports,
        show_yesterday_comparison=report_config.show_yesterday_comparison,
        display_config=dc,
    )
