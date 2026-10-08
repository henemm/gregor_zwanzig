"""Rueckbau Korridor-/Grenzwert-Alarmpfad (#2230): die Alarm-Ausgaben bleiben
byte-gleich, der tote Pfad ist weg.

SPEC: docs/specs/modules/rework_2230_corridor_path_removal.md (AC-1..AC-3)

AC-3: Die Golden-Fixtures unter `tests/fixtures/alert_corridor_removal_2230/`
wurden VOR dem Rueckbau mit den echten Renderern aufgezeichnet
(`build_messages()` + `render_all()` unten) und werden nie nachtraeglich
regeneriert. Kein Mock, kein Netz.

AC-1/AC-2: Import- und Signatur-Pruefung am echten Modul (kein
Dateiinhalt-Check).
"""
from __future__ import annotations

import dataclasses
import importlib
import inspect
import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from app.models import (
    ChangeSeverity, Corridor, GPXPoint, SegmentWeatherData,
    SegmentWeatherSummary, TripSegment, WeatherChange,
)
from app.trip import Stage, Trip, Waypoint
from output.renderers.alert import model as alert_model
from output.renderers.alert import project as alert_project
from output.renderers.alert import render as alert_render
from output.renderers.alert.project import to_alert_message
from output.renderers.alert.render import (
    render_email, render_sms, render_subject, render_telegram,
)

UTC = timezone.utc
TZ = ZoneInfo("Europe/Vienna")
FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "alert_corridor_removal_2230"


# ---------------------------------------------------------------------------
# Eingaben (echte DTOs, feste Zeiten -> deterministisch)
# ---------------------------------------------------------------------------

def _trip_with_corridors() -> Trip:
    """Trip mit gespeicherten Wertebereichen (notify + mark) -- sie duerfen
    die Alarm-Ausgabe nicht beeinflussen."""
    stage = Stage(
        id="ST1", name="Etappe 1", date=datetime(2026, 5, 1).date(),
        waypoints=[
            Waypoint(id="W1", name="Start", lat=47.0, lon=11.0, elevation_m=1000),
            Waypoint(id="W2", name="Ziel", lat=47.1, lon=11.1, elevation_m=1500),
        ],
    )
    return Trip(
        id="golden-2230", name="Golden Korridor Trip", stages=[stage],
        corridors=[
            Corridor(metric="wind_gust", range=[None, 60.0], notify=True, mark=True),
            Corridor(metric="thunder_level", range=[None, 1.0], notify=True, mark=True),
            Corridor(metric="visibility", range=[500.0, None], notify=True, mark=True),
            Corridor(metric="temperature_min", range=[0.0, 20.0], notify=True, mark=True),
        ],
    )


def _segment(seg_id: str, lat: float, lon: float, km0: float, km1: float,
             h0: int, h1: int) -> SegmentWeatherData:
    seg = TripSegment(
        segment_id=seg_id,
        start_point=GPXPoint(lat=lat, lon=lon, elevation_m=1000, distance_from_start_km=km0),
        end_point=GPXPoint(lat=lat + 0.05, lon=lon + 0.05, elevation_m=1500,
                           distance_from_start_km=km1),
        start_time=datetime(2026, 5, 1, h0, 0, tzinfo=UTC),
        end_time=datetime(2026, 5, 1, h1, 0, tzinfo=UTC),
        duration_hours=float(h1 - h0), distance_km=km1 - km0,
        ascent_m=500, descent_m=0,
    )
    return SegmentWeatherData(
        segment=seg, timeseries=None, aggregated=SegmentWeatherSummary(),
        fetched_at=datetime(2026, 5, 1, 6, 0, tzinfo=UTC), provider="openmeteo",
    )


def _change(metric, old, new, thr, direction, seg_id, hour,
            sev=ChangeSeverity.MAJOR) -> WeatherChange:
    return WeatherChange(
        metric=metric, old_value=old, new_value=new, delta=new - old,
        threshold=thr, severity=sev, direction=direction, segment_id=seg_id,
        occurred_at=datetime(2026, 5, 1, hour, 0, tzinfo=UTC),
    )


