"""TDD RED->GREEN: Fix-Loop #1660 B -- Null-Form fuer aktive Metriken ohne Daten.

Bug (Staging-E2E, Verdict BROKEN): "Metrik gewaehlt, keine Daten im Fenster"
zeigte KEINE Null-Form (z.B. 'PT-') -- der Token fehlte VOLLSTAENDIG. Ursache:
trip_report.py fuehrte die 14 erweiterten Metriken (#1660 Scheibe B) nur in
der disabled-only-Schleife (Bug-#944-Muster) -- eine AKTIVE Metrik bekam
dadurch nie eine MetricSpec und builder.py's
`if spec is None and not samples: continue`-Gate liess sie ganz entfallen.

Diese Tests laufen bewusst ueber den ECHTEN Produktionshelfer
`build_extended_metric_specs()` (nicht ueber eine an Ort und Stelle
konstruierte MetricSpec wie der bestehende AC-10-Test) -- Prueforte muss dem
Wirkort entsprechen (Muster aus mehreren Vorfaellen, s. CLAUDE.md).

SPEC: docs/specs/modules/fix_1660b_sms_token_wiring.md DEC-3/§9, AC-10.
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.models import (
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    TripSegment,
)
from output.renderers.sms_trip import SMSTripFormatter, build_extended_metric_specs

_TZ = ZoneInfo("UTC")


def _meta() -> ForecastMeta:
    return ForecastMeta(
        provider=Provider.OPENMETEO, model="test",
        run=datetime(2026, 8, 10, 0, 0, tzinfo=timezone.utc),
        grid_res_km=1.0, interp="point_grid",
    )


def _dp(hour: int, *, day: int = 10, **overrides) -> ForecastDataPoint:
    """Datenpunkt OHNE die zu testenden Klassen-c/a/b-Felder -- Default laesst
    precip_type/visibility_m unbesetzt (None); cloud_total_pct wird bei Bedarf
    per Override auf None gesetzt (Basis-Default ist 50)."""
    base = dict(
        ts=datetime(2026, 8, day, hour, 0, tzinfo=timezone.utc),
        t2m_c=15.0, wind10m_kmh=5.0, gust_kmh=5.0, precip_1h_mm=0.0,
        pop_pct=0, cloud_total_pct=50, thunder_level=ThunderLevel.NONE,
        humidity_pct=55,
    )
    base.update(overrides)
    return ForecastDataPoint(**base)


def _single_day_segment(points: list[ForecastDataPoint]) -> SegmentWeatherData:
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=47.0, lon=11.0, elevation_m=1500),
        end_point=GPXPoint(lat=47.1, lon=11.1, elevation_m=1800),
        start_time=datetime(2026, 8, 10, 4, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 8, 10, 19, 0, tzinfo=timezone.utc),
        duration_hours=15.0, distance_km=20.0, ascent_m=800, descent_m=400,
    )
    ts = NormalizedTimeseries(meta=_meta(), data=points)
    return SegmentWeatherData(
        segment=seg, timeseries=ts,
        aggregated=SegmentWeatherSummary(temp_min_c=10.0, temp_max_c=20.0),
        fetched_at=datetime(2026, 8, 10, 3, 0, tzinfo=timezone.utc),
        provider="openmeteo",
    )


def test_precip_type_null_form_when_active_without_data():
    """Klasse (c), Wirkort-Test: nur precip_type aktiv, KEIN Datenpunkt traegt
    precip_type -> 'PT-' MUSS in der SMS stehen (nicht: Token fehlt ganz)."""
    points = [_dp(h) for h in range(4, 20)]
    segments = [_single_day_segment(points)]

    sms = SMSTripFormatter().format_sms(
        segments, stage_name="Etappe1", report_type="evening", tz=_TZ,
        disabled_specs=build_extended_metric_specs({"precip_type"}),
    )
    assert "PT-" in sms, f"PT-Null-Form fehlt (Bug: Token entfaellt komplett): {sms!r}"


def test_cloud_total_null_and_gap_form_when_active_without_data():
    """Klasse (a): nur cloud_total aktiv, keine Wolkendaten -> 'CT-'; mit
    Datenluecke (has_gap=True) -> 'CT?'."""
    points = [_dp(h, cloud_total_pct=None) for h in range(4, 20)]
    segments = [_single_day_segment(points)]

    sms = SMSTripFormatter().format_sms(
        segments, stage_name="Etappe1", report_type="evening", tz=_TZ,
        disabled_specs=build_extended_metric_specs({"cloud_total"}),
    )
    assert "CT-" in sms, f"CT-Null-Form fehlt: {sms!r}"

    sms_gap = SMSTripFormatter().format_sms(
        segments, stage_name="Etappe1", report_type="evening", tz=_TZ,
        disabled_specs=build_extended_metric_specs({"cloud_total"}),
        has_gap=True,
    )
    assert "CT?" in sms_gap, f"CT-Gap-Form fehlt: {sms_gap!r}"
    assert "CT-" not in sms_gap, f"bei Gap darf keine '-'-Form mehr stehen: {sms_gap!r}"


def test_visibility_null_form_when_active_without_data():
    """Klasse (b): nur visibility aktiv, keine Sichtwerte -> 'VS-'."""
    points = [_dp(h) for h in range(4, 20)]
    segments = [_single_day_segment(points)]

    sms = SMSTripFormatter().format_sms(
        segments, stage_name="Etappe1", report_type="evening", tz=_TZ,
        disabled_specs=build_extended_metric_specs({"visibility"}),
    )
    assert "VS-" in sms, f"VS-Null-Form fehlt: {sms!r}"


def test_empty_active_set_matches_all_disabled_byte_identical():
    """Negativ-Kontrolle: build_extended_metric_specs(set()) (keine der 14
    gewaehlt, aber Daten LIEGEN VOR) muss zeichengleich zum alten
    disabled-only-Muster sein (Bug #944, s. trip_report.py's fruehere
    1:1-Schleife) -- die vollstaendige Abwahl darf durch den Helfer weder ein
    Geistertoken (z.B. 'PT-' aus der Null-Form) noch einen echten Wert
    (z.B. 'HU55@4') erzeugen."""
    from output.renderers.sms_trip import SMS_NULLFORM_METRIC_IDS, SMS_SYMBOL_BY_METRIC
    from output.tokens.dto import MetricSpec

    points = [_dp(h) for h in range(4, 20)]
    segments = [_single_day_segment(points)]

    sms_via_helper = SMSTripFormatter().format_sms(
        segments, stage_name="Etappe1", report_type="evening", tz=_TZ,
        disabled_specs=build_extended_metric_specs(set()),
    )
    old_style_all_disabled = [
        MetricSpec(symbol=SMS_SYMBOL_BY_METRIC[mid], enabled=False)
        for mid in SMS_NULLFORM_METRIC_IDS
    ]
    sms_via_old_pattern = SMSTripFormatter().format_sms(
        segments, stage_name="Etappe1", report_type="evening", tz=_TZ,
        disabled_specs=old_style_all_disabled,
    )
    assert sms_via_helper == sms_via_old_pattern, (
        f"leeres active-Set muss zeichengleich zum alten disabled-only-Muster sein:\n"
        f"  Helfer: {sms_via_helper!r}\n"
        f"  alt:    {sms_via_old_pattern!r}"
    )
    assert "PT-" not in sms_via_helper and "HU55" not in sms_via_helper, (
        f"kein Geistertoken/Wert der 14 bei vollstaendiger Abwahl erwartet: {sms_via_helper!r}"
    )


# ---------------------------------------------------------------------------
# Adversary-Runde 3 (VERDRAHTUNG): die Tests oben rufen build_extended_
# metric_specs() SELBST auf und reichen das Ergebnis von Hand an format_sms()
# -- das prueft die Helfer-Grammatik, nicht die Verdrahtung in trip_report.py
# (Zeile "_disabled_sms_specs += build_extended_metric_specs(active_metric_ids)").
# Mutation "diese Zeile entfernen" = exakt der urspruengliche Staging-Bug --
# und macht KEINEN der obigen Tests rot (Prüfort != Wirkort).
#
# Die folgenden Tests fahren deshalb den ECHTEN Produktionspfad
# TripReportFormatter().format_email() -> report.sms_text (Vorbild:
# tests/tdd/test_sms_thunder_from_hourly_timeseries.py, dort fuer TH:).
# Nur hier wirkt die Metrik-Auswahl (UnifiedWeatherDisplayConfig) tatsaechlich
# ueber sms_metric_ids -> active_metric_ids -> build_extended_metric_specs().
# ---------------------------------------------------------------------------

from output.renderers.trip_report import TripReportFormatter
from tests.tdd import _min_temp_felt_fixtures as F


def test_precip_type_null_form_reaches_production_wiring():
    """AKTIV, ohne precip_type-Daten im Fenster -> 'PT-' MUSS in der ECHTEN
    Trip-SMS stehen (TripReportFormatter().format_email() -> sms_text).

    F.segment()/F.night_weather() tragen nie precip_type (Feld bleibt in der
    Fixture unbesetzt) -- "gewaehlt, aber kein Wert" ist damit automatisch
    gegeben, ohne die Zeitreihe extra zu verstuemmeln."""
    report = TripReportFormatter().format_email(
        [F.segment()],
        trip_name="Issue1660B",
        report_type="evening",
        night_weather=F.night_weather(),
        display_config=F.dc("precip_type"),
        stage_name=F.STAGE_NAME,
        tz=F.TZ,
    )
    sms = report.sms_text
    assert F.sms_token_value(sms, "PT") == "-", (
        f"'PT-' erwartet (Metrik gewaehlt, keine Daten) -- Bug: der Token "
        f"entfaellt komplett, wenn die Verdrahtung in trip_report.py fehlt.\n"
        f"SMS: {sms!r}"
    )


def test_precip_type_absent_via_production_wiring_when_deselected():
    """Negativfall ueber denselben Produktionspfad: precip_type NICHT
    gewaehlt -> kein 'PT'-Token in der SMS (weder Wert noch Null-Form)."""
    report = TripReportFormatter().format_email(
        [F.segment()],
        trip_name="Issue1660B",
        report_type="evening",
        night_weather=F.night_weather(),
        display_config=F.dc("precipitation"),
        stage_name=F.STAGE_NAME,
        tz=F.TZ,
    )
    sms = report.sms_text
    assert F.sms_token_value(sms, "PT") is None, (
        f"'PT' darf bei Abwahl gar nicht vorkommen: {sms!r}"
    )
