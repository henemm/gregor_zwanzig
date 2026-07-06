"""Issue #342 — Pro-Metrik-Zeithorizont-Filter im Email-Renderer.

Spec:  docs/specs/modules/issue_342_pro_metrik_horizon_backend.md
Tests-Spec: docs/specs/tests/issue_342_pro_metrik_horizon_backend_tests.md
Issue: https://github.com/henemm/gregor_zwanzig/issues/342

Tests gegen AC-1 … AC-3 (Renderer-Filter pro Etappe) und AC-7
(Backward-Compat ohne horizons-Feld) sowie ein direkter Mapping-Test fuer
derive_horizon().

KEINE Mocks (CLAUDE.md-Regel). Echte Imports + echte Dict-Strukturen.
Tests scheitern absichtlich (RED): visible_cols() hat heute die Signatur
visible_cols(rows: list[dict]) und kein horizon-Argument. derive_horizon()
existiert noch gar nicht. Bei `pytest` → TypeError / ImportError.
"""

from __future__ import annotations

from datetime import date



# ----------------------------------------------------------------------
# AC-1: today-Filter blendet thunder aus, wind bleibt sichtbar
# ----------------------------------------------------------------------

def test_visible_cols_filters_today_metric():
    """AC-1: horizon='today' + thunder.today=False → thunder fehlt im Ergebnis."""
    from output.renderers.email.helpers import visible_cols

    dc_metrics = [
        {
            "metric_id": "thunder",
            "enabled": True,
            "horizons": {"today": False, "tomorrow": True, "day_after": True},
        },
        {
            "metric_id": "wind",
            "enabled": True,
            "horizons": {"today": True, "tomorrow": True, "day_after": True},
        },
    ]
    cols = visible_cols(dc_metrics, horizon="today")
    assert "thunder" not in cols, f"thunder sollte fuer today gefiltert sein, got {cols}"
    assert "wind" in cols, f"wind muss fuer today sichtbar bleiben, got {cols}"


# ----------------------------------------------------------------------
# AC-2: tomorrow-Filter zeigt thunder (horizons.tomorrow=True)
# ----------------------------------------------------------------------

def test_visible_cols_shows_tomorrow_metric():
    """AC-2: gleiche dc_metrics, horizon='tomorrow' → thunder ist enthalten."""
    from output.renderers.email.helpers import visible_cols

    dc_metrics = [
        {
            "metric_id": "thunder",
            "enabled": True,
            "horizons": {"today": False, "tomorrow": True, "day_after": True},
        },
        {
            "metric_id": "wind",
            "enabled": True,
            "horizons": {"today": True, "tomorrow": True, "day_after": True},
        },
    ]
    cols = visible_cols(dc_metrics, horizon="tomorrow")
    assert "thunder" in cols, f"thunder sollte fuer tomorrow sichtbar sein, got {cols}"
    assert "wind" in cols


# ----------------------------------------------------------------------
# AC-3: horizon=None (Tag 4+) → Filter ignoriert horizons-Flags
# ----------------------------------------------------------------------

def test_visible_cols_ignores_horizon_for_day4():
    """AC-3: horizon=None liefert alle enabled Metriken, auch wenn horizons.* False ist."""
    from output.renderers.email.helpers import visible_cols

    dc_metrics = [
        {
            "metric_id": "thunder",
            "enabled": True,
            "horizons": {"today": False, "tomorrow": False, "day_after": False},
        },
        {
            "metric_id": "wind",
            "enabled": True,
            "horizons": {"today": False, "tomorrow": False, "day_after": False},
        },
        {
            "metric_id": "temperature",
            "enabled": False,
            "horizons": {"today": True, "tomorrow": True, "day_after": True},
        },
    ]
    cols = visible_cols(dc_metrics, horizon=None)
    # Alle enabled Metriken erscheinen, Disabled nicht.
    assert "thunder" in cols
    assert "wind" in cols
    assert "temperature" not in cols, "disabled muss immer gefiltert sein"