def build_messages() -> dict:
    """Drei reale Alarm-Nachrichten ueber die echte Projektion."""
    trip = _trip_with_corridors()
    segments = [
        _segment("1", 47.0, 11.0, 0.0, 6.0, 8, 12),
        _segment("2", 47.1, 11.1, 6.0, 14.0, 12, 16),
    ]
    mixed = [
        _change("gust_max_kmh", 40.0, 85.0, 20.0, "increase", "1", 10),
        _change("thunder_level_max", 0.0, 2.0, 1.0, "increase", "2", 14),
        _change("visibility_min_m", 3000.0, 300.0, 500.0, "decrease", "2", 15),
        _change("precip_sum_mm", 1.0, 14.0, 10.0, "increase", "1", 11),
        _change("temp_min_c", 8.0, -2.0, 5.0, "decrease", "1", 9),
    ]
    onset = [_change(
        "thunder_onset_utc",
        datetime(2026, 5, 1, 13, 0, tzinfo=UTC).timestamp(),
        datetime(2026, 5, 1, 15, 0, tzinfo=UTC).timestamp(),
        3600.0, "increase", "2", 15,
    )]
    single = [_change("gust_max_kmh", 30.0, 72.0, 20.0, "increase", "1", 10)]
    now = datetime(2026, 5, 1, 7, 30, tzinfo=UTC)
    return {
        "mixed_plain": to_alert_message(
            mixed, segments, trip.name, tz=TZ, stand_at="09:30"),
        "mixed_bezug": to_alert_message(
            mixed + onset, segments, trip.name, tz=TZ, stand_at="09:30",
            reference_at="So 06:00", now_utc=now, stage_number=3),
        "single_bezug": to_alert_message(
            single, segments, trip.name, tz=TZ, stand_at="09:30",
            reference_at="So 06:00", now_utc=now, stage_number=3),
    }


def render_all(msg) -> dict:
    html, plain = render_email(msg)
    sms = render_sms(msg)
    return {
        "subject": render_subject(msg), "email_html": html, "email_plain": plain,
        "telegram": render_telegram(msg), "sms": sms,
        # Premium-SMS verschickt denselben Kurztext wie die SMS
        # (`NotificationService._dispatch_alert_message`: `body=sms_body`).
        "premium_sms": sms,
    }


# ---------------------------------------------------------------------------
# AC-3 -- Byte-Gleichheit gegen die vor dem Rueckbau aufgezeichneten Fixtures
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["mixed_plain", "mixed_bezug", "single_bezug"])
def test_ac3_alarm_ausgaben_byte_gleich_zu_golden_fixtures(name):
    golden = json.loads((FIXTURE_DIR / f"{name}.json").read_text(encoding="utf-8"))
    ist = render_all(build_messages()[name])
    assert set(ist) == set(golden)
    for kanal, text in ist.items():
        assert text == golden[kanal], f"AC-3: Kanal {kanal!r} weicht vom Golden-Fixture ab"


def test_ac3_fixtures_sind_nicht_leer():
    golden = json.loads((FIXTURE_DIR / "mixed_bezug.json").read_text(encoding="utf-8"))
    assert all(golden[k] for k in golden)


# ---------------------------------------------------------------------------
# AC-1 / AC-2 -- der tote Pfad existiert nicht mehr
# ---------------------------------------------------------------------------

def test_ac1_modul_corridor_threshold_ist_weg():
    with pytest.raises(ImportError):
        importlib.import_module("services.corridor_threshold")


def test_ac1_corridor_hits_parameter_existiert_nirgends():
    from services.notification_service import NotificationService
    from services.trip_alert import TripAlertService

    for fn in (
        TripAlertService._send_alert,
        NotificationService.send_deviation_alert,
        alert_project.to_alert_message,
    ):
        assert "corridor_hits" not in inspect.signature(fn).parameters, fn.__qualname__
    with pytest.raises(TypeError):
        to_alert_message([], [], "x", tz=TZ, stand_at="09:00", corridor_hits=[])


def test_ac1_klassen_und_funktionen_sind_weg():
    from services import alert_log

    assert not hasattr(alert_model, "CorridorEvent")
    assert not hasattr(alert_project, "to_corridor_events")
    assert not hasattr(alert_project, "CorridorEvent")
    assert not hasattr(alert_log, "register_pairs_from_corridor_hits")


def test_ac2_keine_korridor_renderer_und_kein_feld_corridor_events():
    for name in (
        "_render_email_corridor_only", "_render_sms_corridor_only",
        "_corridor_line", "_corridor_label", "_corridor_where", "_corridor_when",
        "_corridor_value_str", "_sms_corridor_token",
    ):
        assert not hasattr(alert_render, name), name
    assert "corridor_events" not in {
        f.name for f in dataclasses.fields(alert_model.AlertMessage)
    }
    # geteilte Helfer bleiben
    assert hasattr(alert_render, "_stage_prefix")
