"""TDD RED — Telegram-Drilldown: Knopfdruck bis Antwort, mit echter Ortszeit.

Warum dieser Test ZUSAETZLICH zu den 13 vorhandenen Drilldown-Tests existiert:
die decken den Drilldown zwar ab, sind aber seit Issue #1345 stillschweigend
rot geworden, ohne dass jemand hinsah. Beide Fehlerbilder, die dieser Test
festnagelt, sind aus Nutzersicht formuliert und binden sich an den ECHTEN
Empfaengerpfad statt an einen selbstgebauten Zeitstempel:

1. **Absturz statt Antwort.** ``received_at`` entsteht hier ueber
   ``_now_like_the_reader()`` — woertlich derselbe Ausdruck wie in
   ``services/inbound_telegram_reader.py:227`` (Text-Befehl) und ``:321``
   (Knopfdruck): ``datetime.now(tz=timezone.utc)``, also ZEITZONENBEHAFTET.
   ``ForecastDataPoint.ts`` ist per Hausnorm (#1345,
   ``src/app/models.py`` ``__post_init__``) dagegen IMMER naives UTC — auch
   nach dem Snapshot-Roundtrip. Wer beides ungefiltert vergleicht, bekommt
   ``TypeError: can't compare offset-naive and offset-aware datetimes``.
   Der Nutzer sieht: Knopf gedrueckt, nichts passiert.

2. **Weltzeit statt Ortszeit.** ``naiv.astimezone()`` ohne Argument deutet
   einen naiven Zeitstempel als PROZESS-Zeitzone — auf dem UTC-Server
   zufaellig unauffaellig, auf jedem anderen Host falsch. Der Trip liegt hier
   bewusst auf Korsika (``Europe/Paris``, CEST/CET), damit sich Ortszeit von
   Weltzeit ueberhaupt unterscheiden LAESST. Die Erwartung wird unabhaengig
   vom Prueflingsweg gebildet: aus dem AWAREN ``NOW`` per ``.astimezone()``.

Kein Mock: echter Trip, echter Snapshot ueber ``WeatherSnapshotService``,
echte Callback-Aufloesung des Readers, echter ``TripCommandProcessor``.
"""
from __future__ import annotations

import re
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

# Korsika — loest zu Europe/Paris auf, also NIE UTC. Nur dadurch ist auf dem
# UTC-Server ueberhaupt pruefbar, ob Ortszeit oder Weltzeit angezeigt wird.
_WP_LAT, _WP_LON = 42.1, 9.0
_TRIP_TZ = ZoneInfo("Europe/Paris")

_TRIP_ID = "drilldown-ortszeit"
_TRIP_NAME = "Drilldown-Ortszeit-Tour"
_USER_ID = "default"
_HOURS = 12


def _now_like_the_reader() -> datetime:
    """Woertlich der Ausdruck aus inbound_telegram_reader.py:227 und :321.

    Der Empfaenger baut ``received_at`` zeitzonenbehaftet. Ein Test, der hier
    heimlich einen naiven Zeitstempel einsetzt, wuerde den Produktivpfad
    NICHT mehr abbilden — und den Absturz zudecken statt ihn zu zeigen.
    """
    return datetime.now(tz=timezone.utc)


def _make_trip(day: datetime) -> Trip:
    return Trip(
        id=_TRIP_ID,
        name=_TRIP_NAME,
        stages=[
            Stage(
                id="S1",
                name="Heute-Etappe",
                date=day.date(),
                waypoints=[
                    Waypoint(
                        id="W1", name="Vizzavona",
                        lat=_WP_LAT, lon=_WP_LON, elevation_m=900,
                    ),
                ],
            ),
        ],
    )


def _make_segments(now: datetime) -> list[SegmentWeatherData]:
    """12 Stundenpunkte ab ``now``.

    ACHTUNG Hausnorm "naive UTC" (#1345): der hier aware uebergebene ``ts``
    kommt aus ``ForecastDataPoint`` ZEITZONENLOS wieder heraus — schon vor dem
    Speichern. Genau diese Naht prueft der Test.
    """
    thunder_seq = [ThunderLevel.NONE, ThunderLevel.MED, ThunderLevel.HIGH]
    points = [
        ForecastDataPoint(
            ts=now + timedelta(hours=i),
            t2m_c=10.0 + i,
            wind10m_kmh=float(20 + i),
            precip_1h_mm=0.3 * i,
            thunder_level=thunder_seq[i % len(thunder_seq)],
        )
        for i in range(_HOURS)
    ]
    segment = TripSegment(
        segment_id="seg-1",
        start_point=GPXPoint(lat=_WP_LAT, lon=_WP_LON, elevation_m=900),
        end_point=GPXPoint(lat=_WP_LAT + 0.1, lon=_WP_LON + 0.1, elevation_m=600),
        start_time=now,
        end_time=now + timedelta(hours=_HOURS - 1),
        duration_hours=float(_HOURS - 1),
        distance_km=15.0,
        ascent_m=200.0,
        descent_m=400.0,
    )
    return [
        SegmentWeatherData(
            segment=segment,
            timeseries=NormalizedTimeseries(
                meta=ForecastMeta(
                    provider=Provider.OPENMETEO, model="test", grid_res_km=0.0,
                ),
                data=points,
            ),
            aggregated=SegmentWeatherSummary(
                thunder_level_max=ThunderLevel.HIGH,
                wind_max_kmh=31.0,
                precip_sum_mm=3.3,
            ),
            fetched_at=now,
            provider=Provider.OPENMETEO.value,
        )
    ]