# ----------------------------------------------------------------------
# AC-7: Legacy-Trip ohne horizons-Feld → Default greift
# ----------------------------------------------------------------------

def test_visible_cols_legacy_no_horizons_field():
    """AC-7: kein horizons-Schluessel → Default {True,True,True} greift."""
    from output.renderers.email.helpers import visible_cols

    dc_metrics = [
        {"metric_id": "wind", "enabled": True},  # kein horizons-Key
    ]
    cols = visible_cols(dc_metrics, horizon="today")
    assert "wind" in cols, f"Legacy ohne horizons muss alle Horizonte zeigen, got {cols}"


# ----------------------------------------------------------------------
# derive_horizon(): delta-Mapping
# ----------------------------------------------------------------------

def test_derive_horizon_mapping():
    """derive_horizon() liefert today/tomorrow/day_after fuer delta 0/1/2, None fuer >=3."""
    from output.renderers.email.helpers import derive_horizon

    base = date(2026, 5, 23)
    assert derive_horizon(base, date(2026, 5, 23)) == "today"
    assert derive_horizon(base, date(2026, 5, 24)) == "tomorrow"
    assert derive_horizon(base, date(2026, 5, 25)) == "day_after"
    assert derive_horizon(base, date(2026, 5, 26)) is None


def test_derive_horizon_negative_delta():
    """Vergangene Etappen (delta < 0) geben None zurueck — kein Horizont-Treffer.

    Issue #351 / AC-1: Backfill-Coverage fuer expliziten Guard.
    Verhalten war bereits korrekt (catch-all return None), dieser Test
    dokumentiert und sichert es ab.
    """
    from output.renderers.email.helpers import derive_horizon

    report = date(2026, 5, 10)
    assert derive_horizon(report, date(2026, 5, 9)) is None    # delta = -1
    assert derive_horizon(report, date(2026, 5, 1)) is None    # delta = -9
    assert derive_horizon(report, date(2025, 12, 31)) is None  # delta = -130


# ----------------------------------------------------------------------
# End-to-End: render_html() filtert pro Etappe
# ----------------------------------------------------------------------

