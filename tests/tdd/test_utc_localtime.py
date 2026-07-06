"""
TDD Tests for BUG-UTC-LOCALTIME.

All report times must display in LOCAL timezone, not UTC.
Spec: docs/specs/bugfix/utc_localtime_display.md
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo



# ── Test 1: Timezone Utility exists and works ──────────────────────────


class TestTimezoneUtility:
    """src/utils/timezone.py must provide coordinate-to-timezone lookup."""

    def test_tz_for_coords_mallorca_returns_cet(self):
        """
        GIVEN: Coordinates for Sóller, Mallorca (39.77°N, 2.72°E)
        WHEN: tz_for_coords is called
        THEN: Returns Europe/Madrid timezone
        """
        from utils.timezone import tz_for_coords

        tz = tz_for_coords(39.77, 2.72)
        assert tz.key == "Europe/Madrid"

    def test_tz_for_coords_austria_returns_vienna(self):
        """
        GIVEN: Coordinates for Innsbruck, Austria (47.26°N, 11.39°E)
        WHEN: tz_for_coords is called
        THEN: Returns Europe/Vienna timezone
        """
        from utils.timezone import tz_for_coords

        tz = tz_for_coords(47.26, 11.39)
        assert tz.key == "Europe/Vienna"

    def test_tz_for_coords_fallback_to_utc(self):
        """
        GIVEN: Coordinates in the middle of the ocean (0°N, 0°E)
        WHEN: tz_for_coords is called
        THEN: Falls back to UTC
        """
        from utils.timezone import tz_for_coords

        tz = tz_for_coords(0.0, 0.0)
        assert tz is not None

    def test_local_hour_converts_utc_to_local(self):
        """
        GIVEN: A UTC datetime at 06:00 UTC
        WHEN: local_hour is called with CET timezone (UTC+1)
        THEN: Returns 7 (not 6)
        """
        from utils.timezone import local_hour

        dt_utc = datetime(2026, 3, 3, 6, 0, tzinfo=timezone.utc)
        tz = ZoneInfo("Europe/Madrid")
        assert local_hour(dt_utc, tz) == 7

    def test_local_fmt_converts_utc_to_local_string(self):
        """
        GIVEN: A UTC datetime at 06:13 UTC
        WHEN: local_fmt is called with CET timezone
        THEN: Returns "07:13" (not "06:13")
        """
        from utils.timezone import local_fmt

        dt_utc = datetime(2026, 3, 3, 6, 13, tzinfo=timezone.utc)
        tz = ZoneInfo("Europe/Madrid")
        assert local_fmt(dt_utc, tz) == "07:13"

    def test_local_fmt_summer_time(self):
        """
        GIVEN: A UTC datetime in July (CEST = UTC+2)
        WHEN: local_fmt is called with Europe/Madrid
        THEN: Returns time shifted by +2 hours
        """
        from utils.timezone import local_fmt

        dt_utc = datetime(2026, 7, 15, 5, 0, tzinfo=timezone.utc)
        tz = ZoneInfo("Europe/Madrid")
        assert local_fmt(dt_utc, tz) == "07:00"


# ── Test 2 (Daylight banner) entfernt: Tageslicht-Block wurde mit #790
#    aus der Briefing-Mail entfernt (_format_daylight_html/_plain gelöscht). ──


# ── Test 3: Hourly table shows local hours ──────────────────────────


class TestHourlyTableLocalTime:
    """The hourly weather table must show local hours, not UTC."""

    def test_hourly_row_time_is_local(self):
        """
        GIVEN: A ForecastDataPoint with ts=09:00 UTC
        WHEN: Rendered in hourly table with CET timezone (UTC+1)
        THEN: Time column shows "10:00" (not "09:00") — local time, HH:MM format.

        Note: The time format changed to "HH:MM" (e.g. "10:00") for clarity.
        The key assertion remains: local time is used (UTC+1 → hour 10, not UTC hour 09).
        """
        from app.models import ForecastDataPoint
        from app.metric_catalog import build_default_display_config
        from output.renderers.trip_report import TripReportFormatter

        dp = ForecastDataPoint(
            ts=datetime(2026, 3, 3, 9, 0, tzinfo=timezone.utc),
            t2m_c=12.0,
        )

        formatter = TripReportFormatter()
        formatter._tz = ZoneInfo("Europe/Madrid")

        dc = build_default_display_config()
        row = formatter._dp_to_row(dp, dc)
        # Format is "HH:MM" — assert local hour 10 (not UTC 09)
        assert row["time"] == "10:00", f"Expected local time '10:00', got '{row['time']}'"
        assert not row["time"].startswith("09"), f"Must NOT show UTC hour 09, got '{row['time']}'"


# ── Test 4: Compact summary shows local hours ──────────────────────────


class TestCompactSummaryLocalTime:
    """Compact summary rain/wind/thunder times must be local."""

    def test_rain_pattern_hour_is_local(self):
        """
        GIVEN: Rain starting at 14:00 UTC
        WHEN: Compact summary _find_rain_pattern with CET timezone
        THEN: Pattern start_hour shows 15 (not 14)
        """
        from app.models import ForecastDataPoint
        from output.renderers.compact_summary import CompactSummaryFormatter

        # Create data points: dry until 14:00 UTC, then rain
        hourly = []
        for h in range(8, 18):
            dp = ForecastDataPoint(
                ts=datetime(2026, 3, 3, h, 0, tzinfo=timezone.utc),
                t2m_c=10.0,
                precip_1h_mm=2.5 if h >= 14 else 0.0,
            )
            hourly.append(dp)

        fmt = CompactSummaryFormatter()
        fmt._tz = ZoneInfo("Europe/Madrid")

        pattern = fmt._find_rain_pattern(hourly)
        assert pattern is not None, "Should detect rain pattern"
        assert pattern["kind"] == "starts_later"
        # Rain starts at 14:00 UTC = 15:00 CET
        assert pattern["start_hour"] == 15, (
            f"Rain start should be local hour 15, got {pattern['start_hour']}"
        )
