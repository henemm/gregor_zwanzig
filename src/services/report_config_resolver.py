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
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.models import Corridor, TripReportConfig, UnifiedWeatherDisplayConfig

logger = logging.getLogger(__name__)

# Die render-wirksamen TripReportConfig-Felder (Spec v1.1 §Implementation
# Details: 7; seit Issue #1361/ADR-0035 zusaetzlich das Tagesfenster-Paar = 9).
# PO-Entscheidung 2026-07-10 (GREEN-Review): show_daylight war hier
# entfernt und nach RENDER_NEUTRAL verschoben (Toggle strukturell wirkungslos
# seit #790). Issue #1224: das Feld selbst wurde inzwischen ganz aus
# TripReportConfig entfernt — kein RENDER_NEUTRAL-Eintrag mehr noetig.
RENDER_EFFECTIVE_FIELDS: tuple[str, ...] = (
    "email_format",
    "show_stage_stats",
    "show_stability",
    "show_compact_summary",
    "show_yesterday_comparison",
    # Issue #1361 / ADR-0035 (S1b, gemeinsames Tagesfenster Trip + Vergleich):
    # das konfigurierte Tagesfenster erreicht den Render-Pfad
    # (trip_report.py:108-111 -> day_window.resolve_configured_window) und
    # steuert die Kurzformen bzw. die Tages-Aggregation -- render-wirksam,
    # nicht RENDER_NEUTRAL. Beide Grenzen wirken nur als PAAR: eine halb
    # gesetzte Grenze faellt in `resolve_configured_window()` bewusst still
    # auf den Default 4/19 zurueck.
    "day_window_start_hour",
    "day_window_end_hour",
)