@pytest.fixture
def env(tmp_path: Path, monkeypatch) -> datetime:
    """Echter Trip + echter Snapshot unter tmp_path. Gibt ``now`` zurueck."""
    redirect = lambda user_id="default": tmp_path / user_id
    monkeypatch.setattr("app.loader.get_data_dir", redirect)
    monkeypatch.setattr("services.trip_command_processor.get_data_dir", redirect)

    now = _now_like_the_reader()
    save_trip(_make_trip(now), _USER_ID)
    WeatherSnapshotService(_USER_ID).save(
        _TRIP_ID, _make_segments(now), now.date()
    )
    return now


def _press_button(callback_data: str, now: datetime) -> CommandResult:
    """Knopfdruck -> Antwort, ueber die ECHTE Callback-Aufloesung des Readers.

    ``_callback_to_body`` ist dieselbe Funktion, die der Empfaenger in
    ``_handle_callback_query`` benutzt — kein nachgebauter Body.
    """
    body = InboundTelegramReader()._callback_to_body(callback_data)
    assert body is not None, f"Knopf {callback_data!r} ist beim Reader unbekannt"

    msg = InboundMessage(
        channel="telegram",
        trip_name=_TRIP_NAME,
        body=body,
        sender="4711",
        received_at=now,
        user_id=_USER_ID,
    )
    return TripCommandProcessor().process(msg)


def _expected_local(now: datetime, offset_hours: int, fmt: str) -> str:
    """Erwartung UNABHAENGIG vom Prueflingsweg: aus dem awaren ``now``."""
    return (now + timedelta(hours=offset_hours)).astimezone(_TRIP_TZ).strftime(fmt)


# ---------------------------------------------------------------------------
# 1) Knopfdruck liefert eine Antwort statt eines Absturzes
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "callback_data",
    ["dd_thunder_today", "dd_wind_today", "dd_precip_today", "dd_hours_today"],
)
def test_drilldown_button_answers_instead_of_crashing(env, callback_data):
    """
    GIVEN aktiver Trip mit stuendlichem Snapshot,
    WHEN der Nutzer im Telegram-Briefing den Drilldown-Knopf drueckt und
         ``received_at`` so entsteht wie im Empfaenger (aware UTC),
    THEN kommt eine befuellte Antwort zurueck — kein TypeError.
    """
    result = _press_button(callback_data, env)

    assert result.success is True, (
        f"{callback_data}: erwartet eine Antwort, bekam "
        f"success={result.success} / {result.confirmation_body!r}"
    )
    assert len(re.findall(r"\b\d{2}[: ]", result.confirmation_body)) >= 6, (
        f"{callback_data}: erwartet >=6 Stundenzeilen, body:\n"
        f"{result.confirmation_body}"
    )


# ---------------------------------------------------------------------------
# 2) Angezeigte Uhrzeiten sind Ortszeit, nicht Weltzeit
# ---------------------------------------------------------------------------

def test_drilldown_list_shows_local_time_of_the_waypoint(env):
    """
    GIVEN ein Trip auf Korsika (Europe/Paris) und ein UTC-Snapshot,
    WHEN der Nutzer den Gewitter-Drilldown oeffnet,
    THEN stehen dort die ORTSzeiten des Wegpunkts — nicht die UTC-Stunden.
    """
    now = env
    body = _press_button("dd_thunder_today", now).confirmation_body

    first_local = _expected_local(now, 0, "%H:%M")
    assert first_local in body, (
        f"Erwartet die Ortszeit {first_local} (Europe/Paris) in der Liste:\n{body}"
    )

    utc_stamp = now.strftime("%H:%M")
    assert utc_stamp != first_local, "Testaufbau kaputt: Ortszeit == UTC-Zeit"
    assert utc_stamp not in body, (
        f"Weltzeit {utc_stamp} steht in der Liste statt der Ortszeit "
        f"{first_local}:\n{body}"
    )


def test_hours_table_shows_local_time_of_the_waypoint(env):
    """
    GIVEN denselben Trip,
    WHEN der Nutzer die Stunden-Tabelle oeffnet,
    THEN traegt die erste Zeile die ORTS-Stunde des Wegpunkts.
    """
    now = env
    body = _press_button("dd_hours_today", now).confirmation_body

    hours = re.findall(r"^(\d{2})\s", body, flags=re.MULTILINE)
    assert hours, f"Keine Stundenzeilen gefunden:\n{body}"

    expected = [_expected_local(now, i, "%H") for i in range(_HOURS)]
    assert hours[0] == expected[0], (
        f"Erste Zeile zeigt {hours[0]}h, erwartet die Ortszeit {expected[0]}h "
        f"(UTC waere {now.strftime('%H')}h):\n{body}"
    )
    assert hours == expected, (
        f"Stundenspalte weicht von der Ortszeit ab.\n"
        f"gesehen:   {hours}\nerwartet:  {expected}\n{body}"
    )
