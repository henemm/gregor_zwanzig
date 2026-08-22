"""TDD RED — Issue #2036, AC-15: das Echtheits-Flag ('gemessen, nicht
geraten') bleibt auf JEDER Zwischenstufe `True` -- Snapshot-Speichern/
-Rekonstruieren UND alle vier Alert-Event-Typen.

SPEC:    docs/specs/modules/fix_2036_alarm_kilometer_ortsangabe.md (AC-15)
KONTEXT: docs/context/fix-2036-alarm-kilometer.md

Jede Zwischenstufe wird EINZELN geprueft (nicht nur das Endergebnis) --
Nachweisführung der Spec: "Ein Test, der nur mit durchweg vorhandenen oder
durchweg fehlenden Werten arbeitet, deckt diese Unterscheidung nicht ab"
gilt sinngemaess auch hier: eine Kette, die nur am Ende prueft, kann an
JEDER Zwischenstufe still auf den Default `False` zurueckfallen, ohne dass
ein Test das bemerkt.

RED-VERTRAG: `TripSegment.distance_measured`, `AlertEvent.km_measured`,
`OnsetEvent.km_measured`, `OnsetShiftEvent.km_measured`,
`CorridorEvent.km_measured` existieren heute nicht. Jede Konstruktion mit
diesen Schluesselworten schlaegt mit `TypeError` fehl -- das IST der
RED-Zustand.
"""
from __future__ import annotations

from datetime import datetime, timezone

UTC = timezone.utc
TZ_VIENNA = __import__("zoneinfo").ZoneInfo("Europe/Vienna")


def _measured_segment(segment_id="3", km_from=12.0, km_to=20.0):
    from app.models import GPXPoint, TripSegment

    start = GPXPoint(lat=46.6, lon=12.9, elevation_m=1900.0,
                      distance_from_start_km=km_from)
    end = GPXPoint(lat=46.6, lon=12.9, elevation_m=1900.0,
                    distance_from_start_km=km_to)
    try:
        return TripSegment(
            segment_id=segment_id, start_point=start, end_point=end,
            start_time=datetime(2026, 7, 1, 6, 0, tzinfo=UTC),
            end_time=datetime(2026, 7, 1, 8, 0, tzinfo=UTC),
            duration_hours=2.0, distance_km=km_to - km_from,
            ascent_m=200.0, descent_m=50.0, distance_measured=True,
        )
    except TypeError as exc:
        raise AssertionError(
            "TripSegment traegt kein additives 'distance_measured'-Feld "
            f"(Spec, models.py). Urspruenglicher Fehler: {exc}"
        ) from exc


# ---------------------------------------------------------------------------
# AC-15a — weather_snapshot: Speichern und Rekonstruieren
# ---------------------------------------------------------------------------

def test_ac15_flag_ueberlebt_snapshot_serialisierung():
    """AC-15 (Zwischenstufe 1/2): `_serialize_segment()` schreibt das Flag
    in das Snapshot-Dict."""
    from app.models import SegmentWeatherData, SegmentWeatherSummary
    from services.weather_snapshot import _serialize_segment

    seg = _measured_segment()
    swd = SegmentWeatherData(
        segment=seg, timeseries=None,
        aggregated=SegmentWeatherSummary(gust_max_kmh=80.0),
        fetched_at=datetime(2026, 7, 1, 6, 0, tzinfo=UTC), provider="openmeteo",
    )
    entry = _serialize_segment(swd)

    assert entry.get("distance_measured") is True, (
        f"Serialisiertes Segment traegt das Flag nicht: {entry!r}"
    )


