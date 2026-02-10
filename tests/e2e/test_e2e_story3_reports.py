"""
E2E Test: Story 3 - Trip-Reports (Email/SMS)

Tests the COMPLETE flow end-to-end with REAL data:
1. Create a test trip (today's date, 3 waypoints with time windows)
2. Fetch REAL weather data from API (GeoSphere/OpenMeteo)
3. Format HTML email report (TripReportFormatter)
4. Format SMS compact report (SMSTripFormatter)
5. Send REAL email via SMTP
6. Verify email received via IMAP
7. Validate email content (trip name, segments, weather data)
8. Validate SMS length (<=160 chars) and content
9. Test report config persistence (save/load TripReportConfig)
10. Cleanup test trip

NO MOCKS! All real API calls, real email, real weather data.

Usage:
    uv run pytest tests/e2e/test_e2e_story3_reports.py -v
"""
import email
import imaplib
import sys
import time
from datetime import date, datetime, time as dt_time, timezone
from pathlib import Path

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from app.config import Settings
from app.loader import delete_trip, get_trips_dir, load_trip, save_trip
from app.models import GPXPoint, SegmentWeatherData, TripReportConfig, TripSegment
from app.trip import Stage, TimeWindow, Trip, Waypoint
from formatters.sms_trip import SMSTripFormatter
from formatters.trip_report import TripReportFormatter


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

TEST_TRIP_ID = "e2e-test-story3"
TEST_TRIP_NAME = "E2E Story3 GR20"

# Real GR20 coordinates (Corsica) for realistic weather data
GR20_WAYPOINTS = [
    Waypoint(
        id="G1", name="Calenzana", lat=42.5075, lon=8.8553,
        elevation_m=275,
        time_window=TimeWindow(start=dt_time(7, 0), end=dt_time(9, 0)),
    ),
    Waypoint(
        id="G2", name="Ortu di u Piobbu", lat=42.4833, lon=8.9167,
        elevation_m=1520,
        time_window=TimeWindow(start=dt_time(10, 0), end=dt_time(12, 0)),
    ),
    Waypoint(
        id="G3", name="Carrozzu", lat=42.4667, lon=8.9500,
        elevation_m=1270,
        time_window=TimeWindow(start=dt_time(13, 0), end=dt_time(15, 0)),
    ),
]


@pytest.fixture
def test_trip():
    """Create a test trip with today's date and real GR20 coordinates."""
    today = date.today()
    stage = Stage(
        id="T1",
        name="Etappe 1: Calenzana - Carrozzu",
        date=today,
        waypoints=GR20_WAYPOINTS,
    )
    trip = Trip(
        id=TEST_TRIP_ID,
        name=TEST_TRIP_NAME,
        stages=[stage],
        avalanche_regions=[],
    )
    # Save to disk
    save_trip(trip, user_id="default")
    yield trip
    # Cleanup
    delete_trip(TEST_TRIP_ID, user_id="default")


@pytest.fixture
def settings():
    """Load real settings (needs .env with SMTP config)."""
    return Settings()


@pytest.fixture
def segments_from_trip(test_trip):
    """Convert test trip to TripSegments (the way the scheduler does it)."""
    from services.trip_report_scheduler import TripReportSchedulerService

    service = TripReportSchedulerService()
    today = date.today()
    segments = service._convert_trip_to_segments(test_trip, today)
    assert len(segments) == 2, f"Expected 2 segments from 3 waypoints, got {len(segments)}"
    return segments


# ---------------------------------------------------------------------------
# Phase 1: Trip creation & segment conversion
# ---------------------------------------------------------------------------

