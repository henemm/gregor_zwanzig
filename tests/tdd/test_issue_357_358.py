"""
TDD RED — Issue #357 + #358

#357: WIND_EXPOSITION im SMS-Token-Pfad
  AC-1: Exponiertes Segment + Wind >=30 km/h → "GratWind" in SMS
  AC-2: Kein exponierter Abschnitt → kein Risk-Label (Regressions-Guard)
  AC-3: Exponiertes Segment + Wind >=50 km/h → "GratSturm" in SMS

#358: G_BOX_WARNING_BG in compare_html.py (nicht compare_subscription.py)
  AC-4: Token G_BOX_WARNING_BG ist in compare_html.py referenziert
"""
from datetime import datetime, timezone

import pytest

from app.models import (
    ExposedSection,
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    TripSegment,
)


def _seg(
    start_km: float,
    end_km: float,
    elev_m: float,
    wind_max: float,
    gust_max: float,
) -> SegmentWeatherData:
    base = datetime(2026, 3, 1, 8, 0, tzinfo=timezone.utc)
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=47.0, lon=11.0, elevation_m=elev_m, distance_from_start_km=start_km),
        end_point=GPXPoint(lat=47.1, lon=11.1, elevation_m=elev_m, distance_from_start_km=end_km),
        start_time=base,
        end_time=base.replace(hour=10),
        duration_hours=2.0,
        distance_km=end_km - start_km,
        ascent_m=0.0,
        descent_m=0.0,
    )
    ts = NormalizedTimeseries(
        meta=ForecastMeta(
            provider=Provider.OPENMETEO,
            model="test",
            run=base,
            grid_res_km=0.1,
            interp="point_grid",
        ),
        data=[ForecastDataPoint(ts=base, t2m_c=10.0, wind10m_kmh=wind_max, gust_kmh=gust_max)],
    )
    agg = SegmentWeatherSummary(
        temp_min_c=8.0,
        temp_max_c=12.0,
        wind_max_kmh=wind_max,
        gust_max_kmh=gust_max,
        precip_sum_mm=0.0,
    )
    return SegmentWeatherData(
        segment=seg,
        timeseries=ts,
        aggregated=agg,
        fetched_at=base,
        provider="openmeteo",
    )


# ===========================================================================
# AC-1: Exponiertes Segment + Wind MODERATE → "GratWind" im SMS
# ERWARTET ROT: format_sms() ruft _detect_risk() nicht auf → kein Label
# ===========================================================================

def test_ac1_sms_grat_wind_moderate():
    """
    GIVEN: Exponiertes Segment auf 2400m + wind_max=35 km/h
    WHEN:  format_sms() mit exposed_sections aufgerufen wird
    THEN:  "GratWind" erscheint im SMS-String
    """
    from formatters.sms_trip import SMSTripFormatter

    seg = _seg(start_km=0.0, end_km=2.0, elev_m=2400.0, wind_max=35.0, gust_max=40.0)
    exposed = [ExposedSection(start_km=0.0, end_km=2.0, max_elevation_m=2400.0, exposition_type="GRAT")]

    formatter = SMSTripFormatter()
    sms = formatter.format_sms(segments=[seg], exposed_sections=exposed)

    assert "GratWind" in sms, f"Erwartet 'GratWind' in SMS, aber war nicht vorhanden. SMS: {sms!r}"


# ===========================================================================
# AC-2: Kein exponierter Abschnitt → kein Risk-Label (Regressions-Guard)
# ERWARTET GRÜN: Aktuell kein Label, nach Fix ebenfalls keins → Guard
# ===========================================================================

def test_ac2_sms_no_exposition_no_label():
    """
    GIVEN: Nicht-exponiertes Segment (exposed_sections=[])
    WHEN:  format_sms() aufgerufen wird
    THEN:  Weder "GratWind" noch "GratSturm" im SMS-String
    """
    from formatters.sms_trip import SMSTripFormatter

    seg = _seg(start_km=0.0, end_km=2.0, elev_m=1500.0, wind_max=35.0, gust_max=40.0)

    formatter = SMSTripFormatter()
    sms = formatter.format_sms(segments=[seg], exposed_sections=[])
    sms_none = formatter.format_sms(segments=[seg], exposed_sections=None)

    for result in (sms, sms_none):
        assert "GratWind" not in result, f"Unerwartetes 'GratWind' in SMS: {result!r}"
        assert "GratSturm" not in result, f"Unerwartetes 'GratSturm' in SMS: {result!r}"


# ===========================================================================
# AC-3: Exponiertes Segment + Wind HIGH (>=50 km/h) → "GratSturm" im SMS
# ERWARTET ROT: format_sms() ruft _detect_risk() nicht auf → kein Label
# ===========================================================================

def test_ac3_sms_grat_sturm_high():
    """
    GIVEN: Exponiertes Segment auf 2400m + wind_max=55 km/h (HIGH-Schwelle)
    WHEN:  format_sms() mit exposed_sections aufgerufen wird
    THEN:  "GratSturm" erscheint im SMS-String
    """
    from formatters.sms_trip import SMSTripFormatter

    seg = _seg(start_km=0.0, end_km=2.0, elev_m=2400.0, wind_max=55.0, gust_max=65.0)
    exposed = [ExposedSection(start_km=0.0, end_km=2.0, max_elevation_m=2400.0, exposition_type="GRAT")]

    formatter = SMSTripFormatter()
    sms = formatter.format_sms(segments=[seg], exposed_sections=exposed)

    assert "GratSturm" in sms, f"Erwartet 'GratSturm' in SMS, aber war nicht vorhanden. SMS: {sms!r}"


# ===========================================================================
# AC-4: G_BOX_WARNING_BG in compare_html.py referenziert
# ERWARTET GRÜN: Token ist bereits in compare_html.py (Z. 126) genutzt
# ===========================================================================

def test_ac4_warning_token_in_compare_html():
    """
    GIVEN: compare_html.py Source-Code
    WHEN:  auf G_BOX_WARNING_BG geprüft
    THEN:  Token ist referenziert (nicht verbotene Hex-Farben #fff3cd / #ffc107)
    """
    from output.renderers.email import compare_html

    with open(compare_html.__file__) as f:
        source = f.read()

    assert "G_BOX_WARNING_BG" in source, "G_BOX_WARNING_BG fehlt in compare_html.py"
    assert "#fff3cd" not in source, "Verbotene Farbe #fff3cd in compare_html.py"
    assert "#ffc107" not in source, "Verbotene Farbe #ffc107 in compare_html.py"
