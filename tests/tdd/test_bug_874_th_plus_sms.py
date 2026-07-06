"""TDD RED Tests — Bug #874: TH+: SMS-Token — fehlende E2E-Tests + Evening-Briefing-Lücke

Spec: docs/specs/modules/bug_874_th_plus_sms.md

Root-Cause:
  Die Golden Tests (tests/golden/test_sms_golden.py) testen build_token_line()
  direkt mit NormalizedForecast(days=(today, tomorrow)) — Layer B.
  Die Glue-Schicht in sms_trip.py (Layer A) — thunder_forecast dict →
  DailyForecast(thunder_hourly=...) → NormalizedForecast.days[1] — wurde nie
  durch format_sms() end-to-end getestet.

  Zusätzlich: Für das Abendbriefing (target_date=morgen) braucht TH+: Daten,
  die 2 Tage in der Zukunft liegen — dieser Pfad ebenfalls nie explizit geprüft.

Diese Tests beweisen das VERHALTEN: thunder_forecast["+1"] → TH+: im SMS-String.
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo


from src.app.models import (
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
from src.output.renderers.sms_trip import SMSTripFormatter

# Festes Datum: 2026-07-15 UTC
_YEAR, _MONTH, _DAY = 2026, 7, 15
_UTC = ZoneInfo("UTC")


# ---------------------------------------------------------------------------
# Minimal-Fixtures (mock-frei)
# ---------------------------------------------------------------------------

def _dp(hour: int) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=datetime(_YEAR, _MONTH, _DAY, hour, 0, tzinfo=timezone.utc),
        t2m_c=15.0,
        wind10m_kmh=10.0,
        gust_kmh=20.0,
        precip_1h_mm=0.0,
        cloud_total_pct=50,
        thunder_level=ThunderLevel.NONE,
        humidity_pct=55,
    )


def _meta() -> ForecastMeta:
    return ForecastMeta(
        provider=Provider.OPENMETEO,
        model="test",
        run=datetime(_YEAR, _MONTH, _DAY, 0, 0, tzinfo=timezone.utc),
        grid_res_km=1.0,
        interp="point_grid",
    )


def _segment() -> SegmentWeatherData:
    """Minimales Segment mit 24h Stundendaten (kein Gewitter heute)."""
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.0, lon=9.0, elevation_m=500.0),
        end_point=GPXPoint(lat=42.1, lon=9.1, elevation_m=600.0),
        start_time=datetime(_YEAR, _MONTH, _DAY, 7, 0, tzinfo=timezone.utc),
        end_time=datetime(_YEAR, _MONTH, _DAY, 17, 0, tzinfo=timezone.utc),
        duration_hours=10.0,
        distance_km=12.0,
        ascent_m=300.0,
        descent_m=0.0,
    )
    ts = NormalizedTimeseries(
        meta=_meta(),
        data=[_dp(h) for h in range(0, 24)],
    )
    return SegmentWeatherData(
        segment=seg,
        timeseries=ts,
        aggregated=SegmentWeatherSummary(
            temp_min_c=10.0,
            temp_max_c=20.0,
            wind_max_kmh=15.0,
            gust_max_kmh=25.0,
            precip_sum_mm=0.0,
            thunder_level_max=ThunderLevel.NONE,
        ),
        fetched_at=datetime(_YEAR, _MONTH, _DAY, 6, 0, tzinfo=timezone.utc),
        provider="openmeteo",
    )


# ---------------------------------------------------------------------------
# AC-1: Morgenbriefing + thunder_forecast["+1"] Level MED → TH+:M@ im SMS
# ---------------------------------------------------------------------------

class TestAC1MorningMedThunder:
    """AC-1: Morgenbriefing mit MED-Gewitter morgen → TH+:M@ im SMS-String."""

    def test_format_sms_morning_med_thunder_shows_th_plus_m(self):
        """
        GIVEN: Segment-Set + thunder_forecast["+1"] level=MED
        WHEN:  format_sms(..., report_type="morning", thunder_forecast=...)
        THEN:  SMS-String enthält "TH+:M@" (Layer A durch Layer B bewiesen)
        """
        thunder_forecast = {
            "+1": {
                "date": "16.07.2026",
                "level": ThunderLevel.MED,
                "text": "Gewitter möglich ab 14:00",
            }
        }
        sms = SMSTripFormatter().format_sms(
            [_segment()],
            report_type="morning",
            thunder_forecast=thunder_forecast,
        )
        assert "TH+:M@" in sms, (
            f"Erwarte 'TH+:M@' im SMS für MED-Gewitter morgen (morning-Briefing), "
            f"bekommen: {sms!r}"
        )


# ---------------------------------------------------------------------------
# AC-2: Abendbriefing + thunder_forecast["+1"] Level HIGH → TH+:H@ im SMS
# ---------------------------------------------------------------------------

class TestAC2EveningHighThunder:
    """AC-2: Abendbriefing mit HIGH-Gewitter übermorgen → TH+:H@ im SMS.

    Im Abendbriefing ist target_date=morgen, thunder_forecast["+1"] = übermorgen.
    Der format_sms()-Pfad ist identisch — der Unterschied liegt im Scheduler.
    Dieser Test beweist, dass der Formatter den Abend-Kontext korrekt durchlässt.
    """

    def test_format_sms_evening_high_thunder_shows_th_plus_h(self):
        """
        GIVEN: Segment-Set + thunder_forecast["+1"] level=HIGH
        WHEN:  format_sms(..., report_type="evening", thunder_forecast=...)
        THEN:  SMS-String enthält "TH+:H@" (Abend-Pfad: TH+ = Gewitter übermorgen)
        """
        thunder_forecast = {
            "+1": {
                "date": "17.07.2026",
                "level": ThunderLevel.HIGH,
                "text": "Starkes Gewitter erwartet ab 15:00",
            }
        }
        sms = SMSTripFormatter().format_sms(
            [_segment()],
            report_type="evening",
            thunder_forecast=thunder_forecast,
        )
        assert "TH+:H@" in sms, (
            f"Erwarte 'TH+:H@' im SMS für HIGH-Gewitter (evening-Briefing, "
            f"thunder_forecast['+1'] = übermorgen), bekommen: {sms!r}"
        )


# ---------------------------------------------------------------------------
# AC-3: thunder_forecast["+1"]["level"] == NONE → TH+:- im SMS
# ---------------------------------------------------------------------------

class TestAC3NoneLevel:
    """AC-3: Level NONE → keine Injektion → TH+:- im SMS."""

    def test_format_sms_none_level_shows_th_plus_dash(self):
        """
        GIVEN: thunder_forecast["+1"] level=NONE
        WHEN:  format_sms(segments, thunder_forecast=...)
        THEN:  SMS-String enthält "TH+:-" (kein Gewitter-Token)
        """
        thunder_forecast = {
            "+1": {
                "date": "16.07.2026",
                "level": ThunderLevel.NONE,
                "text": "Kein Gewitter erwartet",
            }
        }
        sms = SMSTripFormatter().format_sms(
            [_segment()],
            thunder_forecast=thunder_forecast,
        )
        assert "TH+:-" in sms, (
            f"Erwarte 'TH+:-' bei Level NONE, bekommen: {sms!r}"
        )
        assert "TH+:M@" not in sms, f"TH+:M@ darf nicht erscheinen bei NONE: {sms!r}"
        assert "TH+:H@" not in sms, f"TH+:H@ darf nicht erscheinen bei NONE: {sms!r}"


# ---------------------------------------------------------------------------
# AC-4: thunder_forecast=None / {} → TH+:- im SMS
# ---------------------------------------------------------------------------

class TestAC4NoForecast:
    """AC-4: Kein thunder_forecast → TH+:- im SMS."""

    def test_format_sms_none_forecast_shows_th_plus_dash(self):
        """
        GIVEN: thunder_forecast=None
        WHEN:  format_sms(segments, thunder_forecast=None)
        THEN:  SMS-String enthält "TH+:-"
        """
        sms = SMSTripFormatter().format_sms(
            [_segment()],
            thunder_forecast=None,
        )
        assert "TH+:-" in sms, (
            f"Erwarte 'TH+:-' bei thunder_forecast=None, bekommen: {sms!r}"
        )

    def test_format_sms_empty_dict_shows_th_plus_dash(self):
        """
        GIVEN: thunder_forecast={} (kein '+1'-Schlüssel)
        WHEN:  format_sms(segments, thunder_forecast={})
        THEN:  SMS-String enthält "TH+:-"
        """
        sms = SMSTripFormatter().format_sms(
            [_segment()],
            thunder_forecast={},
        )
        assert "TH+:-" in sms, (
            f"Erwarte 'TH+:-' bei thunder_forecast={{}}, bekommen: {sms!r}"
        )
