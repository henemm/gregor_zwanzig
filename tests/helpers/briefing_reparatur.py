"""Gemeinsame, mock-freie Bausteine fuer die #2231-Reparatur-Tests.

SPEC: docs/specs/modules/fix_2231_slot_reparatur.md

Benutzt von:
* ``tests/test_briefing_slot_reparatur.py`` (AC-1..AC-5, AC-7, AC-8)
* ``tests/test_briefing_log_beschaedigt.py`` (AC-6, AC-7, AC-9)

:func:`zaehlender_scheduler` ist eine ECHTE Unterklasse von
``TripReportSchedulerService``; ersetzt ist nur die Naht zum Netz
(``_send_trip_report_outcome``), die vorgegebene Ausgaenge liefert und jeden
Versandversuch mitschreibt (Haus-Muster
``test_briefing_slot_idempotenz._scheduler_mit_festem_ausgang``).

:func:`takt` faehrt den ECHTEN stuendlichen Trip-Pfad (``TripDispatchStrategy``:
``collect_due`` → ``pre_pass`` → ``dispatch_one``). Bewusst nicht direkt
``_collect_due_trips``: gemessen wird der Takt, den der Produktivpfad faehrt.

Ortszone der Trips ist ``Atlantic/Reykjavik`` (ganzjaehrig UTC+0): Ortstag =
UTC-Tag.
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime
from pathlib import Path

from app.loader import get_data_dir
from tests.helpers.briefing_imminent_fixtures import (
    fresh_uid,
    settings_email_only,
    write_user_tier,
)

SLOTS_DATEI = "briefing_slots.json"
LOG_DATEI = "briefing_log.json"
MARKER = "rebuilt_from_log_at"

#: Beschaedigte Inhalte: Abbruch-JSON, Liste statt Objekt, String statt Objekt.
KAPUTT_ABBRUCH = '{"entries": [{"trip_id": "abgeschnitten'
KAPUTT_LISTE = '[{"trip_id": "x"}]'
KAPUTT_TEXT = '"text"'


def nutzer(kennung: str) -> str:
    """Eigene Kennung je Fall (Mandantentrennung, nie ``default``);
    ``_isolate_data_root`` gibt jedem Test einen frischen Daten-Baum."""
    uid = fresh_uid(f"2231-{kennung}")
    write_user_tier(uid)
    return uid


def pfad(uid: str, name: str) -> Path:
    d = get_data_dir(uid)
    d.mkdir(parents=True, exist_ok=True)
    return d / name


def quarantaene(ordner: Path, name: str) -> list[Path]:
    """Beiseitegelegte Dateien ``<name>.corrupt-<UTC>`` in ``ordner``."""
    return sorted(Path(ordner).glob(f"{name}.corrupt-*"))


def lies_json(p: Path) -> object:
    return json.loads(p.read_text(encoding="utf-8"))


def log_eintrag(trip_id: str, kind: str, sent_at: datetime, *,
                on_demand: bool = False) -> dict:
    """Ein Eintrag im Format von ``_append_briefing_log``."""
    return {
        "trip_id": trip_id, "kind": kind, "sent_at": sent_at.isoformat(),
        "channels": ["email"], "on_demand": on_demand,
    }


def error_zeilen(caplog, *stichworte: str) -> list[logging.LogRecord]:
    """ERROR-Eintraege, deren Text ALLE Stichworte enthaelt — damit der schon
    heute vorhandene ERROR aus ``_load`` die Reparatur-Zusicherung (AC-7)
    nicht zufaellig erfuellt."""
    return [
        r for r in caplog.records
        if r.levelno >= logging.ERROR
        and all(s in r.getMessage() for s in stichworte)
    ]


def zaehlender_scheduler(uid: str, ausgaenge: list):
    """Echter Scheduler, nur ``_send_trip_report_outcome`` ersetzt.

    ``ausgaenge`` wird der Reihe nach abgegeben; der letzte wiederholt sich.
    ``versandversuche`` zaehlt jeden Aufruf — das ist die Versandzahl.
    """
    from services.trip_report_scheduler import TripReportSchedulerService

    class _Zaehlend(TripReportSchedulerService):
        def _send_trip_report_outcome(self, trip, report_type, **kwargs):
            self.versandversuche.append((trip.id, report_type))
            idx = min(len(self.versandversuche) - 1, len(self.ausgaenge) - 1)
            return self.ausgaenge[idx]

    s = _Zaehlend(settings=settings_email_only(), user_id=uid)
    s.versandversuche = []
    s.ausgaenge = list(ausgaenge)
    return s


def strategie(uid: str, service):
    """Der ECHTE stuendliche Trip-Pfad mit ausgetauschtem ``_service``."""
    from services.dispatch_orchestrator import TripDispatchStrategy

    st = TripDispatchStrategy(settings=settings_email_only(), user_id=uid)
    st._service = service
    return st


def takt(st, now_utc: datetime) -> list:
    """Ein Sammellauf wie ``run_briefing_dispatch`` (ohne 2-s-Pause)."""
    due = st.collect_due(now_utc)
    st.pre_pass(now_utc, due)
    for item in due:
        st.dispatch_one(item, now_utc)
    return [(t.id, rt) for t, rt, _ in due]


def ortstag(moment: datetime) -> date:
    from tests.helpers.briefing_imminent_fixtures import TRIP_ZONE

    return moment.astimezone(TRIP_ZONE).date()
