"""TDD RED -- die Fenstergrenze einer Alarmpruefung steht im Log (Eintrag C5-02b,
Issue #2218 Scheibe C, Epic #2505).

SPEC: docs/specs/modules/fix_2218_scheibe_c_observability.md (AC-26, AC-27)

Heute wird die Grenze, gegen die ein Alarm geprueft wird, nirgends
protokolliert: weder der Zeitraum der nassen Aenderungen im Delta-Zweig noch
das Aufenthaltsfenster im Radar-Zweig. Gefordert ist genau EINE Info-Zeile je
Pruefung (Trip-ID, Fenster-Start, Fenster-Ende, Quelle ``delta`` bzw. ``radar``,
OHNE Koordinaten), bei fehlendem Fenster ``fenster=keines``. Es aendert sich
keine Fensterlogik.

Formvorgabe an die Umsetzung (Test-Vertrag): ``quelle=delta`` bzw.
``quelle=radar`` und ``fenster=keines`` stehen woertlich in der Zeile, der
Logger ist ``trip_alert``.

Gemessen ueber den ECHTEN Pruefpfad: Delta ueber ``check_and_send_alerts`` mit
echten Modellobjekten, Radar ueber ``check_radar_alerts_run`` mit echten Trips
auf der Platte und einer echten ``RadarNowcastService``-Unterklasse am DI-Seam
(Fake nur an der Systemgrenze). Kein Mock-Theater.
"""
from __future__ import annotations

import logging
import re
import time
import uuid
from datetime import date as date_type, datetime, timezone

import pytest
from freezegun import freeze_time

from app.models import (
    ForecastMeta,
    GPXPoint,
    MetricConfig,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    TripReportConfig,
    TripSegment,
    UnifiedWeatherDisplayConfig,
)
from app.trip import Stage, Trip, Waypoint
from services.trip_alert import TripAlertService

from tests.helpers.alert_log_fixtures import settings_email_only
from tests.tdd.test_radar_alarmlauf_fairness import (
    _ScriptedRadar,
    _make_trips,
    _trip_idx,
    _trip_service,
)

LOGGER = "trip_alert"
LAT, LON = 47.0, 11.0
_AT = datetime(2026, 4, 5, 10, 0, tzinfo=timezone.utc)
_SEG_START = datetime(2026, 4, 5, 8, 0, tzinfo=timezone.utc)
_SEG_END = datetime(2026, 4, 5, 12, 0, tzinfo=timezone.utc)
_MINUTEN = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}")


def _uid(tag: str) -> str:
    return f"tdd-2218c-{tag}-{uuid.uuid4().hex[:6]}"


# ---------------------------------------------------------------------------
# Delta-Zweig
# ---------------------------------------------------------------------------

def _wd(**summary) -> SegmentWeatherData:
    segment = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=LAT, lon=LON, elevation_m=1000, distance_from_start_km=12.0),
        end_point=GPXPoint(lat=LAT + 0.1, lon=LON + 0.1, elevation_m=1500, distance_from_start_km=18.0),
        start_time=_SEG_START, end_time=_SEG_END, duration_hours=4.0,
        distance_km=6.0, ascent_m=500, descent_m=0,
    )
    return SegmentWeatherData(
        segment=segment,
        timeseries=NormalizedTimeseries(
            meta=ForecastMeta(provider=Provider.OPENMETEO, model="test", grid_res_km=1.0),
            data=[],
        ),
        aggregated=SegmentWeatherSummary(**summary),
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )


def _trip_delta(trip_id: str) -> Trip:
    stage = Stage(
        id="T1", name="Tag 1", date=date_type(2026, 4, 5),
        waypoints=[Waypoint(id="G1", name="Start", lat=LAT, lon=LON, elevation_m=1000.0)],
    )
    trip = Trip(
        id=trip_id, name="Fenster-Trip", stages=[stage],
        display_config=UnifiedWeatherDisplayConfig(
            trip_id=trip_id,
            metrics=[MetricConfig(metric_id=m, enabled=True)
                     for m in ("precipitation", "thunder", "gust")],
            metric_alert_levels={
                "precipitation_sum": "standard", "thunder_level": "sensibel",
                "wind_gust": "standard",
            },
        ),
    )
    trip.report_config = TripReportConfig(
        trip_id=trip_id, send_email=True, alert_on_changes=True,
    )
    trip.alert_cooldown_minutes = 0
    return trip


def _delta_lauf(uid: str, trip: Trip, cached: list, fresh: list) -> tuple[bool, list]:
    zugestellt: list = []
    dienst = TripAlertService(
        settings=settings_email_only(), throttle_hours=2, user_id=uid,
        mail_sink=lambda *a, **kw: zugestellt.append((a, kw)),
    )
    with freeze_time(_AT):
        return dienst.check_and_send_alerts(trip, cached_weather=cached, fresh_weather=fresh), zugestellt


def _fenster_zeilen(caplog, trip_id: str, quelle: str) -> list[str]:
    return [
        r.getMessage() for r in caplog.records
        if r.name == LOGGER and r.levelno == logging.INFO
        and trip_id in r.getMessage() and f"quelle={quelle}" in r.getMessage()
    ]


