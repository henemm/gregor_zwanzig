"""
Unit tests for WeatherMetricsService (Feature 2.2a).

Tests compute_basis_metrics() with synthetic data.
NO MOCKS - uses real DTO structures with known values.
"""
from datetime import datetime, timezone

import pytest

from app.models import (
    ForecastDataPoint,
    ForecastMeta,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherSummary,
    ThunderLevel,
)
from services.weather_metrics import WeatherMetricsService


class TestWeatherMetricsServiceKnownValues:
    """Test metrics computation with known synthetic values."""

    @pytest.fixture
    def service(self):
        """WeatherMetricsService instance."""
        return WeatherMetricsService()

    @pytest.fixture
    def known_timeseries(self):
        """
        Synthetic timeseries with known values for exact validation.
        
        3 data points:
        - t2m_c: 10.0, 15.0, 20.0 → min=10, max=20, avg=15
        - wind10m_kmh: 10.0, 25.0, 15.0 → max=25
        - gust_kmh: 15.0, 35.0, 20.0 → max=35
        - precip_1h_mm: 1.0, 2.0, 0.5 → sum=3.5
        - cloud_total_pct: 45, 50, 55 → avg=50
        - humidity_pct: 60, 70, 80 → avg=70
        - thunder_level: NONE, MED, NONE → max=MED
        - visibility_m: 5000, 3000, 4000 → min=3000
        """
        meta = ForecastMeta(
            provider=Provider.GEOSPHERE,
            model="test",
            run=datetime.now(timezone.utc),
            grid_res_km=1.0,
            interp="test",
        )

        data = [
            ForecastDataPoint(
                ts=datetime(2026, 2, 1, 10, 0, tzinfo=timezone.utc),
                t2m_c=10.0,
                wind10m_kmh=10.0,
                gust_kmh=15.0,
                precip_1h_mm=1.0,
                cloud_total_pct=45,
                humidity_pct=60,
                thunder_level=ThunderLevel.NONE,
                visibility_m=5000,
            ),
            ForecastDataPoint(
                ts=datetime(2026, 2, 1, 11, 0, tzinfo=timezone.utc),
                t2m_c=15.0,
                wind10m_kmh=25.0,
                gust_kmh=35.0,
                precip_1h_mm=2.0,
                cloud_total_pct=50,
                humidity_pct=70,
                thunder_level=ThunderLevel.MED,
                visibility_m=3000,
            ),
            ForecastDataPoint(
                ts=datetime(2026, 2, 1, 12, 0, tzinfo=timezone.utc),
                t2m_c=20.0,
                wind10m_kmh=15.0,
                gust_kmh=20.0,
                precip_1h_mm=0.5,
                cloud_total_pct=55,
                humidity_pct=80,
                thunder_level=ThunderLevel.NONE,
                visibility_m=4000,
            ),
        ]

        return NormalizedTimeseries(meta=meta, data=data)

    def test_compute_basis_metrics_known_values(self, service, known_timeseries):
        """
        GIVEN: Timeseries with known values
        WHEN: compute_basis_metrics(timeseries)
        THEN: All 8 metrics match expected calculations
        """
        result = service.compute_basis_metrics(known_timeseries)

        # Temperature
        assert result.temp_min_c == 10.0
        assert result.temp_max_c == 20.0
        assert result.temp_avg_c == 15.0

        # Wind
        assert result.wind_max_kmh == 25.0

        # Gust
        assert result.gust_max_kmh == 35.0

        # Precipitation (SUM, not AVG!)
        assert result.precip_sum_mm == 3.5

        # Cloud Cover (AVG, rounded to int)
        assert result.cloud_avg_pct == 50

        # Humidity (AVG, rounded to int)
        assert result.humidity_avg_pct == 70

        # Thunder (MAX: NONE < MED < HIGH)
        assert result.thunder_level_max == ThunderLevel.MED

        # Visibility (MIN)
        assert result.visibility_min_m == 3000

    def test_aggregation_config_populated(self, service, known_timeseries):
        """
        GIVEN: Timeseries
        WHEN: compute_basis_metrics(timeseries)
        THEN: aggregation_config has 10 entries with correct functions
        """
        result = service.compute_basis_metrics(known_timeseries)

        assert len(result.aggregation_config) == 10
        assert result.aggregation_config["temp_min_c"] == "min"
        assert result.aggregation_config["temp_max_c"] == "max"
        assert result.aggregation_config["temp_avg_c"] == "avg"
        assert result.aggregation_config["wind_max_kmh"] == "max"
        assert result.aggregation_config["gust_max_kmh"] == "max"
        assert result.aggregation_config["precip_sum_mm"] == "sum"
        assert result.aggregation_config["cloud_avg_pct"] == "avg"
        assert result.aggregation_config["humidity_avg_pct"] == "avg"
        assert result.aggregation_config["thunder_level_max"] == "max"
        assert result.aggregation_config["visibility_min_m"] == "min"


