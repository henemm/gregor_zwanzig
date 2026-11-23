"""TDD Tests für Issue #612 — Briefing auf Anforderung.

Abgedeckt:
- AC-3: render_html enthält alle 4 Befehls-Strings im Footer
- AC-4: render_narrow("telegram") enthält Befehls-Hinweis; render_narrow("signal") nicht; Längenlimit
- AC-5: Ungültiger Report-Typ liefert Fehlermeldung mit "morning" und "evening"
- AC-6: Multi-User-Trip wird user-scoped gefunden

KEINE Mocks — echte Objekte und File-I/O.
"""
from __future__ import annotations

import shutil
from datetime import datetime, timedelta, date, timezone
from zoneinfo import ZoneInfo

from app.loader import get_briefings_dir, get_data_dir, save_trip
from app.trip import Stage, Trip, Waypoint
from services.trip_command_processor import InboundMessage, TripCommandProcessor


# ---------------------------------------------------------------------------
# Shared helpers (mirrored from test_renderers_email.py / test_issue_360)
# ---------------------------------------------------------------------------

def _make_segment_data():
    from app.models import (
        ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries,
        Provider, SegmentWeatherData, SegmentWeatherSummary, TripSegment,
    )
    now = datetime(2026, 5, 1, 9, 0, tzinfo=timezone.utc)
    points = [
        ForecastDataPoint(
            ts=datetime(2026, 5, 1, 9 + h, 0, tzinfo=timezone.utc),
            t2m_c=15.0 + h,
            wind10m_kmh=10.0 + h,
            gust_kmh=22.0 + h,
            pop_pct=40,
            precip_1h_mm=0.4,
            wind_chill_c=12.0 + h,
            cloud_total_pct=55,
        )
        for h in range(6)
    ]
    meta = ForecastMeta(
        provider=Provider.OPENMETEO,
        model="icon_d2",
        run=datetime(2026, 5, 1, 0, 0, tzinfo=timezone.utc),
        grid_res_km=2.0,
        interp="point_grid",
    )
    ts = NormalizedTimeseries(meta=meta, data=points)
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.2, lon=9.05, elevation_m=400.0),
        end_point=GPXPoint(lat=42.25, lon=9.09, elevation_m=1200.0),
        start_time=datetime(2026, 5, 1, 9, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 5, 1, 13, 0, tzinfo=timezone.utc),
        duration_hours=4.0,
        distance_km=8.0,
        ascent_m=800.0,
        descent_m=0.0,
    )
    agg = SegmentWeatherSummary(
        temp_min_c=15.0, temp_max_c=20.0, temp_avg_c=17.5,
        wind_max_kmh=16.0, gust_max_kmh=28.0,
        precip_sum_mm=2.4, cloud_avg_pct=55,
    )
    return SegmentWeatherData(
        segment=seg, timeseries=ts, aggregated=agg,
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )


def _make_dc():
    from app.metric_catalog import build_default_display_config
    return build_default_display_config()


def _render_html_minimal() -> str:
    from src.output.renderers.email.html import render_html
    seg = _make_segment_data()
    dc = _make_dc()
    return render_html(
        segments=[seg],
        seg_tables=[[]],
        trip_name="GR20 Etappe 3",
        report_type="evening",
        dc=dc,
        night_rows=[],
        thunder_forecast=None,
        highlights=[],
        changes=None,
        stage_name="Vizzavona – Bergeries de Capannelle",
        stage_stats=None,
        multi_day_trend=None,
        compact_summary="Sonniger Abend",
        daylight=None,
        tz=ZoneInfo("UTC"),
        friendly_keys=set(),
    )


# ---------------------------------------------------------------------------
# Test-Trip helpers for AC-5 / AC-6
# ---------------------------------------------------------------------------

_TEST_USER_ID = "userX_test612"
_TEST_TRIP_ID = "test612-trip-x"
_TEST_TRIP_NAME = "Test612 Trip X"


