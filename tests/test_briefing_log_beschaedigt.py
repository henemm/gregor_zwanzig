"""#2231: beschaedigtes Versandprotokoll ``briefing_log.json``.

SPEC: docs/specs/modules/fix_2231_slot_reparatur.md (AC-6, AC-7, AC-9)

* AC-6: ``_append_briefing_log`` liest das Protokoll ungeschuetzt per
  ``json.loads`` — ein kaputtes Protokoll laesst den Lauf NACH dem Versand
  abstuerzen. Soll: beiseitelegen, neu anlegen, ERROR.
* AC-7: auch die Protokoll-Reparatur ist nie lautlos.
* AC-9: verwaister Claim + kaputtes Protokoll ⇒ keine Uebernahme (niemand
  weiss, ob das Briefing schon draussen ist), ERROR, am Folgetag normal.

🔴 Folgerung aus AC-9 fuer GREEN: Ist nur das Protokoll beschaedigt und die
Slot-Datei gueltig, darf der Scheduler-Einstieg das Protokoll NICHT schon vor
der Faelligkeitspruefung leeren — sonst waere der Zeuge weg und der verwaiste
Claim wuerde uebernommen. Eine Protokoll-Reparatur gehoert nur in den
Slot-Reparaturpfad (beide Dateien kaputt) bzw. in ``_append_briefing_log``.
``test_ac9_takt_...`` faengt genau das.

Echte kaputte Dateien im isolierten Datenbaum; keine Mocks. Im Takt-Test ist
nur die Naht zum Netz ersetzt (``zaehlender_scheduler``).
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta, timezone

import pytest

from services import briefing_slots
from services.briefing_slots import BriefingSlotStore

from tests.helpers.briefing_imminent_fixtures import settings_email_only
from tests.helpers.briefing_reparatur import (
    KAPUTT_ABBRUCH,
    KAPUTT_LISTE,
    KAPUTT_TEXT,
    LOG_DATEI,
    SLOTS_DATEI,
    error_zeilen,
    lies_json,
    nutzer,
    ortstag,
    pfad,
    quarantaene,
    strategie,
    takt,
    zaehlender_scheduler,
)

SLOT = "morning"
DAY = date(2026, 8, 20)
NOW = datetime(2026, 8, 20, 6, 0, tzinfo=timezone.utc)
KAPUTT = pytest.mark.parametrize(
    "inhalt", [KAPUTT_ABBRUCH, KAPUTT_LISTE, KAPUTT_TEXT],
    ids=["abbruch_json", "liste_statt_objekt", "text_statt_objekt"],
)


def _alle(caplog) -> list:
    return [(r.levelname, r.name, r.getMessage()) for r in caplog.records]


# ---------------------------------------------------------------------------
# AC-6 / AC-7 — Protokoll schreiben trotz kaputtem Protokoll
# ---------------------------------------------------------------------------


@KAPUTT
def test_ac6_protokolleintrag_trotz_kaputtem_protokoll(inhalt, caplog):
    """GIVEN ``briefing_log.json`` ist beschaedigt
    WHEN nach einem Versand der Protokolleintrag geschrieben wird
    THEN keine Ausnahme; das kaputte Protokoll liegt byte-identisch als
         ``.corrupt-*`` beiseite; das neue Protokoll enthaelt genau den neuen
         Eintrag; genau eine ERROR-Zeile nennt Datei und Beiseite-Ziel.
    """
    from services.trip_report_scheduler import TripReportSchedulerService

    uid = nutzer("ac6")
    log = pfad(uid, LOG_DATEI)
    log.write_text(inhalt, encoding="utf-8")
    vorher = log.read_bytes()
    s = TripReportSchedulerService(settings=settings_email_only(), user_id=uid)

    with caplog.at_level(logging.WARNING):
        s._append_briefing_log("t-2231-ac6", SLOT, ["email"])

    beiseite = quarantaene(log.parent, LOG_DATEI)
    assert len(beiseite) == 1, beiseite
    assert beiseite[0].read_bytes() == vorher
    neu = lies_json(log)
    assert isinstance(neu, dict), neu
    eintraege = neu.get("entries", [])
    assert len(eintraege) == 1, neu
    assert eintraege[0].get("trip_id") == "t-2231-ac6"
    assert eintraege[0].get("kind") == SLOT
    assert len(error_zeilen(caplog, LOG_DATEI, beiseite[0].name)) == 1, _alle(caplog)


def test_ac6_slot_reparatur_legt_auch_kaputtes_protokoll_beiseite(tmp_path, caplog):
    """GIVEN Slot-Datei UND Protokoll beschaedigt
    WHEN die Slot-Reparatur das Protokoll als Zeugen braucht
    THEN beide liegen beiseite, je eine ERROR-Zeile (AC-7), und der Slot
         reserviert (bewusst akzeptiertes Doppelversand-Risiko, Known
         Limitations — gegen den Dauerausfall abgewogen).
    """
    (tmp_path / SLOTS_DATEI).write_text(KAPUTT_ABBRUCH, encoding="utf-8")
    (tmp_path / LOG_DATEI).write_text(KAPUTT_LISTE, encoding="utf-8")
    log_vorher = (tmp_path / LOG_DATEI).read_bytes()
    store = BriefingSlotStore("user-a", data_dir=tmp_path)

    with caplog.at_level(logging.ERROR):
        assert store.repair_if_corrupt(moment=NOW) is True

    slots_beiseite = quarantaene(tmp_path, SLOTS_DATEI)
    log_beiseite = quarantaene(tmp_path, LOG_DATEI)
    assert len(slots_beiseite) == 1 and len(log_beiseite) == 1
    assert log_beiseite[0].read_bytes() == log_vorher
    assert len(error_zeilen(caplog, SLOTS_DATEI, slots_beiseite[0].name)) == 1, _alle(caplog)
    assert len(error_zeilen(caplog, LOG_DATEI, log_beiseite[0].name)) == 1, _alle(caplog)
    assert store.reserve("t1", SLOT, DAY, moment=NOW) is True


# ---------------------------------------------------------------------------
# AC-9 — verwaister Claim + kaputtes Protokoll
# ---------------------------------------------------------------------------


def _verwaister_claim(datei, trip_id: str, tag: date, moment: datetime) -> None:
    """Zustand nach hart beendetem Versandprozess: ``outcome: null``, aelter
    als ``CLAIM_TTL`` (zur Laufzeit gelesen, nie getippt)."""
    alt = moment - timedelta(seconds=briefing_slots.CLAIM_TTL * 2)
    datei.write_text(json.dumps({"entries": [{
        "trip_id": trip_id, "slot": SLOT, "local_day": tag.isoformat(),
        "recorded_at": alt.isoformat(), "outcome": None,
    }]}, indent=2), encoding="utf-8")


@pytest.mark.parametrize("inhalt", [KAPUTT_ABBRUCH, KAPUTT_LISTE],
                         ids=["abbruch_json", "liste_statt_objekt"])
def test_ac9_verwaister_claim_wird_bei_kaputtem_protokoll_nicht_uebernommen(
    tmp_path, inhalt, caplog,
):
    """GIVEN verwaister Claim und beschaedigtes Protokoll
    WHEN ``reserve`` den Claim uebernehmen will
    THEN ``False`` (kein Doppelversand ohne Beleg), ERROR nennt das
         Protokoll, am Folgetag reserviert der Slot normal.

    RED heute: ``_log_traegt_versand`` wertet das kaputte Protokoll still als
    „nicht versendet", der Claim wird uebernommen.
    """
    _verwaister_claim(tmp_path / SLOTS_DATEI, "t1", DAY, NOW)
    (tmp_path / LOG_DATEI).write_text(inhalt, encoding="utf-8")
    store = BriefingSlotStore("user-a", data_dir=tmp_path)

    with caplog.at_level(logging.WARNING):
        reserviert = store.reserve("t1", SLOT, DAY, moment=NOW)

    assert reserviert is False, (
        "Verwaister Claim bei kaputtem Versandprotokoll darf nicht "
        "uebernommen werden (Doppelversand-Risiko)."
    )
    assert error_zeilen(caplog, LOG_DATEI), _alle(caplog)

    folgetag = NOW + timedelta(days=1)
    assert store.reserve("t1", SLOT, DAY + timedelta(days=1), moment=folgetag) is True


def test_ac9_takt_mit_verwaistem_claim_und_kaputtem_protokoll_versendet_nichts(caplog):
    """AC-9 ueber den ECHTEN stuendlichen Takt.

    GIVEN faelliger Trip, verwaister Claim, GUELTIGE Slot-Datei, kaputtes
          Protokoll
    WHEN der Sammellauf laeuft
    THEN kein Versandversuch, ERROR zum Protokoll.

    Faengt auch den Fehlweg, das Protokoll schon im Scheduler-Einstieg zu
    reparieren: danach waere es leer und der Claim wuerde uebernommen.
    """
    from freezegun import freeze_time

    from tests.helpers.briefing_imminent_fixtures import write_trip

    jetzt = datetime(2026, 3, 15, 7, 5, tzinfo=timezone.utc)
    with freeze_time(jetzt):
        uid = nutzer("ac9takt")
        trip_id = "t-2231-ac9"
        write_trip(uid, trip_id, morgen_stunde=7, abend_stunde=18)
        _verwaister_claim(pfad(uid, SLOTS_DATEI), trip_id, ortstag(jetzt), jetzt)
        pfad(uid, LOG_DATEI).write_text(KAPUTT_ABBRUCH, encoding="utf-8")
        s = zaehlender_scheduler(uid, ["sent"])
        with caplog.at_level(logging.WARNING):
            takt(strategie(uid, s), jetzt)

    assert [v for v in s.versandversuche if v == (trip_id, SLOT)] == [], (
        f"Versuche: {s.versandversuche!r}"
    )
    assert error_zeilen(caplog, LOG_DATEI), _alle(caplog)


def test_ac9_gegenprobe_gueltiges_leeres_protokoll_uebernimmt_den_claim():
    """Waechter (heute gruen): derselbe Aufbau mit GUELTIGEM, leerem
    Protokoll ⇒ der verwaiste Claim wird uebernommen, genau ein Versuch
    (#1897-Verhalten bleibt). Ohne diese Probe bewiese „0 Versuche" oben nur,
    dass der Trip gar nicht faellig war.
    """
    from freezegun import freeze_time

    from tests.helpers.briefing_imminent_fixtures import write_trip

    jetzt = datetime(2026, 3, 15, 7, 5, tzinfo=timezone.utc)
    with freeze_time(jetzt):
        uid = nutzer("ac9gegen")
        trip_id = "t-2231-ac9g"
        write_trip(uid, trip_id, morgen_stunde=7, abend_stunde=18)
        _verwaister_claim(pfad(uid, SLOTS_DATEI), trip_id, ortstag(jetzt), jetzt)
        pfad(uid, LOG_DATEI).write_text(json.dumps({"entries": []}), encoding="utf-8")
        s = zaehlender_scheduler(uid, ["sent"])
        takt(strategie(uid, s), jetzt)

    assert [v for v in s.versandversuche if v == (trip_id, SLOT)] == [(trip_id, SLOT)], (
        s.versandversuche
    )



def test_ac6_rename_fehler_beim_protokoll_ist_fail_closed(monkeypatch, caplog):
    """GIVEN kaputtes Protokoll UND ``os.rename`` scheitert (OSError)
    WHEN ``_append_briefing_log`` schreibt
    THEN keine Ausnahme, Protokoll byte-identisch, ERROR nennt den Pfad.
    """
    import os

    from services.trip_report_scheduler import TripReportSchedulerService

    uid = nutzer("ac6rename")
    log = pfad(uid, LOG_DATEI)
    log.write_text(KAPUTT_ABBRUCH, encoding="utf-8")
    vorher = log.read_bytes()
    s = TripReportSchedulerService(settings=settings_email_only(), user_id=uid)

    def _scheitert(src, dst):
        raise OSError(18, "Invalid cross-device link (injiziert)")

    monkeypatch.setattr(os, "rename", _scheitert)
    with caplog.at_level(logging.ERROR):
        s._append_briefing_log("t-2231-rn", SLOT, ["email"])

    assert log.read_bytes() == vorher
    assert quarantaene(log.parent, LOG_DATEI) == []
    assert error_zeilen(caplog, str(log), "scheiterte"), _alle(caplog)
