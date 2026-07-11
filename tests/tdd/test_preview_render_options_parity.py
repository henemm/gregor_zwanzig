"""Issue #1209 AC-1 — Vorschau ≡ Versand, kein Bestandsobjekt-Mutations-Hack.

Spec: docs/specs/modules/report_config_resolver_slice_b.md

Bug F002 (Adversary-Befund, #1208): `PreviewService._build_report()` mutiert
`trip.display_config.show_compact_summary = trip.report_config.show_compact_summary`
(preview_service.py:120-121) statt den Resolver zu benutzen und das Ergebnis
explizit an `format_email(..., render_options=...)` durchzureichen.

Zwei Assertions in EINEM Test (AC-1-Text):
  A) Bug-Repro: `trip.display_config.show_compact_summary` ist nach einem
     Preview-Aufruf unveraendert gegenueber vorher (Patch-Hack mutiert das
     Bestandsobjekt heute — ROT).
  B) Paritaet: Vorschau und ein resolver-basierter Referenz-Renderaufruf
     (Vorbild fuer den Versandpfad, identisch zu trip_report_scheduler.py
     nach #1208) treffen fuer denselben Trip dieselbe compact/full-
     Format-Entscheidung.

KEINE Mocks/patch/MagicMock — echte In-Memory-Trip-Fixture + echter
FixtureProvider (Issue #346/#483), kein Dateiinhalt-Check.
"""
from __future__ import annotations

import copy
from datetime import date
from pathlib import Path

_FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "openmeteo"


def _build_trip(target: date):
    """In-Memory-Trip: email_format=compact, show_compact_summary=False im
    report_config; display_config-Default (show_compact_summary=True) weicht
    davon ab, damit eine Mutation ueberhaupt beobachtbar waere."""
    from app.metric_catalog import build_default_display_config
    from app.models import TripReportConfig
    from app.trip import Stage, Trip, Waypoint

    wp1 = Waypoint(id="G1", name="Start", lat=47.2692, lon=11.4041, elevation_m=600)
    wp2 = Waypoint(id="G2", name="Ziel", lat=47.3010, lon=11.4500, elevation_m=1200)
    stage = Stage(id="T1", name="Etappe 1", date=target, waypoints=[wp1, wp2])

    dc = build_default_display_config(trip_id="parity-trip")
    assert dc.show_compact_summary is True, "Testvoraussetzung: Default ist True"

    rc = TripReportConfig(
        trip_id="parity-trip",
        email_format="compact",
        show_compact_summary=False,
    )

    return Trip(
        id="parity-trip",
        name="Parity-Test-Trip",
        stages=[stage],
        display_config=dc,
        report_config=rc,
    )


def _render_reference(trip, target: date, report_type: str):
    """Referenz-Renderaufruf — resolver-basiert, OHNE Patch-Hack (Vorbild:
    trip_report_scheduler.py nach #1208). Simuliert den korrekten Versandpfad."""
    from providers.fixture import FixtureProvider
    from services.report_config_resolver import resolve_report_render_options
    from services.trip_report_scheduler import TripReportSchedulerService
    from src.output.renderers.trip_report import TripReportFormatter
    from utils.timezone import tz_for_coords

    scheduler = TripReportSchedulerService()
    segments = scheduler._convert_trip_to_segments(trip, target)
    provider = FixtureProvider(str(_FIXTURE_DIR))
    segment_weather = scheduler._fetch_weather(segments, provider=provider)
    trip_tz = tz_for_coords(segments[0].start_point.lat, segments[0].start_point.lon)
    stage = trip.get_stage_for_date(target)
    stage_name = trip.numbered_stage_label(stage) if stage else None
    stage_stats = scheduler._compute_stage_stats(stage) if stage else None

    render_options = resolve_report_render_options(
        trip.report_config, trip.display_config, report_type,
    )
    return TripReportFormatter().format_email(
        segments=segment_weather,
        trip_name=trip.name,
        report_type=report_type,
        display_config=trip.display_config,
        stage_name=stage_name,
        stage_stats=stage_stats,
        tz=trip_tz,
        profile=trip.aggregation.profile,
        stability_result=None,
        report_config=trip.report_config,
        render_options=render_options,
    )


def test_preview_does_not_mutate_display_config_and_matches_reference_render():
    """AC-1: Preview mutiert `trip.display_config` nicht mehr (A) UND trifft
    dieselbe compact/full-Entscheidung wie der resolver-basierte Referenzpfad (B)."""
    from services.preview_service import PreviewService

    target = date.today()
    trip_for_preview = _build_trip(target)
    trip_for_reference = copy.deepcopy(trip_for_preview)

    before = trip_for_preview.display_config.show_compact_summary

    preview_report, _segments, _stage_name, _tz = PreviewService()._build_report(
        trip_for_preview, target, "morning", demo=True,
    )

    after = trip_for_preview.display_config.show_compact_summary

    # --- Assertion A (Bug-Repro, F002) ---
    assert after == before, (
        f"AC-1: trip.display_config.show_compact_summary wurde durch den "
        f"Preview-Aufruf mutiert (Patch-Hack preview_service.py:120-121): "
        f"vorher={before!r}, nachher={after!r}. Der Resolver "
        f"(resolve_report_render_options) muss show_compact_summary aus "
        f"report_config lesen, OHNE das Bestandsobjekt trip.display_config "
        f"zu veraendern."
    )

    # --- Assertion B (Paritaet Vorschau vs. Referenz-Versandpfad) ---
    reference_report = _render_reference(trip_for_reference, target, "morning")

    preview_is_compact = preview_report.email_html == "" and bool(preview_report.email_plain)
    reference_is_compact = reference_report.email_html == "" and bool(reference_report.email_plain)
    assert preview_is_compact == reference_is_compact, (
        f"AC-1: Vorschau und Referenz-Versandpfad treffen unterschiedliche "
        f"compact/full-Format-Entscheidungen fuer denselben Trip: "
        f"preview_is_compact={preview_is_compact!r} (html={preview_report.email_html!r}), "
        f"reference_is_compact={reference_is_compact!r} (html={reference_report.email_html!r})"
    )
    assert preview_is_compact, (
        "Testvoraussetzung: report_config.email_format='compact' muss zu "
        "leerem email_html fuehren (compact-Vertrag)."
    )
