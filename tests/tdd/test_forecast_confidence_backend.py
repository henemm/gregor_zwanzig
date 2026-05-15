"""
TDD RED: Forecast Confidence Backend (Issue #121, Workflow 1)

SPEC: docs/specs/modules/forecast_confidence.md v1.0

Tests for AC-1, AC-3 to AC-8 (Backend). AC-2 (Go) lives in
internal/model/forecast_confidence_test.go.

PHASE: TDD RED — all tests MUST FAIL with current code.

No mocks — real OpenMeteo Ensemble API calls, real DTOs, real RiskEngine.
Fault-injection (AC-6) uses a closed local TCP port to produce a genuine
connection error, not a Mock object.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest


class TestForecastDataPointBackwardCompat:
    """AC-1: ForecastDataPoint (Python) backward-compat without confidence fields."""

    def test_can_construct_without_confidence_fields(self):
        """Old snapshots without the three new fields load without error."""
        from app.models import ForecastDataPoint

        dp = ForecastDataPoint(
            ts=datetime.now(timezone.utc),
            t2m_c=20.0,
            wind10m_kmh=10.0,
        )
        assert dp.confidence_pct is None
        assert dp.spread_t2m_k is None
        assert dp.spread_precip_mm is None

    def test_can_construct_with_confidence_fields(self):
        """New code can populate the three new fields."""
        from app.models import ForecastDataPoint

        dp = ForecastDataPoint(
            ts=datetime.now(timezone.utc),
            t2m_c=20.0,
            confidence_pct=85,
            spread_t2m_k=1.0,
            spread_precip_mm=0.5,
        )
        assert dp.confidence_pct == 85
        assert dp.spread_t2m_k == 1.0
        assert dp.spread_precip_mm == 0.5


class TestConfidenceCalculation:
    """AC-4 & AC-5: compute_confidence_pct() with Lead-Time-Cap."""

    def test_t12h_spread_2k_1mm_yields_60pct(self):
        """AC-5: T+12h, spread=(2.0, 1.0) → 100 - 30 - 10 = 60, no cap effect."""
        from providers.openmeteo import compute_confidence_pct

        result = compute_confidence_pct(
            spread_t2m_k=2.0, spread_precip_mm=1.0, lead_time_hours=12
        )
        assert result == 60

    def test_t96h_zero_spread_capped_at_40pct(self):
        """AC-4: T+96h, spread=(0, 0) → cap = 40, NOT 100. This is the critical case."""
        from providers.openmeteo import compute_confidence_pct

        result = compute_confidence_pct(
            spread_t2m_k=0.0, spread_precip_mm=0.0, lead_time_hours=96
        )
        assert result == 40, f"Lead-time cap not enforced — got {result} for T+96h"

    def test_t1h_perfect_spread_capped_at_95pct(self):
        """T+1h, zero spread → cap = 95 (never 100)."""
        from providers.openmeteo import compute_confidence_pct

        assert compute_confidence_pct(0.0, 0.0, 1) == 95

    def test_t36h_capped_at_80pct(self):
        """T+36h falls in the 24-48h band → cap = 80."""
        from providers.openmeteo import compute_confidence_pct

        assert compute_confidence_pct(0.0, 0.0, 36) == 80

    def test_t60h_capped_at_60pct(self):
        """T+60h falls in the 48-72h band → cap = 60."""
        from providers.openmeteo import compute_confidence_pct

        assert compute_confidence_pct(0.0, 0.0, 60) == 60

    def test_high_spread_clamped_to_zero(self):
        """Very high spread → confidence_pct clamped to 0 (no negative values)."""
        from providers.openmeteo import compute_confidence_pct

        result = compute_confidence_pct(
            spread_t2m_k=10.0, spread_precip_mm=20.0, lead_time_hours=12
        )
        assert result == 0


@pytest.mark.tdd
class TestEnsembleSpreadFetchLive:
    """AC-3: Real OpenMeteo Ensemble call for Salzburg."""

    def test_salzburg_yields_spread_for_90pct_of_hours(self):
        """≥90% of hourly points must have spread_t2m_k and confidence_pct populated."""
        from app.models import Location
        from providers.openmeteo import OpenMeteoProvider

        provider = OpenMeteoProvider()
        salzburg = Location(name="Salzburg", latitude=47.8, longitude=13.0)
        now = datetime.now(timezone.utc)
        end = now + timedelta(hours=168)

        result = provider.fetch_forecast(salzburg, start=now, end=end)

        total = len(result.data)
        assert total > 0, "Forecast returned zero data points"

        with_spread = sum(1 for dp in result.data if dp.spread_t2m_k is not None)
        coverage = with_spread / total
        assert coverage >= 0.9, (
            f"Only {with_spread}/{total} = {coverage:.0%} hours have spread_t2m_k "
            f"(need ≥90%)"
        )

        for dp in result.data:
            if dp.spread_t2m_k is not None:
                assert dp.confidence_pct is not None, "spread set but confidence_pct missing"
                assert 0 <= dp.confidence_pct <= 100, (
                    f"confidence_pct={dp.confidence_pct} out of [0, 100]"
                )


class TestEnsembleFailureGraceful:
    """AC-6: Unreachable Ensemble API → forecast still returns, confidence fields None."""

    def test_unreachable_ensemble_host_does_not_break_forecast(self):
        """
        With the ensemble host pointing at a closed local port we get a real
        connection error (NOT a mock). The main forecast must still succeed and
        all three confidence fields must be None.
        """
        from app.models import Location
        from providers.openmeteo import OpenMeteoProvider

        provider = OpenMeteoProvider(ensemble_base_host="http://127.0.0.1:1")
        salzburg = Location(name="Salzburg", latitude=47.8, longitude=13.0)
        now = datetime.now(timezone.utc)
        end = now + timedelta(hours=24)

        result = provider.fetch_forecast(salzburg, start=now, end=end)

        assert len(result.data) > 0, "Forecast must succeed even if ensemble fails"
        for dp in result.data:
            assert dp.confidence_pct is None, "confidence_pct must be None on ensemble failure"
            assert dp.spread_t2m_k is None
            assert dp.spread_precip_mm is None


class TestSegmentConfidenceAggregation:
    """AC-7: aggregation picks minimum confidence_pct across hourly points."""

    def _make_timeseries(self, confidences):
        from app.models import (
            ForecastDataPoint,
            ForecastMeta,
            NormalizedTimeseries,
            Provider,
        )

        base = datetime.now(timezone.utc)
        data = [
            ForecastDataPoint(
                ts=base + timedelta(hours=i),
                t2m_c=20.0,
                confidence_pct=c,
            )
            for i, c in enumerate(confidences)
        ]
        meta = ForecastMeta(
            provider=Provider.OPENMETEO,
            model="ecmwf_ifs",
            grid_res_km=40.0,
        )
        return NormalizedTimeseries(meta=meta, data=data)

    def test_aggregation_returns_minimum(self):
        """[90, 80, 30, 75, 80] → confidence_pct_min = 30."""
        from services.weather_metrics import WeatherMetricsService

        ts = self._make_timeseries([90, 80, 30, 75, 80])
        service = WeatherMetricsService()
        confidence_min = service._compute_confidence_min(ts)
        assert confidence_min == 30

    def test_aggregation_returns_none_when_all_none(self):
        """All None → confidence_pct_min = None."""
        from services.weather_metrics import WeatherMetricsService

        ts = self._make_timeseries([None, None, None])
        service = WeatherMetricsService()
        assert service._compute_confidence_min(ts) is None

    def test_segment_weather_summary_has_field(self):
        """SegmentWeatherSummary.confidence_pct_min default = None."""
        from app.models import SegmentWeatherSummary

        summary = SegmentWeatherSummary()
        assert summary.confidence_pct_min is None

        summary2 = SegmentWeatherSummary(confidence_pct_min=42)
        assert summary2.confidence_pct_min == 42


class TestRiskEngineLowConfidence:
    """AC-8: LOW_CONFIDENCE risk fires ONLY in combination with a HIGH-level event."""

    def _make_segment(self, **summary_kwargs):
        from datetime import datetime, timezone

        from app.models import (
            GPXPoint,
            SegmentWeatherData,
            SegmentWeatherSummary,
            TripSegment,
        )

        point = GPXPoint(lat=47.8, lon=13.0, elevation_m=800, distance_from_start_km=0.0)
        segment = TripSegment(
            segment_id=1,
            start_point=point,
            end_point=point,
            start_time=datetime(2026, 5, 16, 8, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 5, 16, 10, 0, tzinfo=timezone.utc),
            duration_hours=2.0,
            distance_km=4.0,
            ascent_m=200,
            descent_m=100,
        )
        return SegmentWeatherData(
            segment=segment,
            timeseries=None,
            aggregated=SegmentWeatherSummary(**summary_kwargs),
            fetched_at=datetime.now(timezone.utc),
            provider="openmeteo",
        )

    def test_low_confidence_with_thunderstorm_high_fires_risk(self):
        """confidence_min=25 + ThunderLevel.HIGH → both THUNDERSTORM HIGH and LOW_CONFIDENCE."""
        from app.models import RiskLevel, RiskType, ThunderLevel
        from services.risk_engine import RiskEngine

        seg = self._make_segment(
            confidence_pct_min=25,
            thunder_level_max=ThunderLevel.HIGH,
        )
        engine = RiskEngine()
        assessment = engine.assess_segment(seg)

        risk_types = [r.type for r in assessment.risks]
        assert RiskType.THUNDERSTORM in risk_types
        assert RiskType.LOW_CONFIDENCE in risk_types

        low_conf = next(r for r in assessment.risks if r.type == RiskType.LOW_CONFIDENCE)
        assert low_conf.level == RiskLevel.MODERATE

    def test_low_confidence_without_high_event_does_not_fire(self):
        """confidence_min=25 but no HIGH-level event → no LOW_CONFIDENCE risk."""
        from app.models import RiskType, ThunderLevel
        from services.risk_engine import RiskEngine

        seg = self._make_segment(
            confidence_pct_min=25,
            thunder_level_max=ThunderLevel.NONE,
            wind_max_kmh=15,
            gust_max_kmh=20,
        )
        engine = RiskEngine()
        assessment = engine.assess_segment(seg)

        risk_types = [r.type for r in assessment.risks]
        assert RiskType.LOW_CONFIDENCE not in risk_types

    def test_high_confidence_with_thunderstorm_high_does_not_fire_low_conf(self):
        """confidence_min=80 with HIGH event → THUNDERSTORM yes, LOW_CONFIDENCE no."""
        from app.models import RiskType, ThunderLevel
        from services.risk_engine import RiskEngine

        seg = self._make_segment(
            confidence_pct_min=80,
            thunder_level_max=ThunderLevel.HIGH,
        )
        engine = RiskEngine()
        assessment = engine.assess_segment(seg)

        risk_types = [r.type for r in assessment.risks]
        assert RiskType.THUNDERSTORM in risk_types
        assert RiskType.LOW_CONFIDENCE not in risk_types

    def test_none_confidence_does_not_fire_risk(self):
        """confidence_pct_min=None (no ensemble data) → no LOW_CONFIDENCE risk."""
        from app.models import RiskType, ThunderLevel
        from services.risk_engine import RiskEngine

        seg = self._make_segment(
            confidence_pct_min=None,
            thunder_level_max=ThunderLevel.HIGH,
        )
        engine = RiskEngine()
        assessment = engine.assess_segment(seg)

        risk_types = [r.type for r in assessment.risks]
        assert RiskType.LOW_CONFIDENCE not in risk_types

    def test_risktype_enum_has_low_confidence(self):
        """RiskType enum must include LOW_CONFIDENCE."""
        from app.models import RiskType

        assert hasattr(RiskType, "LOW_CONFIDENCE")
        assert RiskType.LOW_CONFIDENCE.value == "low_confidence"
