"""Wächter für die Richtungs-Auflösung der Alarm-Metrik (Issue #3026,
Nebenbefund F001 aus #2783).

SPEC: docs/specs/fast/test-3026-cmp-ueber-waechter.md (AC-1..AC-3)

`temp_min_c` ist das einzige mehrdeutige Feld im Metrik-Katalog: es gehört
zu `temperature` (cmp „über“) UND zu `temperature_cold` (cmp „unter“).
`_resolve_metric_id` (`output/renderers/alert/project.py`) entscheidet per
Richtung des Δ-Ereignisses. Bisher bewacht kein Test, dass `increase` die
„über“-Seite trifft -- die Mutation `"über"` → `"ueber"` blieb unbemerkt.

Kern-Schicht: deterministisch, keine Mocks, kein Netz. Geprüft wird am
öffentlichen Weg `to_alert_message()` (dort WIRKT die Auflösung: das
`AlertEvent` trägt `metric_id` und `cmp`) und zusätzlich an der Funktion.

Charakterisierungstest: der Produktionscode ist korrekt, RED-Nachweis ist
die Mutations-Gegenprobe (AC-3).
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from app.ampel import resolve_ampel
from app.metric_catalog import get_metric
from app.models import (
    ChangeSeverity,
    GPXPoint,
    SegmentWeatherData,
    SegmentWeatherSummary,
    TripSegment,
    WeatherChange,
)
from output.renderers.alert.project import _resolve_metric_id, to_alert_message

UTC = timezone.utc
TRIP_TZ = ZoneInfo("Europe/Vienna")


def _segment_weather() -> SegmentWeatherData:
    seg = TripSegment(
        segment_id="1",
        start_point=GPXPoint(lat=46.6, lon=12.9, elevation_m=1900.0,
                             distance_from_start_km=0.0),
        end_point=GPXPoint(lat=46.7, lon=13.0, elevation_m=2100.0,
                           distance_from_start_km=6.0),
        start_time=datetime(2026, 7, 1, 6, 0, tzinfo=UTC),
        end_time=datetime(2026, 7, 1, 9, 0, tzinfo=UTC),
        duration_hours=3.0, distance_km=6.0, ascent_m=200.0, descent_m=0.0,
    )
    return SegmentWeatherData(
        segment=seg, timeseries=None,
        aggregated=SegmentWeatherSummary(temp_min_c=2.0),
        fetched_at=datetime(2026, 7, 1, 6, 0, tzinfo=UTC), provider="openmeteo",
    )


def _delta_change(direction: str, old: float, new: float) -> WeatherChange:
    """Δ-Ereignis (ohne Ampel-Art) auf dem mehrdeutigen Feld `temp_min_c`."""
    return WeatherChange(
        metric="temp_min_c", old_value=old, new_value=new, delta=new - old,
        threshold=3.0, severity=ChangeSeverity.MODERATE, direction=direction,
        segment_id="1", occurred_at=datetime(2026, 7, 1, 7, 0, tzinfo=UTC),
    )


def _event_for(direction: str, old: float, new: float):
    msg = to_alert_message(
        [_delta_change(direction, old, new)], [_segment_weather()], "Testtrip",
        tz=TRIP_TZ, stand_at="10:00", ampel=resolve_ampel(None),
    )
    assert len(msg.events) == 1, f"Fixtur-Schutz: genau ein Ereignis erwartet, {msg.events!r}"
    return msg.events[0]


def test_ac1_steigende_tiefsttemperatur_traegt_temperature_mit_cmp_ueber():
    """AC-1: Δ `increase` auf `temp_min_c` → Metrik `temperature`, cmp „über“."""
    ev = _event_for("increase", 2.0, 8.0)
    assert ev.metric_id == "temperature"
    assert ev.cmp == "über"


def test_ac2_fallende_tiefsttemperatur_traegt_temperature_cold_mit_cmp_unter():
    """AC-2: Δ `decrease` auf `temp_min_c` → Metrik `temperature_cold`, cmp „unter“."""
    ev = _event_for("decrease", 8.0, 2.0)
    assert ev.metric_id == "temperature_cold"
    assert ev.cmp == "unter"


@pytest.mark.parametrize(
    ("direction", "erwartete_metrik", "erwarteter_cmp"),
    [("increase", "temperature", "über"), ("decrease", "temperature_cold", "unter")],
)
def test_resolve_metric_id_waehlt_die_seite_nach_richtung(
    direction, erwartete_metrik, erwarteter_cmp,
):
    """Funktion direkt: gewählte Metrik und deren Katalog-cmp passen zur Richtung."""
    metric_id = _resolve_metric_id("temp_min_c", direction)
    assert metric_id == erwartete_metrik
    assert get_metric(metric_id).cmp == erwarteter_cmp
