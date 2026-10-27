"""Stundenzeilen: die ALTE Reihe stammt vom Segment der Aenderung (Issue #1737, AC-1/AC-10).

Ein Trip hat zwei Segmente mit eindeutig verschiedenen Anker-Boeen im betroffenen Stundenfenster
(Segment "1": 10 km/h, Segment "2": 25 km/h, beide gruen). Die Aenderung betrifft Segment "2" -> die
"alt"-Werte der Stundenzeilen sind die von Segment "2". Gibt es fuer Segment "2" keinen Anker
(nur einen fuer Segment "1"), zeigen die Zeilen nur den neuen Wert -- ein fremdes Segment ist nie
die Alt-Reihe. Beide Faelle fordern NICHT-LEERE Zeilen (sonst waere die Aussage vakuum-gruen).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models import (
    ChangeSeverity, GPXPoint, SegmentWeatherData, SegmentWeatherSummary, TripSegment,
    WeatherChange,
)
from services.weather_snapshot import _deserialize_timeseries

UTC = timezone.utc
T0 = datetime(2026, 5, 1, 10, tzinfo=UTC)
STURM = {12: 90.0, 13: 90.0, 14: 90.0}  # frische Reihe Segment "2"
ANKER_SEG1, ANKER_SEG2 = 10.0, 25.0
FRISCH_BASIS = 10.0  # gruen; nur 12Z-14Z UTC wechseln die Stufe (-> 90 km/h)


def _segment(seg_id: str, boeen: dict[int, float], basis: float) -> SegmentWeatherData:
    rows = [{"ts": (T0 + timedelta(hours=i)).isoformat(),
             "gust_kmh": boeen.get(10 + i, basis)} for i in range(8)]
    ts = _deserialize_timeseries({"hourly": rows}, "openmeteo")
    km = 0.0 if seg_id == "1" else 6.0
    return SegmentWeatherData(
        segment=TripSegment(
            segment_id=seg_id,
            start_point=GPXPoint(lat=47.0, lon=11.0, elevation_m=1000, distance_from_start_km=km),
            end_point=GPXPoint(lat=47.05, lon=11.05, elevation_m=1500,
                               distance_from_start_km=km + 6.0),
            start_time=T0, end_time=T0 + timedelta(hours=7), duration_hours=7.0,
            distance_km=6.0, ascent_m=500, descent_m=0,
        ),
        timeseries=ts, aggregated=SegmentWeatherSummary(),
        fetched_at=datetime(2026, 5, 1, 6, tzinfo=UTC), provider="openmeteo",
    )


def _aenderung_an_segment_2() -> WeatherChange:
    return WeatherChange(
        metric="gust_max_kmh", old_value=ANKER_SEG2, new_value=90.0, delta=60.0, threshold=20.0,
        severity=ChangeSeverity.MAJOR, direction="increase", segment_id="2",
        occurred_at=T0 + timedelta(hours=2),
    )


def _zeilen(anchor_segments) -> list[tuple[str, float | None, float]]:
    from output.renderers.alert.project import to_alert_message

    frisch = [_segment("1", {}, ANKER_SEG1), _segment("2", STURM, FRISCH_BASIS)]
    msg = to_alert_message(
        [_aenderung_an_segment_2()], frisch, "Trip X", tz=UTC, stand_at="09:30",
        anchor_segments=anchor_segments,
    )
    return [(h.time, h.value_from, h.value_to) for e in msg.events for h in e.hours]


def test_alt_werte_kommen_vom_anker_des_segments_der_aenderung():
    zeilen = _zeilen([_segment("1", {}, ANKER_SEG1), _segment("2", {}, ANKER_SEG2)])
    # Ortszeit des Segments (47 N / 11 O, Mai: UTC+2) -- 12Z..14Z UTC.
    assert [t for t, _a, _n in zeilen] == ["14:00", "15:00", "16:00"], zeilen
    assert [a for _t, a, _n in zeilen] == [ANKER_SEG2] * 3, (
        f"Alt-Werte stammen nicht aus Segment 2 ({ANKER_SEG2}): {zeilen!r}")


def test_ohne_anker_fuer_das_segment_der_aenderung_nur_neuer_wert():
    zeilen = _zeilen([_segment("1", {}, ANKER_SEG1)])
    assert zeilen, "Vorbedingung: auch ohne passenden Anker entstehen Zeilen (nur neu)"
    assert all(a is None for _t, a, _n in zeilen), (
        f"ein fremdes Segment lieferte Alt-Werte: {zeilen!r}")
    assert [n for _t, _a, n in zeilen] == [90.0] * len(zeilen)
