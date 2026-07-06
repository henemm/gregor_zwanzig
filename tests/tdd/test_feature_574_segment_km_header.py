"""
TDD RED — Feature #574: Segment-Header mit km-Bereich.

Issue: https://github.com/henemm/gregor_zwanzig/issues/574

Aktuell zeigt die Briefing-E-Mail in den Segment-Überschriften nur die reine
Segmentlänge ("4.2 km"). Gewünscht ist der kumulative km-Bereich ("km 0.0–4.2"),
damit Wanderer sehen, wo auf der Etappe das Zeitfenster liegt.

Spec: docs/specs/modules/feature_574_segment_km_header.md
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def _build_two_segments():
    """Zwei normale Segmente: Seg 1 km 0.0–4.2, Seg 2 km 4.2–9.3."""
    from app.models import (
        ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries,
        Provider, SegmentWeatherData, SegmentWeatherSummary, ThunderLevel,
        TripSegment,
    )

    def _make_seg(seg_id, start_km, end_km, start_h, end_h):
        seg = TripSegment(
            segment_id=seg_id,
            start_point=GPXPoint(
                lat=42.13, lon=9.13, elevation_m=400.0,
                distance_from_start_km=start_km,
            ),
            end_point=GPXPoint(
                lat=42.10, lon=9.18, elevation_m=1200.0,
                distance_from_start_km=end_km,
            ),
            start_time=datetime(2026, 7, 11, start_h, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 7, 11, end_h, 0, tzinfo=timezone.utc),
            duration_hours=float(end_h - start_h),
            distance_km=round(end_km - start_km, 1),
            ascent_m=800.0,
            descent_m=0.0,
        )
        meta = ForecastMeta(
            provider=Provider.OPENMETEO, model="demo", grid_res_km=1.3,
            run=datetime(2026, 7, 11, 0, 0, tzinfo=timezone.utc),
        )
        data = [
            ForecastDataPoint(
                ts=datetime(2026, 7, 11, h, 0, tzinfo=timezone.utc),
                t2m_c=15.0, wind10m_kmh=20.0,
                precip_1h_mm=0.0, cloud_total_pct=30,
                thunder_level=ThunderLevel.NONE,
            )
            for h in range(start_h, end_h + 1)
        ]
        ts = NormalizedTimeseries(meta=meta, data=data)
        agg = SegmentWeatherSummary(
            temp_min_c=14.0, temp_max_c=22.0, temp_avg_c=18.0,
            wind_max_kmh=20.0, gust_max_kmh=30.0,
            precip_sum_mm=0.0, cloud_avg_pct=30, humidity_avg_pct=50,
            thunder_level_max=ThunderLevel.NONE,
        )
        return SegmentWeatherData(
            segment=seg, timeseries=ts, aggregated=agg,
            fetched_at=datetime.now(timezone.utc), provider="demo",
        )

    return [
        _make_seg(1, 0.0, 4.2, 6, 10),
        _make_seg(2, 4.2, 9.3, 10, 14),
    ]


def _build_seg_with_destination():
    """Ein normales Segment + Ziel-Segment."""
    from app.models import (
        ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries,
        Provider, SegmentWeatherData, SegmentWeatherSummary, ThunderLevel,
        TripSegment,
    )

    def _make_normal():
        seg = TripSegment(
            segment_id=1,
            start_point=GPXPoint(
                lat=42.13, lon=9.13, elevation_m=400.0,
                distance_from_start_km=0.0,
            ),
            end_point=GPXPoint(
                lat=42.10, lon=9.18, elevation_m=1200.0,
                distance_from_start_km=4.2,
            ),
            start_time=datetime(2026, 7, 11, 6, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 7, 11, 10, 0, tzinfo=timezone.utc),
            duration_hours=4.0,
            distance_km=4.2,
            ascent_m=800.0,
            descent_m=0.0,
        )
        meta = ForecastMeta(
            provider=Provider.OPENMETEO, model="demo", grid_res_km=1.3,
            run=datetime(2026, 7, 11, 0, 0, tzinfo=timezone.utc),
        )
        data = [
            ForecastDataPoint(
                ts=datetime(2026, 7, 11, h, 0, tzinfo=timezone.utc),
                t2m_c=15.0, wind10m_kmh=20.0,
                precip_1h_mm=0.0, cloud_total_pct=30,
                thunder_level=ThunderLevel.NONE,
            )
            for h in range(6, 11)
        ]
        ts = NormalizedTimeseries(meta=meta, data=data)
        agg = SegmentWeatherSummary(
            temp_min_c=14.0, temp_max_c=22.0, temp_avg_c=18.0,
            wind_max_kmh=20.0, gust_max_kmh=30.0,
            precip_sum_mm=0.0, cloud_avg_pct=30, humidity_avg_pct=50,
            thunder_level_max=ThunderLevel.NONE,
        )
        return SegmentWeatherData(
            segment=seg, timeseries=ts, aggregated=agg,
            fetched_at=datetime.now(timezone.utc), provider="demo",
        )

    def _make_destination():
        seg = TripSegment(
            segment_id="Ziel",
            start_point=GPXPoint(
                lat=42.08, lon=9.20, elevation_m=800.0,
                distance_from_start_km=4.2,
            ),
            end_point=GPXPoint(
                lat=42.08, lon=9.20, elevation_m=800.0,
                distance_from_start_km=4.2,
            ),
            start_time=datetime(2026, 7, 11, 10, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 7, 11, 12, 0, tzinfo=timezone.utc),
            duration_hours=2.0,
            distance_km=0.0,
            ascent_m=0.0,
            descent_m=0.0,
        )
        meta = ForecastMeta(
            provider=Provider.OPENMETEO, model="demo", grid_res_km=1.3,
            run=datetime(2026, 7, 11, 0, 0, tzinfo=timezone.utc),
        )
        data = [
            ForecastDataPoint(
                ts=datetime(2026, 7, 11, h, 0, tzinfo=timezone.utc),
                t2m_c=16.0, wind10m_kmh=18.0,
                precip_1h_mm=0.0, cloud_total_pct=20,
                thunder_level=ThunderLevel.NONE,
            )
            for h in range(10, 13)
        ]
        ts = NormalizedTimeseries(meta=meta, data=data)
        agg = SegmentWeatherSummary(
            temp_min_c=15.0, temp_max_c=20.0, temp_avg_c=17.0,
            wind_max_kmh=18.0, gust_max_kmh=25.0,
            precip_sum_mm=0.0, cloud_avg_pct=20, humidity_avg_pct=45,
            thunder_level_max=ThunderLevel.NONE,
        )
        return SegmentWeatherData(
            segment=seg, timeseries=ts, aggregated=agg,
            fetched_at=datetime.now(timezone.utc), provider="demo",
        )

    return [_make_normal(), _make_destination()]


_SIMPLE_ROWS = [
    {
        "time": "06:00",
        "temp": 15.0,
        "_wind_dir_deg": None,
        "_is_day": True,
        "_dni_wm2": None,
        "_sunny_hours": 0.0,
        "_wmo_code": None,
    },
]


# ---------------------------------------------------------------------------
# AC-1: Plain-Text zeigt km X.X–Y.Y für beide Segmente
# ---------------------------------------------------------------------------

class TestAC1PlainTextKmRange:

    def test_plain_segment1_shows_km_0_to_4_2(self):
        """
        AC-1 (Teil 1): Plain-Text-Header von Segment 1 enthält 'km 0.0–4.2'.

        GIVEN 2 Segmente (km 0.0–4.2, km 4.2–9.3)
        WHEN Plain-Text-E-Mail gerendert wird
        THEN enthält Segment-1-Überschrift 'km 0.0–4.2'
        """
        from app.metric_catalog import build_default_display_config
        from output.renderers.email.plain import render_plain

        segs = _build_two_segments()
        result = render_plain(
            segments=segs,
            seg_tables=[_SIMPLE_ROWS, _SIMPLE_ROWS],
            trip_name="GR20 Test",
            report_type="morning",
            dc=build_default_display_config(),
            night_rows=[],
            thunder_forecast=None,
            highlights=[],
            changes=None,
            stage_name=None,
            stage_stats=None,
            multi_day_trend=None,
            compact_summary=None,
            daylight=None,
            tz=ZoneInfo("Europe/Berlin"),
            friendly_keys=set(),
        )
        assert "km 0.0–4.2" in result, (
            f"Erwartet 'km 0.0–4.2' im Plain-Text-Header, "
            f"aber nicht gefunden. Ausgabe:\n{result[:1000]}"
        )

    def test_plain_segment2_shows_km_4_2_to_9_3(self):
        """
        AC-1 (Teil 2): Plain-Text-Header von Segment 2 enthält 'km 4.2–9.3'.

        GIVEN 2 Segmente (km 0.0–4.2, km 4.2–9.3)
        WHEN Plain-Text-E-Mail gerendert wird
        THEN enthält Segment-2-Überschrift 'km 4.2–9.3'
        """
        from app.metric_catalog import build_default_display_config
        from output.renderers.email.plain import render_plain

        segs = _build_two_segments()
        result = render_plain(
            segments=segs,
            seg_tables=[_SIMPLE_ROWS, _SIMPLE_ROWS],
            trip_name="GR20 Test",
            report_type="morning",
            dc=build_default_display_config(),
            night_rows=[],
            thunder_forecast=None,
            highlights=[],
            changes=None,
            stage_name=None,
            stage_stats=None,
            multi_day_trend=None,
            compact_summary=None,
            daylight=None,
            tz=ZoneInfo("Europe/Berlin"),
            friendly_keys=set(),
        )
        assert "km 4.2–9.3" in result, (
            f"Erwartet 'km 4.2–9.3' im Plain-Text-Header, "
            f"aber nicht gefunden. Ausgabe:\n{result[:1000]}"
        )


# ---------------------------------------------------------------------------
# AC-2: HTML — normales Segment hat km-Bereich, Ziel-Segment nicht
# ---------------------------------------------------------------------------

class TestAC2HtmlKmRangeNormalSegmentOnly:

    def test_html_normal_segment_has_km_range(self):
        """
        AC-2 (Teil 1): HTML-<h3> des normalen Segments enthält 'km 0.0–4.2'.

        GIVEN 1 normales Segment (km 0.0–4.2) + Ziel-Segment
        WHEN HTML-E-Mail gerendert wird
        THEN enthält der <h3>-Tag 'km 0.0–4.2'
        """
        from app.metric_catalog import build_default_display_config
        from output.renderers.email.html import render_html

        segs = _build_seg_with_destination()
        result = render_html(
            segments=segs,
            seg_tables=[_SIMPLE_ROWS, _SIMPLE_ROWS],
            trip_name="GR20 Test",
            report_type="morning",
            dc=build_default_display_config(),
            night_rows=[],
            thunder_forecast=None,
            highlights=[],
            changes=None,
            stage_name=None,
            stage_stats=None,
            multi_day_trend=None,
            compact_summary=None,
            daylight=None,
            tz=ZoneInfo("Europe/Berlin"),
            friendly_keys=set(),
        )
        assert "km 0.0–4.2" in result, (
            "Erwartet 'km 0.0–4.2' im HTML-Segment-Header, "
            "aber nicht gefunden."
        )

    def test_html_destination_segment_has_no_km_range(self):
        """
        AC-2 (Teil 2): Ziel-Segment-Header enthält KEIN 'km X.X–Y.Y'.

        GIVEN 1 normales Segment + Ziel-Segment
        WHEN HTML-E-Mail gerendert wird
        THEN enthält der Ziel-Header ('🏁 Wetter am Ziel') kein 'km X.X–Y.Y'
        """
        from app.metric_catalog import build_default_display_config
        from output.renderers.email.html import render_html

        segs = _build_seg_with_destination()
        result = render_html(
            segments=segs,
            seg_tables=[_SIMPLE_ROWS, _SIMPLE_ROWS],
            trip_name="GR20 Test",
            report_type="morning",
            dc=build_default_display_config(),
            night_rows=[],
            thunder_forecast=None,
            highlights=[],
            changes=None,
            stage_name=None,
            stage_stats=None,
            multi_day_trend=None,
            compact_summary=None,
            daylight=None,
            tz=ZoneInfo("Europe/Berlin"),
            friendly_keys=set(),
        )
        # Ziel-Block isolieren
        ziel_idx = result.find("Wetter am Ziel")
        assert ziel_idx != -1, "Ziel-Segment-Block nicht gefunden"
        # Im Ziel-Block darf kein km-Bereich stehen
        ziel_block = result[ziel_idx:ziel_idx + 200]
        import re
        assert not re.search(r"km\s+\d+\.\d+", ziel_block), (
            f"Ziel-Header darf keinen km-Bereich enthalten, "
            f"gefunden in: {ziel_block}"
        )


# ---------------------------------------------------------------------------
# AC-3: Mobile-Header (.mobile-compact) enthält ebenfalls km-Bereich
# ---------------------------------------------------------------------------

class TestAC3MobileHeaderKmRange:

    def test_mobile_compact_header_contains_km_range(self):
        """
        AC-3: Mobile-Compact-Header enthält 'km 0.0–4.2'.

        GIVEN 2 normale Segmente (km 0.0–4.2, km 4.2–9.3)
        WHEN HTML-E-Mail gerendert wird
        THEN enthält der mobile-compact-Block 'km 0.0–4.2'
        """
        from app.metric_catalog import build_default_display_config
        from output.renderers.email.html import render_html

        segs = _build_two_segments()
        result = render_html(
            segments=segs,
            seg_tables=[_SIMPLE_ROWS, _SIMPLE_ROWS],
            trip_name="GR20 Test",
            report_type="morning",
            dc=build_default_display_config(),
            night_rows=[],
            thunder_forecast=None,
            highlights=[],
            changes=None,
            stage_name=None,
            stage_stats=None,
            multi_day_trend=None,
            compact_summary=None,
            daylight=None,
            tz=ZoneInfo("Europe/Berlin"),
            friendly_keys=set(),
        )
        mobile_idx = result.find('class="mobile-compact"')
        assert mobile_idx != -1, "mobile-compact-Content-Div nicht gefunden"
        mobile_block = result[mobile_idx:mobile_idx + 500]
        assert "km 0.0–4.2" in mobile_block, (
            f"Erwartet 'km 0.0–4.2' im mobile-compact-Content-Div, "
            f"aber nicht gefunden. Mobile-Block:\n{mobile_block}"
        )


# ---------------------------------------------------------------------------
# AC-4: Alte "X.X km"-Darstellung taucht im Segment-Header nicht mehr auf
# ---------------------------------------------------------------------------

class TestAC4NoRawDistanceInHeader:

    def test_plain_header_does_not_contain_raw_distance_km(self):
        """
        AC-4 (Plain-Text): '4.2 km' erscheint nicht mehr im Segment-Header.

        GIVEN Segment mit distance_km=4.2
        WHEN Plain-Text-E-Mail gerendert wird
        THEN enthält die Segment-Überschrift NICHT '4.2 km' (nur noch km-Bereich)
        """
        from app.metric_catalog import build_default_display_config
        from output.renderers.email.plain import render_plain

        segs = _build_two_segments()
        result = render_plain(
            segments=segs,
            seg_tables=[_SIMPLE_ROWS, _SIMPLE_ROWS],
            trip_name="GR20 Test",
            report_type="morning",
            dc=build_default_display_config(),
            night_rows=[],
            thunder_forecast=None,
            highlights=[],
            changes=None,
            stage_name=None,
            stage_stats=None,
            multi_day_trend=None,
            compact_summary=None,
            daylight=None,
            tz=ZoneInfo("Europe/Berlin"),
            friendly_keys=set(),
        )
        # Den Segment-Header isolieren (erste ━━-Zeile)
        lines = result.splitlines()
        seg_headers = [l for l in lines if "Segment 1:" in l]
        assert seg_headers, "Segment-1-Header nicht gefunden"
        header = seg_headers[0]
        assert "4.2 km" not in header, (
            f"Alter '4.2 km'-Text noch im Segment-Header: '{header}'"
        )
