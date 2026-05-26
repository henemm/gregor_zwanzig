"""TDD RED — Issue #397: Segment-Zeitangaben in UTC statt lokaler Zeit.

SPEC: docs/specs/modules/bug_397_segment_timezone_display.md (AC-1..AC-3)

Alle drei Tests MÜSSEN ROT sein, weil die Renderer und build_segment_label
aktuell `.strftime('%H:%M')` auf UTC-Datetimes aufrufen, statt local_fmt zu
verwenden.

Kein Mocking — reine Datenstrukturen + echte Aufrufe der echten Funktionen.
"""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

# ---------------------------------------------------------------------------
# Shared fixture factory
# ---------------------------------------------------------------------------

_CEST = ZoneInfo("Europe/Paris")  # UTC+2 im Sommer
# Segment 08:00–10:00 UTC = 10:00–12:00 CEST
_SEG_START_UTC = datetime(2026, 7, 15, 8, 0, tzinfo=timezone.utc)
_SEG_END_UTC   = datetime(2026, 7, 15, 10, 0, tzinfo=timezone.utc)
_LOCAL_START   = "10:00"  # Erwartete lokale Darstellung (CEST)
_LOCAL_END     = "12:00"
_UTC_START     = "08:00"  # DARF NICHT im Output erscheinen nach dem Fix


def _make_seg_data():
    """Minimale SegmentWeatherData mit UTC 08:00–10:00 Segment."""
    from app.models import (
        ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries,
        Provider, SegmentWeatherData, SegmentWeatherSummary, TripSegment,
    )

    points = [
        ForecastDataPoint(
            ts=datetime(2026, 7, 15, 8 + h, 0, tzinfo=timezone.utc),
            t2m_c=18.0 + h,
            wind10m_kmh=12.0,
            gust_kmh=20.0,
            pop_pct=10,
            precip_1h_mm=0.0,
        )
        for h in range(3)
    ]
    meta = ForecastMeta(
        provider=Provider.OPENMETEO,
        model="icon_d2",
        run=_SEG_START_UTC,
        grid_res_km=2.0,
        interp="nearest",
    )
    ts = NormalizedTimeseries(meta=meta, data=points)
    segment = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.3, lon=9.1, elevation_m=800),
        end_point=GPXPoint(lat=42.4, lon=9.15, elevation_m=1200),
        start_time=_SEG_START_UTC,
        end_time=_SEG_END_UTC,
        duration_hours=2.0,
        distance_km=8.5,
        ascent_m=400,
        descent_m=0,
    )
    return SegmentWeatherData(
        segment=segment,
        timeseries=ts,
        aggregated=SegmentWeatherSummary(),
        fetched_at=_SEG_START_UTC,
        provider="openmeteo",
    )


def _make_dc():
    """Minimale UnifiedWeatherDisplayConfig (Temperatur aktiviert)."""
    from app.models import MetricConfig, UnifiedWeatherDisplayConfig
    return UnifiedWeatherDisplayConfig(
        trip_id="test-397",
        metrics=[MetricConfig(metric_id="temperature", enabled=True)],
        updated_at=_SEG_START_UTC,
    )


# ===========================================================================
# AC-2: build_segment_label gibt lokale Zeit zurück
# ===========================================================================

def test_build_segment_label_local_time_cest():
    """AC-2: build_segment_label(change, segments, tz) muss lokale CEST-Zeit
    im Label verwenden, nicht UTC.

    RED: Schlägt fehl, weil build_segment_label noch keinen tz-Parameter hat
    (TypeError) und intern UTC-strftime aufruft.
    """
    from app.models import ChangeSeverity, WeatherChange
    from src.output.renderers.email.helpers import build_segment_label

    change = WeatherChange(
        metric="wind10m_kmh",
        old_value=12.0,
        new_value=28.0,
        delta=16.0,
        threshold=10.0,
        severity=ChangeSeverity.MODERATE,
        direction="increase",
        segment_id="1",
    )
    seg_data = _make_seg_data()

    # tz als drittes Argument — existiert noch nicht → TypeError erwartet im RED
    label = build_segment_label(change, [seg_data], _CEST)

    # Nach dem Fix muss die lokale CEST-Zeit erscheinen, nicht UTC
    assert _LOCAL_START in label, (
        f"Label '{label}' muss lokale Startzeit {_LOCAL_START!r} enthalten, "
        f"nicht UTC {_UTC_START!r}"
    )
    assert _LOCAL_END in label, (
        f"Label '{label}' muss lokale Endzeit {_LOCAL_END!r} enthalten"
    )
    assert _UTC_START not in label, (
        f"Label '{label}' darf UTC-Zeit {_UTC_START!r} NICHT enthalten"
    )


# ===========================================================================
# AC-1: render_plain Segment-Header zeigt lokale Zeit
# ===========================================================================

def test_render_plain_segment_header_local_time_cest():
    """AC-1: render_plain muss in der ━━-Kopfzeile lokale CEST-Zeit anzeigen,
    nicht UTC.

    RED: Schlägt fehl, weil plain.py aktuell seg.start_time.strftime('%H:%M')
    aufruft → gibt '08:00' aus, aber '10:00' (CEST) wird erwartet.
    """
    from src.output.renderers.email.plain import render_plain

    seg_data = _make_seg_data()
    dc = _make_dc()

    output = render_plain(
        segments=[seg_data],
        seg_tables=[[{"time": "10", "temp": 18.0}]],
        trip_name="GR20 Etappe 1",
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
        tz=_CEST,
        friendly_keys=set(),
    )

    # Segment-Kopfzeile: "━━ Segment 1: HH:MM–HH:MM | ..."
    assert _LOCAL_START in output, (
        f"render_plain-Output muss lokale Startzeit {_LOCAL_START!r} enthalten.\n"
        f"Tatsächlicher Output (Auszug):\n"
        + "\n".join(line for line in output.splitlines() if "━━" in line or "Segment" in line)
    )
    assert _UTC_START not in output, (
        f"render_plain-Output darf UTC-Zeit {_UTC_START!r} NICHT enthalten.\n"
        f"Tatsächlicher Output (Auszug):\n"
        + "\n".join(line for line in output.splitlines() if _UTC_START in line)
    )


# ===========================================================================
# AC-3: render_narrow Segment-Header zeigt lokale Zeit (Signal/Telegram)
# ===========================================================================

def test_render_narrow_segment_header_local_time_cest():
    """AC-3: render_narrow muss lokale CEST-Zeit in der Segment-Kopfzeile
    anzeigen, nicht UTC.

    RED: Schlägt fehl, weil narrow.py aktuell seg.start_time.strftime('%H:%M')
    aufruft UND local_fmt noch nicht importiert hat → '08:00' statt '10:00'.
    """
    from src.output.renderers.narrow import render_narrow

    seg_data = _make_seg_data()
    dc = _make_dc()

    output = render_narrow(
        "signal",
        segments=[seg_data],
        seg_tables=[[{"time": "10", "temp": 18.0}]],
        dc=dc,
        report_type="morning",
        tz=_CEST,
        trip_name="GR20",
    )

    assert _LOCAL_START in output, (
        f"render_narrow-Output muss lokale Startzeit {_LOCAL_START!r} enthalten.\n"
        f"Tatsächlicher Output:\n{output}"
    )
    assert _UTC_START not in output, (
        f"render_narrow-Output darf UTC-Zeit {_UTC_START!r} NICHT enthalten.\n"
        f"Tatsächlicher Output:\n{output}"
    )
