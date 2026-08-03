"""TDD RED — Issue #1474 Adversary-Folgeaudit: der Telegram-Drilldown-Pfad
(``TripCommandProcessor``) kennt ``ThunderLevel.LOW`` an VIER weiteren Stellen
nicht (dieselbe Fehlerklasse wie F004/F005 in ``trip_report_scheduler.py``):

1. ``_aggregate_day()`` -- lokale Liste ``[TL.NONE, TL.MED, TL.HIGH]`` +
   ``.index()`` -- wirft ``ValueError`` sobald ein Tagespunkt LOW ist. Live
   ueber ``/glance`` UND als Vorstufe von ``_timeline_buttons()``.
2. ``_timeline_buttons()`` -- zweite, identische Kopie derselben Liste.
3. ``_thunder_fmt()`` -- ``_MAP_EMOJI``/``_MAP_PLAIN`` fehlt LOW, faellt auf
   "keine Daten" zurueck (Gewitter-Drilldown ``dd_thunder_*``).
4. ``_handle_hours_drilldown()`` -- die Stundenzeile behandelt jeden Wert
   ausser NONE/MED als HIGH (roter Punkt) -- LOW wird als "starkes Gewitter"
   angezeigt (Stunden-Drilldown ``dd_hours_*``).

Mock-frei, Muster aus ``test_telegram_drilldown_local_time_boundary.py``:
echter Trip, echter Snapshot ueber ``WeatherSnapshotService``, echte
Callback-Aufloesung ueber ``InboundTelegramReader``, echter
``TripCommandProcessor``.

Spec: docs/specs/modules/feat_1474_gewitter_befund_stufen.md v2.4
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from app.loader import save_trip
from app.models import (
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    TripSegment,
)
from app.trip import Stage, Trip, Waypoint
from services.inbound_telegram_reader import InboundTelegramReader
from services.trip_command_processor import (
    CommandResult,
    InboundMessage,
    TripCommandProcessor,
)
from services.weather_snapshot import WeatherSnapshotService

_WP_LAT, _WP_LON = 42.1, 9.0
_TRIP_ID = "telegram-thunder-low"
_TRIP_NAME = "Telegram-LOW-Tour"
_USER_ID = "default"
_HOURS = 12


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _make_trip(day: datetime) -> Trip:
    return Trip(
        id=_TRIP_ID,
        name=_TRIP_NAME,
        stages=[
            Stage(
                id="S1", name="Heute-Etappe", date=day.date(),
                waypoints=[
                    Waypoint(id="W1", name="Vizzavona", lat=_WP_LAT, lon=_WP_LON, elevation_m=900),
                ],
            ),
        ],
    )


def _make_segments_low_only(now: datetime) -> list[SegmentWeatherData]:
    """12 Stundenpunkte, AUSSCHLIESSLICH ThunderLevel.LOW -- kein einziger
    NONE/MED/HIGH-Punkt, damit jede Aggregation zwingend LOW zeigen muss
    (bzw. bei einem Bug crasht oder falsch labelt).

    ``end_time=now`` (statt ``now + 11h``) ist bewusst: die Tages-Aggregation
    (``_aggregate_day``) bucket-t nach ``segment.end_time.date()`` -- ein
    Versatz um 11h koennte je nach Testlaufzeit ueber Mitternacht in den
    Folgetag rutschen und den Test flaky machen (mal "heute", mal "morgen").
    """
    points = [
        ForecastDataPoint(
            ts=now + timedelta(hours=i),
            t2m_c=10.0 + i, wind10m_kmh=float(20 + i), precip_1h_mm=0.0,
            thunder_level=ThunderLevel.LOW,
        )
        for i in range(_HOURS)
    ]
    segment = TripSegment(
        segment_id="seg-1",
        start_point=GPXPoint(lat=_WP_LAT, lon=_WP_LON, elevation_m=900),
        end_point=GPXPoint(lat=_WP_LAT + 0.1, lon=_WP_LON + 0.1, elevation_m=600),
        start_time=now, end_time=now,
        duration_hours=float(_HOURS - 1), distance_km=15.0, ascent_m=200.0, descent_m=400.0,
    )
    return [
        SegmentWeatherData(
            segment=segment,
            timeseries=NormalizedTimeseries(
                meta=ForecastMeta(provider=Provider.OPENMETEO, model="test", grid_res_km=0.0),
                data=points,
            ),
            aggregated=SegmentWeatherSummary(
                thunder_level_max=ThunderLevel.LOW, wind_max_kmh=31.0, precip_sum_mm=0.0,
            ),
            fetched_at=now, provider=Provider.OPENMETEO.value,
        )
    ]


@pytest.fixture
def env(tmp_path: Path, monkeypatch) -> datetime:
    redirect = lambda user_id="default": tmp_path / user_id
    monkeypatch.setattr("app.loader.get_data_dir", redirect)
    monkeypatch.setattr("services.trip_command_processor.get_data_dir", redirect)

    now = _now()
    save_trip(_make_trip(now), _USER_ID)
    WeatherSnapshotService(_USER_ID).save(_TRIP_ID, _make_segments_low_only(now), now.date())
    return now


def _press_button(callback_data: str, now: datetime) -> CommandResult:
    body = InboundTelegramReader()._callback_to_body(callback_data)
    assert body is not None, f"Knopf {callback_data!r} ist beim Reader unbekannt"
    msg = InboundMessage(
        channel="telegram", trip_name=_TRIP_NAME, body=body, sender="4711",
        received_at=now, user_id=_USER_ID,
    )
    return TripCommandProcessor().process(msg)


def test_glance_low_only_day_does_not_crash_and_shows_leicht(env):
    """
    GIVEN: ein Tag AUSSCHLIESSLICH mit LOW-Punkten
    WHEN:  der Nutzer /glance abruft (-> ``_aggregate_day`` + ``_THUNDER_LABEL``)
    THEN:  keine Exception, UND das Label "leicht" statt "?" (Fallback fuer
           unbekannte Stufen) -- LOW ist eine bekannte, benannte Stufe.
    """
    result = _press_button("glance", env)

    assert result.success is True, (
        f"/glance mit LOW-only-Tag muss antworten statt zu crashen: "
        f"{result.confirmation_body!r}"
    )
    assert "leicht" in result.confirmation_body, (
        f"Erwartet die Beschriftung 'leicht' fuer LOW, bekam: "
        f"{result.confirmation_body!r}"
    )
    assert "⛈ Gewitter: ?" not in result.confirmation_body, (
        f"LOW darf nicht auf den Unbekannt-Fallback '?' fallen: "
        f"{result.confirmation_body!r}"
    )


def test_dd_thunder_today_low_level_shows_leicht_not_keine_daten(env):
    """
    GIVEN: ein Tag AUSSCHLIESSLICH mit LOW-Punkten
    WHEN:  der Nutzer den Gewitter-Drilldown oeffnet (-> ``_thunder_fmt``)
    THEN:  die Stundenliste zeigt "leicht" (bzw. das gelbe/hellere Symbol),
           NICHT "keine Daten" fuer einen Wert, der tatsaechlich vorliegt.
    """
    result = _press_button("dd_thunder_today", env)

    assert result.success is True
    assert "keine Daten" not in result.confirmation_body, (
        f"LOW ist ein bekannter Wert, darf nicht als 'keine Daten' erscheinen: "
        f"{result.confirmation_body!r}"
    )
    assert "leicht" in result.confirmation_body, (
        f"Erwartet 'leicht' fuer LOW im Gewitter-Drilldown: "
        f"{result.confirmation_body!r}"
    )


def test_dd_hours_today_low_level_not_mislabeled_as_high(env):
    """
    GIVEN: ein Tag AUSSCHLIESSLICH mit LOW-Punkten
    WHEN:  der Nutzer die Stunden-Tabelle oeffnet
    THEN:  KEINE Zeile zeigt das rote HIGH-Symbol -- LOW ist kein "starkes
           Gewitter". Die aktuelle Kopie behandelt "alles ausser NONE/MED"
           als HIGH und wuerde hier bei JEDER Zeile faelschlich 🔴 zeigen.
    """
    result = _press_button("dd_hours_today", env)

    assert result.success is True
    assert "🔴" not in result.confirmation_body, (
        f"LOW darf nicht als starkes Gewitter (🔴) angezeigt werden: "
        f"{result.confirmation_body!r}"
    )


def test_timeline_buttons_low_only_day_does_not_crash(env):
    """
    GIVEN: ein Tag AUSSCHLIESSLICH mit LOW-Punkten
    WHEN:  die Timeline geoeffnet wird (-> ``_timeline_buttons``, zweite
           Kopie derselben Ordinal-Liste wie ``_aggregate_day``)
    THEN:  keine Exception -- der Gewitter-Drilldown-Knopf erscheint NICHT
           (LOW liegt unterhalb der MED-Schwelle fuer den Button, unveraendertes
           Verhalten).
    """
    result = _press_button("tl_today", env)

    assert result.success is True, (
        f"Timeline mit LOW-only-Tag muss antworten statt zu crashen: "
        f"{result.confirmation_body!r}"
    )
    buttons = result.reply_markup["inline_keyboard"] if result.reply_markup else []
    callbacks = {b["callback_data"] for row in buttons for b in row}
    assert "dd_thunder_today" not in callbacks, (
        f"LOW liegt unter der MED-Schwelle -- der Gewitter-Knopf darf hier "
        f"nicht erscheinen: {callbacks!r}"
    )