class TestTripCreationAndSegments:
    """Verify trip is correctly created and segments are properly derived."""

    def test_trip_saved_to_disk(self, test_trip):
        """Trip JSON exists on disk after creation."""
        trip_path = get_trips_dir("default") / f"{TEST_TRIP_ID}.json"
        assert trip_path.exists(), f"Trip file not found: {trip_path}"

    def test_trip_roundtrip(self, test_trip):
        """Trip can be loaded back from disk with correct data."""
        trip_path = get_trips_dir("default") / f"{TEST_TRIP_ID}.json"
        loaded = load_trip(trip_path)
        assert loaded.id == TEST_TRIP_ID
        assert loaded.name == TEST_TRIP_NAME
        assert len(loaded.stages) == 1
        assert len(loaded.stages[0].waypoints) == 3

    def test_segment_conversion(self, segments_from_trip):
        """3 waypoints produce 2 segments with correct coordinates."""
        assert len(segments_from_trip) == 2

        seg1 = segments_from_trip[0]
        assert seg1.segment_id == 1
        assert seg1.start_point.lat == pytest.approx(42.5075, abs=0.01)
        assert seg1.end_point.lat == pytest.approx(42.4833, abs=0.01)
        assert seg1.ascent_m > 0  # Calenzana (275m) -> Ortu (1520m)

        seg2 = segments_from_trip[1]
        assert seg2.segment_id == 2
        assert seg2.descent_m > 0  # Ortu (1520m) -> Carrozzu (1270m)

    def test_segment_time_windows(self, segments_from_trip):
        """Segments have correct UTC time windows from waypoints."""
        seg1 = segments_from_trip[0]
        assert seg1.start_time.hour == 7   # G1 start: 07:00
        assert seg1.end_time.hour == 10    # G2 start: 10:00
        assert seg1.duration_hours == pytest.approx(3.0)

        seg2 = segments_from_trip[1]
        assert seg2.start_time.hour == 10  # G2 start: 10:00
        assert seg2.end_time.hour == 13    # G3 start: 13:00
        assert seg2.duration_hours == pytest.approx(3.0)


# ---------------------------------------------------------------------------
# Phase 2: Real weather fetch
# ---------------------------------------------------------------------------

class TestWeatherFetch:
    """Fetch REAL weather data from API for trip segments."""

    def test_fetch_real_weather(self, segments_from_trip):
        """Weather data is fetched for all segments with plausible values."""
        from services.trip_report_scheduler import TripReportSchedulerService

        service = TripReportSchedulerService()
        weather_data = service._fetch_weather(segments_from_trip)

        assert len(weather_data) > 0, "No weather data returned"
        assert len(weather_data) == len(segments_from_trip), (
            f"Expected {len(segments_from_trip)} segments, got {len(weather_data)}"
        )

        for seg_weather in weather_data:
            agg = seg_weather.aggregated
            # Temperature must be plausible (-40 to +50)
            assert -40 <= agg.temp_min_c <= 50, f"Implausible temp_min: {agg.temp_min_c}"
            assert -40 <= agg.temp_max_c <= 50, f"Implausible temp_max: {agg.temp_max_c}"
            assert agg.temp_min_c <= agg.temp_max_c, "temp_min > temp_max"
            # Wind must be non-negative
            assert agg.wind_max_kmh >= 0, f"Negative wind: {agg.wind_max_kmh}"
            # Precipitation must be non-negative
            assert agg.precip_sum_mm >= 0, f"Negative precip: {agg.precip_sum_mm}"


# ---------------------------------------------------------------------------
# Phase 3: Report formatting (Email + SMS)
# ---------------------------------------------------------------------------

