"""
TDD RED Tests fuer Bug #288 — Ensemble-API nur 1x taeglich abrufen.

Jeder Test mappt 1:1 auf ein AC aus
docs/specs/modules/bug_288_ensemble_api_limit.md.

Diese Tests MUESSEN im RED-Phase fehlschlagen weil:
- fetch_forecast() hat noch kein enrich_ensemble-Parameter
- fetch_segment_weather() hat noch kein enrich_ensemble-Parameter
- TripReportSchedulerService._enrich_ensemble_for_trip() existiert noch nicht

KEINE MOCKS — echte Dataclasses, echte Logik, kein Mock()/patch().
"""
from __future__ import annotations

import inspect
from datetime import date, datetime, timezone, timedelta

import pytest


# ---------------------------------------------------------------------------
# Helpers: minimale Objekte ohne externe Deps
# ---------------------------------------------------------------------------

def _make_waypoint(id_: str = "wp-1", lat: float = 47.27, lon: float = 11.39):
    from app.trip import Waypoint
    return Waypoint(id=id_, name=f"Punkt {id_}", lat=lat, lon=lon, elevation_m=800)


def _make_stage(stage_id: str = "s-1", waypoints=None):
    from app.trip import Stage
    if waypoints is None:
        waypoints = [
            _make_waypoint("wp-1", 47.10, 9.20),
            _make_waypoint("wp-2", 47.20, 9.30),
        ]
    return Stage(id=stage_id, name=f"Etappe {stage_id}",
                 date=date(2026, 6, 15), waypoints=waypoints)


def _make_trip(num_stages: int = 2):
    from app.trip import Trip
    stages = [
        _make_stage(
            f"s-{i}",
            waypoints=[
                _make_waypoint(f"wp-{i}a", 47.10 + i * 0.05, 9.20 + i * 0.05),
                _make_waypoint(f"wp-{i}b", 47.15 + i * 0.05, 9.25 + i * 0.05),
            ],
        )
        for i in range(1, num_stages + 1)
    ]
    return Trip(id="test-trip", name="Test Trip", stages=stages)


def _make_segment(lat: float = 47.27, lon: float = 11.39):
    from app.models import GPXPoint, TripSegment
    now = datetime.now(timezone.utc).replace(hour=6, minute=0, second=0, microsecond=0)
    return TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=lat, lon=lon, elevation_m=800),
        end_point=GPXPoint(lat=lat + 0.05, lon=lon + 0.05, elevation_m=1200),
        start_time=now,
        end_time=now + timedelta(hours=8),
        duration_hours=8.0,
        distance_km=12.0,
        ascent_m=500,
        descent_m=100,
    )


def _make_scheduler():
    """Baut TripReportSchedulerService minimal ohne vollstaendige Settings."""
    from services.trip_report_scheduler import TripReportSchedulerService
    svc = TripReportSchedulerService.__new__(TripReportSchedulerService)
    svc._user_id = "default"
    return svc


# ---------------------------------------------------------------------------
# AC-1: Alert-Check ruft keine Ensemble-API auf
# fetch_forecast() und fetch_segment_weather() muessen enrich_ensemble akzeptieren
# ---------------------------------------------------------------------------

def test_ac1_fetch_forecast_signature_has_enrich_ensemble():
    """
    AC-1 (Signatur): fetch_forecast() hat den Parameter enrich_ensemble.

    GIVEN: OpenMeteoProvider-Klasse
    WHEN:  Signatur von fetch_forecast() inspiziert
    THEN:  Parameter 'enrich_ensemble' mit Default True existiert

    RED: Parameter existiert noch nicht → AssertionError
    """
    from providers.openmeteo import OpenMeteoProvider

    sig = inspect.signature(OpenMeteoProvider.fetch_forecast)
    assert "enrich_ensemble" in sig.parameters, (
        "fetch_forecast() hat noch keinen enrich_ensemble-Parameter"
    )
    param = sig.parameters["enrich_ensemble"]
    assert param.default is True, (
        f"enrich_ensemble sollte Default=True haben, hat aber Default={param.default}"
    )


def test_ac1_segment_weather_signature_has_enrich_ensemble():
    """
    AC-1 (Signatur): fetch_segment_weather() hat den Parameter enrich_ensemble.

    GIVEN: SegmentWeatherService-Klasse
    WHEN:  Signatur von fetch_segment_weather() inspiziert
    THEN:  Parameter 'enrich_ensemble' mit Default True existiert

    RED: Parameter existiert noch nicht → AssertionError
    """
    from services.segment_weather import SegmentWeatherService

    sig = inspect.signature(SegmentWeatherService.fetch_segment_weather)
    assert "enrich_ensemble" in sig.parameters, (
        "fetch_segment_weather() hat noch keinen enrich_ensemble-Parameter"
    )
    param = sig.parameters["enrich_ensemble"]
    assert param.default is True, (
        f"enrich_ensemble sollte Default=True haben, ist aber {param.default}"
    )


