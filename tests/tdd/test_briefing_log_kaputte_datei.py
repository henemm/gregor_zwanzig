"""Kaputter Briefing-Log laesst den Versand nicht scheitern (#2281, AC-7).

SPEC: docs/specs/modules/feat_2281_vergleich_versand_historie.md (AC-7, Test 5)

Wirkort: der Schreib-Helfer, aufgerufen aus BEIDEN Engstellen. Gemessen wird
deshalb an der Engstelle selbst:

* Ortsvergleich: ``send_one_compare_preset`` -- Erfolg = Rueckgabe des Tupels
  ``(top_ort, empfaenger)`` ohne Ausnahme.
* Trip: ``_send_trip_report_outcome`` -- Erfolg = Rueckgabe ``"sent"``.

Danach: die kaputte Datei liegt byte-identisch als ``briefing_log.json.corrupt-*``
beiseite (Muster #2231, ``lege_beschaedigte_datei_beiseite``), und die frische
Datei enthaelt genau den neuen Eintrag.

RED heute:
* Vergleich: kein Log-Schreiber -> weder Beiseite-Datei noch neuer Eintrag.
* Trip: Beiseitelegen und Fortsetzen gibt es seit #2231 schon; rot ist nur
  das fehlende ``entity_type``/``entity_id`` im frischen Eintrag.
"""
from __future__ import annotations

import json

import pytest

from app.loader import get_data_dir
from services.trip_report_scheduler import TripReportSchedulerService
from tests.helpers.briefing_reparatur import (
    KAPUTT_ABBRUCH,
    KAPUTT_LISTE,
    KAPUTT_TEXT,
    quarantaene,
)
from tests.tdd._briefing_log_historie_fixtures import (
    mitschrift,  # noqa: F401 -- Fixture
    trip_anlegen,
    trip_nutzer,
    vergleich,  # noqa: F401 -- Fixture
    vergleich_nutzer,
    vergleich_senden,
)

LOG = "briefing_log.json"
KAPUTT = pytest.mark.parametrize(
    "inhalt", [KAPUTT_ABBRUCH, KAPUTT_LISTE, KAPUTT_TEXT],
    ids=["abbruch_json", "liste_statt_objekt", "text_statt_objekt"],
)


def _kaputt_ablegen(uid: str, inhalt: str) -> bytes:
    pfad = get_data_dir(uid) / LOG
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(inhalt, encoding="utf-8")
    return pfad.read_bytes()


def _frische_eintraege(uid: str) -> list[dict]:
    pfad = get_data_dir(uid) / LOG
    assert pfad.exists(), f"AC-7: nach dem Versand fehlt {pfad}"
    daten = json.loads(pfad.read_text(encoding="utf-8"))
    assert isinstance(daten, dict), f"AC-7: frische Datei ist kein JSON-Objekt: {daten!r}"
    return list(daten.get("entries", []))


def _beiseite_pruefen(uid: str, vorher: bytes) -> None:
    beiseite = quarantaene(get_data_dir(uid), LOG)
    assert len(beiseite) == 1, f"AC-7: kaputte Datei muss beiseitegelegt sein, gefunden {beiseite!r}"
    assert beiseite[0].read_bytes() == vorher, "AC-7: Beiseite-Datei muss byte-identisch sein"


@KAPUTT
def test_vergleich_versand_trotz_kaputtem_log(vergleich, inhalt):  # noqa: F401, F811
    """AC-7 (Ortsvergleich, Cron).

    GIVEN ``briefing_log.json`` des Nutzers ist kaputt.
    WHEN  ``send_one_compare_preset`` zustellt.
    THEN  Rueckgabe ist das Erfolgs-Tupel (keine Ausnahme), die kaputte Datei
          liegt beiseite, die frische Datei traegt genau den Compare-Eintrag.
    """
    uid, preset_id = vergleich_nutzer()
    vorher = _kaputt_ablegen(uid, inhalt)

    ergebnis = vergleich_senden(uid, preset_id, on_demand=False, tage_ab_ortstag=0)

    assert isinstance(ergebnis, tuple) and len(ergebnis) == 2, (
        f"AC-7: Versand muss Erfolg melden, Rueckgabe {ergebnis!r}"
    )
    assert vergleich.kanaele, f"Vorbedingung: zugestellt ({vergleich!r})"
    _beiseite_pruefen(uid, vorher)
    neu = _frische_eintraege(uid)
    assert len(neu) == 1, f"AC-7: genau der neue Eintrag erwartet, war {neu!r}"
    assert neu[0].get("entity_type") == "compare" and neu[0].get("entity_id") == preset_id, neu


@KAPUTT
def test_trip_versand_trotz_kaputtem_log(mitschrift, inhalt):  # noqa: F401, F811
    """AC-7 (Trip).

    GIVEN ``briefing_log.json`` des Nutzers ist kaputt.
    WHEN  ``_send_trip_report_outcome`` zustellt.
    THEN  Ausgang ``"sent"``, die kaputte Datei liegt beiseite, die frische
          Datei traegt genau den Trip-Eintrag (mit ``entity_type="trip"``).

    Heute schon gruen bis auf ``entity_type``/``entity_id`` (#2231 deckt das
    Beiseitelegen) -- der Test bewacht, dass der neue Helfer das beibehaelt.
    """
    uid = trip_nutzer()
    trip = trip_anlegen(uid)
    vorher = _kaputt_ablegen(uid, inhalt)

    ausgang = TripReportSchedulerService(user_id=uid)._send_trip_report_outcome(
        trip, "morning", on_demand=False, angefordert=False,
    )

    assert ausgang == "sent", f"AC-7: Versand muss Erfolg melden, Ausgang {ausgang!r}"
    assert mitschrift.kanaele == ["email"], f"Vorbedingung: {mitschrift!r}"
    _beiseite_pruefen(uid, vorher)
    neu = _frische_eintraege(uid)
    assert len(neu) == 1, f"AC-7: genau der neue Eintrag erwartet, war {neu!r}"
    assert neu[0].get("trip_id") == trip.id, neu
    assert neu[0].get("entity_type") == "trip" and neu[0].get("entity_id") == trip.id, neu
