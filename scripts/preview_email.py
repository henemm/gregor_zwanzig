#!/usr/bin/env python3
"""Lokales Email-Preview — render_html() mit Fixture-Daten, kein API-Call.

Erzeugt eine Browser-prüfbare HTML-Datei aus dem produktiven render_html()
mit Inline-Dummy-Daten. Keine Netzwerk-Calls, keine Datenbank, keine externen
Deps. Dient EPIC 9 (Issue #236) als Sichtkontrolle der Template-Struktur.

SPEC: docs/specs/modules/issue_254_email_template_vorarbeit.md

Usage:
    uv run python scripts/preview_email.py
    uv run python scripts/preview_email.py --out /tmp/my_preview.html
    uv run python scripts/preview_email.py --report-type evening
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from app.metric_catalog import build_default_display_config  # noqa: E402
from app.models import (  # noqa: E402
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
from output.renderers.email.html import render_html  # noqa: E402


def _build_fixture() -> SegmentWeatherData:
    """Inline-Dummy-Segment mit allen Pflichtfeldern."""
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.13, lon=9.13, elevation_m=900.0),
        end_point=GPXPoint(lat=42.10, lon=9.18, elevation_m=1450.0),
        start_time=datetime(2026, 7, 11, 8, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 7, 11, 12, 0, tzinfo=timezone.utc),
        duration_hours=4.0,
        distance_km=14.5,
        ascent_m=820.0,
        descent_m=440.0,
    )
    meta = ForecastMeta(
        provider=Provider.OPENMETEO,
        model="demo",
        grid_res_km=1.3,
        run=datetime(2026, 7, 11, 0, 0, tzinfo=timezone.utc),
    )
    data = [
        ForecastDataPoint(
            ts=datetime(2026, 7, 11, h, 0, tzinfo=timezone.utc),
            t2m_c=15.0 + h * 0.3,
            wind10m_kmh=15.0,
            wind_direction_deg=180,
            precip_1h_mm=0.2,
            cloud_total_pct=50,
            thunder_level=ThunderLevel.NONE,
        )
        for h in range(0, 24)
    ]
    timeseries = NormalizedTimeseries(meta=meta, data=data)
    aggregated = SegmentWeatherSummary(
        temp_min_c=14.0, temp_max_c=22.0, temp_avg_c=18.0,
        wind_max_kmh=22.0, gust_max_kmh=35.0,
        precip_sum_mm=0.8, cloud_avg_pct=50, humidity_avg_pct=55,
        thunder_level_max=ThunderLevel.NONE,
    )
    return SegmentWeatherData(
        segment=seg, timeseries=timeseries, aggregated=aggregated,
        fetched_at=datetime.now(timezone.utc), provider="demo",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Email-HTML lokal rendern")
    parser.add_argument("--out", default="/tmp/email_preview.html")
    parser.add_argument(
        "--report-type", default="morning", choices=["morning", "evening"]
    )
    args = parser.parse_args()

    seg = _build_fixture()
    rows = [{"time": "08:00", "Temp": "18 C", "Wind": "15 km/h"}]
    html = render_html(
        segments=[seg],
        seg_tables=[rows],
        trip_name="GR20 Vorschau",
        report_type=args.report_type,
        dc=build_default_display_config(),
        night_rows=[],
        thunder_forecast=None,
        highlights=["Wind moderat erwartet", "Kein Gewitterrisiko"],
        changes=None,
        stage_name="E3: Vizzavona-Bergeries de Capanelle",
        stage_stats={"distance_km": 14.5, "ascent_m": 820, "descent_m": 440},
        multi_day_trend=None,
        compact_summary="Guter Wandertag, nachmittags leichte Bewoelkung.",
        daylight=None,
        tz=ZoneInfo("Europe/Paris"),
        friendly_keys=set(),
    )

    out_path = Path(args.out)
    out_path.write_text(html, encoding="utf-8")
    print(f"Preview geschrieben: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