def test_ac1_fetch_segment_weather_accepts_enrich_ensemble_false():
    """
    AC-1 (Verhalten): fetch_segment_weather(enrich_ensemble=False) liefert
    Daten ohne Ensemble; alle confidence_pct-Werte sind None.

    GIVEN: SegmentWeatherService mit echtem OpenMeteo-Provider
    WHEN:  fetch_segment_weather(segment, enrich_ensemble=False) aufgerufen
    THEN:  Kein TypeError; alle DataPoints haben confidence_pct=None

    RED: TypeError weil enrich_ensemble-Parameter noch nicht existiert
    """
    from providers.base import get_provider
    from services.segment_weather import SegmentWeatherService

    provider = get_provider("openmeteo")
    service = SegmentWeatherService(provider)
    segment = _make_segment(lat=47.27, lon=11.39)

    result = service.fetch_segment_weather(segment, enrich_ensemble=False)

    assert result is not None
    assert not result.has_error, f"Fetch schlug fehl: {result.error_message}"
    assert result.timeseries is not None
    for dp in result.timeseries.data:
        assert dp.confidence_pct is None, (
            f"confidence_pct sollte None sein bei enrich_ensemble=False, "
            f"ist aber {dp.confidence_pct} fuer ts={dp.ts}"
        )


# ---------------------------------------------------------------------------
# AC-2: Report-Run ruft Ensemble genau 1x auf (letzter Waypoint der letzten Etappe)
# _enrich_ensemble_for_trip() muss existieren
# ---------------------------------------------------------------------------

def test_ac2_enrich_ensemble_for_trip_method_exists():
    """
    AC-2: TripReportSchedulerService hat _enrich_ensemble_for_trip()-Methode.

    GIVEN: TripReportSchedulerService-Klasse
    WHEN:  Methoden-Existenz geprueft
    THEN:  _enrich_ensemble_for_trip existiert und ist callable

    RED: Methode existiert noch nicht → AssertionError
    """
    from services.trip_report_scheduler import TripReportSchedulerService

    assert hasattr(TripReportSchedulerService, "_enrich_ensemble_for_trip"), (
        "TripReportSchedulerService hat keine _enrich_ensemble_for_trip()-Methode"
    )
    assert callable(getattr(TripReportSchedulerService, "_enrich_ensemble_for_trip"))


def test_ac2_enrich_uses_last_waypoint_of_last_stage():
    """
    AC-2: _enrich_ensemble_for_trip() greift auf trip.stages[-1].last_waypoint zu.

    GIVEN: Trip mit 2 Etappen
    WHEN:  _enrich_ensemble_for_trip(trip, []) aufgerufen (leere weather_data)
    THEN:  Kein IndexError; Methode laeuft ohne Exception durch

    RED: AttributeError weil Methode nicht existiert
    """
    from services.trip_report_scheduler import TripReportSchedulerService

    trip = _make_trip(num_stages=2)
    last_wp = trip.stages[-1].last_waypoint

    assert last_wp is not None, "trip.stages[-1].last_waypoint sollte nicht None sein"
    assert last_wp.lat == pytest.approx(47.25, abs=0.01)

    svc = _make_scheduler()
    svc._enrich_ensemble_for_trip(trip=trip, weather_data=[])


def test_ac2_single_stage_trip_no_index_error():
    """
    AC-2/AC-5: Einetappiger Trip liefert keinen IndexError.

    GIVEN: Trip mit genau 1 Etappe
    WHEN:  _enrich_ensemble_for_trip(trip, []) aufgerufen
    THEN:  Kein IndexError; trip.stages[-1] ist identisch mit trip.stages[0]

    RED: AttributeError weil Methode nicht existiert
    """
    from services.trip_report_scheduler import TripReportSchedulerService

    trip = _make_trip(num_stages=1)
    assert len(trip.stages) == 1
    assert trip.stages[-1] is trip.stages[0]

    svc = _make_scheduler()
    svc._enrich_ensemble_for_trip(trip=trip, weather_data=[])


# ---------------------------------------------------------------------------
# AC-3: Confidence-Daten fliessen nach Anreicherung in Ausgabe
# Nach _enrich_ensemble_for_trip() muessen confidence_pct_min-Werte gesetzt sein
# ---------------------------------------------------------------------------

