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

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.models import Corridor, TripReportConfig, UnifiedWeatherDisplayConfig

logger = logging.getLogger(__name__)

# Die 7 render-wirksamen TripReportConfig-Felder (Spec v1.1 §Implementation
# Details). PO-Entscheidung 2026-07-10 (GREEN-Review): show_daylight war hier
# entfernt und nach RENDER_NEUTRAL verschoben (Toggle strukturell wirkungslos
# seit #790). Issue #1224: das Feld selbst wurde inzwischen ganz aus
# TripReportConfig entfernt — kein RENDER_NEUTRAL-Eintrag mehr noetig.
RENDER_EFFECTIVE_FIELDS: tuple[str, ...] = (
    "email_format",
    "show_outlook",
    "show_stage_stats",
    "show_stability",
    "show_compact_summary",
    "show_yesterday_comparison",
    "multi_day_trend_reports",
)

# Die uebrigen 19 TripReportConfig-Felder — begruendet nach Kategorie
# (Spec-Tabelle "RENDER_NEUTRAL — 20 Felder, kategorisiert und begruendet";
# seit #1224 nur noch 19, show_daylight entfernt).
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
    # Issue #1306: unklassifiziertes Feld aus der Rot-Triage (#1211b).
    "telegram_style": (
        "Steuert den Telegram-Kurzstil-Kanal (#1260: 'rich'|'kurzform'), "
        "nicht den E-Mail/Plain-Render-Pfad — wirkt nachweislich weder auf "
        "render_html noch render_plain."
    ),
}


@dataclass(frozen=True)
class ReportRenderOptions:
    """Aufgeloeste Optionen fuer einen Briefing-Versand.

    Immutable — ersetzt den frueheren Patch-Hack, der
    `trip.display_config.show_compact_summary` mutiert hat
    (`trip_report_scheduler.py:779`).

    Issue #1224: `show_daylight` entfernt — die Tageslicht-BERECHNUNG (Pre-
    Render-Gate im Scheduler) wurde ersatzlos gestrichen, der Tageslicht-Block
    war seit #790 ohnehin nie im Rendering.
    """

    email_format: str
    show_outlook: bool
    show_stage_stats: bool
    show_stability: bool
    show_compact_summary: bool
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
        show_multi_day_trend=report_type in trend_reports,
        show_yesterday_comparison=report_config.show_yesterday_comparison,
        display_config=dc,
    )


@dataclass(frozen=True)
class CompareRenderOptions:
    """Aufgeloeste Render-Optionen fuer den Compare-Versandpfad (Scheibe B, #1209).

    Buendelt die bisher inline in `scheduler_dispatch_service.py:252-276`
    verstreute Default-/Clamp-/Metrik-Aufloesungslogik zu einer expliziten,
    unveraenderlichen Struktur — analog `ReportRenderOptions`.
    """

    # Issue #1360 (Scheibe S1a von Epic #1372): `top_n_details` ersatzlos
    # entfernt. Der Wert wurde seit der PO-Entscheidung 2026-07-08 von JEDEM
    # Render-Pfad verworfen (`compare_html.py`: `_ = top_n_details`) und
    # taeuschte im Editor eine Wirkung vor, die es nie gab.
    # Issue #1359: GEORDNETE Liste, kein `set`. `resolve_enabled_metrics()`
    # liefert seit #1335 bewusst eine reihenfolge-erhaltende Liste — die
    # Listenposition IST die vom Nutzer eingestellte Metrik-Reihenfolge und
    # bestimmt die Zeilenfolge in HTML-Mail, Klartext und Telegram (und ueber
    # das SMS-Budget, welche Metriken die SMS erreichen). Eine Mengen-
    # Annotation an dieser vorgelagerten Stelle laedt zum naechsten
    # Reihenfolge-Verlust ein (dieselbe Fehlerklasse wie in comparison.py).
    enabled_metrics: Optional[list[str]]
    hourly_metrics: Optional[set]
    hourly_enabled: bool
    corridors: "Optional[list[Corridor]]" = None
    # Epic #1301 B4 — 3-Tage-Ausblick je Ort. TOP-LEVEL Preset-Feld (nicht im
    # display_config-Blob, analog hourly_enabled), Default True bei
    # fehlendem Preset-Key (PO-Entscheidung 2026-07-18: Ausblick ist sofort
    # sichtbar, kein Opt-in).
    outlook_enabled: bool = True


