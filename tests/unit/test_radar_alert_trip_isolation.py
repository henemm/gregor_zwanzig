"""TDD RED — Issue #2217 (AC-4, AC-5): ein Trip mit beschaedigten Daten reisst
den Radar-Alarmlauf fuer die FOLGE-Trips desselben Nutzers nicht mit.

SPEC: docs/specs/modules/fix_2217_stapellaeufe_abschotten.md

Heute stehen ``trip_local_today()`` und ``_resolve_alert_segment()`` in
``_check_radar_trips()`` ungeschuetzt in der Trip-Schleife: wirft eines davon
fuer Trip A, bricht der ganze Lauf ab und Trip B bekommt nie einen Alarm.

Der Fehler wird ECHT erzeugt (kein Mock, kein patch): beschaedigte
Etappendaten im Trip.

* ``waypoints=[None]``  -> ``trip_local_today()`` wirft ``AttributeError``
  (Ortstag-Bestimmung),
* ``lat=None``          -> ``resolve_current_segment()`` wirft ``TypeError``
  (Segment-Auswahl; die Nachruestung davor ist fail-soft).

PRUEFORT = WIRKORT: Trip B hinterlaesst seinen Eintrag im echten
``alert_log.json``; Trip A bekommt seinen Fortschrittsstempel in
``alert_last_checked_radar.json``. Einzige monkeypatch-Naht ist die
Trip-Einspeisung (``app.loader.load_all_trips``), wie in
``test_radar_alert_channel_resolution.py``.
"""
from __future__ import annotations

import dataclasses
import logging
import uuid

import pytest

from services.alert_check_state import AlertCheckStateStore
from tests.helpers.nowcast_gate_fixtures import (
    CountingFrameSource,
    clean_uid,
    entries_for,
    fresh_uid,
    make_trip,
    quiet_window_elsewhere,
    reset_radar_cache,
    settings_no_channel_reachable,
    trip_alert_service,
    write_user_tier,
    TRIP_ZONE,
)

_STATE = "alert_last_checked_radar.json"


def _break_ortstag(trip) -> None:
    stage = trip.stages[0]
    trip.stages[0] = dataclasses.replace(stage, waypoints=[None])


def _break_segment(trip) -> None:
    stage = trip.stages[0]
    wp0 = dataclasses.replace(stage.waypoints[0], lat=None)
    trip.stages[0] = dataclasses.replace(stage, waypoints=[wp0, *stage.waypoints[1:]])


def _good_trip(trip_id: str):
    qf, qt = quiet_window_elsewhere(zone=TRIP_ZONE)
    trip = make_trip(trip_id, quiet_from=qf, quiet_to=qt)
    trip.alert_channels = {"email": False, "telegram": False, "sms": True}
    return trip


@pytest.mark.parametrize("breaker", [_break_ortstag, _break_segment],
                         ids=["ortstag", "segment"])
def test_radar_run_skips_broken_trip_and_still_checks_next_trip(
    monkeypatch, caplog, breaker,
):
    """AC-4 + AC-5."""
    import app.loader as loader

    uid = fresh_uid("2217")
    clean_uid(uid)
    try:
        write_user_tier(uid, "standard")
        sfx = uuid.uuid4().hex[:6]
        # Sortierung nach ID: A kommt VOR B, ein Abbruch an A trifft also B.
        id_a, id_b = f"t2217-a-{sfx}", f"t2217-b-{sfx}"
        trip_a = _good_trip(id_a)
        breaker(trip_a)
        trip_b = _good_trip(id_b)
        trips = [trip_a, trip_b]
        monkeypatch.setattr(loader, "load_all_trips", lambda **kw: list(trips))
        reset_radar_cache()

        with caplog.at_level(logging.ERROR):
            result = trip_alert_service(
                uid, settings_no_channel_reachable(),
                CountingFrameSource(onset_minutes=8), lambda s, b: None,
            ).check_radar_alerts_run()

        # AC-4: Trip B hinterlaesst seinen Protokoll-Eintrag (Wirkort).
        eintraege_b = (
            entries_for(uid, id_b, bucket="entries")
            + entries_for(uid, id_b, bucket="not_delivered")
        )
        assert len(eintraege_b) == 1, (
            f"AC-4: Trip B muss trotz defektem Trip A geprueft werden und "
            f"einen alert_log-Eintrag hinterlassen, gefunden: {eintraege_b!r}"
        )
        assert not (
            entries_for(uid, id_a, bucket="entries")
            + entries_for(uid, id_a, bucket="not_delivered")
        ), "AC-4: der defekte Trip A darf keinen Alarm-Eintrag haben"
        # AC-4: Fehler-Log nennt die Trip-ID.
        fehler = [
            r for r in caplog.records
            if r.levelno >= logging.ERROR and id_a in r.getMessage()
        ]
        assert fehler, (
            f"AC-4: erwartet ERROR-Log, das {id_a!r} nennt, erhalten: "
            f"{[r.getMessage() for r in caplog.records]!r}"
        )
        # AC-5: A zaehlt als erreicht -- checked UND Fortschrittsstempel.
        assert result.checked == 2, (
            f"AC-5: beide Trips zaehlen als erreicht, checked={result.checked}"
        )
        stamps = AlertCheckStateStore(uid, filename=_STATE).load([id_a, id_b])
        assert id_a in stamps, (
            f"AC-5: der uebersprungene Trip braucht seinen Fortschrittsstempel, "
            f"vorhanden: {sorted(stamps)!r}"
        )
        assert id_b in stamps
    finally:
        clean_uid(uid)


@pytest.mark.parametrize("breaker", [_break_ortstag, _break_segment],
                         ids=["ortstag", "segment"])
def test_radar_run_counts_broken_trip_as_failed_with_stacktrace(
    monkeypatch, caplog, breaker,
):
    """#2217 AC-1/AC-6 fuer kaputte Etappendaten: der aeussere Schutz je Trip
    zaehlt den Ausfall in ``failed`` und loggt ID MIT Stacktrace. Ein innerer
    ``try/except ... continue`` um Ortstag/Segment-Auswahl wuerde den Fall
    schlucken (kein failed, kein exc_info) => rot."""
    import app.loader as loader

    uid = fresh_uid("2217f")
    clean_uid(uid)
    try:
        write_user_tier(uid, "standard")
        sfx = uuid.uuid4().hex[:6]
        id_a, id_b = f"t2217-a-{sfx}", f"t2217-b-{sfx}"
        trip_a = _good_trip(id_a)
        breaker(trip_a)
        trips = [trip_a, _good_trip(id_b)]
        monkeypatch.setattr(loader, "load_all_trips", lambda **kw: list(trips))
        reset_radar_cache()

        with caplog.at_level(logging.ERROR):
            result = trip_alert_service(
                uid, settings_no_channel_reachable(),
                CountingFrameSource(onset_minutes=8), lambda s, b: None,
            ).check_radar_alerts_run()

        assert result.failed == 1, f"kaputter Trip muss als failed zaehlen: {result!r}"
        assert result.checked == 2, result
        mit_trace = [
            r for r in caplog.records
            if r.levelno >= logging.ERROR and id_a in r.getMessage()
            and r.exc_info and r.exc_info[0] is not None
        ]
        assert mit_trace, (
            f"ERROR mit Trip-ID {id_a!r} und Stacktrace fehlt: "
            f"{[(r.getMessage(), bool(r.exc_info)) for r in caplog.records]!r}"
        )
    finally:
        clean_uid(uid)