class TestWeatherMetricsServiceTemperature:
    """Test temperature-specific calculations."""

    @pytest.fixture
    def service(self):
        return WeatherMetricsService()

    def test_temperature_min_max_avg(self, service):
        """
        GIVEN: Timeseries with varying temperatures
        WHEN: compute_basis_metrics(timeseries)
        THEN: MIN/MAX/AVG calculated correctly
        """
        meta = ForecastMeta(
            provider=Provider.GEOSPHERE,
            model="test",
            run=datetime.now(timezone.utc),
            grid_res_km=1.0,
            interp="test",
        )

        data = [
            ForecastDataPoint(
                ts=datetime(2026, 2, 1, 10, 0, tzinfo=timezone.utc), t2m_c=-5.0
            ),
            ForecastDataPoint(
                ts=datetime(2026, 2, 1, 11, 0, tzinfo=timezone.utc), t2m_c=0.0
            ),
            ForecastDataPoint(
                ts=datetime(2026, 2, 1, 12, 0, tzinfo=timezone.utc), t2m_c=5.0
            ),
            ForecastDataPoint(
                ts=datetime(2026, 2, 1, 13, 0, tzinfo=timezone.utc), t2m_c=10.0
            ),
        ]

        timeseries = NormalizedTimeseries(meta=meta, data=data)
        result = service.compute_basis_metrics(timeseries)

        assert result.temp_min_c == -5.0
        assert result.temp_max_c == 10.0
        assert result.temp_avg_c == 2.5  # (-5 + 0 + 5 + 10) / 4


class TestWeatherMetricsServicePrecipitation:
    """Test precipitation SUM (not AVG)."""

    @pytest.fixture
    def service(self):
        return WeatherMetricsService()

    def test_precipitation_sum_not_avg(self, service):
        """
        GIVEN: Timeseries with hourly precipitation
        WHEN: compute_basis_metrics(timeseries)
        THEN: precip_sum_mm is SUM of all values, not AVG
        """
        meta = ForecastMeta(
            provider=Provider.GEOSPHERE,
            model="test",
            run=datetime.now(timezone.utc),
            grid_res_km=1.0,
            interp="test",
        )

        data = [
            ForecastDataPoint(
                ts=datetime(2026, 2, 1, 10, 0, tzinfo=timezone.utc), precip_1h_mm=2.5
            ),
            ForecastDataPoint(
                ts=datetime(2026, 2, 1, 11, 0, tzinfo=timezone.utc), precip_1h_mm=3.0
            ),
            ForecastDataPoint(
                ts=datetime(2026, 2, 1, 12, 0, tzinfo=timezone.utc), precip_1h_mm=1.5
            ),
            ForecastDataPoint(
                ts=datetime(2026, 2, 1, 13, 0, tzinfo=timezone.utc), precip_1h_mm=0.0
            ),
            ForecastDataPoint(
                ts=datetime(2026, 2, 1, 14, 0, tzinfo=timezone.utc), precip_1h_mm=4.0
            ),
        ]

        timeseries = NormalizedTimeseries(meta=meta, data=data)
        result = service.compute_basis_metrics(timeseries)

        # SUM, not AVG!
        assert result.precip_sum_mm == 11.0  # 2.5 + 3.0 + 1.5 + 0.0 + 4.0