class TestReportFormatting:
    """Test formatters produce correct output with real weather data."""

    def _get_weather_data(self, segments_from_trip):
        """Helper: fetch real weather for segments."""
        from services.trip_report_scheduler import TripReportSchedulerService
        service = TripReportSchedulerService()
        return service._fetch_weather(segments_from_trip)

    def test_email_html_contains_trip_name(self, segments_from_trip):
        """HTML email contains the trip name."""
        weather = self._get_weather_data(segments_from_trip)
        formatter = TripReportFormatter()
        report = formatter.format_email(weather, TEST_TRIP_NAME, "morning")

        assert TEST_TRIP_NAME in report.email_html
        assert TEST_TRIP_NAME in report.email_subject

    def test_email_html_contains_segments(self, segments_from_trip):
        """HTML email contains segment table with real data."""
        weather = self._get_weather_data(segments_from_trip)
        formatter = TripReportFormatter()
        report = formatter.format_email(weather, TEST_TRIP_NAME, "morning")

        # Must have segment IDs
        assert "#1" in report.email_html
        assert "#2" in report.email_html
        # Must have temperature values
        assert "°C" in report.email_html
        # Must have wind values
        assert "km/h" in report.email_html
        # Must have summary section
        assert "Summary" in report.email_html
        assert "Max Temperature" in report.email_html

    def test_email_plain_text_fallback(self, segments_from_trip):
        """Plain text email is also generated."""
        weather = self._get_weather_data(segments_from_trip)
        formatter = TripReportFormatter()
        report = formatter.format_email(weather, TEST_TRIP_NAME, "morning")

        assert report.email_plain is not None
        assert len(report.email_plain) > 100
        assert "SEGMENTS" in report.email_plain
        assert "SUMMARY" in report.email_plain

    def test_email_subject_format(self, segments_from_trip):
        """Subject line follows format: [Trip Name] Type - DD.MM.YYYY."""
        weather = self._get_weather_data(segments_from_trip)
        formatter = TripReportFormatter()
        report = formatter.format_email(weather, TEST_TRIP_NAME, "morning")

        assert report.email_subject.startswith(f"[{TEST_TRIP_NAME}]")
        assert "Morning Report" in report.email_subject
        assert date.today().strftime("%d.%m.%Y") in report.email_subject

    def test_sms_format_compact(self, segments_from_trip):
        """SMS is <=160 chars with correct format."""
        weather = self._get_weather_data(segments_from_trip)
        formatter = SMSTripFormatter()
        sms = formatter.format_sms(weather)

        assert len(sms) <= 160, f"SMS too long: {len(sms)} chars: {sms}"
        assert "E1:" in sms
        assert "E2:" in sms
        assert "T" in sms  # Temperature

    def test_sms_contains_temperature(self, segments_from_trip):
        """SMS contains temperature data for each segment."""
        weather = self._get_weather_data(segments_from_trip)
        formatter = SMSTripFormatter()
        sms = formatter.format_sms(weather)

        # Format: E1:T{min}/{max}
        assert "E1:T" in sms
        assert "/" in sms  # min/max separator


# ---------------------------------------------------------------------------
# Phase 4: Real email send + IMAP verify
# ---------------------------------------------------------------------------

class TestEmailDelivery:
    """Send REAL email and verify via IMAP. Requires SMTP config."""

    def test_send_and_verify_report_email(self, segments_from_trip, settings):
        """Full flow: weather -> format -> SMTP send -> IMAP receive."""
        if not settings.can_send_email():
            pytest.skip("SMTP not configured")

        # 1. Fetch weather
        from services.trip_report_scheduler import TripReportSchedulerService
        service = TripReportSchedulerService(settings)
        weather = service._fetch_weather(segments_from_trip)
        assert len(weather) > 0, "No weather data"

        # 2. Format email
        formatter = TripReportFormatter()
        report = formatter.format_email(weather, TEST_TRIP_NAME, "morning")

        # 3. Send via SMTP
        from outputs.email import EmailOutput
        email_out = EmailOutput(settings)
        email_out.send(
            subject=report.email_subject,
            body=report.email_html,
            plain_text_body=report.email_plain,
        )

        # 4. Wait for delivery
        time.sleep(8)

        # 5. Verify via IMAP
        imap = imaplib.IMAP4_SSL("imap.gmail.com")
        imap.login(settings.smtp_user, settings.smtp_pass)
        imap.select('"[Google Mail]/Gesendet"')

        _, data = imap.search(None, "ALL")
        all_ids = data[0].split()
        assert len(all_ids) > 0, "No emails in sent folder"

        # Get latest email
        _, msg_data = imap.fetch(all_ids[-1], "(RFC822)")
        msg = email.message_from_bytes(msg_data[0][1])

        subject = msg.get("Subject", "")
        imap.close()
        imap.logout()

        # 6. Validate subject contains trip name
        assert TEST_TRIP_NAME in subject, (
            f"Trip name '{TEST_TRIP_NAME}' not in subject: {subject}"
        )
        assert "Morning Report" in subject, (
            f"'Morning Report' not in subject: {subject}"
        )

        # 7. Validate HTML body content
        body_html = ""
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                body_html = part.get_payload(decode=True).decode("utf-8")
                break

        assert TEST_TRIP_NAME in body_html, "Trip name missing from email body"
        assert "#1" in body_html, "Segment #1 missing from email"
        assert "#2" in body_html, "Segment #2 missing from email"
        assert "km/h" in body_html, "Wind data missing from email"
        assert "Summary" in body_html, "Summary section missing from email"