def resolve_compare_time_window(preset: dict) -> tuple[int, int]:
    """Loest das Tagesfenster eines Compare-Presets ueber dieselbe Quelle auf
    wie der Trip-Zweig (Issue #1361/#1372 S1b, AC-1/AC-2). Ersetzt die
    deprecateten Preset-Felder ``hour_from``/``hour_to`` (#1268-Alt-Pfad) —
    diese werden hier bewusst NICHT gelesen. Geteilt zwischen
    ``scheduler_dispatch_service.send_one_compare_preset`` und
    ``compare_preview_service.ComparePreviewService._prepare`` (identisches
    Fenster fuer Versand UND Vorschau, AC-2)."""
    from output.renderers.day_window import resolve_configured_window

    return resolve_configured_window(
        preset.get("day_window_start_hour"),
        preset.get("day_window_end_hour"),
    )


def resolve_compare_render_options(preset: dict) -> CompareRenderOptions:
    """Loest ein rohes Compare-Preset-Dict VOLLSTAENDIG in `CompareRenderOptions` auf.

    Reproduziert 1:1 das Bestandsverhalten aus
    `scheduler_dispatch_service.py:252-276` (Issue #1104/#1106/#1107):
    - `enabled_metrics`/`hourly_metrics`: ueber `resolve_enabled_metrics()`/
      `resolve_hourly_metrics()` aus `display_config`.
    - `hourly_enabled`: TOP-LEVEL Preset-Feld (nicht im display_config-Blob),
      Default True.
    - `corridors`: Issue #1231, Slice 7 — TOP-LEVEL Preset-Feld `corridors`
      (Dual-Write seit Slice 1/2), geparst ueber denselben defensiven
      Trip-Parser `_corridor_from_dict` (malformte Eintraege fallen still
      raus statt den Versand zu crashen, analog Trip-Ladepfad).

    Issue #1360: ein noch gespeichertes `display_config.top_n` wird nicht mehr
    gelesen — es hat auf die Auflösung und damit auf die Mail keinerlei
    Wirkung. Aus den Daten raeumt es `scripts/migrate_1360_drop_compare_top_n.py`.

    Reine Funktion — kein I/O, keine Mutation von `preset`.
    """
    from app.loader import _corridor_from_dict
    from output.renderers.compare_hourly_metric_ids import resolve_hourly_metrics
    from output.renderers.compare_metric_ids import resolve_enabled_metrics

    preset_id = preset.get("id", "")
    display_config = preset.get("display_config") or {}

    # Adversary F004 (Fix-Loop): Nicht-Dict-Eintraege (str/int/None/...) crashen
    # sonst den gesamten Versand -- `_corridor_from_dict` ruft `d.get(...)`
    # auf, was bei Nicht-Dicts AttributeError statt der bisher gefangenen
    # (KeyError, TypeError, ValueError) wirft. isinstance-Check UND breiteres
    # except (Belt-and-Suspenders) -- ein malformter Korridor darf nie den
    # kompletten Preset-Versand verhindern (BUG-DATALOSS-GR221-Muster).
    corridors = []
    for raw in preset.get("corridors") or []:
        if not isinstance(raw, dict):
            logger.warning("Compare-Preset %s: ungueltiger Korridor %r uebersprungen", preset_id, raw)
            continue
        try:
            corridors.append(_corridor_from_dict(raw))
        except (KeyError, TypeError, ValueError, AttributeError):
            logger.warning("Compare-Preset %s: ungueltiger Korridor %r uebersprungen", preset_id, raw)

    return CompareRenderOptions(
        enabled_metrics=resolve_enabled_metrics(display_config.get("active_metrics")),
        hourly_metrics=resolve_hourly_metrics(display_config.get("hourly_metrics")),
        hourly_enabled=preset.get("hourly_enabled", True),
        corridors=corridors or None,
        outlook_enabled=preset.get("outlook_enabled", True),
    )
