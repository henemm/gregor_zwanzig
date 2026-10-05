"""#2231 AC-3/AC-4: unbekannter Versand-Ausgang sperrt den Slot (fail-closed);
allein `channels_unreachable` gibt ihn frei.

Echter Scheduler und echter BriefingSlotStore; ersetzt ist nur die Netz-Naht
(`_send_trip_report_outcome`) durch eine echte Unterklasse mit festem Ausgang.
Spec: docs/specs/modules/fail_closed_versand_defaults.md
"""
from __future__ import annotations

import logging
from datetime import date, datetime

from services.briefing_slots import BriefingSlotStore
from tests.tdd.test_briefing_slot_idempotenz import (
    KORSIKA, PARIS, _schreibe, _scheduler_mit_festem_ausgang, _trip_json,
    _zeitpunkt,
)

TAGE = [date(2026, 8, 19), date(2026, 8, 20), date(2026, 8, 21)]
TAG = date(2026, 8, 20)


def _aufbau(user: str, ausgang):
    _schreibe(user, [_trip_json("korsika", *KORSIKA, TAGE, morning="07:00:00")])
    sched = _scheduler_mit_festem_ausgang(user, ausgang)
    moment: datetime = _zeitpunkt(PARIS, TAG, 7)
    trip, rt, ortstag = sched._collect_due_trips(moment)[0]
    return sched, trip, rt, ortstag, moment


def test_unknown_outcome_locks_slot_and_logs_error(caplog):
    sched, trip, rt, ortstag, moment = _aufbau("u2231-unknown", "weird_new_outcome")
    with caplog.at_level(logging.ERROR):
        sched._dispatch_due_item(trip, rt, ortstag, now_utc=moment)
        second = sched._dispatch_due_item(trip, rt, ortstag, now_utc=moment)

    store = BriefingSlotStore("u2231-unknown")
    assert store.is_recorded(trip.id, rt, ortstag) is True
    assert second is None
    assert len(sched.versandversuche) == 1
    assert any(
        r.levelno == logging.ERROR and "weird_new_outcome" in r.getMessage()
        for r in caplog.records
    )
    # Auch im Nachholfenster (spaeterer Lauf) wird der Trip nicht mehr faellig
    spaeter = _zeitpunkt(PARIS, TAG, 8)
    assert sched._collect_due_trips(spaeter) == []


def test_non_string_outcome_locks_slot_as_unknown():
    sched, trip, rt, ortstag, moment = _aufbau("u2231-none", None)
    sched._dispatch_due_item(trip, rt, ortstag, now_utc=moment)
    assert BriefingSlotStore("u2231-none").is_recorded(trip.id, rt, ortstag) is True
    sched._dispatch_due_item(trip, rt, ortstag, now_utc=moment)
    assert len(sched.versandversuche) == 1


def test_channels_unreachable_releases_slot_and_retries():
    sched, trip, rt, ortstag, moment = _aufbau("u2231-unreach", "channels_unreachable")
    sched._dispatch_due_item(trip, rt, ortstag, now_utc=moment)
    assert BriefingSlotStore("u2231-unreach").is_recorded(trip.id, rt, ortstag) is False
    sched._dispatch_due_item(trip, rt, ortstag, now_utc=moment)
    assert len(sched.versandversuche) == 2
