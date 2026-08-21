"""TDD RED — Issue #2036, AC-3: amtliche Warnungen sprechen dieselbe
gemessene Ortssprache wie Nowcast- und Abweichungsalarm.

SPEC:    docs/specs/modules/fix_2036_alarm_kilometer_ortsangabe.md (AC-3)
KONTEXT: docs/context/fix-2036-alarm-kilometer.md

`official_alerts.py` baut seine Ortsangabe heute UNABHAENGIG von
`segments.format_alert_location()` -- ueber einen eigenen, zweiten
Formatierer (`format_segment_reference()` + eigene 'Segment '->'Seg '-
Ersetzung, official_alerts.py:2180-2184). Die Teilungs-Invariante aus
#1744 (`test_alert_location_vocabulary.py:296-298`) verlangt Gleichheit
zwischen allen drei Alarmarten -- diese Spec speist `official_alerts.py`
deshalb ueber einen additiven Parameter `segment_km` aus DERSELBEN Quelle.

RED-VERTRAG: `build_official_alert_notices()` kennt heute KEIN `segment_km`-
Schluesselwort. Der Aufruf mit diesem Parameter schlaegt mit
`TypeError: unexpected keyword argument 'segment_km'` fehl -- das IST der
RED-Zustand.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

UTC = timezone.utc
TRIP_TZ = ZoneInfo("Europe/Vienna")
TRIP_NAME = "KHW 403"
WARN_FROM = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)
WARN_TO = datetime(2026, 7, 1, 20, 0, tzinfo=UTC)


def _trip(waypoint_count: int = 10):
    """Trip mit `waypoint_count` Wegpunkten -> Segmente '1'..'N-1' + 'Ziel'.
    Zehn Wegpunkte verhindern die 'gesamte Route'-Verdichtung (Vorbild
    `test_alert_location_vocabulary.py::_trip`)."""
    from app.trip import Stage, Trip, Waypoint

    waypoints = [
        Waypoint(id=f"w{i}", name=f"P{i}", lat=46.6 + i / 100, lon=12.9 + i / 100,
                 elevation_m=1900.0 + i)
        for i in range(waypoint_count)
    ]
    stage = Stage(id="s1", name="Tag 1", date=date(2026, 7, 1), waypoints=waypoints)
    return Trip(id="tdd-2036-official", name=TRIP_NAME, stages=[stage])


def _official_notice_scope_label(segment_id: str, km_from: float, km_to: float) -> str:
    """Baut EINE amtliche Warnung fuer `segment_id` mit einer gemessenen
    km-Spanne ueber den additiven `segment_km`-Parameter und liefert das
    entstehende `scope_label` (die Ortsangabe der amtlichen Warnung)."""
    from output.renderers.alert.official_alerts import build_official_alert_notices
    from services.official_alerts.models import OfficialAlert

    alert = OfficialAlert(
        source="geosphere_warn", hazard="thunderstorm", level=2, label="Gewitter",
        valid_from=WARN_FROM, valid_to=WARN_TO, region_label="Kaernten",
    )
    try:
        notices = build_official_alert_notices(
            _trip(), [(alert, [segment_id])],
            segment_km={segment_id: (km_from, km_to)},
        )
    except TypeError as exc:
        raise AssertionError(
            "build_official_alert_notices() kennt keinen additiven "
            "'segment_km'-Parameter (Spec Implementation Details, "
            "'Amtliche Warnungen teilen dieselbe Aufloesung'). "
            f"Urspruenglicher Fehler: {exc}"
        ) from exc
    assert len(notices) == 1, f"Erwartete genau eine Notice, erhielt: {notices!r}"
    return notices[0].scope_label


def _delta_subject_location(segment_id: str, km_from: float, km_to: float) -> str:
    """Ortsangabe des Trip-Abweichungsalarms fuer dasselbe Segment, ueber
    die echte Projektion (`to_alert_message`) -- Vorbild
    `test_alert_location_vocabulary.py::_delta_message`."""
    import re

    from app.models import ChangeSeverity, GPXPoint, SegmentWeatherData, \
        SegmentWeatherSummary, TripSegment, WeatherChange
    from output.renderers.alert.project import to_alert_message
    from output.renderers.alert.render import render_subject

    start = GPXPoint(lat=46.6, lon=12.9, elevation_m=1900.0,
                      distance_from_start_km=km_from)
    end = GPXPoint(lat=46.6, lon=12.9, elevation_m=1900.0,
                   distance_from_start_km=km_to)
    try:
        seg = TripSegment(
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
    swd = SegmentWeatherData(
        segment=seg, timeseries=None,
        aggregated=SegmentWeatherSummary(gust_max_kmh=80.0),
        fetched_at=datetime(2026, 7, 1, 6, 0, tzinfo=UTC), provider="openmeteo",
    )
    change = WeatherChange(
        metric="gust_max_kmh", old_value=30.0, new_value=80.0, delta=50.0,
        threshold=20.0, severity=ChangeSeverity.MODERATE, direction="increase",
        segment_id=segment_id, occurred_at=datetime(2026, 7, 1, 14, 0, tzinfo=UTC),
    )
    msg = to_alert_message([change], [swd], TRIP_NAME, tz=TRIP_TZ, stand_at="10:00")
    subject = render_subject(msg)
    match = re.match(r"^\[[^\]]*\]\s+(?P<where>.+?)\s+·\s+.+$", subject)
    assert match, f"Betreff hat nicht die Bauform '[Trip] <Ort> · <Kern>': {subject!r}"
    return match.group("where")


def test_ac3_amtliche_warnung_und_abweichungsalarm_zeigen_dieselbe_km_spanne():
    """AC-3: Given Nowcast-Alarm, Abweichungsalarm und amtliche Warnung
    beziehen sich auf dasselbe vermessene Segment / When alle Alarmarten
    ihre Ortsangabe rendern / Then zeigen sie identisch 'km A-B'
    (Ratschen-Test `test_alert_location_vocabulary.py:296-298` verlangt
    Gleichheit ueber alle drei Alarmarten)."""
    from output.renderers.alert.segments import format_alert_location

    segment_id, km_from, km_to = "3", 12.31, 20.0

    direct = format_alert_location(None, [segment_id], km_from, km_to, km_measured=True)
    official = _official_notice_scope_label(segment_id, km_from, km_to)
    delta = _delta_subject_location(segment_id, km_from, km_to)

    assert direct == "km 12-20", f"Direkte Aufloesung: {direct!r}"
    assert official == direct, (
        f"Amtliche Warnung {official!r} != gemeinsame Aufloesung {direct!r}"
    )
    assert delta == direct, (
        f"Abweichungsalarm {delta!r} != gemeinsame Aufloesung {direct!r}"
    )


def test_ac3_amtliche_warnung_faellt_ohne_segment_km_weiterhin_auf_segmentsprache_zurueck():
    """AC-3 (Negativfall, Fallback-Garantie): traegt der additive
    `segment_km`-Parameter fuer eine Segment-Kennung KEINEN Eintrag, bleibt
    die amtliche Warnung bei der heutigen Segment-Sprache ('Segment N') --
    kein zweiter, unabhaengiger Auflösungspfad, keine geratene km-Angabe."""
    from output.renderers.alert.official_alerts import build_official_alert_notices
    from services.official_alerts.models import OfficialAlert

    alert = OfficialAlert(
        source="geosphere_warn", hazard="thunderstorm", level=2, label="Gewitter",
        valid_from=WARN_FROM, valid_to=WARN_TO, region_label="Kaernten",
    )
    try:
        notices = build_official_alert_notices(
            _trip(), [(alert, ["3"])], segment_km={},
        )
    except TypeError as exc:
        raise AssertionError(
            "build_official_alert_notices() kennt keinen additiven "
            f"'segment_km'-Parameter. Urspruenglicher Fehler: {exc}"
        ) from exc

    assert notices[0].scope_label == "Segment 3", (
        f"Ohne Eintrag in segment_km muss die Segment-Sprache stehen bleiben: "
        f"{notices[0].scope_label!r}"
    )