# Die uebrigen (seit #3237: 21) TripReportConfig-Felder — begruendet nach Kategorie
# (Spec-Tabelle "RENDER_NEUTRAL — 20 Felder, kategorisiert und begruendet";
# seit #1224 nur noch 19, show_daylight entfernt).
RENDER_NEUTRAL: dict[str, str] = {
    # Metadaten
    "trip_id": "Reine Identifikation, keine Render-Wirkung.",  # i18n-log
    "updated_at": "Reiner Zeitstempel, keine Render-Wirkung.",  # i18n-log
    # Pre-Render-Gate
    "enabled": "Entscheidet VOR dem Rendern, ob ueberhaupt versendet wird.",
    "paused_until": "Entscheidet VOR dem Rendern, ob ueberhaupt versendet wird.",
    "skip_next": "Entscheidet VOR dem Rendern, ob ueberhaupt versendet wird.",
    # Issue #2422 S3: Einzel-Slot-Schalter, ausgewertet ueber slot_aktiv().
    "morning_enabled": "Entscheidet VOR dem Rendern, ob ueberhaupt versendet wird.",
    "evening_enabled": "Entscheidet VOR dem Rendern, ob ueberhaupt versendet wird.",
    # Zeitplanung
    "morning_time": "Steuert WANN der Scheduler laeuft, nicht WAS gerendert wird.",  # i18n-log
    "evening_time": "Steuert WANN der Scheduler laeuft, nicht WAS gerendert wird.",  # i18n-log
    # Kanalwahl
    "send_email": "Steuert WELCHER Kanal versendet wird, nicht den Mail-Inhalt.",  # i18n-log
    "send_sms": "Steuert WELCHER Kanal versendet wird, nicht den Mail-Inhalt.",  # i18n-log
    "send_telegram": "Steuert WELCHER Kanal versendet wird, nicht den Mail-Inhalt.",  # i18n-log
    # Issue #1676 S2a (ADR-0049): vierter Kanal, gleiche Begruendung wie die
    # drei darueber — der Premium-SMS-Text ist unveraendert `report.sms_text`.
    "send_premium_sms": "Steuert WELCHER Kanal versendet wird, nicht den Mail-Inhalt.",  # i18n-log
    # Alert-Pfad
    "alert_on_changes": "Gehoert zum separaten Alert-/Deviation-Pfad, nicht zum Briefing-Rendering.",  # i18n-log
    "change_threshold_temp_c": "Gehoert zum separaten Alert-/Deviation-Pfad, nicht zum Briefing-Rendering.",  # i18n-log
    "change_threshold_wind_kmh": "Gehoert zum separaten Alert-/Deviation-Pfad, nicht zum Briefing-Rendering.",  # i18n-log
    "change_threshold_precip_mm": "Gehoert zum separaten Alert-/Deviation-Pfad, nicht zum Briefing-Rendering.",  # i18n-log
    # Pre-Renderer-Service
    "wind_exposition_min_elevation_m": "Wird von einem vorgelagerten Exposition-Service konsumiert, kein direktes Render-Flag.",
    # Tote #790-Toggles
    "show_quick_take_tags": "Seit #790 in render_email() **_ignored absorbiert, strukturell wirkungslos.",
    "show_highlights": "Seit #790 in render_email() **_ignored absorbiert, strukturell wirkungslos.",
    "daily_summary_metrics": "Seit #790 in render_email() **_ignored absorbiert, strukturell wirkungslos.",
    "show_metrics_summary": "Seit #790 in render_email() **_ignored absorbiert, strukturell wirkungslos.",
    # Issue #3237: Altfelder des Ausblicks. Ob und in welchen Briefings der
    # Ausblick erscheint, steht allein in der Tabelle "Was steht wo"
    # (``placements.outlook_reports``/Haken Ausblick); Feld entfaellt in #3277.
    "show_outlook": "Altfeld seit #3237: der Ausblick folgt allein der Tabelle 'Was steht wo'.",  # i18n-log
    "multi_day_trend_reports": "Altfeld seit #3237: 'Ausblick erscheint im' steht in placements.outlook_reports.",  # i18n-log
    # Issue #1306: unklassifiziertes Feld aus der Rot-Triage (#1211b).
    "telegram_style": (
        "Steuert den Telegram-Kurzstil-Kanal (#1260: 'rich'|'kurzform'), "  # i18n-log
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
    - `show_multi_day_trend`: allein das View-Model der Tabelle (#3122 Nr. 6,
      #3237); `show_outlook`/`multi_day_trend_reports` wirken nicht.

    Reine Funktion — mutiert weder `report_config` noch `display_config`.
    """
    from app.metric_catalog import build_default_display_config

    dc = display_config if display_config is not None else build_default_display_config()
    ausblick = bool(resolve_trip_view(report_config, dc, report_type).outlook)
    rc = report_config  # None: alle Toggles an, "full" (getattr-Vorgabe)
    return ReportRenderOptions(
        email_format=getattr(rc, "email_format", "full"), show_outlook=True,
        show_multi_day_trend=ausblick, display_config=dc,
        **{f: getattr(rc, f, True) for f in (
            "show_stage_stats", "show_stability", "show_compact_summary",
            "show_yesterday_comparison")},
    )


def trip_enabled_reports(report_config: Optional["TripReportConfig"]) -> tuple[str, ...]:
    """#3122 (Spec Nr. 6/7): die eingeschalteten Briefings des Trips -- die
    eine Regel ``slot_aktiv`` (ohne report_config beide)."""
    from app.models import slot_aktiv

    return tuple(rt for rt in ("morning", "evening") if slot_aktiv(report_config, rt))


def resolve_trip_view(
    report_config: Optional["TripReportConfig"], display_config: object, report_type: str,
):
    """#3122: das View-Model eines Trip-Briefings (``resolve_channel_lists``)
    mit den eingeschalteten Briefings des Abos (Vorbelegung des Ausblicks)."""
    from services.channel_list_resolver import resolve_channel_lists

    return resolve_channel_lists(
        display_config, "trip", report_type,
        enabled_reports=trip_enabled_reports(report_config),
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
    # Issue #3122 B1b: das fruehere Feld `enabled_metrics` (globale
    # Grundauswahl) ist entfallen -- es hatte keinen Leser mehr; die Renderer
    # lesen `enabled_metrics_by_channel` (geordnete Listen, #1359).
    # `hourly_metrics`: Spalten des Stundenverlaufs (auch bei abgeschaltetem
    # Block -- die Spalten-Legende nennt sie dann weiter, bisheriges Verhalten).
    hourly_metrics: Optional[set]
    hourly_enabled: bool
    corridors: "Optional[list[Corridor]]" = None
    # Epic #1301 B4 — 3-Tage-Ausblick je Ort. TOP-LEVEL Preset-Feld (nicht im
    # display_config-Blob, analog hourly_enabled), Default True bei
    # fehlendem Preset-Key (PO-Entscheidung 2026-07-18: Ausblick ist sofort
    # sichtbar, kein Opt-in).
    outlook_enabled: bool = True
    # Issue #1361/#1368: Ausblick-Spaltenauswahl aus dem display_config-Blob,
    # Neuformat `[{"metric_id", "aggregation"}]` (dasselbe Vokabular wie
    # `active_metrics`, #1373). `None` = Feld fehlt (Altbestand, bisherige
    # sieben Spalten), `[]` = bewusst leer (Block entfaellt).
    outlook_metrics: Optional[list[dict]] = None
    # Issue #2049: Roh/Einfach je Ausblick-Groesse aus demselben
    # display_config-Blob, `{kennung: bool}` (True = Einfach). Paralleles Feld
    # zu `outlook_metrics`, das damit eine reine Kennungsliste bleibt. `None`
    # = nie eingestellt; fehlende Kennung = Rohzahl (Default hart "Roh").
    outlook_metric_formats: Optional[dict] = None
    # Issue #3097 (ADR-0121 Nachtrag 3b): Roh/Einfach je Stundenverlauf-
    # Groesse `{kennung: True}` aus `view.hourly[].format`; `None` = alles Roh.
    hourly_metric_formats: Optional[dict] = None
    # Issue #1703 Scheibe 8: kanal-eigene Auswahl der UEBERSICHTSTABELLE, je
    # Kanal aus der Tabelle "Was steht wo" (#3122/#3237). Keys: "email"/"telegram"/"sms" --
    # Compare-Briefing kennt strukturell nur diese drei (ADR-0049): Premium-SMS
    # ist seit #2275 auch im Vergleich Briefing-Kanal, hat aber keine eigene
    # Metrik-Auswahl -- sie sendet den fertig gerenderten SMS-Text.
    #
    # Die Renderer-Signaturen bleiben `list[str] | None`; `None` je Kanal
    # heisst "kein Filter" (nur Altbestand ohne Grundauswahl und Kanal-Liste).
    enabled_metrics_by_channel: dict[str, Optional[list[str]]] = field(
        default_factory=dict
    )
    # Issue #1405 S3: je Kanal die Anzahl GEWAEHLTER Eintraege ohne Renderer-
    # Zuordnung (Grundauswahl, dedupliziert). Zentral nicht
    # waehlbare und vom Kanal abgewaehlte Groessen zaehlen nicht. Die Renderer
    # zeigen die Zahl (Hinweiszeile bzw. SMS-Zaehler `?N`), statt sie nur zu
    # loggen. Lesestelle: `.get(kanal, 0)` (fehlender Eintrag = nichts fehlt).
    unresolved_by_channel: dict[str, int] = field(default_factory=dict)
    # Issue #3039 (ADR-0119): je Kanal die geordneten Zeilen samt Format aus
    # der Tabelle als `(renderer_id, einfach)`. BEWUSST ADDITIV:
    # `enabled_metrics_by_channel` traegt dieselbe Reihenfolge ohne Format.
    # `None` je Kanal = Festzustand (nur Aufrufer ohne Resolver).
    channel_rows_by_channel: dict[str, Optional[list[tuple[str, bool]]]] = field(
        default_factory=dict
    )

    def metric_formats(self, channel: str) -> Optional[dict[str, bool]]:
        """`{renderer_id: einfach}` eines Kanals fuer die Renderer; `None` =
        Festzustand (kein `channel_layouts` fuer diesen Kanal)."""
        rows = self.channel_rows_by_channel.get(channel)
        return None if rows is None else dict(rows)


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


def resolve_compare_render_options(
    preset: dict, *, report_type: Optional[str] = None,
) -> CompareRenderOptions:
    """Loest ein rohes Compare-Preset-Dict VOLLSTAENDIG in `CompareRenderOptions` auf.

    Issue #3122 B1b: Auswahl, Reihenfolge, Darstellung und die Block-
    Entscheidung fuer Stundenverlauf und Ausblick kommen allein aus dem
    View-Model des Kanal-Listen-Resolvers. Er bekommt dafuer die Abo-Angaben
    (Briefing-Typ ``report_type`` des Versand-Slots, eingeschaltete Briefings,
    ``hourly_enabled``, ``outlook_enabled``); ``report_type=None`` (Vorschau)
    heisst "irgendein Typ". Abos ohne ``placements`` lesen die Tabelle aus
    ihrer Grundauswahl (#3237).
    - `corridors`: Issue #1231, Slice 7 — TOP-LEVEL Preset-Feld `corridors`,
      geparst ueber den defensiven Trip-Parser `_corridor_from_dict`.

    Issue #1360: ein noch gespeichertes `display_config.top_n` wird nicht mehr
    gelesen. Reine Funktion — kein I/O, keine Mutation von `preset`.
    """
    from services.channel_list_resolver import grundauswahl, resolve_channel_lists

    display_config = preset.get("display_config") or {}
    hourly_schalter = preset.get("hourly_enabled", True)
    abo = {"enabled_reports": compare_enabled_reports(preset)}
    view = resolve_channel_lists(
        display_config, "compare", report_type, **abo,
        hourly_enabled=bool(hourly_schalter),
        outlook_enabled=bool(preset.get("outlook_enabled", True)),
    )
    hourly = _compare_hourly(view.hourly, view.hourly, hourly_schalter)
    # Issue #3039/#3057: Kanal-Zeilen samt Format je Metrik-Kanal.
    # ADR-0049: nur Metrik-/Layout-Kanaele -- Premium-SMS sendet den SMS-Text.
    kanaele = ("email", "telegram", "sms")
    channel_rows = {
        ch: [(rid, z.format == "simplified") for rid, z in orte_renderer_zeilen(getattr(view, ch))]
        for ch in kanaele
    }
    # Issue #1405 S3: Hinweiszaehler -- Grundauswahl ueber die Resolver-Hilfe.
    unaufloesbar = len(dict.fromkeys(
        grundauswahl(display_config, "compare", report_type).unaufloesbar))
    return CompareRenderOptions(
        **hourly,
        corridors=_compare_corridors(preset) or None,
        **_compare_outlook(view.outlook),
        enabled_metrics_by_channel={ch: orte_renderer_ids(getattr(view, ch)) for ch in kanaele},
        unresolved_by_channel={ch: unaufloesbar for ch in kanaele},
        channel_rows_by_channel=channel_rows,
    )


def orte_renderer_zeilen(zeilen) -> list[tuple[str, object]]:
    """Adapter vor dem Renderer (Issue #3101, ADR-0121 Nachtrag 4): die
    eingeschalteten Zeilen einer Orte-Kanalliste des View-Models (Katalog-ID
    + Aggregation) -> ``[(renderer_kennung, zeile)]`` in Listenfolge.
    Ein Paar ohne Renderer-Zeile hat keine Ausgabe und faellt heraus."""
    from output.renderers.compare_metric_ids import renderer_kennung

    out = []
    for z in zeilen or ():
        rid = renderer_kennung(z.metric_id, z.aggregation) if z.enabled else None
        if rid is not None:
            out.append((rid, z))
    return out


def orte_renderer_ids(zeilen) -> Optional[list[str]]:
    """Renderer-Kennungen einer Orte-Kanalliste; ``None`` (kein Filter)
    bleibt ``None``."""
    return None if zeilen is None else [rid for rid, _z in orte_renderer_zeilen(zeilen)]


def compare_enabled_reports(preset: dict) -> Optional[list[str]]:
    """Eingeschaltete Briefings eines Orte-Abos (``morning``/``evening``) aus
    den Slot-Feldern (``resolve_preset_slots``, samt Altbestand-Rueckfall);
    ``None`` bei unlesbaren Zeitplan-Daten."""
    from services.compare_slot_scheduler import resolve_preset_slots

    try:
        slots = resolve_preset_slots(preset)
    except (ValueError, TypeError, KeyError):
        return None
    return [typ for typ, an in (("morning", slots.morning_enabled),
                                ("evening", slots.evening_enabled)) if an]


def _compare_hourly(block: tuple, spalten: tuple, schalter: object) -> dict:
    """Stundenverlauf aus dem View-Model: ``block == ()`` = Block entfaellt;
    eine Auswahl ohne sichtbare Wert-Spalte schaltet ihn ebenfalls ab
    (#1366/#1361 Befund 3). ``hourly_enabled`` behaelt bei gespeichertem
    ``null`` den Wert ``None`` (Mail-Kopf entfaellt dann wie bisher, #1107)."""
    from app.metric_catalog import get_metric
    from output.renderers.email.compare_html import has_visible_hour_columns

    an = bool(block) and has_visible_hour_columns([get_metric(z.metric_id).dp_field for z in block])
    return {
        "hourly_metrics": [get_metric(z.metric_id).dp_field for z in spalten],
        "hourly_enabled": an if (an or schalter) else schalter,
        # Issue #3097: Roh/Einfach je Stundenverlauf-Groesse; None = alles Roh.
        "hourly_metric_formats": {
            z.metric_id: True for z in spalten if z.format == "simplified"} or None,
    }


def _compare_outlook(zeilen: Optional[tuple]) -> dict:
    """3-Tages-Ausblick aus dem View-Model: ``()`` = Block entfaellt, ``None``
    = Renderer-Vorgabe; Auswahl, Folge und Roh/Einfach aus den Zeilen."""
    return {
        "outlook_enabled": zeilen != (),
        "outlook_metrics": None if zeilen is None else [z.metric_id for z in zeilen],
        "outlook_metric_formats": {
            z.metric_id: True for z in zeilen or () if z.format == "simplified"} or None,
    }


def _compare_corridors(preset: dict) -> list:
    """Adversary F004: Nicht-Dict-Eintraege und malformte Korridore fallen
    still heraus (geloggt), statt den ganzen Versand zu verhindern."""
    from app.loader import _corridor_from_dict

    preset_id = preset.get("id", "")
    corridors = []
    for raw in preset.get("corridors") or []:
        if not isinstance(raw, dict):
            logger.warning("Compare-Preset %s: ungueltiger Korridor %r uebersprungen", preset_id, raw)
            continue
        try:
            corridors.append(_corridor_from_dict(raw))
        except (KeyError, TypeError, ValueError, AttributeError):
            logger.warning("Compare-Preset %s: ungueltiger Korridor %r uebersprungen", preset_id, raw)
    return corridors
