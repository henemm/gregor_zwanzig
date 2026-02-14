"""
Integration test: Manipulated Snapshot → Alert Pipeline.

ALERT-01: Weather Snapshot Service
Tests the full pipeline: Morning report saves snapshot → manipulate snapshot data →
alert check detects significant deviation → sends alert email.

Uses REAL API calls (OpenMeteo), real trips, and real SMTP (if configured).
NO MOCKS.

SPEC: docs/specs/modules/weather_snapshot.md v1.0
"""
from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from pathlib import Path

import pytest

from app.loader import get_snapshots_dir, load_all_trips
from app.models import ChangeSeverity

logger = logging.getLogger(__name__)


def _get_active_trip():
    """Find a trip with a stage on today's date and alert_on_changes=True."""
    today = date.today()
    for trip in load_all_trips():
        if not trip.report_config or not trip.report_config.alert_on_changes:
            continue
        stage = trip.get_stage_for_date(today)
        if stage is not None:
            return trip, today

    # Fallback: try tomorrow (evening reports use tomorrow)
    tomorrow = today + timedelta(days=1)
    for trip in load_all_trips():
        if not trip.report_config or not trip.report_config.alert_on_changes:
            continue
        stage = trip.get_stage_for_date(tomorrow)
        if stage is not None:
            return trip, tomorrow

    return None, None