def test_render_html_filters_per_stage():
    """E2E: render_html() propagiert horizon pro Etappe.

    Baut drei Etappen mit Startdatum heute/morgen/uebermorgen, schreibt ein
    UnifiedWeatherDisplayConfig mit per-Metrik unterschiedlichen horizons
    und prueft, dass jeder Etappen-HTML-Block nur die erwarteten Spalten enthaelt.
    """
    from datetime import datetime, timedelta, timezone
    from zoneinfo import ZoneInfo

    from app.metric_catalog import get_metric
    from app.models import (
        ForecastDataPoint, ForecastMeta, GPXPoint, MetricConfig,
        NormalizedTimeseries, Provider, SegmentWeatherData,
        SegmentWeatherSummary, ThunderLevel, TripSegment,
        UnifiedWeatherDisplayConfig,
    )
    from output.renderers.email.helpers import (
        build_friendly_keys, extract_hourly_rows,
    )
    from output.renderers.email.html import render_html

    base = datetime(2026, 6, 1, 0, 0, tzinfo=timezone.utc)

    def _seg(seg_id: int, day_offset: int) -> SegmentWeatherData:
        start = base + timedelta(days=day_offset, hours=8)
        end = base + timedelta(days=day_offset, hours=12)
        seg = TripSegment(
            segment_id=seg_id,
            start_point=GPXPoint(lat=42.20, lon=9.05, elevation_m=400.0),
            end_point=GPXPoint(lat=42.25, lon=9.09, elevation_m=1200.0),
            start_time=start, end_time=end,
            duration_hours=4.0, distance_km=8.0,
            ascent_m=800.0, descent_m=0.0,
        )
        meta = ForecastMeta(
            provider=Provider.OPENMETEO, model="arome_france",
            run=base, grid_res_km=1.3, interp="point_grid",
        )
        dps = [
            ForecastDataPoint(
                ts=start + timedelta(hours=h),
                t2m_c=18.0 + h, wind10m_kmh=12.0, gust_kmh=22.0,
                precip_1h_mm=0.0, cloud_total_pct=40,
                thunder_level=ThunderLevel.NONE,
                wind_chill_c=16.0, humidity_pct=55,
            )
            for h in range(0, 5)
        ]
        ts = NormalizedTimeseries(meta=meta, data=dps)
        agg = SegmentWeatherSummary(
            temp_min_c=18.0, temp_max_c=22.0, temp_avg_c=20.0,
            wind_max_kmh=12.0, gust_max_kmh=22.0,
            precip_sum_mm=0.0, cloud_avg_pct=40, humidity_avg_pct=55,
            thunder_level_max=ThunderLevel.NONE, wind_chill_min_c=16.0,
        )
        return SegmentWeatherData(
            segment=seg, timeseries=ts, aggregated=agg,
            fetched_at=base, provider="openmeteo",
        )

    segments = [_seg(1, 0), _seg(2, 1), _seg(3, 2)]

    # DC: thunder NUR heute, wind NUR morgen, temperature alle drei Tage.
    dc = UnifiedWeatherDisplayConfig(
        trip_id="t1",
        metrics=[
            MetricConfig(metric_id="thunder", enabled=True,
                         horizons={"today": True, "tomorrow": False, "day_after": False}),
            MetricConfig(metric_id="wind", enabled=True,
                         horizons={"today": False, "tomorrow": True, "day_after": False}),
            MetricConfig(metric_id="temperature", enabled=True,
                         horizons={"today": True, "tomorrow": True, "day_after": True}),
        ],
    )

    tz = ZoneInfo("UTC")
    seg_tables = [extract_hourly_rows(s, dc, tz=tz) for s in segments]
    friendly_keys = build_friendly_keys(dc)

    html = render_html(
        segments=segments,
        seg_tables=seg_tables,
        trip_name="Test-Trip",
        report_type="morning",
        dc=dc,
        night_rows=[],
        thunder_forecast=None,
        highlights=[],
        changes=None,
        stage_name=None,
        stage_stats=None,
        multi_day_trend=None,
        compact_summary=None,
        daylight=None,
        tz=tz,
        friendly_keys=friendly_keys,
    )

    # Erwartete col_labels aus dem MetricCatalog (Vermeidung Hardcoding).
    th_label = get_metric("thunder").col_label
    wind_label = get_metric("wind").col_label
    temp_label = get_metric("temperature").col_label

    # Drei desktop-only Segment-Bloecke (1=heute, 2=morgen, 3=uebermorgen).
    # Note: #884 added style attribute to segment divs:
    #   '<div class="section desktop-only" style="padding:14px 28px 0;">'
    # Split on the partial string (without closing >) to match both variants.
    parts = html.split('<div class="section desktop-only"')
    assert len(parts) >= 4, f"Erwartet 3 Etappen-Bloecke, got {len(parts) - 1}"
    block_today, block_tomorrow, block_dayafter = parts[1], parts[2], parts[3]

    # Etappe 1 (heute): Thunder sichtbar, Wind nicht.
    assert f"<th>{th_label}</th>" in block_today, "thunder fehlt im heute-Block"
    assert f"<th>{wind_label}</th>" not in block_today, "wind sollte heute gefiltert sein"
    assert f"<th>{temp_label}</th>" in block_today

    # Etappe 2 (morgen): Wind sichtbar, Thunder nicht.
    assert f"<th>{wind_label}</th>" in block_tomorrow, "wind fehlt im morgen-Block"
    assert f"<th>{th_label}</th>" not in block_tomorrow, "thunder sollte morgen gefiltert sein"
    assert f"<th>{temp_label}</th>" in block_tomorrow

    # Etappe 3 (uebermorgen): nur Temperature.
    assert f"<th>{temp_label}</th>" in block_dayafter
    assert f"<th>{th_label}</th>" not in block_dayafter
    assert f"<th>{wind_label}</th>" not in block_dayafter
