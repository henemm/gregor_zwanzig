"""TDD — Issue #823: Alert-Pfad bevorzugt datierten Snapshot (heute) vor undatiertem.

Nach dem Abend-Briefing zeigt {trip_id}.json auf target_date=morgen. Der Alert-Dienst
darf NICHT diesen Snapshot als Referenz verwenden — er muss den datierten
{trip_id}_{heute}.json laden. Nur so vergleicht er heutige Nowcast-Daten gegen
die heutige Etappe.

Drei Tests — alle ohne Mocks (CLAUDE.md):
- dated_snapshot_preferred_over_undated: dated vorhanden → dated wird zurückgegeben
- undated_fallback_when_no_dated_exists: kein dated → undated wird zurückgegeben
- evening_briefing_stale_snapshot_does_not_trigger_false_alert: E2E-Szenario,
  kein Alert auf Basis von morgen-Daten
"""
from __future__ import annotations

import shutil
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from app.models import (
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    TripReportConfig,
    TripSegment,
)
from app.trip import Stage, Trip, Waypoint


# ────────────────────────── Fixtures ────────────────────────────────────────

@pytest.fixture()
def clean_user_dirs():
    created: list[str] = []

    def _register(user_id: str) -> str:
        created.append(user_id)
        path = Path(f"data/users/{user_id}")
        if path.exists():
            shutil.rmtree(path)
        return user_id

    yield _register

    for user_id in created:
        path = Path(f"data/users/{user_id}")
        if path.exists():
            shutil.rmtree(path)


# ────────────────────────── Helpers ─────────────────────────────────────────

def _segment(segment_id: int = 1) -> TripSegment:
    start = datetime(2026, 4, 5, 8, 0, tzinfo=timezone.utc)
    end = datetime(2026, 4, 5, 12, 0, tzinfo=timezone.utc)
    return TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=47.0, lon=11.0, elevation_m=1000, distance_from_start_km=0.0),
        end_point=GPXPoint(lat=47.1, lon=11.1, elevation_m=1500, distance_from_start_km=6.0),
        start_time=start,
        end_time=end,
        duration_hours=4.0,
        distance_km=6.0,
        ascent_m=500,
        descent_m=0,
    )


def _segment_data(segment_id: int = 1, precip: float = 2.0) -> SegmentWeatherData:
    return SegmentWeatherData(
        segment=_segment(segment_id),
        timeseries=NormalizedTimeseries(
            meta=ForecastMeta(provider=Provider.OPENMETEO, model="test", grid_res_km=1.0),
            data=[],
        ),
        aggregated=SegmentWeatherSummary(precip_sum_mm=precip),
        fetched_at=datetime.now(timezone.utc),
        provider="openmeteo",
    )


def _two_day_trip(trip_id: str, today: date) -> Trip:
    tomorrow = date.fromordinal(today.toordinal() + 1)
    stage_today = Stage(
        id="D1", name="Tag 1", date=today,
        waypoints=[Waypoint(id="W1", name="Start", lat=47.0, lon=11.0, elevation_m=1000.0)],
    )
    stage_tomorrow = Stage(
        id="D2", name="Tag 2", date=tomorrow,
        waypoints=[Waypoint(id="W2", name="Ziel", lat=47.2, lon=11.2, elevation_m=1200.0)],
    )
    trip = Trip(id=trip_id, name="Mehrtages-Trip", stages=[stage_today, stage_tomorrow])
    trip.report_config = TripReportConfig(
        trip_id=trip_id,
        send_email=False,
        send_telegram=True,
        alert_on_changes=True,
    )
    return trip


# ────────────────────────── Tests ───────────────────────────────────────────

def test_dated_snapshot_preferred_over_undated(clean_user_dirs):
    """dated_snapshot_preferred_over_undated — AC-1 Bug #823:
    Wenn ein datierter Snapshot für heute existiert, wird dieser zurückgegeben —
    nicht der undatierte (der nach Abend-Briefing auf morgen zeigen kann)."""
    from services.trip_alert import TripAlertService
    from services.weather_snapshot import WeatherSnapshotService

    user_id = clean_user_dirs("tdd-823-ac1")
    today = date.today()
    trip_id = "trip-823-ac1"

    svc = WeatherSnapshotService(user_id=user_id)

    # Undatierter Snapshot: simuliert Abend-Briefing mit morgen-Daten (hohes Regen)
    svc.save(trip_id, [_segment_data(precip=20.0)], date.fromordinal(today.toordinal() + 1))

    # Datierter Snapshot für heute: korrekte Referenz (wenig Regen)
    svc.save_dated(trip_id, today, [_segment_data(precip=2.0)])

    trip = _two_day_trip(trip_id, today)
    alert_svc = TripAlertService(settings=None, user_id=user_id)
    result = alert_svc._get_cached_weather(trip)

    assert result is not None, "Snapshot nicht geladen"
    assert len(result) == 1
    actual_precip = result[0].aggregated.precip_sum_mm
    assert actual_precip == pytest.approx(2.0), (
        f"Alert-Pfad hat den undatierten (Abend-Briefing-)Snapshot geladen "
        f"(precip={actual_precip}) statt dem datierten für heute (precip=2.0). "
        f"Ursache: _get_cached_weather() ruft load() statt load_dated(today)."
    )


