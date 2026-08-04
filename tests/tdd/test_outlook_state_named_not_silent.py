"""Fix #1486 (TDD RED) — der Ausblick benennt seinen Zustand, statt zu schweigen.

Spec: docs/specs/modules/fix_1486_outlook_silent_exit.md (AC-1, AC-2, AC-3)
Kontext: docs/context/fix-1486-outlook-silent-exit.md

Diese Datei prueft die ERZEUGUNGS-Seite: welchen Zustand
``TripReportSchedulerService._build_stage_trend()`` meldet und was es dabei
protokolliert. Die sichtbaren Texte der vier Ausgabewege prueft
``tests/tdd/test_outlook_state_visible_in_channels.py``.

RED heute: ``_build_stage_trend()`` liefert fuer ALLE fuenf Ausstiege dasselbe
``None`` — der Grund ist nicht rekonstruierbar; ``OutlookState``/``TrendResult``
existieren noch nicht.

KEINE Mocks: echte Trip-/Stage-/Waypoint-Objekte und echte Scheduler-
Unterklassen (Bestandsmuster ``tests/tdd/test_trip_briefing_anchor_unchanged.py``
:132 / ``tests/tdd/test_alert_state_briefing_reset.py``:418) statt patch().
Kein Netz: jeder gepruefte Fall bricht VOR dem Wetterabruf ab oder bekommt sein
Wetter aus der Unterklasse.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta, timezone

_LOGGER_NAME = "trip_report_scheduler"


def _outlook_state():
    """``OutlookState``-Enum aus dem neuen Baustein (RED: existiert noch nicht)."""
    from output.renderers.email.outlook_state_hint import OutlookState

    return OutlookState


def _waypoints():
    from app.trip import Waypoint

    return [
        Waypoint(id="A", name="Start", lat=47.10, lon=11.30, elevation_m=500),
        Waypoint(id="B", name="Ziel", lat=47.11, lon=11.31, elevation_m=600),
    ]


def _trip(stages, trip_id="fix1486"):
    from app.trip import Trip

    return Trip(id=trip_id, name="Fix 1486 Ausblick", stages=stages)


def _stage(stage_id, day_offset, *, waypoints=None):
    from app.trip import Stage

    return Stage(
        id=stage_id,
        name=f"Etappe {stage_id}",
        date=date.today() + timedelta(days=day_offset),
        start_time=time(7, 0),
        waypoints=_waypoints() if waypoints is None else waypoints,
    )


def _error_weather(segments):
    """Echte WEATHER-04-Fehlerplatzhalter — exakt das, was ``_fetch_weather``
    bei erschoepftem Kontingent (#1329/#1348) selbst erzeugt
    (trip_report_scheduler.py:1208-1217)."""
    from app.models import SegmentWeatherData, SegmentWeatherSummary

    return [
        SegmentWeatherData(
            segment=seg,
            timeseries=None,
            aggregated=SegmentWeatherSummary(),
            fetched_at=datetime.now(timezone.utc),
            provider="unknown",
            has_error=True,
            error_message="Kontingent erschoepft",
        )
        for seg in segments
    ]


def _scheduler(weather=None):
    """Echter Scheduler; ``weather`` ersetzt NUR den Wetterabruf (Unterklasse,
    kein Mock). ``None`` = unveraenderter Abruf (offline via FixtureProvider)."""
    from services.trip_report_scheduler import TripReportSchedulerService

    if weather is None:
        return TripReportSchedulerService()

    class _FixtureWeatherScheduler(TripReportSchedulerService):
        def _fetch_weather(self, segments, provider=None):
            return weather(segments)

    return _FixtureWeatherScheduler()


def _warnings(caplog):
    """WARNINGs des SCHEDULERS — bewusst nach Logger-Namen gefiltert.

    Ohne diesen Filter waere der Nachweis falsch gruen: der geteilte
    Segment-Bau meldet bei der Ursache "keine Segmente" bereits selbst
    ("trip_segments: Stage S2 has less than 2 waypoints"). Gefordert ist aber
    ein Eintrag der Stelle, die den Ausblick verwirft.
    """
    return [
        r for r in caplog.records
        if r.levelno >= logging.WARNING and r.name == _LOGGER_NAME
    ]


# ---------------------------------------------------------------------------
# AC-1 — Klasse A: keine weiteren Etappen (normaler Tourabschluss, KEIN WARNING)
# ---------------------------------------------------------------------------

def test_ac1_no_future_stages_reports_state_and_logs_nothing(caplog):
    """AC-1: letzte Etappe ist das Zieldatum -> Zustand ``NO_STAGES``,
    ``rows`` bleibt leer UND es entsteht kein WARNING (kein Stoerfall)."""
    OutlookState = _outlook_state()
    trip = _trip([_stage("S1", 0)])
    service = _scheduler()

    with caplog.at_level(logging.DEBUG, logger=_LOGGER_NAME):
        result = service._build_stage_trend(trip, date.today(), tz=None)

    assert result.state is OutlookState.NO_STAGES, (
        "Eine Tour ohne Folge-Etappe muss den Zustand NO_STAGES melden, "
        f"bekam: {result!r}"
    )
    assert result.rows is None, (
        f"Ohne Folge-Etappe darf es keine Ausblick-Zeilen geben: {result!r}"
    )
    assert _warnings(caplog) == [], (
        "Der normale Tourabschluss ist kein Stoerfall und darf NICHT als "
        f"WARNING protokolliert werden: {[r.getMessage() for r in _warnings(caplog)]}"
    )


# ---------------------------------------------------------------------------
# AC-2 — Klasse B: Folge-Etappe jenseits des Vorhersagehorizonts
# ---------------------------------------------------------------------------

def test_ac2_beyond_horizon_reports_state_with_real_horizon(caplog):
    """AC-2: Etappe jenseits ``OPENMETEO_MAX_FORECAST_DAYS`` -> Zustand
    ``BEYOND_HORIZON`` mit dem echten Horizont-Wert."""
    from providers.openmeteo import OPENMETEO_MAX_FORECAST_DAYS

    OutlookState = _outlook_state()
    far = OPENMETEO_MAX_FORECAST_DAYS + 5
    trip = _trip([_stage("S1", 0), _stage("S2", far)])
    service = _scheduler()

    with caplog.at_level(logging.DEBUG, logger=_LOGGER_NAME):
        result = service._build_stage_trend(trip, date.today(), tz=None)

    assert result.state is OutlookState.BEYOND_HORIZON, (
        "Eine Folge-Etappe jenseits des Vorhersagehorizonts muss den Zustand "
        f"BEYOND_HORIZON melden, bekam: {result!r}"
    )
    assert result.horizon_days == OPENMETEO_MAX_FORECAST_DAYS, (
        "Der Zustand muss den ECHTEN, konfigurierten Horizont tragen "
        f"({OPENMETEO_MAX_FORECAST_DAYS}), bekam: {result.horizon_days!r}"
    )
    assert result.rows is None


def test_ac2_beyond_horizon_is_logged_as_warning(caplog):
    """AC-2: der Horizont-Fall wird als WARNING protokolliert (vorher
    ``logger.debug`` — im Betrieb unsichtbar) und nennt die Etappe."""
    from providers.openmeteo import OPENMETEO_MAX_FORECAST_DAYS

    trip = _trip([_stage("S1", 0), _stage("S2", OPENMETEO_MAX_FORECAST_DAYS + 5)])
    service = _scheduler()

    with caplog.at_level(logging.DEBUG, logger=_LOGGER_NAME):
        service._build_stage_trend(trip, date.today(), tz=None)

    messages = [r.getMessage() for r in _warnings(caplog)]
    assert any("S2" in m for m in messages), (
        "Der Horizont-Fall muss als WARNING mit Etappen-Bezug protokolliert "
        f"werden, WARNINGs waren: {messages}"
    )
    assert any(str(OPENMETEO_MAX_FORECAST_DAYS) in m for m in messages), (
        "Das WARNING muss den Horizont in Tagen nennen "
        f"({OPENMETEO_MAX_FORECAST_DAYS}), WARNINGs waren: {messages}"
    )


# ---------------------------------------------------------------------------
# AC-3 — Klasse C: drei Ursachen, EIN Zustand, jeweils ein WARNING
# ---------------------------------------------------------------------------

def _trip_without_segments():
    """Ursache 1 (:1404): Folge-Etappe mit nur EINEM Wegpunkt -> der geteilte
    Segment-Bau (``trip_segments.convert_trip_to_segments``) liefert nichts."""
    from app.trip import Waypoint

    solo = [Waypoint(id="A", name="Einzelpunkt", lat=47.10, lon=11.30, elevation_m=500)]
    return _trip([_stage("S1", 0), _stage("S2", 1, waypoints=solo)]), None


def _trip_without_weather():
    """Ursache 2 (:1408): Abruf liefert keine Wetterdaten."""
    return _trip([_stage("S1", 0), _stage("S2", 1)]), (lambda segments: [])


def _trip_with_row_build_error():
    """Ursache 3 (:1463): echte Ausnahme beim Zeilenbau — ``aggregate_stage``
    scheitert an lauter Fehlerplatzhaltern ("All segments have errors")."""
    return _trip([_stage("S1", 0), _stage("S2", 1)]), _error_weather


def _unavailable_cases():
    return {
        "keine_segmente": _trip_without_segments,
        "keine_wetterdaten": _trip_without_weather,
        "fehler_beim_zeilenbau": _trip_with_row_build_error,
    }


def test_ac3_all_three_failure_causes_report_unavailable():
    """AC-3: fehlende Segmente / fehlende Wetterdaten / Fehler beim Zeilenbau
    melden ALLE den Zustand ``UNAVAILABLE`` — heute schweigen alle drei."""
    OutlookState = _outlook_state()
    for label, build in _unavailable_cases().items():
        trip, weather = build()
        result = _scheduler(weather)._build_stage_trend(trip, date.today(), tz=None)
        assert result.state is OutlookState.UNAVAILABLE, (
            f"Ursache '{label}' ist eine Stoerung und muss UNAVAILABLE melden, "
            f"bekam: {result!r}"
        )
        assert result.rows is None, f"Ursache '{label}': keine Zeilen erwartet"


def test_ac3_all_three_failure_causes_log_a_warning(caplog):
    """AC-3: jede der drei Ursachen hinterlaesst ein WARNING mit Etappen-Bezug
    (heute: zwei von dreien protokollieren gar nichts)."""
    for label, build in _unavailable_cases().items():
        caplog.clear()
        trip, weather = build()
        with caplog.at_level(logging.DEBUG, logger=_LOGGER_NAME):
            _scheduler(weather)._build_stage_trend(trip, date.today(), tz=None)
        messages = [r.getMessage() for r in _warnings(caplog)]
        assert any("S2" in m for m in messages), (
            f"Ursache '{label}' muss ein WARNING mit Etappen-Bezug erzeugen, "
            f"WARNINGs waren: {messages}"
        )
