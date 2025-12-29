"""Tests for aggregation service."""
from datetime import datetime, timezone


from app.models import ForecastDataPoint, ForecastMeta, NormalizedTimeseries, Provider
from app.trip import AggregationConfig, AggregationFunc, Waypoint
from services.aggregation import AggregationService, WaypointForecast


class TestAggregationService:
    """Tests for AggregationService."""

    def _create_waypoint(self, name: str, elevation: int) -> Waypoint:
        """Create a test waypoint."""
        return Waypoint(
            id=f"G{elevation}",
            name=name,
            lat=47.0,
            lon=11.0,
            elevation_m=elevation,
        )

    def _create_forecast(
        self,
        temp: float,
        wind: float,
        gust: float = None,
        precip: float = 0,
        wind_chill: float = None,
    ) -> NormalizedTimeseries:
        """Create a simple forecast with one data point."""
        meta = ForecastMeta(
            provider=Provider.GEOSPHERE,
            model="TEST",
            run=datetime.now(timezone.utc),
            grid_res_km=1.0,
            interp="bilinear",
        )
        dp = ForecastDataPoint(
            ts=datetime.now(timezone.utc),
            t2m_c=temp,
            wind10m_kmh=wind,
            gust_kmh=gust or wind * 1.5,
            precip_1h_mm=precip,
            wind_chill_c=wind_chill,
        )
        return NormalizedTimeseries(meta=meta, data=[dp])

    def test_aggregate_empty(self):
        """Aggregating empty list returns empty summary."""
        config = AggregationConfig()
        service = AggregationService(config)
        summary = service.aggregate([])
        assert summary.temp_min.value is None
        assert summary.wind.value is None

    def test_aggregate_single_waypoint(self):
        """Aggregating single waypoint returns its values."""
        config = AggregationConfig()
        service = AggregationService(config)

        wp = self._create_waypoint("Gipfel", 3000)
        forecast = self._create_forecast(temp=-10.0, wind=40.0)
        wf = WaypointForecast(waypoint=wp, timeseries=forecast)

        summary = service.aggregate([wf])
        assert summary.temp_min.value == -10.0
        assert summary.temp_max.value == -10.0
        assert summary.wind.value == 40.0

    def test_aggregate_min_temperature(self):
        """MIN aggregation finds coldest temperature."""
        config = AggregationConfig()
        service = AggregationService(config)

        wp1 = self._create_waypoint("Tal", 1500)
        wp2 = self._create_waypoint("Gipfel", 3000)
        wf1 = WaypointForecast(waypoint=wp1, timeseries=self._create_forecast(temp=5.0, wind=10.0))
        wf2 = WaypointForecast(waypoint=wp2, timeseries=self._create_forecast(temp=-15.0, wind=50.0))

        summary = service.aggregate([wf1, wf2])
        assert summary.temp_min.value == -15.0
        assert summary.temp_min.source_waypoint == "Gipfel"

    def test_aggregate_max_temperature(self):
        """MAX aggregation finds warmest temperature."""
        config = AggregationConfig()
        service = AggregationService(config)

        wp1 = self._create_waypoint("Tal", 1500)
        wp2 = self._create_waypoint("Gipfel", 3000)
        wf1 = WaypointForecast(waypoint=wp1, timeseries=self._create_forecast(temp=5.0, wind=10.0))
        wf2 = WaypointForecast(waypoint=wp2, timeseries=self._create_forecast(temp=-15.0, wind=50.0))

        summary = service.aggregate([wf1, wf2])
        assert summary.temp_max.value == 5.0
        assert summary.temp_max.source_waypoint == "Tal"

    def test_aggregate_max_wind(self):
        """MAX aggregation finds strongest wind."""
        config = AggregationConfig()
        service = AggregationService(config)

        wp1 = self._create_waypoint("Tal", 1500)
        wp2 = self._create_waypoint("Gipfel", 3000)
        wf1 = WaypointForecast(waypoint=wp1, timeseries=self._create_forecast(temp=0.0, wind=10.0))
        wf2 = WaypointForecast(waypoint=wp2, timeseries=self._create_forecast(temp=0.0, wind=60.0))

        summary = service.aggregate([wf1, wf2])
        assert summary.wind.value == 60.0
        assert summary.wind.source_waypoint == "Gipfel"

    def test_aggregate_sum_precipitation(self):
        """SUM aggregation totals precipitation."""
        config = AggregationConfig()
        service = AggregationService(config)

        wp1 = self._create_waypoint("A", 2000)
        wp2 = self._create_waypoint("B", 2500)
        wf1 = WaypointForecast(waypoint=wp1, timeseries=self._create_forecast(temp=0.0, wind=10.0, precip=2.0))
        wf2 = WaypointForecast(waypoint=wp2, timeseries=self._create_forecast(temp=0.0, wind=10.0, precip=3.0))

        summary = service.aggregate([wf1, wf2])
        assert summary.precipitation.value == 5.0
        assert summary.precipitation.aggregation == AggregationFunc.SUM

    def test_aggregate_wind_chill(self):
        """MIN wind chill finds worst (coldest) value."""
        config = AggregationConfig()
        service = AggregationService(config)

        wp1 = self._create_waypoint("Tal", 1500)
        wp2 = self._create_waypoint("Gipfel", 3000)
        wf1 = WaypointForecast(waypoint=wp1, timeseries=self._create_forecast(temp=0.0, wind=10.0, wind_chill=-5.0))
        wf2 = WaypointForecast(waypoint=wp2, timeseries=self._create_forecast(temp=-10.0, wind=50.0, wind_chill=-25.0))

        summary = service.aggregate([wf1, wf2])
        assert summary.wind_chill.value == -25.0
        assert summary.wind_chill.source_waypoint == "Gipfel"

    def test_aggregate_with_custom_config(self):
        """Custom aggregation config is respected."""
        config = AggregationConfig()
        config.wind = AggregationFunc.AVG  # Use average instead of max

        service = AggregationService(config)

        wp1 = self._create_waypoint("A", 2000)
        wp2 = self._create_waypoint("B", 2500)
        wf1 = WaypointForecast(waypoint=wp1, timeseries=self._create_forecast(temp=0.0, wind=20.0))
        wf2 = WaypointForecast(waypoint=wp2, timeseries=self._create_forecast(temp=0.0, wind=40.0))

        summary = service.aggregate([wf1, wf2])
        assert summary.wind.value == 30.0  # Average of 20 and 40
        assert summary.wind.aggregation == AggregationFunc.AVG

    def test_aggregate_tracks_source(self):
        """Aggregated values track their source waypoint."""
        config = AggregationConfig()
        service = AggregationService(config)

        wp = self._create_waypoint("TestPoint", 2500)
        wf = WaypointForecast(waypoint=wp, timeseries=self._create_forecast(temp=-8.0, wind=30.0))

        summary = service.aggregate([wf])
        assert summary.temp_min.source_waypoint == "TestPoint"
        assert summary.wind.source_waypoint == "TestPoint"


class TestAggregatedValue:
    """Tests for AggregatedValue."""

    def test_aggregated_value_with_source(self):
        """AggregatedValue stores source metadata."""
        from services.aggregation import AggregatedValue

        ts = datetime.now(timezone.utc)
        val = AggregatedValue(
            value=-15.0,
            source_waypoint="Gipfel",
            source_time=ts,
            aggregation=AggregationFunc.MIN,
        )
        assert val.value == -15.0
        assert val.source_waypoint == "Gipfel"
        assert val.aggregation == AggregationFunc.MIN