class TestWeatherMetricsServiceThunderLevel:
    """Test thunder level MAX ordering."""

    @pytest.fixture
    def service(self):
        return WeatherMetricsService()

    def test_thunder_level_ordering_high(self, service):
        """
        GIVEN: Timeseries with mixed thunder levels including HIGH
        WHEN: compute_basis_metrics(timeseries)
        THEN: thunder_level_max = HIGH
        """
        meta = ForecastMeta(
            provider=Provider.GEOSPHERE,
            model="test",
            run=datetime.now(timezone.utc),
            grid_res_km=1.0,
            interp="test",
        )

        data = [
            ForecastDataPoint(
                ts=datetime(2026, 2, 1, 10, 0, tzinfo=timezone.utc),
                thunder_level=ThunderLevel.NONE,
            ),
            ForecastDataPoint(
                ts=datetime(2026, 2, 1, 11, 0, tzinfo=timezone.utc),
                thunder_level=ThunderLevel.MED,
            ),
            ForecastDataPoint(
                ts=datetime(2026, 2, 1, 12, 0, tzinfo=timezone.utc),
                thunder_level=ThunderLevel.NONE,
            ),
            ForecastDataPoint(
                ts=datetime(2026, 2, 1, 13, 0, tzinfo=timezone.utc),
                thunder_level=ThunderLevel.HIGH,
            ),
            ForecastDataPoint(
                ts=datetime(2026, 2, 1, 14, 0, tzinfo=timezone.utc),
                thunder_level=ThunderLevel.MED,
            ),
        ]

        timeseries = NormalizedTimeseries(meta=meta, data=data)
        result = service.compute_basis_metrics(timeseries)

        assert result.thunder_level_max == ThunderLevel.HIGH

    def test_thunder_level_ordering_med(self, service):
        """
        GIVEN: Timeseries with NONE and MED (no HIGH)
        WHEN: compute_basis_metrics(timeseries)
        THEN: thunder_level_max = MED
        """
        meta = ForecastMeta(
            provider=Provider.GEOSPHERE,
            model="test",
            run=datetime.now(timezone.utc),
            grid_res_km=1.0,
            interp="test",
        )

        data = [
            ForecastDataPoint(
                ts=datetime(2026, 2, 1, 10, 0, tzinfo=timezone.utc),
                thunder_level=ThunderLevel.NONE,
            ),
            ForecastDataPoint(
                ts=datetime(2026, 2, 1, 11, 0, tzinfo=timezone.utc),
                thunder_level=ThunderLevel.MED,
            ),
            ForecastDataPoint(
                ts=datetime(2026, 2, 1, 12, 0, tzinfo=timezone.utc),
                thunder_level=ThunderLevel.NONE,
            ),
        ]

        timeseries = NormalizedTimeseries(meta=meta, data=data)
        result = service.compute_basis_metrics(timeseries)

        assert result.thunder_level_max == ThunderLevel.MED


