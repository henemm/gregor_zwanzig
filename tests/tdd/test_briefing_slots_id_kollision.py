"""Doppelversand-Schutz bei ID-Kollision Trip/Ortsvergleich (#2281, AC-5).

SPEC: docs/specs/modules/feat_2281_vergleich_versand_historie.md (AC-5, Test 3)

Wirkort: ``BriefingSlotStore._log_traegt_versand`` und
``BriefingSlotStore._log_bezeugt_versand``. Beide zaehlen nach #2281 nur
Eintraege mit ``entity_type in (None, "trip")``.

Ausgangslage ist ein vorab gelegter Log (legitim: gemessen wird der LESER).
``briefing_slots.json`` existiert NICHT -- sonst gaebe ``_log_bezeugt_versand``
unbedingt ``False`` zurueck und jede "unterdrueckt nicht"-Aussage waere vakuum-
gruen (das prueft ``_vorbedingung_keine_slot_datei``).

Faelle:

* Compare-Eintrag MIT ``trip_id`` == Trip-ID (Fehl-/Kompat-Schreiber):
  **RED heute** -- der einzige Fall, der die Mutation "Guard entfernen" faengt.
* Compare-Eintrag ohne ``trip_id`` (spec-konforme Form): Regressionswaechter
  (heute gruen) -- faengt einen kuenftigen Leser, der nach ``entity_id`` sucht.
* Echter Trip-Eintrag (neue Form mit ``entity_type="trip"``) und Alt-Eintrag
  nur mit ``trip_id``: schuetzen weiterhin. Regressionswaechter (heute gruen) --
  faengt einen Guard ``== "trip"``, der ``None`` (Altbestand) verliert.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone

import pytest

from services.briefing_slots import BriefingSlotStore

ID = "gleiche-kennung"
SLOT = "morning"
TAG = date(2026, 10, 21)
GESENDET = datetime(2026, 10, 21, 6, 0, tzinfo=timezone.utc).isoformat()


def _basis(**extra) -> dict:
    e = {"kind": SLOT, "sent_at": GESENDET, "channels": ["email"], "on_demand": False}
    e.update(extra)
    return e


COMPARE_MIT_TRIP_ID = _basis(entity_type="compare", entity_id=ID, trip_id=ID)
COMPARE_OHNE_TRIP_ID = _basis(entity_type="compare", entity_id=ID)
TRIP_NEU = _basis(entity_type="trip", entity_id=ID, trip_id=ID)
TRIP_ALT = _basis(trip_id=ID)


def _store(tmp_path, *eintraege: dict) -> BriefingSlotStore:
    (tmp_path / "briefing_log.json").write_text(
        json.dumps({"entries": list(eintraege)}), encoding="utf-8",
    )
    store = BriefingSlotStore("kollision-nutzer", data_dir=tmp_path)
    _vorbedingung_keine_slot_datei(tmp_path)
    return store


def _vorbedingung_keine_slot_datei(ordner) -> None:
    assert not (ordner / "briefing_slots.json").exists(), (
        "Vorbedingung: ohne Slot-Datei liest _log_bezeugt_versand den Log"
    )


def _traegt(store) -> bool:
    return store._log_traegt_versand(ID, SLOT, TAG, None)


def _bezeugt(store) -> bool:
    return store._log_bezeugt_versand(ID, SLOT, TAG, None)


LESER = [pytest.param(_traegt, id="log_traegt_versand"),
         pytest.param(_bezeugt, id="log_bezeugt_versand")]


# ─────────────── Compare-Eintrag unterdrueckt den Trip NICHT ────────────────


@pytest.mark.parametrize("leser", LESER)
def test_compare_eintrag_mit_gleicher_trip_id_zaehlt_nicht_als_trip_versand(tmp_path, leser):
    """AC-5 (RED heute).

    GIVEN im Log steht nur ein Compare-Eintrag (``entity_type="compare"``),
          der zufaellig ``trip_id`` == Trip-ID traegt, Slot und Tag passen.
    WHEN  der Doppelversand-Schutz fuer den Trip prueft.
    THEN  ``False`` -- ein Ortsvergleich nimmt dem Trip sein Briefing nicht.

    RED heute: der Leser prueft nur ``trip_id``/``kind``.
    """
    store = _store(tmp_path, COMPARE_MIT_TRIP_ID)
    assert leser(store) is False, "AC-5: Compare-Eintrag darf den Trip-Slot nicht als versendet zeigen"


@pytest.mark.parametrize("leser", LESER)
def test_compare_eintrag_ohne_trip_id_zaehlt_nicht_als_trip_versand(tmp_path, leser):
    """AC-5 -- Regressionswaechter (heute gruen): spec-konformer Compare-Eintrag
    (``entity_id`` == Trip-ID, kein ``trip_id``)."""
    store = _store(tmp_path, COMPARE_OHNE_TRIP_ID)
    assert leser(store) is False, "AC-5: Compare-Eintrag darf den Trip-Slot nicht als versendet zeigen"


# ─────────────── Echter Trip-Eintrag schuetzt weiterhin ─────────────────────


@pytest.mark.parametrize("leser", LESER)
@pytest.mark.parametrize("trip_eintrag", [pytest.param(TRIP_NEU, id="trip-neu"),
                                          pytest.param(TRIP_ALT, id="trip-altbestand")])
def test_echter_trip_eintrag_schuetzt_weiterhin(tmp_path, leser, trip_eintrag):
    """AC-5 -- Regressionswaechter (heute gruen): neben einem Compare-Eintrag
    gleicher ID schuetzt ein echter Trip-Eintrag (neu oder Altbestand ohne
    ``entity_type``) weiterhin vor Doppelversand."""
    store = _store(tmp_path, COMPARE_MIT_TRIP_ID, trip_eintrag)
    assert leser(store) is True, "AC-5: echter Trip-Eintrag muss den Slot weiterhin belegen"