class TestManipulatedSnapshotTriggersAlert:
    """
    Full pipeline test:
    1. Fetch real weather for a real trip (API call)
    2. Save as snapshot (simulates morning report)
    3. Manipulate snapshot (extreme weather values)
    4. Detect changes between manipulated cache and real fresh data
    5. Assert MODERATE/MAJOR changes detected
    6. Send alert email (if SMTP configured)
    """

    def test_manipulated_snapshot_detects_significant_changes(self) -> None:
        """
        GIVEN: Real weather snapshot for an active trip
        WHEN: Snapshot is manipulated (+20°C temp, +50 km/h wind)
              and compared against the real (fresh) weather data
        THEN: Change detection finds MODERATE or MAJOR changes
              for temp_max_c and wind_max_kmh
        """
        from services.trip_report_scheduler import TripReportSchedulerService
        from services.weather_change_detection import WeatherChangeDetectionService
        from services.weather_snapshot import WeatherSnapshotService

        # --- Step 1: Find active trip ---
        trip, target_date = _get_active_trip()
        if trip is None:
            pytest.skip("No active trip with stage on today/tomorrow — cannot test")

        logger.info(f"Testing with trip: {trip.name}, date: {target_date}")

        # --- Step 2: Fetch real weather (API call) ---
        scheduler = TripReportSchedulerService()
        segments = scheduler._convert_trip_to_segments(trip, target_date)
        assert len(segments) > 0, f"No segments for {trip.id} on {target_date}"

        fresh_weather = scheduler._fetch_weather(segments)
        assert len(fresh_weather) > 0, "API returned no weather data"

        logger.info(
            f"Fetched weather for {len(fresh_weather)} segments, "
            f"provider={fresh_weather[0].provider}"
        )

        # --- Step 3: Save snapshot (simulates morning report) ---
        snapshot_service = WeatherSnapshotService()
        snapshot_service.save(trip.id, fresh_weather, target_date)

        snapshot_path = get_snapshots_dir() / f"{trip.id}.json"
        assert snapshot_path.exists(), "Snapshot file was not created"

        # --- Step 4: Manipulate snapshot (extreme values) ---
        raw = json.loads(snapshot_path.read_text())

        for seg in raw["segments"]:
            agg = seg["aggregated"]
            # Add +20°C to temp_max_c (threshold 5°C → delta/threshold = 4x → MAJOR)
            if "temp_max_c" in agg:
                agg["temp_max_c"] = agg["temp_max_c"] + 20.0
            # Add +50 km/h to wind_max_kmh (threshold 20 km/h → delta/threshold = 2.5x → MAJOR)
            if "wind_max_kmh" in agg:
                agg["wind_max_kmh"] = agg["wind_max_kmh"] + 50.0

        snapshot_path.write_text(json.dumps(raw, indent=2))
        logger.info("Snapshot manipulated: temp +20°C, wind +50 km/h")

        # --- Step 5: Load manipulated data as "cached" ---
        cached_weather = snapshot_service.load(trip.id)
        assert cached_weather is not None, "Failed to load manipulated snapshot"
        assert len(cached_weather) == len(fresh_weather)

        # Verify manipulation was loaded correctly
        original_temp = fresh_weather[0].aggregated.temp_max_c
        cached_temp = cached_weather[0].aggregated.temp_max_c
        if original_temp is not None and cached_temp is not None:
            assert abs(cached_temp - original_temp - 20.0) < 0.01, (
                f"Manipulation not reflected: cached={cached_temp}, original={original_temp}"
            )

        # --- Step 6: Detect changes (manipulated vs real) ---
        detector = WeatherChangeDetectionService.from_trip_config(trip.report_config)

        all_changes = []
        for cached_seg, fresh_seg in zip(cached_weather, fresh_weather):
            changes = detector.detect_changes(cached_seg, fresh_seg)
            all_changes.extend(changes)

        logger.info(f"Detected {len(all_changes)} total changes")
        for change in all_changes:
            logger.info(
                f"  {change.metric}: {change.old_value:.1f} → {change.new_value:.1f} "
                f"(Δ{change.delta:+.1f}, severity={change.severity.value})"
            )

        # --- Step 7: Assert significant changes ---
        significant = [
            c for c in all_changes
            if c.severity in (ChangeSeverity.MODERATE, ChangeSeverity.MAJOR)
        ]
        assert len(significant) > 0, (
            f"Expected MODERATE/MAJOR changes from +20°C/+50 km/h manipulation, "
            f"but got only: {[c.severity.value for c in all_changes]}"
        )

        changed_metrics = {c.metric for c in significant}
        assert "temp_max_c" in changed_metrics, (
            f"temp_max_c not in significant changes: {changed_metrics}"
        )

        # Verify severity is MAJOR (delta = 20°C, threshold = 5°C → 4x → MAJOR)
        temp_change = next(c for c in significant if c.metric == "temp_max_c")
        assert temp_change.severity == ChangeSeverity.MAJOR, (
            f"Expected MAJOR for +20°C delta, got {temp_change.severity}"
        )
        assert abs(temp_change.delta) >= 15.0, (
            f"Expected delta >= 15°C, got {temp_change.delta}"
        )

        logger.info(
            f"SUCCESS: {len(significant)} significant changes detected "
            f"({', '.join(changed_metrics)})"
        )

    def test_manipulated_snapshot_sends_alert_email(self) -> None:
        """
        GIVEN: Manipulated snapshot with extreme deltas
        WHEN: check_and_send_alerts() is called with cached=manipulated, fresh=real
        THEN: Alert email is sent (returns True)

        Requires SMTP to be configured — skips if not available.
        """
        from app.config import Settings
        from services.trip_alert import TripAlertService
        from services.trip_report_scheduler import TripReportSchedulerService
        from services.weather_snapshot import WeatherSnapshotService

        settings = Settings()
        if not settings.can_send_email():
            pytest.skip("SMTP not configured — cannot send alert email")

        # --- Find active trip ---
        trip, target_date = _get_active_trip()
        if trip is None:
            pytest.skip("No active trip with stage on today/tomorrow")

        # --- Fetch real weather ---
        scheduler = TripReportSchedulerService()
        segments = scheduler._convert_trip_to_segments(trip, target_date)
        fresh_weather = scheduler._fetch_weather(segments)
        assert len(fresh_weather) > 0

        # --- Save + manipulate snapshot ---
        snapshot_service = WeatherSnapshotService()
        snapshot_service.save(trip.id, fresh_weather, target_date)

        snapshot_path = get_snapshots_dir() / f"{trip.id}.json"
        raw = json.loads(snapshot_path.read_text())
        for seg in raw["segments"]:
            agg = seg["aggregated"]
            if "temp_max_c" in agg:
                agg["temp_max_c"] = agg["temp_max_c"] + 20.0
            if "wind_max_kmh" in agg:
                agg["wind_max_kmh"] = agg["wind_max_kmh"] + 50.0
            if "precip_sum_mm" in agg:
                agg["precip_sum_mm"] = agg["precip_sum_mm"] + 25.0
        snapshot_path.write_text(json.dumps(raw, indent=2))

        # --- Load manipulated as cached ---
        cached_weather = snapshot_service.load(trip.id)
        assert cached_weather is not None

        # --- Send alert (real SMTP) ---
        alert_service = TripAlertService(settings=settings, throttle_hours=0)
        alert_service.clear_throttle(trip.id)

        sent = alert_service.check_and_send_alerts(
            trip=trip,
            cached_weather=cached_weather,
            fresh_weather=fresh_weather,
        )

        assert sent is True, (
            "check_and_send_alerts() returned False — alert was NOT sent. "
            "Expected True with +20°C/+50km/h/+25mm manipulation."
        )

        logger.info(f"Alert email sent successfully for trip {trip.name}")

        # --- Restore: save original (non-manipulated) snapshot ---
        snapshot_service.save(trip.id, fresh_weather, target_date)