def test_undated_fallback_when_no_dated_exists(clean_user_dirs):
    """undated_fallback_when_no_dated_exists — AC-2 Bug #823:
    Wenn kein datierter Snapshot für heute existiert, wird der undatierte
    geladen (Rückwärts-Kompatibilität / Erster Tag ohne Morgen-Briefing)."""
    from services.trip_alert import TripAlertService
    from services.weather_snapshot import WeatherSnapshotService

    user_id = clean_user_dirs("tdd-823-ac2")
    today = date.today()
    trip_id = "trip-823-ac2"

    svc = WeatherSnapshotService(user_id=user_id)
    # Nur undatierter Snapshot vorhanden (kein dated)
    svc.save(trip_id, [_segment_data(precip=5.0)], today)

    trip = _two_day_trip(trip_id, today)
    alert_svc = TripAlertService(settings=None, user_id=user_id)
    result = alert_svc._get_cached_weather(trip)

    assert result is not None, "Fallback auf undatierten Snapshot schlug fehl"
    assert result[0].aggregated.precip_sum_mm == pytest.approx(5.0)


def test_evening_briefing_stale_snapshot_does_not_trigger_false_alert(clean_user_dirs):
    """evening_briefing_stale_snapshot_does_not_trigger_false_alert — AC-3 Bug #823:
    Abend-Briefing überschreibt {trip_id}.json mit morgen-Daten (hohes Regen).
    Ein Alert-Lauf danach darf KEINEN Alert auslösen, wenn der Nowcast für heute
    mit dem datierten Snapshot übereinstimmt (kein Δ auf der heutigen Etappe).

    Ohne Fix würde der Alert den undatierten Snapshot (morgen, 20 mm) laden und
    gegen frischen Nowcast (2 mm) vergleichen → fälschlich Δ=18 mm → Alert.
    Mit Fix wird der datierte Snapshot (heute, 2 mm) geladen → Δ=0 → kein Alert.
    """
    from app.config import Settings
    from services.trip_alert import TripAlertService
    from services.weather_snapshot import WeatherSnapshotService

    user_id = clean_user_dirs("tdd-823-ac3")
    today = date.today()
    trip_id = "trip-823-ac3"

    svc = WeatherSnapshotService(user_id=user_id)

    # Datierter Snapshot für heute: Referenz 2 mm (entspricht dem Morgen-Briefing)
    today_data = [_segment_data(precip=2.0)]
    svc.save_dated(trip_id, today, today_data)

    # Abend-Briefing überschreibt undatierten Snapshot mit morgen-Daten (20 mm)
    tomorrow = date.fromordinal(today.toordinal() + 1)
    svc.save(trip_id, [_segment_data(precip=20.0)], tomorrow)

    # Frischer Nowcast für heute: 2 mm (kein Δ zur heutigen Referenz)
    fresh_data = [_segment_data(precip=2.0)]

    settings = Settings(
        telegram_bot_token="dummy-token",
        telegram_chat_id="dummy-chat",
    )
    trip = _two_day_trip(trip_id, today)
    trip.alert_cooldown_minutes = 0

    cached = TripAlertService(settings=settings, user_id=user_id)._get_cached_weather(trip)
    assert cached is not None

    alert_svc = TripAlertService(settings=settings, user_id=user_id)
    alert_fired = alert_svc.check_and_send_alerts(trip, cached, fresh_weather=fresh_data)

    assert not alert_fired, (
        "Falscher Alert: Der Alert-Pfad benutzte den undatierten Snapshot "
        "(Abend-Briefing, morgen, 20 mm) statt des datierten für heute (2 mm). "
        "Δ=18 mm löste fälschlicherweise einen Alert aus. "
        "Fix: _get_cached_weather() muss load_dated(today) bevorzugen."
    )
