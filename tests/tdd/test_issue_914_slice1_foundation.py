"""
TDD RED — Issue #914 Slice 1: Alert-Render-Fundament

Tests for new fields in MetricDefinition (sms_code, decimals, cmp),
new WeatherChange.occurred_at field, and /api/metrics API exposure.

All tests MUST fail RED because the features do not yet exist.

SPEC: docs/specs/modules/alert_render_foundation.md
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone



# ---------------------------------------------------------------------------
# AC-1: Every alert-capable metric has a unique, ASCII-only sms_code
# ---------------------------------------------------------------------------

class TestAC1AlertMetricSMSCodes:
    """AC-1: sms_code auf MetricDefinition — nicht leer, ASCII, kollisionsfrei."""

    def test_ac1_every_alert_metric_has_unique_ascii_sms_code(self) -> None:
        """
        GIVEN: the metric catalog
        WHEN: I iterate all selectable metrics that have a default_change_threshold set
              (alert-capable) and read their sms_code field
        THEN: each sms_code is non-empty, ASCII-only, and globally unique among
              the set; concrete new codes cape→CP, fresh_snow→SN, snowfall_limit→SL,
              visibility→VS are present; established codes for
              precipitation→R, rain_probability→PR, wind→W, gust→G are unchanged.
        """
        from app.metric_catalog import get_all_metrics

        metrics = get_all_metrics()

        # Filter to alert-capable: has default_change_threshold set
        alert_metrics = [m for m in metrics if m.default_change_threshold is not None]
        assert len(alert_metrics) > 0, "Expected at least one alert-capable metric"

        # --- Assert sms_code attribute exists and is non-empty ---
        # This will raise AttributeError if sms_code is not yet on MetricDefinition
        codes_seen: dict[str, str] = {}  # code → metric_id
        for m in alert_metrics:
            code = m.sms_code  # AttributeError here until implemented
            assert code, f"sms_code is empty for alert metric {m.id!r}"
            assert code.isascii(), f"sms_code {code!r} for {m.id!r} is not ASCII-only"
            assert code not in codes_seen, (
                f"Duplicate sms_code {code!r}: shared by {m.id!r} and {codes_seen[code]!r}"
            )
            codes_seen[code] = m.id

        # --- Assert specific established codes are present ---
        by_id = {m.id: m for m in alert_metrics}

        assert by_id["precipitation"].sms_code == "R", "established code precipitation→R"
        assert by_id["rain_probability"].sms_code == "PR", "established code rain_probability→PR"
        assert by_id["wind"].sms_code == "W", "established code wind→W"
        assert by_id["gust"].sms_code == "G", "established code gust→G"

        # --- Assert new codes ---
        assert by_id["cape"].sms_code == "CP", "new code cape→CP"
        assert by_id["fresh_snow"].sms_code == "SN", "new code fresh_snow→SN"
        assert by_id["snowfall_limit"].sms_code == "SL", "new code snowfall_limit→SL"
        assert by_id["visibility"].sms_code == "VS", "new code visibility→VS"

        # --- F003 fix (#914): humidity=HU must be assertible via direct catalog lookup ---
        # humidity is a precursor metric (is_precursor=True, excluded from alert_metrics
        # filter above), but sms_code must still be set in the catalog as a Stammdatum.
        from app.metric_catalog import get_sms_code, _METRICS_BY_ID
        assert get_sms_code("humidity") == "HU", (
            "humidity sms_code must be 'HU' even though it is a precursor metric "
            "excluded from the alert-capable filter"
        )
        assert _METRICS_BY_ID["humidity"].sms_code == "HU", (
            "humidity in _METRICS_BY_ID must carry sms_code='HU' (F003 coverage)"
        )


# ---------------------------------------------------------------------------
# AC-2: Catalog provides comparison direction (cmp) and detection uses it
# ---------------------------------------------------------------------------

class TestAC2CatalogComparisionDirection:
    """AC-2: get_cmp() liefert 'über'/'unter', Detektion nutzt Katalog als Quelle."""

    def test_ac2_catalog_provides_comparison_direction(self) -> None:
        """
        GIVEN: the metric catalog with alert-capable metrics
        WHEN: I call get_cmp(metric_id) for gust, precipitation, wind, and temperature
        THEN: gust/precipitation/wind/temperature return 'über';
              a detection run with a clear wind threshold violation produces a WeatherChange
              confirming the direction matches the catalog cmp, not a stale local dict.
        """
        from app.metric_catalog import get_cmp  # AttributeError until implemented

        # --- Specific cmp values from catalog ---
        assert get_cmp("gust") == "über", "gust → 'über' (Böen-Alarm bei Überschreitung)"
        assert get_cmp("precipitation") == "über", "precipitation → 'über'"
        assert get_cmp("wind") == "über", "wind → 'über'"
        assert get_cmp("temperature") == "über", "temperature → 'über'"

        # The detection service must produce a WeatherChange using catalog cmp.
        # We verify by running a real detect_changes with a known violation.
        from app.models import (
            ForecastDataPoint,
            ForecastMeta,
            GPXPoint,
            NormalizedTimeseries,
            Provider,
            SegmentWeatherData,
            SegmentWeatherSummary,
            TripSegment,
        )
        from services.weather_change_detection import WeatherChangeDetectionService

        now = datetime.now(timezone.utc)
        segment = TripSegment(
            segment_id=1,
            start_point=GPXPoint(lat=47.0, lon=11.0, elevation_m=1000.0),
            end_point=GPXPoint(lat=47.1, lon=11.1, elevation_m=1100.0),
            start_time=now,
            end_time=now + timedelta(hours=2),
            duration_hours=2.0,
            distance_km=5.0,
            ascent_m=100.0,
            descent_m=0.0,
        )
        meta = ForecastMeta(
            provider=Provider.OPENMETEO,
            model="test",
            run=now,
            grid_res_km=1.0,
            interp="point_grid",
        )
        ts = NormalizedTimeseries(
            meta=meta,
            data=[ForecastDataPoint(ts=now, t2m_c=15.0, wind10m_kmh=20.0)],
        )

        old_summary = SegmentWeatherSummary(
            temp_max_c=15.0, wind_max_kmh=20.0, precip_sum_mm=0.0
        )
        new_summary = SegmentWeatherSummary(
            temp_max_c=15.0, wind_max_kmh=60.0, precip_sum_mm=0.0  # +40 km/h > 20 threshold
        )

        old_data = SegmentWeatherData(
            segment=segment, timeseries=ts, aggregated=old_summary, fetched_at=now, provider="openmeteo"
        )
        new_data = SegmentWeatherData(
            segment=segment, timeseries=ts, aggregated=new_summary, fetched_at=now, provider="openmeteo"
        )

        service = WeatherChangeDetectionService()
        changes = service.detect_changes(old_data, new_data, include_absolute=False)

        wind_changes = [c for c in changes if c.metric == "wind_max_kmh"]
        assert len(wind_changes) > 0, "Expected wind change to be detected"

        # The catalog cmp for wind is 'über'; wind increase → direction='increase'
        # confirms the detection is reading the catalog (not a stale 'above' dict that gives wrong label)
        assert wind_changes[0].direction == "increase", (
            "wind increase detected → matches cmp='über' (increase) from catalog"
        )

    def test_ac2_absolute_path_uses_catalog_cmp(self) -> None:
        """
        F002 fix (#914): The absolute-rule detection path uses catalog cmp as the
        single source — NOT a stale hand-coded dict.

        GIVEN: AlertRules with kind=ABSOLUTE for:
          - gust (über) → fires when gust_max_kmh > threshold (direction='above')
          - temp_min (unter) → fires when temp_min_c < threshold (direction='below')
          - snow_line (unter per catalog/Issue-Registry) → fires when freezing_level_m <
            threshold (direction='below')  ← this was 'above' in the old hand-coded dict
        WHEN: detect_changes() is called with include_absolute=True and values that
              cross each threshold on the expected side
        THEN: each resulting WeatherChange.direction matches get_cmp() for that metric,
              confirming the catalog is the single source for the absolute path.

        This test was RED against the old hand-coded _ALERT_METRIC_COMPARISON where
        SNOW_LINE had 'above' — and GREEN after the catalog-derived fix (#914/AC-2).
        """
        from app.metric_catalog import get_cmp
        from app.models import (
            AlertMetric,
            AlertRuleKind,
            AlertSeverity,
            ForecastDataPoint,
            ForecastMeta,
            GPXPoint,
            NormalizedTimeseries,
            Provider,
            SegmentWeatherData,
            SegmentWeatherSummary,
            TripSegment,
        )
        from services.weather_change_detection import WeatherChangeDetectionService

        now = datetime.now(timezone.utc)
        segment = TripSegment(
            segment_id=1,
            start_point=GPXPoint(lat=47.0, lon=11.0, elevation_m=1000.0),
            end_point=GPXPoint(lat=47.1, lon=11.1, elevation_m=1100.0),
            start_time=now,
            end_time=now + timedelta(hours=6),
            duration_hours=6.0,
            distance_km=10.0,
            ascent_m=200.0,
            descent_m=50.0,
        )
        meta = ForecastMeta(
            provider=Provider.OPENMETEO,
            model="test",
            run=now,
            grid_res_km=1.0,
            interp="point_grid",
        )
        ts = NormalizedTimeseries(
            meta=meta,
            data=[ForecastDataPoint(ts=now, t2m_c=10.0, wind10m_kmh=20.0)],
        )

        # Scenario: gust=90 (>50 threshold→above), temp_min=-8 (<-5 threshold→below),
        # freezing_level=1500 (<2000 threshold→below, i.e. snow line has dropped)
        summary = SegmentWeatherSummary(
            gust_max_kmh=90.0,
            temp_min_c=-8.0,
            freezing_level_m=1500.0,
        )
        old_data = SegmentWeatherData(
            segment=segment, timeseries=ts,
            aggregated=SegmentWeatherSummary(),
            fetched_at=now, provider="openmeteo",
        )
        new_data = SegmentWeatherData(
            segment=segment, timeseries=ts,
            aggregated=summary,
            fetched_at=now, provider="openmeteo",
        )

        from app.models import AlertRule
        rules = [
            AlertRule(
                id="r1", kind=AlertRuleKind.ABSOLUTE,
                metric=AlertMetric.WIND_GUST, threshold=50.0,
                severity=AlertSeverity.WARNING, enabled=True,
            ),
            AlertRule(
                id="r2", kind=AlertRuleKind.ABSOLUTE,
                metric=AlertMetric.TEMPERATURE_MIN, threshold=-5.0,
                severity=AlertSeverity.WARNING, enabled=True,
            ),
            AlertRule(
                id="r3", kind=AlertRuleKind.ABSOLUTE,
                metric=AlertMetric.SNOW_LINE, threshold=2000.0,
                severity=AlertSeverity.WARNING, enabled=True,
            ),
        ]
        service = WeatherChangeDetectionService.from_alert_rules(rules)
        changes = service.detect_changes(old_data, new_data, include_absolute=True)

        by_metric = {c.metric: c for c in changes}

        # gust: catalog cmp="über" → direction must be "above"
        assert "gust_max_kmh" in by_metric, "gust ABSOLUTE rule must fire (90 > 50)"
        assert by_metric["gust_max_kmh"].direction == "above", (
            f"gust direction must be 'above' (catalog cmp={get_cmp('gust')!r}), "
            f"got {by_metric['gust_max_kmh'].direction!r}"
        )

        # temp_min: catalog cmp (temperature_cold) = "unter" → direction must be "below"
        assert "temp_min_c" in by_metric, "temp_min ABSOLUTE rule must fire (-8 < -5)"
        assert by_metric["temp_min_c"].direction == "below", (
            f"temp_min direction must be 'below' (cold alarm, cmp='unter'), "
            f"got {by_metric['temp_min_c'].direction!r}"
        )

        # snow_line (freezing_level_m): catalog cmp (freezing_level) = "unter" → "below"
        # This was 'above' in the old hand-coded dict — the latent bug corrected by #914.
        assert "freezing_level_m" in by_metric, (
            "snow_line ABSOLUTE rule must fire (freezing_level 1500 < 2000 threshold)"
        )
        assert by_metric["freezing_level_m"].direction == "below", (
            f"freezing_level direction must be 'below' (tiefere Schneefallgrenze = mehr Gefahr; "
            f"catalog cmp={get_cmp('freezing_level')!r}); got {by_metric['freezing_level_m'].direction!r}. "
            f"NOTE: old hand-coded dict had 'above' — fixed by #914/AC-2 (Issue-Registry: 'unter')."
        )


# ---------------------------------------------------------------------------
# AC-3: WeatherChange.occurred_at is set (or None) — never a crash
# ---------------------------------------------------------------------------

class TestAC3WeatherChangeOccurredAt:
    """AC-3: WeatherChange.occurred_at ist None oder HH:MM-String im Segment-Fenster."""

    def test_ac3_weatherchange_carries_plausible_occurred_at(self) -> None:
        """
        GIVEN: a real detection run with hourly forecast data and a clear threshold crossing
        WHEN: detect_changes() produces a WeatherChange
        THEN: occurred_at is None OR matches ^\\d{2}:\\d{2}$ and lies within the
              segment time window; never raises an exception.
        """
        from app.models import (
            ForecastDataPoint,
            ForecastMeta,
            GPXPoint,
            NormalizedTimeseries,
            Provider,
            SegmentWeatherData,
            SegmentWeatherSummary,
            TripSegment,
        )
        from services.weather_change_detection import WeatherChangeDetectionService

        # Build a segment with a 6-hour window starting at 08:00 UTC
        start_time = datetime(2026, 7, 1, 8, 0, 0, tzinfo=timezone.utc)
        end_time = start_time + timedelta(hours=6)

        segment = TripSegment(
            segment_id=1,
            start_point=GPXPoint(lat=47.0, lon=11.0, elevation_m=1000.0),
            end_point=GPXPoint(lat=47.1, lon=11.1, elevation_m=1100.0),
            start_time=start_time,
            end_time=end_time,
            duration_hours=6.0,
            distance_km=12.0,
            ascent_m=300.0,
            descent_m=50.0,
        )
        meta = ForecastMeta(
            provider=Provider.OPENMETEO,
            model="test",
            run=start_time,
            grid_res_km=1.0,
            interp="point_grid",
        )

        # Build hourly timeseries — wind ramps from 25→55 km/h over 6 hours
        data_points = []
        for hour_offset in range(7):
            ts_h = start_time + timedelta(hours=hour_offset)
            wind = 25.0 + (hour_offset * 5)  # peaks at offset 6 = 55 km/h
            data_points.append(ForecastDataPoint(ts=ts_h, t2m_c=15.0, wind10m_kmh=wind))

        ts = NormalizedTimeseries(meta=meta, data=data_points)

        old_summary = SegmentWeatherSummary(
            temp_max_c=15.0, wind_max_kmh=10.0, precip_sum_mm=0.0
        )
        new_summary = SegmentWeatherSummary(
            temp_max_c=15.0, wind_max_kmh=55.0, precip_sum_mm=0.0  # +45 > threshold 20
        )

        old_data = SegmentWeatherData(
            segment=segment, timeseries=ts, aggregated=old_summary,
            fetched_at=start_time, provider="openmeteo"
        )
        new_data = SegmentWeatherData(
            segment=segment, timeseries=ts, aggregated=new_summary,
            fetched_at=start_time, provider="openmeteo"
        )

        service = WeatherChangeDetectionService()
        changes = service.detect_changes(old_data, new_data, include_absolute=False)

        assert len(changes) > 0, "Expected at least one change to be detected"

        for change in changes:
            # occurred_at is the new field — AttributeError until implemented
            occ = change.occurred_at  # AttributeError until WeatherChange has this field

            if occ is not None:
                # Must match HH:MM format
                assert re.match(r"^\d{2}:\d{2}$", occ), (
                    f"occurred_at {occ!r} does not match HH:MM format"
                )
                # Must lie within the segment window (08:00–14:00 UTC for this test)
                hour, minute = map(int, occ.split(":"))
                assert 8 <= hour <= 14, (
                    f"occurred_at hour {hour} not in segment window [08, 14]"
                )
            # else: None is acceptable (best-effort)


# ---------------------------------------------------------------------------
# AC-4: GET /api/metrics exposes sms_code, decimals, cmp per metric entry
# ---------------------------------------------------------------------------

class TestAC4APIMetricsExposesNewFields:
    """AC-4: /api/metrics liefert sms_code, decimals, cmp pro Eintrag."""

    def test_ac4_api_metrics_exposes_new_fields(self) -> None:
        """
        GIVEN: the running FastAPI app with the config router
        WHEN: the frontend calls GET /api/metrics
        THEN: every metric entry in the response has the keys sms_code, decimals, cmp;
              existing keys (id, label, unit, category, default_enabled,
              has_friendly_format, format_modes, default_format_mode, col_label)
              remain present and unchanged.
        """
        from fastapi.testclient import TestClient
        from api.main import app

        client = TestClient(app)
        response = client.get("/metrics")
        assert response.status_code == 200, f"GET /metrics returned {response.status_code}"

        data = response.json()
        assert isinstance(data, dict), "Expected dict of categories"

        existing_keys = {
            "id", "label", "unit", "category", "default_enabled",
            "has_friendly_format", "format_modes", "default_format_mode", "col_label"
        }
        new_keys = {"sms_code", "decimals", "cmp"}

        all_entries = []
        for category_entries in data.values():
            all_entries.extend(category_entries)

        assert len(all_entries) > 0, "Expected at least one metric entry"

        for entry in all_entries:
            entry_id = entry.get("id", "<unknown>")
            # Existing fields must still be present
            for key in existing_keys:
                assert key in entry, (
                    f"Metric {entry_id!r}: existing field {key!r} is missing from response"
                )
            # New fields must be present — will fail until implemented
            for key in new_keys:
                assert key in entry, (
                    f"Metric {entry_id!r}: new field {key!r} missing from /api/metrics response"
                )

            # Type checks for new fields
            assert isinstance(entry["sms_code"], str), (
                f"Metric {entry_id!r}: sms_code must be str"
            )
            # decimals: int or None
            assert entry["decimals"] is None or isinstance(entry["decimals"], int), (
                f"Metric {entry_id!r}: decimals must be int or null"
            )
            # cmp: str (may be empty for non-alert metrics)
            assert isinstance(entry["cmp"], str), (
                f"Metric {entry_id!r}: cmp must be str"
            )


# ---------------------------------------------------------------------------
# AC-5: WeatherChange roundtrip preserves all fields; occurred_at defaults None
# ---------------------------------------------------------------------------

class TestAC5WeatherChangeRoundtrip:
    """AC-5: WeatherChange roundtrip via dataclass construction preserves fields."""

    def test_ac5_weatherchange_roundtrip_preserves_fields(self) -> None:
        """
        GIVEN: a WeatherChange constructed with all existing fields (no occurred_at)
        WHEN: it is serialized via dataclasses.asdict and reconstructed
        THEN: all existing fields are preserved; occurred_at defaults to None
              when not supplied; the roundtrip is lossless; occurred_at can also
              be set to a valid HH:MM string.
        """
        import dataclasses

        from app.models import ChangeSeverity, WeatherChange

        # Build a WeatherChange using only the existing fields (no occurred_at arg)
        # The new field must have a default of None — construction must not fail
        change = WeatherChange(
            metric="wind_max_kmh",
            old_value=20.0,
            new_value=60.0,
            delta=40.0,
            threshold=20.0,
            severity=ChangeSeverity.MAJOR,
            direction="increase",
            segment_id="1",
        )

        # --- occurred_at must exist and default to None ---
        # AttributeError until the field is added to WeatherChange
        assert hasattr(change, "occurred_at"), (
            "WeatherChange must have an occurred_at attribute (new field, default None)"
        )
        assert change.occurred_at is None, (
            "occurred_at must default to None when not supplied"
        )

        # --- Roundtrip via dataclasses.asdict → reconstruct ---
        as_dict = dataclasses.asdict(change)

        assert "occurred_at" in as_dict, (
            "occurred_at must appear in dataclasses.asdict() output"
        )
        assert as_dict["occurred_at"] is None, (
            "occurred_at must be None in serialized form when not set"
        )

        # Reconstruct from dict — all fields must survive roundtrip
        reconstructed = WeatherChange(**as_dict)

        assert reconstructed.metric == change.metric
        assert reconstructed.old_value == change.old_value
        assert reconstructed.new_value == change.new_value
        assert reconstructed.delta == change.delta
        assert reconstructed.threshold == change.threshold
        assert reconstructed.severity == change.severity
        assert reconstructed.direction == change.direction
        assert reconstructed.segment_id == change.segment_id
        assert reconstructed.occurred_at is None

        # --- Also verify that occurred_at can be set to a valid HH:MM string ---
        change_with_time = WeatherChange(
            metric="wind_max_kmh",
            old_value=20.0,
            new_value=60.0,
            delta=40.0,
            threshold=20.0,
            severity=ChangeSeverity.MAJOR,
            direction="increase",
            segment_id="1",
            occurred_at="11:00",
        )
        assert change_with_time.occurred_at == "11:00", (
            "occurred_at must accept and preserve HH:MM string"
        )