def test_ac15_flag_ueberlebt_snapshot_rekonstruktion():
    """AC-15 (Zwischenstufe 2/2): `_reconstruct_segment()` liest das Flag aus
    dem Snapshot-Dict zurueck in ein `TripSegment`."""
    from services.weather_snapshot import _reconstruct_segment

    seg_data = {
        "segment_id": "3", "start_time": "2026-07-01T06:00:00+00:00",
        "end_time": "2026-07-01T08:00:00+00:00",
        "start_lat": 46.6, "start_lon": 12.9, "start_elevation_m": 1900.0,
        "start_distance_from_start_km": 12.0,
        "end_lat": 46.6, "end_lon": 12.9, "end_elevation_m": 1900.0,
        "end_distance_from_start_km": 20.0,
        "distance_km": 8.0, "ascent_m": 200.0, "descent_m": 50.0,
        "distance_measured": True,
    }
    segment = _reconstruct_segment(seg_data)

    assert getattr(segment, "distance_measured", None) is True, (
        f"Rekonstruiertes Segment traegt das Flag nicht: "
        f"{getattr(segment, 'distance_measured', None)!r}"
    )


# ---------------------------------------------------------------------------
# AC-15b — vier Alert-Event-Typen: das Flag kommt bis zum Renderer durch
# ---------------------------------------------------------------------------

def test_ac15_alertevent_traegt_das_flag_aus_der_echten_projektion():
    """AC-15 (AlertEvent, ueber `to_alert_message`): ein vermessenes
    Segment ergibt ein `AlertEvent` mit `km_measured=True` -- nicht nur bei
    direkter Konstruktion, sondern aus der PRODUKTIONS-Projektion."""
    from app.models import ChangeSeverity, WeatherChange
    from output.renderers.alert.project import to_alert_message

    seg = _measured_segment(segment_id="3")
    from app.models import SegmentWeatherData, SegmentWeatherSummary
    swd = SegmentWeatherData(
        segment=seg, timeseries=None,
        aggregated=SegmentWeatherSummary(gust_max_kmh=80.0),
        fetched_at=datetime(2026, 7, 1, 6, 0, tzinfo=UTC), provider="openmeteo",
    )
    change = WeatherChange(
        metric="gust_max_kmh", old_value=30.0, new_value=80.0, delta=50.0,
        threshold=20.0, severity=ChangeSeverity.MODERATE, direction="increase",
        segment_id="3", occurred_at=datetime(2026, 7, 1, 14, 0, tzinfo=UTC),
    )
    msg = to_alert_message([change], [swd], "TDD-AC15", tz=TZ_VIENNA, stand_at="10:00")

    assert len(msg.events) == 1, f"Erwartete ein Event, erhielt: {msg.events!r}"
    event = msg.events[0]
    assert getattr(event, "km_measured", None) is True, (
        f"AlertEvent aus to_alert_message() traegt km_measured nicht: "
        f"{getattr(event, 'km_measured', None)!r}"
    )


def test_ac15_onsetevent_traegt_das_flag():
    """AC-15 (OnsetEvent): additives Feld, analog `segment_id`
    (`test_alert_location_vocabulary.py`-RED-Vertrag Punkt 1) -- der
    Nowcast-Pfad konstruiert `OnsetEvent` direkt, ohne Projektionsfunktion."""
    from output.renderers.alert.model import OnsetEvent

    try:
        event = OnsetEvent(
            onset_minutes=8, onset_time="14:08", km_from=12.0, km_to=20.0,
            is_convective=True, intensity_label="kraeftiger Regen",
            source_label="Radar (GeoSphere INCA)", segment_id="3",
            km_measured=True,
        )
    except TypeError as exc:
        raise AssertionError(
            "OnsetEvent traegt kein additives 'km_measured'-Feld "
            f"(Spec, model.py). Urspruenglicher Fehler: {exc}"
        ) from exc

    assert event.km_measured is True