def test_ac26_delta_pruefung_mit_nasser_aenderung_loggt_genau_eine_fensterzeile(caplog):
    """AC-26: Δ-Pruefung mit nasser Aenderung -> genau EINE Info-Zeile mit
    Trip-ID, Fenster-Start, Fenster-Ende (Segmentfenster der nassen Aenderung)
    und ``quelle=delta``; weder Koordinaten noch Adressen."""
    uid = _uid("ac26")
    trip = _trip_delta("t-ac26")

    with caplog.at_level(logging.INFO, logger=LOGGER):
        gesendet, mails = _delta_lauf(uid, trip, [_wd(precip_sum_mm=2.0)], [_wd(precip_sum_mm=45.0)])

    assert gesendet is True and mails, "Testaufbau: die nasse Aenderung muss alarmieren"
    zeilen = _fenster_zeilen(caplog, "t-ac26", "delta")
    assert len(zeilen) == 1, (
        f"genau eine Fensterzeile erwartet, bekam {len(zeilen)}: "
        f"{[r.getMessage() for r in caplog.records if r.name == LOGGER]}"
    )
    zeitpunkte = _MINUTEN.findall(zeilen[0])
    assert [z.replace("T", " ") for z in zeitpunkte[:2]] == ["2026-04-05 08:00", "2026-04-05 12:00"], (
        f"Fenster-Start/-Ende des Segments fehlen in der Zeile: {zeilen[0]}"
    )
    assert "fenster=keines" not in zeilen[0]
    assert "47.0" not in zeilen[0] and "11.0" not in zeilen[0], f"Koordinaten in der Zeile: {zeilen[0]}"


def test_ac26_delta_pruefung_ohne_nasse_aenderung_loggt_fenster_keines(caplog):
    """AC-26 (Gegenfall): nur eine Boeen-Aenderung (nicht nass) -> die Zeile
    erscheint trotzdem, mit ``fenster=keines`` -- "keine Grenze" ist von
    "nicht geprueft" unterscheidbar."""
    uid = _uid("ac26k")
    trip = _trip_delta("t-ac26k")

    with caplog.at_level(logging.INFO, logger=LOGGER):
        gesendet, mails = _delta_lauf(
            uid, trip, [_wd(gust_max_kmh=10.0)], [_wd(gust_max_kmh=90.0)],
        )

    assert gesendet is True and mails, "Testaufbau: die Boeen-Aenderung muss alarmieren"
    zeilen = _fenster_zeilen(caplog, "t-ac26k", "delta")
    assert len(zeilen) == 1, f"genau eine Fensterzeile erwartet: {zeilen}"
    assert "fenster=keines" in zeilen[0], zeilen[0]


# ---------------------------------------------------------------------------
# Radar-Zweig
# ---------------------------------------------------------------------------

@pytest.fixture
def _gestellte_uhr():
    # Mittags UTC, damit das aktive Segment aller Trips gleich liegt (Muster
    # test_radar_alarmlauf_fairness.py); time.monotonic bleibt echt.
    echte_monotonic = time.monotonic
    with freeze_time("2026-10-01T10:00:00+00:00", tick=True):
        time.monotonic = echte_monotonic
        yield


def test_ac27_radar_pruefung_loggt_je_segmentpruefung_genau_eine_zeile(
    _gestellte_uhr, caplog,
):
    """AC-27: ein Radar-Alarmlauf mit drei Trips (je ein aktives Segment) ->
    je Segmentpruefung genau eine Info-Zeile mit der Trip-ID und
    ``quelle=radar``, also drei Zeilen, ohne Koordinaten."""
    uid = _uid("ac27")
    ids = _make_trips(uid, ["t-r1", "t-r2", "t-r3"])
    radar = _ScriptedRadar(_trip_idx)

    with caplog.at_level(logging.INFO, logger=LOGGER):
        lauf = _trip_service(uid, radar).check_radar_alerts_run()

    assert lauf.checked == 3, f"Testaufbau: alle drei Trips muessen geprueft werden: {lauf}"
    assert sorted(radar.first_seen) == [0, 1, 2], (
        f"Testaufbau: jeder Trip muss die Positionsbestimmung passieren und "
        f"den Nowcast abrufen: {radar.first_seen}"
    )
    for trip_id in ids:
        zeilen = _fenster_zeilen(caplog, trip_id, "radar")
        assert len(zeilen) == 1, (
            f"{trip_id}: genau eine Radar-Fensterzeile erwartet, bekam {len(zeilen)}: "
            f"{[r.getMessage() for r in caplog.records if r.name == LOGGER]}"
        )
        assert not re.search(r"\b4[0-9]\.\d{2,}", zeilen[0]), (
            f"Koordinaten in der Fensterzeile: {zeilen[0]}"
        )
    alle = [r for r in caplog.records if r.name == LOGGER and "quelle=radar" in r.getMessage()]
    assert len(alle) == 3, f"insgesamt drei Radar-Fensterzeilen erwartet, bekam {len(alle)}"