def test_ac3_confidence_propagated_to_all_segments_after_enrichment():
    """
    AC-3: Nach _enrich_ensemble_for_trip() haben SegmentWeatherSummaries
    confidence_pct_min gesetzt (nicht None).

    GIVEN: Trip + 1 SegmentWeatherData ohne Ensemble-Daten
    WHEN:  _enrich_ensemble_for_trip(trip, weather_data) aufgerufen
    THEN:  weather_data[0].aggregated.confidence_pct_min ist nicht None

    RED: AttributeError weil Methode nicht existiert
    """
    from app.models import SegmentWeatherData, SegmentWeatherSummary
    from services.trip_report_scheduler import TripReportSchedulerService

    trip = _make_trip(num_stages=1)
    segment = _make_segment(lat=trip.stages[-1].last_waypoint.lat,
                            lon=trip.stages[-1].last_waypoint.lon)

    summary = SegmentWeatherSummary()
    assert summary.confidence_pct_min is None

    weather_item = SegmentWeatherData(
        segment=segment,
        timeseries=None,
        aggregated=summary,
        fetched_at=datetime.now(timezone.utc),
        provider="openmeteo",
        has_error=False,
    )

    svc = _make_scheduler()
    svc._enrich_ensemble_for_trip(trip=trip, weather_data=[weather_item])

    assert weather_item.aggregated.confidence_pct_min is not None, (
        "confidence_pct_min sollte nach _enrich_ensemble_for_trip() gesetzt sein, ist aber None"
    )


# ---------------------------------------------------------------------------
# AC-4: Backward-Compatibility — Default enrich_ensemble=True unveraendert
# ---------------------------------------------------------------------------

def test_ac4_fetch_forecast_default_true_is_backward_compatible():
    """
    AC-4: fetch_forecast(enrich_ensemble=True) verhält sich wie der bisherige
    Standard (Ensemble wird abgerufen, kein TypeError).

    GIVEN: OpenMeteoProvider, echte Innsbruck-Koordinaten
    WHEN:  fetch_forecast(..., enrich_ensemble=True) aufgerufen
    THEN:  Kein TypeError; Ergebnis ist NormalizedTimeseries mit Daten

    RED: TypeError weil enrich_ensemble-Parameter noch nicht existiert
    """
    from providers.openmeteo import OpenMeteoProvider
    from app.config import Location

    provider = OpenMeteoProvider()
    location = Location(latitude=47.27, longitude=11.39, name="Innsbruck")
    now = datetime.now(timezone.utc)

    result = provider.fetch_forecast(
        location=location,
        start=now,
        end=now + timedelta(days=1),
        enrich_ensemble=True,
    )

    assert result is not None
    assert len(result.data) > 0


def test_ac4_geosphere_accepts_enrich_ensemble_parameter():
    """
    AC-4 (GeoSphere): GeoSphereProvider.fetch_forecast() akzeptiert
    enrich_ensemble-Parameter (wird ignoriert).

    GIVEN: GeoSphereProvider-Klasse
    WHEN:  Signatur von fetch_forecast() inspiziert
    THEN:  Parameter 'enrich_ensemble' existiert

    RED: Parameter existiert noch nicht → AssertionError
    """
    from providers.geosphere import GeoSphereProvider

    sig = inspect.signature(GeoSphereProvider.fetch_forecast)
    assert "enrich_ensemble" in sig.parameters, (
        "GeoSphereProvider.fetch_forecast() hat noch keinen enrich_ensemble-Parameter"
    )


# ---------------------------------------------------------------------------
# AC-5: Einetappiger Trip — kein IndexError, korrekter Waypoint
# ---------------------------------------------------------------------------

def test_ac5_single_stage_last_waypoint_resolves_correctly():
    """
    AC-5: Bei einetappigem Trip wird last_waypoint korrekt aufgeloest;
    _enrich_ensemble_for_trip laeuft ohne Fehler.

    GIVEN: Trip mit 1 Etappe und 2 Wegpunkten (Start + Ziel)
    WHEN:  trip.stages[-1].last_waypoint abgerufen + _enrich_ensemble_for_trip aufgerufen
    THEN:  Letzter Waypoint = Ziel (zweiter Waypoint); kein Fehler

    RED: AttributeError weil Methode nicht existiert
    """
    from app.trip import Trip, Stage, Waypoint
    from services.trip_report_scheduler import TripReportSchedulerService

    wp_start = Waypoint(id="g1", name="Start", lat=47.10, lon=9.20, elevation_m=500)
    wp_end = Waypoint(id="g2", name="Ziel", lat=47.30, lon=9.40, elevation_m=1200)
    stage = Stage(id="s1", name="Einzige Etappe", date=date(2026, 6, 15),
                  waypoints=[wp_start, wp_end])
    trip = Trip(id="single-stage-trip", name="Eintagestest", stages=[stage])

    assert len(trip.stages) == 1
    last_wp = trip.stages[-1].last_waypoint
    assert last_wp.id == "g2", (
        f"Letzter Waypoint sollte g2 (Ziel) sein, ist aber {last_wp.id}"
    )
    assert last_wp.lat == pytest.approx(47.30)

    svc = _make_scheduler()
    svc._enrich_ensemble_for_trip(trip=trip, weather_data=[])
