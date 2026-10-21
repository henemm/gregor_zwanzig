"""Alarm-Vorschau eines heute laufenden Trips mit ECHTER Etappen-Kennung (Issue #1737, AC-11).

Die Oberflaeche (``alertPreviewHelpers.buildAlertPreviewPayload``) sendet in ``changes`` und
``segment_times`` eine SEGMENT-Kennung des Tages (``"1"``, ``trip_segments.py``:
``segment_id=i+1``). Bis #1737 stand dort ``stages[0].id`` -- bei echten Trips ``"T01"``
(``fullProfile.ts``) -- und der Kern lehnte die Vorschau jedes heute laufenden Trips mit 422 ab,
die Stundenzeilen kamen beim Nutzer nie an.

Kein Mock-Theater: Anker und frische Reihe laufen ueber dieselben Naehte wie die AC-11-Tests
(``GZ_TEST_FIXTURE_DIR`` -> FixtureProvider, nutzergebundener Speicher).
"""
from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi import HTTPException

from tests.integration.test_briefing_preview_bundle import env  # noqa: F401  (Fixture)
from tests.tdd.test_alert_hour_rows import (
    TRIP_ID, TRIP_LAT, TRIP_LON, TRIP_STURM, _erwartete_zeilen, _plant, _rows,
    _trip_anker_schreiben, _trip_body, _trip_versand,
)


def _trip_mit_echter_etappe(uid: str):
    """Trip wie aus dem Editor: Etappen-Kennungen ``T01``/``T02``, ``T01`` ist HEUTE."""
    from app.loader import save_trip
    from app.models import MetricConfig, UnifiedWeatherDisplayConfig
    from app.trip import Stage, Trip, Waypoint
    from tests.helpers.ortstag import ortstag

    heute = ortstag(TRIP_LAT, TRIP_LON)
    wp = [
        Waypoint(id="G1", name="Start", lat=TRIP_LAT, lon=TRIP_LON, elevation_m=600.0),
        Waypoint(id="G2", name="Ziel", lat=47.30, lon=11.45, elevation_m=1200.0),
    ]
    trip = Trip(
        id=TRIP_ID, name="Stunden-Trip",
        stages=[Stage(id="T01", name="Etappe 1", date=heute, waypoints=wp),
                Stage(id="T02", name="Etappe 2", date=heute + timedelta(days=1), waypoints=wp)],
        official_warnings=None, corridors=[],
        display_config=UnifiedWeatherDisplayConfig(
            trip_id=TRIP_ID, metrics=[MetricConfig(metric_id="gust", enabled=True)],
            metric_alert_levels={"wind_gust": "standard"},
        ),
    )
    save_trip(trip, user_id=uid)
    assert trip.start_date <= heute <= trip.end_date, "Vorbedingung: Trip laeuft heute"
    return trip


def _body_wie_oberflaeche(segment_id: str) -> dict:
    """Body exakt wie der korrigierte Helper (``segment_id`` in changes UND segment_times)."""
    body = _trip_body()
    body["changes"][0]["segment_id"] = segment_id
    body["segment_times"][0]["segment_id"] = segment_id
    return body


def test_vorschau_eines_heute_laufenden_trips_mit_etappe_t01_zeigt_die_stundenzeilen_des_versands(
    env, monkeypatch, tmp_path,  # noqa: F811
):
    """Etappe ``T01`` laeuft heute, Anker im Speicher des Nutzers, frische Reihe ueber die
    Fixture-Naht. Der Body, den die Oberflaeche jetzt sendet (``segment_id "1"``), liefert eine
    Antwort (200) mit denselben Stundenzeilen wie der Versand."""
    from api.routers.validator import AlertPreviewBody, alert_preview
    from utils.timezone import tz_for_coords

    uid = env
    trip = _trip_mit_echter_etappe(uid)
    _trip_anker_schreiben(monkeypatch, tmp_path, uid, trip, {}, "anker-t01")
    _plant(tmp_path, monkeypatch, "sturm", TRIP_STURM)
    erwartet = _erwartete_zeilen(tz_for_coords(TRIP_LAT, TRIP_LON), TRIP_STURM, {})
    assert len(erwartet) == 3

    mails, tgs = _trip_versand(monkeypatch, uid, trip)
    assert _rows(mails[0]) == erwartet, "Vorbedingung: der Versand traegt die Zeilen"

    vorschau = alert_preview(
        trip.id, AlertPreviewBody.model_validate(_body_wie_oberflaeche("1")), user_id=uid)
    assert _rows(vorschau["email_plain"]) == _rows(mails[0])
    assert _rows(vorschau["telegram"]) == _rows(tgs[0])


@pytest.mark.parametrize("etappen_kennung", ["T01", "T1"])
def test_etappen_kennung_im_segment_feld_wird_mit_422_abgelehnt(env, etappen_kennung):  # noqa: F811
    """Gegenprobe (warum der Frontend-Fix noetig ist): die Etappen-Kennung im Segment-Feld --
    der alte Oberflaechen-Body -- lehnt der Kern bei einem heute laufenden Trip mit 422 ab."""
    from api.routers.validator import AlertPreviewBody, alert_preview

    trip = _trip_mit_echter_etappe(env)
    with pytest.raises(HTTPException) as fehler:
        alert_preview(trip.id, AlertPreviewBody.model_validate(
            _body_wie_oberflaeche(etappen_kennung)), user_id=env)
    assert fehler.value.status_code == 422
    assert etappen_kennung in str(fehler.value.detail)
