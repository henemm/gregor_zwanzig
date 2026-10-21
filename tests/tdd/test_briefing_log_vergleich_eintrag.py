"""Versand-Historie: Ortsvergleich und Trip schreiben je einen Log-Eintrag (#2281, AC-1).

SPEC: docs/specs/modules/feat_2281_vergleich_versand_historie.md (AC-1, Test 1+2)

Wirkort sind die beiden Versand-Engstellen, NICHT der Schreib-Helfer:

* Ortsvergleich: ``send_one_compare_preset`` -- Cron (``on_demand=False``, Slot
  aus ``tage_ab_ortstag``) UND Handversand (``on_demand=True``), inkl. der
  echten Handversand-Form aus ``send_compare_preset`` (ohne ``target_date``/
  ``tage_ab_ortstag`` -> Slot ``morning``).
* Trip: ``TripReportSchedulerService._send_trip_report_outcome``.

Mock-frei: echte Dateien auf der isolierten Datenwurzel (autouse
``_isolate_data_root``), Preset ueber den echten Loader, Wetter ueber die
etablierte ``engine_naht`` (Vergleich) bzw. ``GZ_TEST_FIXTURE_DIR`` (Trip),
Transport ueber den geteilten Aufzeichner. Kein Fixture schreibt
``entity_type``/``entity_id`` -- das muss das Produkt tun.

Kanaele: der Nutzer hat E-Mail, Telegram, SMS und Premium-SMS eingeschaltet,
das SMS-Tageslimit ist aber erschoepft -> zugestellt werden nur E-Mail und
Telegram. Der Eintrag muss die ZUGESTELLTEN Kanaele tragen
(``send_result.sent_channels``), nicht die konfigurierten.

RED heute: der Vergleich schreibt keinen Eintrag; der Trip-Eintrag traegt weder
``entity_type`` noch ``entity_id``.
"""
from __future__ import annotations

from datetime import datetime

import pytest

from services.trip_report_scheduler import TripReportSchedulerService
from tests.tdd._briefing_log_historie_fixtures import (
    eintraege,
    mitschrift,  # noqa: F401 -- Fixture
    trip_anlegen,
    trip_nutzer,
    vergleich,  # noqa: F401 -- Fixture
    vergleich_nutzer,
    vergleich_senden,
)


FAELLE = [
    pytest.param(False, 0, "morning", id="cron-morgen"),
    pytest.param(False, 1, "evening", id="cron-abend"),
    pytest.param(True, 0, "morning", id="hand-morgen"),
    pytest.param(True, 1, "evening", id="hand-abend"),
    pytest.param(True, None, "morning", id="hand-echte-aufrufform-ohne-zieltag"),
]


@pytest.mark.parametrize("on_demand, tage_ab_ortstag, slot", FAELLE)
def test_vergleich_versand_schreibt_genau_einen_compare_eintrag(
    vergleich, on_demand, tage_ab_ortstag, slot,  # noqa: F401, F811
):
    """AC-1 / Test 1.

    GIVEN ein Ortsvergleich (Preset-Kennung P), E-Mail+Telegram zustellbar,
          SMS/Premium-SMS am Tageslimit gesperrt.
    WHEN  ``send_one_compare_preset`` zustellt (Cron bzw. Handversand).
    THEN  genau EIN neuer Eintrag: ``entity_type == "compare"``,
          ``entity_id == P``, ``kind`` aus ``tage_ab_ortstag``,
          ``on_demand`` wie der Aufruf, ``channels`` == zugestellte Kanaele,
          KEIN ``trip_id``.

    RED heute: ``send_one_compare_preset`` schreibt keinen Log-Eintrag.
    """
    uid, preset_id = vergleich_nutzer()
    vorher = len(eintraege(uid))

    ergebnis = vergleich_senden(uid, preset_id, on_demand=on_demand, tage_ab_ortstag=tage_ab_ortstag)

    assert isinstance(ergebnis, tuple), f"Vorbedingung: Erfolgs-Rueckgabe, war {ergebnis!r}"
    assert vergleich.kanaele == ["email", "telegram"], f"Vorbedingung: {vergleich!r}"

    neu = eintraege(uid)[vorher:]
    assert len(neu) == 1, f"AC-1: genau ein neuer Eintrag erwartet, gefunden {len(neu)}: {neu!r}"
    e = neu[0]
    assert e.get("entity_type") == "compare", e
    assert e.get("entity_id") == preset_id, e
    assert "trip_id" not in e, f"AC-1: Compare-Eintrag darf kein trip_id tragen: {e!r}"
    assert e.get("kind") == slot, e
    assert e.get("on_demand") is on_demand, e
    assert e.get("channels") == vergleich.kanaele, (
        f"AC-1: Kanaele muessen die ZUGESTELLTEN sein ({vergleich.kanaele}), war {e.get('channels')!r}"
    )
    assert "sms" not in e["channels"] and "premium_sms" not in e["channels"], e
    gesendet = datetime.fromisoformat(e["sent_at"])
    assert gesendet.tzinfo is not None, e


# ═══════════════════ Test 2: Trip ════════════════════════════════════════════


@pytest.mark.parametrize("slot", ["morning", "evening"])
def test_trip_versand_schreibt_trip_eintrag_mit_entity_feldern(mitschrift, slot):  # noqa: F401, F811
    """AC-1 / Test 2.

    GIVEN ein Trip (nur E-Mail).
    WHEN  ``_send_trip_report_outcome`` planmaessig zustellt.
    THEN  genau ein neuer Eintrag mit ``entity_type == "trip"``,
          ``entity_id == trip.id`` UND weiterhin ``trip_id == trip.id``
          (Kompat fuer ``briefing_slots``), ``kind`` == Slot,
          ``channels == ["email"]``, ``on_demand is False``.

    RED heute: der Trip-Eintrag traegt kein ``entity_type``/``entity_id``.
    """
    uid = trip_nutzer()
    trip = trip_anlegen(uid)
    vorher = len(eintraege(uid))

    ausgang = TripReportSchedulerService(user_id=uid)._send_trip_report_outcome(
        trip, slot, on_demand=False, angefordert=False,
    )

    assert ausgang == "sent", f"Vorbedingung: zugestellt, Ausgang {ausgang!r} ({mitschrift!r})"
    assert mitschrift.kanaele == ["email"], f"Vorbedingung: {mitschrift!r}"
    neu = eintraege(uid)[vorher:]
    assert len(neu) == 1, f"AC-1: genau ein neuer Eintrag erwartet, gefunden {len(neu)}: {neu!r}"
    e = neu[0]
    assert e.get("trip_id") == trip.id, f"AC-1: trip_id muss bleiben: {e!r}"
    assert e.get("kind") == slot, e
    assert e.get("channels") == ["email"], e
    assert e.get("on_demand") is False, e
    assert e.get("entity_type") == "trip", f"AC-1: entity_type fehlt/falsch: {e!r}"
    assert e.get("entity_id") == trip.id, f"AC-1: entity_id fehlt/falsch: {e!r}"