# ---------------------------------------------------------------------------
# Phase 5: Report config persistence
# ---------------------------------------------------------------------------

class TestReportConfigPersistence:
    """Test TripReportConfig save/load roundtrip."""

    def test_save_and_load_report_config(self, test_trip):
        """Report config survives save/load roundtrip."""
        config = TripReportConfig(
            trip_id=TEST_TRIP_ID,
            enabled=True,
            morning_time=dt_time(6, 30),
            evening_time=dt_time(19, 0),
            send_email=True,
            send_sms=False,
            alert_on_changes=True,
            change_threshold_temp_c=3.0,
            change_threshold_wind_kmh=25.0,
            change_threshold_precip_mm=8.0,
        )
        test_trip.report_config = config
        save_trip(test_trip, user_id="default")

        # Reload from disk
        trip_path = get_trips_dir("default") / f"{TEST_TRIP_ID}.json"
        loaded = load_trip(trip_path)

        assert loaded.report_config is not None
        assert loaded.report_config.trip_id == TEST_TRIP_ID
        assert loaded.report_config.morning_time == dt_time(6, 30)
        assert loaded.report_config.evening_time == dt_time(19, 0)
        assert loaded.report_config.send_email is True
        assert loaded.report_config.send_sms is False
        assert loaded.report_config.alert_on_changes is True
        assert loaded.report_config.change_threshold_temp_c == 3.0
        assert loaded.report_config.change_threshold_wind_kmh == 25.0
        assert loaded.report_config.change_threshold_precip_mm == 8.0

    def test_trip_without_config_loads_none(self, test_trip):
        """Trip without report_config loads as None."""
        trip_path = get_trips_dir("default") / f"{TEST_TRIP_ID}.json"
        loaded = load_trip(trip_path)
        assert loaded.report_config is None


# ---------------------------------------------------------------------------
# Phase 6: Full scheduler integration
# ---------------------------------------------------------------------------

class TestSchedulerIntegration:
    """Test the scheduler service with a real trip."""

    def test_scheduler_finds_active_trip(self, test_trip):
        """Scheduler identifies test trip as active for today (morning)."""
        from services.trip_report_scheduler import TripReportSchedulerService
        service = TripReportSchedulerService()

        active = service._get_active_trips("morning")
        active_ids = [t.id for t in active]
        assert TEST_TRIP_ID in active_ids, (
            f"Test trip not found in active trips: {active_ids}"
        )

    def test_scheduler_send_reports(self, test_trip, settings):
        """Scheduler sends report for test trip (full E2E)."""
        if not settings.can_send_email():
            pytest.skip("SMTP not configured")

        from services.trip_report_scheduler import TripReportSchedulerService
        service = TripReportSchedulerService(settings)

        sent = service.send_reports("morning")
        assert sent >= 1, f"Expected at least 1 report sent, got {sent}"