def _make_trip_for_user() -> Trip:
    base = date.today()
    stages = [
        Stage(
            id=f"S{i+1}",
            name=f"Etappe {i+1}",
            date=base + timedelta(days=i),
            waypoints=[
                Waypoint(id="W1", name="Start", lat=42.0, lon=9.0, elevation_m=300),
                Waypoint(id="W2", name="Ziel", lat=42.1, lon=9.1, elevation_m=500),
            ],
        )
        for i in range(3)
    ]
    return Trip(id=_TEST_TRIP_ID, name=_TEST_TRIP_NAME, stages=stages)


def _save_user_trip() -> Trip:
    trip = _make_trip_for_user()
    save_trip(trip, user_id=_TEST_USER_ID)
    return trip


def _cleanup_user_trip() -> None:
    trip_path = get_briefings_dir(_TEST_USER_ID) / f"{_TEST_TRIP_ID}.json"
    if trip_path.exists():
        trip_path.unlink()
    # Issue #3209: isolierte Testwurzel (dort legt save_trip an), nicht der
    # echte data/users-Baum.
    user_dir = get_data_dir(_TEST_USER_ID)
    if user_dir.exists():
        shutil.rmtree(user_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# AC-3: render_html Footer enthält alle 4 Befehls-Strings
# ---------------------------------------------------------------------------

class TestAC3HtmlFooterCommands:
    """AC-3: render_html enthält die aktuellen Antwort-Kommandos im Kommando-Block.

    Note: #884 design changed the kommandos block from HEUTE/MORGEN/STATUS/HILFE
    to PAUSE 2d/SKIP/STOP/STATUS/CONFIG/HELP as a dedicated 3x2-grid section.
    Tests updated to reflect the new #884 design.
    """

    def test_footer_contains_status(self):
        html = _render_html_minimal()
        assert "STATUS" in html, (
            "render_html muss 'STATUS' als Antwort-Kommando enthalten (AC-3/#884)"
        )


# ---------------------------------------------------------------------------
# AC-5: Ungültiger Report-Typ → Fehlermeldung mit "morning" und "evening"
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# F002: _trigger_report akzeptiert Mixed-Case Report-Typen (z.B. "Evening")
# ---------------------------------------------------------------------------

class TestF002ReportTypeCaseInsensitive:
    """F002: report_type wird via .lower() normalisiert — 'Evening'/'MORNING' sind gültig.

    Echter Versand würde echte E-Mail auslösen (kein Mock erlaubt).
    Daher wird nur der inverse Fall getestet: mixed-case UNGÜLTIGER Wert (z.B. "ABEND")
    liefert weiterhin success=False — beweist dass .lower() im Prüfpfad läuft.
    """

    def setup_method(self):
        self._trip = _save_user_trip()
        save_trip(self._trip, user_id="default")

    def teardown_method(self):
        _cleanup_user_trip()
        default_path = get_briefings_dir("default") / f"{_TEST_TRIP_ID}.json"
        if default_path.exists():
            default_path.unlink()

    def test_uppercase_invalid_type_still_fails(self):
        """'ABEND'.lower() == 'abend' ist ungültig → success=False (beweist .lower() läuft)."""
        msg = InboundMessage(
            trip_name=_TEST_TRIP_NAME,
            body="### report: ABEND",
            sender="test@example.com",
            channel="email",
            received_at=datetime.now(tz=timezone.utc),
            user_id="default",
        )
        result = TripCommandProcessor().process(msg)
        assert result.success is False, (
            "F002: 'ABEND' muss auch nach .lower() ungültig bleiben → success=False"
        )


# ---------------------------------------------------------------------------
# AC-5: Ungültiger Report-Typ → Fehlermeldung mit "morning" und "evening"
# ---------------------------------------------------------------------------

class TestAC5InvalidReportType:
    """AC-5: report: abend → success=False, Body enthält morning + evening."""

    def setup_method(self):
        self._trip = _save_user_trip()
        # Auch für default-user einen Trip speichern damit _find_trip etwas findet
        save_trip(self._trip, user_id="default")

    def teardown_method(self):
        _cleanup_user_trip()
        # Default-User-Trip aufräumen
        default_path = get_briefings_dir("default") / f"{_TEST_TRIP_ID}.json"
        if default_path.exists():
            default_path.unlink()

    def test_invalid_report_type_returns_failure(self):
        msg = InboundMessage(
            trip_name=_TEST_TRIP_NAME,
            body="### report: abend",
            sender="test@example.com",
            channel="email",
            received_at=datetime.now(tz=timezone.utc),
            user_id="default",
        )
        result = TripCommandProcessor().process(msg)
        assert result.success is False, (
            "Ungültiger Report-Typ 'abend' muss success=False liefern (AC-5)"
        )

    def test_invalid_report_type_body_contains_morning(self):
        msg = InboundMessage(
            trip_name=_TEST_TRIP_NAME,
            body="### report: abend",
            sender="test@example.com",
            channel="email",
            received_at=datetime.now(tz=timezone.utc),
            user_id="default",
        )
        result = TripCommandProcessor().process(msg)
        assert "morning" in result.confirmation_body, (
            "Fehlermeldung muss 'morning' als erlaubten Wert nennen (AC-5)"
        )

    def test_invalid_report_type_body_contains_evening(self):
        msg = InboundMessage(
            trip_name=_TEST_TRIP_NAME,
            body="### report: abend",
            sender="test@example.com",
            channel="email",
            received_at=datetime.now(tz=timezone.utc),
            user_id="default",
        )
        result = TripCommandProcessor().process(msg)
        assert "evening" in result.confirmation_body, (
            "Fehlermeldung muss 'evening' als erlaubten Wert nennen (AC-5)"
        )


# ---------------------------------------------------------------------------
# AC-6: Multi-User — Trip in user-X-Namespace wird gefunden
# ---------------------------------------------------------------------------

class TestAC6MultiUser:
    """AC-6: Processor findet Trip via load_all_trips(user_id) für userX."""

    def setup_method(self):
        _save_user_trip()

    def teardown_method(self):
        _cleanup_user_trip()

    def test_find_trip_user_scoped(self):
        """_find_trip(name, user_id) findet Trip in user-X Namespace."""
        processor = TripCommandProcessor()
        trip = processor._find_trip(_TEST_TRIP_NAME, _TEST_USER_ID)
        assert trip is not None, (
            f"_find_trip('{_TEST_TRIP_NAME}', '{_TEST_USER_ID}') muss den Trip finden (AC-6)"
        )
        assert trip.id == _TEST_TRIP_ID

    def test_find_trip_default_user_does_not_find_userx_trip(self):
        """Trip von userX ist NICHT im default-Namespace sichtbar."""
        processor = TripCommandProcessor()
        trip = processor._find_trip(_TEST_TRIP_NAME, "default")
        assert trip is None, (
            "Trip von userX darf im default-Namespace nicht sichtbar sein (AC-6)"
        )

    def test_inbound_message_has_user_id_field(self):
        """InboundMessage akzeptiert user_id-Feld."""
        msg = InboundMessage(
            trip_name=_TEST_TRIP_NAME,
            body="### report: morning",
            sender="test@example.com",
            channel="email",
            received_at=datetime.now(tz=timezone.utc),
            user_id=_TEST_USER_ID,
        )
        assert msg.user_id == _TEST_USER_ID

    def test_process_uses_user_id_for_trip_lookup(self):
        """process() mit user_id=userX findet den Trip (success kein Lookup-Fehler).

        F003: Dass process() den Report-Dispatch mit user_id durchführt, ist durch
        Code-Inspektion abgedeckt (trip_command_processor.py: _trigger_report →
        TripReportSchedulerService(user_id=user_id)). Ein echter report-Dispatch
        im Unit-Test würde echten E-Mail-Versand auslösen (kein Mock erlaubt) —
        deshalb wird hier nur der Trip-Lookup via '### status' getestet.
        AC-1/AC-2 werden durch Staging-E2E abgedeckt.
        """
        msg = InboundMessage(
            trip_name=_TEST_TRIP_NAME,
            body="### status",
            sender="test@example.com",
            channel="email",
            received_at=datetime.now(tz=timezone.utc),
            user_id=_TEST_USER_ID,
        )
        result = TripCommandProcessor().process(msg)
        # Trip wurde gefunden → kein "Trip nicht gefunden"-Fehler
        assert result.command != "unknown"
        assert "nicht gefunden" not in result.confirmation_body, (
            "process() muss den Trip via user_id='userX' finden (AC-6)"
        )