def test_ac15_onsetshiftevent_traegt_das_flag_aus_der_echten_projektion():
    """AC-15 (OnsetShiftEvent, ueber `to_alert_message`s Onset-Zweig): eine
    Beginn-Verschiebung auf einem vermessenen Segment ergibt ein
    `OnsetShiftEvent` mit `km_measured=True`."""
    from app.models import ChangeSeverity, SegmentWeatherData, \
        SegmentWeatherSummary, WeatherChange
    from output.renderers.alert.project import to_alert_message

    seg = _measured_segment(segment_id="3")
    swd = SegmentWeatherData(
        segment=seg, timeseries=None,
        aggregated=SegmentWeatherSummary(gust_max_kmh=80.0),
        fetched_at=datetime(2026, 7, 1, 6, 0, tzinfo=UTC), provider="openmeteo",
    )
    now = datetime(2026, 7, 1, 12, 0, tzinfo=UTC).timestamp()
    later = datetime(2026, 7, 1, 14, 0, tzinfo=UTC).timestamp()
    change = WeatherChange(
        metric="thunder_onset_utc", old_value=now, new_value=later,
        delta=later - now, threshold=1800.0, severity=ChangeSeverity.MODERATE,
        direction="increase", segment_id="3",
        occurred_at=datetime(2026, 7, 1, 14, 0, tzinfo=UTC),
    )
    msg = to_alert_message([change], [swd], "TDD-AC15", tz=TZ_VIENNA, stand_at="10:00")

    assert len(msg.onset_shift_events) == 1, (
        f"Erwartete ein OnsetShiftEvent, erhielt: {msg.onset_shift_events!r}"
    )
    oe = msg.onset_shift_events[0]
    assert getattr(oe, "km_measured", None) is True, (
        f"OnsetShiftEvent aus to_alert_message() traegt km_measured nicht: "
        f"{getattr(oe, 'km_measured', None)!r}"
    )


def test_ac15_corridorevent_traegt_das_flag_aus_der_echten_projektion():
    """AC-15 (CorridorEvent, ueber `to_corridor_events`): ein Schwellen-
    Treffer auf einem vermessenen Segment ergibt ein `CorridorEvent` mit
    `km_measured=True`."""
    from output.renderers.alert.project import to_corridor_events
    from services.corridor_threshold import CorridorHit

    seg = _measured_segment(segment_id="3")
    hit = CorridorHit(
        metric="wind_gust", value=90.0, bound=70.0, direction="above",
        segment_id="3", occurred_at=datetime(2026, 7, 1, 14, 0, tzinfo=UTC),
    )
    events = to_corridor_events([hit], [seg], tz=TZ_VIENNA)

    assert len(events) == 1, f"Erwartete ein CorridorEvent, erhielt: {events!r}"
    ce = events[0]
    assert getattr(ce, "km_measured", None) is True, (
        f"CorridorEvent aus to_corridor_events() traegt km_measured nicht: "
        f"{getattr(ce, 'km_measured', None)!r}"
    )


def test_ac15_flag_erreicht_am_ende_auch_den_renderer():
    """AC-15 (End-zu-End-Nachweis): dasselbe vermessene AlertEvent zeigt am
    Renderer die km-Angabe -- das Flag ist nicht nur auf dem Datenmodell
    gesetzt, sondern WIRKT auch (Leitfrage aus CLAUDE.md: 'Ist die
    Zusicherung an der Stelle geprueft, an der sie WIRKT?')."""
    from output.renderers.alert.model import AlertEvent, AlertMessage
    from output.renderers.alert.render import render_sms

    try:
        event = AlertEvent(
            metric_id="gust", value_from=30.0, value_to=80.0, threshold=20.0,
            cmp="über", occurred_at="11:00", km_from=12.0, km_to=20.0,
            segment_id="3", km_measured=True,
        )
    except TypeError as exc:
        raise AssertionError(
            f"AlertEvent traegt kein additives 'km_measured'-Feld: {exc}"
        ) from exc
    msg = AlertMessage(trip_short="TDD", stand_at="10:00", events=(event,), source=None)

    sms = render_sms(msg)
    assert "km 12-20" in sms, f"Flag wirkt nicht am Renderer: {sms!r}"