class TestWeatherMetricsServiceSparseData:
    """Test handling of sparse data with None values."""

    @pytest.fixture
    def service(self):
        return WeatherMetricsService()

    def test_sparse_data_with_none_values(self, service):
        """
        GIVEN: Timeseries with 50% None values for temperature
        WHEN: compute_basis_metrics(timeseries)
        THEN: Metrics computed from available values only
        """
        meta = ForecastMeta(
            provider=Provider.GEOSPHERE,
            model="test",
            run=datetime.now(timezone.utc),
            grid_res_km=1.0,
            interp="test",
        )

        data = [
            ForecastDataPoint(
                ts=datetime(2026, 2, 1, 10, 0, tzinfo=timezone.utc), t2m_c=10.0
            ),
            ForecastDataPoint(
                ts=datetime(2026, 2, 1, 11, 0, tzinfo=timezone.utc), t2m_c=None
            ),
            ForecastDataPoint(
                ts=datetime(2026, 2, 1, 12, 0, tzinfo=timezone.utc), t2m_c=20.0
            ),
            ForecastDataPoint(
                ts=datetime(2026, 2, 1, 13, 0, tzinfo=timezone.utc), t2m_c=None
            ),
        ]

        timeseries = NormalizedTimeseries(meta=meta, data=data)
        result = service.compute_basis_metrics(timeseries)

        # Computed from 10.0 and 20.0 only (ignore None)
        assert result.temp_min_c == 10.0
        assert result.temp_max_c == 20.0
        assert result.temp_avg_c == 15.0

    def test_all_none_values_for_metric(self, service):
        """
        GIVEN: Timeseries where all t2m_c are None
        WHEN: compute_basis_metrics(timeseries)
        THEN: temp_min/max/avg all None, no error
        """
        meta = ForecastMeta(
            provider=Provider.GEOSPHERE,
            model="test",
            run=datetime.now(timezone.utc),
            grid_res_km=1.0,
            interp="test",
        )

        data = [
            ForecastDataPoint(
                ts=datetime(2026, 2, 1, 10, 0, tzinfo=timezone.utc),
                t2m_c=None,
                wind10m_kmh=10.0,
            ),
            ForecastDataPoint(
                ts=datetime(2026, 2, 1, 11, 0, tzinfo=timezone.utc),
                t2m_c=None,
                wind10m_kmh=15.0,
            ),
        ]

        timeseries = NormalizedTimeseries(meta=meta, data=data)
        result = service.compute_basis_metrics(timeseries)

        # Temperature all None
        assert result.temp_min_c is None
        assert result.temp_max_c is None
        assert result.temp_avg_c is None

        # But wind still computed
        assert result.wind_max_kmh == 15.0


class TestWeatherMetricsServiceEdgeCases:
    """Test edge cases and error handling."""

    @pytest.fixture
    def service(self):
        return WeatherMetricsService()

    def test_empty_timeseries_raises_error(self, service):
        """
        GIVEN: Timeseries with empty data list
        WHEN: compute_basis_metrics(timeseries)
        THEN: ValueError raised
        """
        meta = ForecastMeta(
            provider=Provider.GEOSPHERE,
            model="test",
            run=datetime.now(timezone.utc),
            grid_res_km=1.0,
            interp="test",
        )

        timeseries = NormalizedTimeseries(meta=meta, data=[])

        with pytest.raises(ValueError) as exc_info:
            service.compute_basis_metrics(timeseries)

        assert "empty" in str(exc_info.value).lower()

    def test_percentage_rounding(self, service):
        """
        GIVEN: Timeseries with cloud_total_pct values that average to non-integer
        WHEN: compute_basis_metrics(timeseries)
        THEN: cloud_avg_pct is rounded to int
        """
        meta = ForecastMeta(
            provider=Provider.GEOSPHERE,
            model="test",
            run=datetime.now(timezone.utc),
            grid_res_km=1.0,
            interp="test",
        )

        data = [
            ForecastDataPoint(
                ts=datetime(2026, 2, 1, 10, 0, tzinfo=timezone.utc), cloud_total_pct=45
            ),
            ForecastDataPoint(
                ts=datetime(2026, 2, 1, 11, 0, tzinfo=timezone.utc), cloud_total_pct=50
            ),
            ForecastDataPoint(
                ts=datetime(2026, 2, 1, 12, 0, tzinfo=timezone.utc), cloud_total_pct=56
            ),
        ]

        timeseries = NormalizedTimeseries(meta=meta, data=data)
        result = service.compute_basis_metrics(timeseries)

        # (45 + 50 + 56) / 3 = 50.333... → rounds to 50
        assert isinstance(result.cloud_avg_pct, int)
        assert result.cloud_avg_pct == 50
