"""#2231: beschaedigte ``briefing_slots.json`` wird repariert statt dauerhaft zu sperren.

SPEC: docs/specs/modules/fix_2231_slot_reparatur.md (AC-1..AC-5, AC-7, AC-8)
Loest AC-5 von docs/specs/modules/fail_closed_versand_defaults.md ab.

Echter ``BriefingSlotStore`` in ``tmp_path`` bzw. echter Scheduler-Takt im
isolierten Datenbaum — keine Mocks. Ersetzt ist im Takt-Test nur die Naht zum
Netz (``zaehlender_scheduler``).

Waechter (heute schon gruen, sollen es bleiben): die lock-freien Leser in
AC-5 und die Gegenprobe zu AC-4 (Datei fehlt ⇒ Ableitung greift).
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import date, datetime, timedelta, timezone

import pytest

from services.briefing_slots import BriefingSlotStore

from tests.helpers.briefing_reparatur import (
    KAPUTT_ABBRUCH,
    KAPUTT_LISTE,
    KAPUTT_TEXT,
    LOG_DATEI,
    MARKER,
    SLOTS_DATEI,
    error_zeilen,
    lies_json,
    log_eintrag,
    nutzer,
    ortstag,
    pfad,
    quarantaene,
    strategie,
    takt,
    zaehlender_scheduler,
)

DAY = date(2026, 8, 20)
NOW = datetime(2026, 8, 20, 6, 0, tzinfo=timezone.utc)
KAPUTT = pytest.mark.parametrize(
    "inhalt", [KAPUTT_ABBRUCH, KAPUTT_LISTE, KAPUTT_TEXT],
    ids=["abbruch_json", "liste_statt_objekt", "text_statt_objekt"],
)


def _kaputt(ordner, inhalt: str):
    p = ordner / SLOTS_DATEI
    p.write_text(inhalt, encoding="utf-8")
    return p


def _log(ordner, *eintraege: dict) -> None:
    (ordner / LOG_DATEI).write_text(
        json.dumps({"entries": list(eintraege)}, indent=2), encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# AC-1 — Reparatur legt beiseite, setzt Marker, Slot reserviert wieder
# ---------------------------------------------------------------------------


@KAPUTT
def test_ac1_reparatur_legt_kaputte_datei_beiseite_und_setzt_marker(tmp_path, inhalt):
    """GIVEN beschaedigte ``briefing_slots.json``
    WHEN ``repair_if_corrupt`` laeuft
    THEN liegt die Datei als ``.corrupt-*`` beiseite, eine neue gueltige Datei
         traegt den Marker ``rebuilt_from_log_at`` und ein unversendeter Slot
         reserviert (keine Dauersperre).
    """
    _kaputt(tmp_path, inhalt)
    store = BriefingSlotStore("user-a", data_dir=tmp_path)

    assert store.repair_if_corrupt(moment=NOW) is True

    assert len(quarantaene(tmp_path, SLOTS_DATEI)) == 1
    assert re.search(
        r"briefing_slots\.json\.corrupt-\d{8}T\d{6}Z(-\d+)?$",
        quarantaene(tmp_path, SLOTS_DATEI)[0].name,
    )  # F004: Dateinamen-Muster
    neu = lies_json(tmp_path / SLOTS_DATEI)
    assert isinstance(neu, dict), neu
    assert neu.get("entries") == [], neu
    assert neu.get(MARKER) == NOW.isoformat(), neu
    assert store.reserve("t1", "morning", DAY, moment=NOW) is True


def test_ac1_reparatur_verzeichnis_statt_datei(tmp_path):
    """GIVEN an der Stelle von ``briefing_slots.json`` steht ein Verzeichnis
    (``read_text`` wirft ``IsADirectoryError``)
    WHEN repariert wird
    THEN wird es beiseitegelegt und der Slot reserviert wieder.
    """
    (tmp_path / SLOTS_DATEI).mkdir()
    store = BriefingSlotStore("user-a", data_dir=tmp_path)

    assert store.repair_if_corrupt(moment=NOW) is True

    beiseite = quarantaene(tmp_path, SLOTS_DATEI)
    assert len(beiseite) == 1 and beiseite[0].is_dir(), beiseite
    assert lies_json(tmp_path / SLOTS_DATEI).get(MARKER) == NOW.isoformat()
    assert store.reserve("t1", "morning", DAY, moment=NOW) is True


def test_ac1_takt_mit_kaputter_slot_datei_versendet_das_briefing():
    """AC-1 ueber den ECHTEN stuendlichen Takt (Verdrahtung).

    GIVEN ein faelliger Trip und eine beschaedigte ``briefing_slots.json``
    WHEN der Sammellauf laeuft
    THEN wird repariert und das Morgen-Briefing genau einmal versendet.

    Ohne diesen Test bliebe ein vergessener Reparatur-Aufruf in
    ``_collect_due_trips`` unentdeckt: ``is_recorded_or_claimed`` liefert bei
    beschaedigter Datei ``True``, der Trip wird nie faellig und ``reserve``
    (mit der Reparatur im Schreibpfad) nie erreicht.
    """
    from freezegun import freeze_time

    from tests.helpers.briefing_imminent_fixtures import write_trip

    jetzt = datetime(2026, 3, 15, 7, 5, tzinfo=timezone.utc)
    with freeze_time(jetzt):
        uid = nutzer("ac1takt")
        trip_id = "t-2231-ac1"
        write_trip(uid, trip_id, morgen_stunde=7, abend_stunde=18)
        slots = pfad(uid, SLOTS_DATEI)
        slots.write_text(KAPUTT_ABBRUCH, encoding="utf-8")
        s = zaehlender_scheduler(uid, ["sent"])
        takt(strategie(uid, s), jetzt)

    assert s.versandversuche == [(trip_id, "morning")], (
        "Beschaedigte Slot-Datei darf das Briefing nicht dauerhaft sperren — "
        f"Versuche: {s.versandversuche!r}"
    )
    assert len(quarantaene(slots.parent, SLOTS_DATEI)) == 1
    neu = lies_json(slots)
    assert neu.get(MARKER), neu
    eintraege = [
        e for e in neu.get("entries", [])
        if e.get("trip_id") == trip_id and e.get("slot") == "morning"
        and e.get("local_day") == ortstag(jetzt).isoformat()
    ]
    assert len(eintraege) == 1 and eintraege[0].get("outcome") == "sent", neu


# ---------------------------------------------------------------------------
# AC-2 — Doppelversand-Schutz aus dem Versandprotokoll nach der Reparatur
# ---------------------------------------------------------------------------


def test_ac2_protokoll_bezeugt_versand_nach_reparatur(tmp_path):
    """GIVEN beschaedigte Slot-Datei, Protokoll: t1/morning heute regulaer
          versendet; t2/morning heute nur ANGEFORDERT; t3/morning gestern
    WHEN repariert und danach reserviert wird
    THEN geht t1/morning nicht erneut raus; t1/evening, t2/morning und
         t3/morning reservieren normal — und der Marker ueberlebt spaetere
         Schreibvorgaenge.
    """
    _kaputt(tmp_path, KAPUTT_ABBRUCH)
    _log(
        tmp_path,
        log_eintrag("t1", "morning", NOW - timedelta(hours=1)),
        log_eintrag("t2", "morning", NOW - timedelta(hours=1), on_demand=True),
        log_eintrag("t3", "morning", NOW - timedelta(days=1)),
    )
    store = BriefingSlotStore("user-a", data_dir=tmp_path)

    assert store.repair_if_corrupt(moment=NOW) is True

    assert store.reserve("t1", "evening", DAY, moment=NOW) is True
    assert store.reserve("t2", "morning", DAY, moment=NOW) is True
    assert store.reserve("t3", "morning", DAY, moment=NOW) is True
    assert store.is_recorded("t1", "morning", DAY) is True
    assert store.reserve("t1", "morning", DAY, moment=NOW) is False
    assert lies_json(tmp_path / SLOTS_DATEI).get(MARKER) == NOW.isoformat(), (
        "Marker muss nach Read-Modify-Write erhalten bleiben, sonst entfaellt "
        "der Protokoll-Zeuge nach dem ersten Vermerk."
    )


# ---------------------------------------------------------------------------
# AC-3 — beiseitegelegte Datei unveraendert, nie ueberschrieben
# ---------------------------------------------------------------------------


def test_ac3_beiseitegelegte_datei_bleibt_byte_identisch_auch_beim_zweiten_defekt(tmp_path):
    """GIVEN Defekt A wird repariert, danach tritt Defekt B auf — bei
          angehaltener Uhr, also identischem Zeitstempel
    WHEN erneut repariert wird
    THEN liegen zwei verschiedene ``.corrupt-*``-Dateien vor, A unveraendert.
    """
    from freezegun import freeze_time

    store = BriefingSlotStore("user-a", data_dir=tmp_path)
    with freeze_time(NOW):
        a = _kaputt(tmp_path, KAPUTT_ABBRUCH).read_bytes()
        assert store.repair_if_corrupt(moment=NOW) is True
        erste = quarantaene(tmp_path, SLOTS_DATEI)
        assert len(erste) == 1 and erste[0].read_bytes() == a

        b = _kaputt(tmp_path, KAPUTT_LISTE).read_bytes()
        assert store.repair_if_corrupt(moment=NOW) is True

    beide = quarantaene(tmp_path, SLOTS_DATEI)
    assert len(beide) == 2, beide
    assert erste[0].read_bytes() == a, "Erste Beiseite-Datei wurde ueberschrieben."
    assert {p.read_bytes() for p in beide} == {a, b}


# ---------------------------------------------------------------------------
# AC-4 — gueltige Datei ohne Marker: keine Ableitung (PO 2026-08-11)
# ---------------------------------------------------------------------------


def test_ac4_gueltige_datei_ohne_marker_bleibt_unangetastet(tmp_path):
    """GIVEN gueltige Datei ohne Marker, Protokoll zeigt Versand heute
    WHEN geprueft und repariert wird
    THEN keine Ableitung (``is_recorded`` False, ``reserve`` True), keine
         Umbenennung, ``repair_if_corrupt`` liefert False.
    """
    p = tmp_path / SLOTS_DATEI
    p.write_text(json.dumps({"entries": []}), encoding="utf-8")
    vorher = p.read_bytes()
    _log(tmp_path, log_eintrag("t1", "morning", NOW - timedelta(hours=1)))
    store = BriefingSlotStore("user-a", data_dir=tmp_path)

    assert store.repair_if_corrupt(moment=NOW) is False
    assert p.read_bytes() == vorher
    assert quarantaene(tmp_path, SLOTS_DATEI) == []
    assert store.is_recorded("t1", "morning", DAY) is False
    assert store.reserve("t1", "morning", DAY, moment=NOW) is True


def test_ac4_gegenprobe_fehlende_datei_leitet_weiter_ab(tmp_path):
    """Waechter: fehlt die Datei, gilt die Rollout-Ableitung weiter."""
    _log(tmp_path, log_eintrag("t1", "morning", NOW - timedelta(hours=1)))
    store = BriefingSlotStore("user-a", data_dir=tmp_path)

    assert store.is_recorded("t1", "morning", DAY) is True
    assert store.reserve("t1", "morning", DAY, moment=NOW) is False


# ---------------------------------------------------------------------------
# AC-5 — lock-freie Leser reparieren nicht
# ---------------------------------------------------------------------------


@KAPUTT
def test_ac5_leser_ohne_sperre_antworten_true_und_reparieren_nicht(tmp_path, inhalt):
    """GIVEN beschaedigte Datei
    WHEN ``is_recorded`` / ``is_recorded_or_claimed`` fragen
    THEN beide True, Datei unveraendert, keine ``.corrupt-*`` — erst
         ``repair_if_corrupt`` legt beiseite.
    """
    p = _kaputt(tmp_path, inhalt)
    vorher = p.read_bytes()
    store = BriefingSlotStore("user-a", data_dir=tmp_path)

    assert store.is_recorded("t1", "morning", DAY) is True
    assert store.is_recorded_or_claimed("t1", "morning", DAY, moment=NOW) is True
    assert p.read_bytes() == vorher
    assert quarantaene(tmp_path, SLOTS_DATEI) == []

    assert store.repair_if_corrupt(moment=NOW) is True
    assert len(quarantaene(tmp_path, SLOTS_DATEI)) == 1


# ---------------------------------------------------------------------------
# AC-7 — Reparatur ist nie lautlos
# ---------------------------------------------------------------------------


@KAPUTT
def test_ac7_reparatur_der_slot_datei_schreibt_genau_eine_error_zeile(tmp_path, caplog, inhalt):
    """GIVEN beschaedigte Slot-Datei
    WHEN repariert wird
    THEN genau eine ERROR-Zeile nennt den Dateinamen UND das Beiseite-Ziel.

    Gezaehlt werden nur Zeilen mit ``.corrupt-`` — der schon heute
    vorhandene ERROR aus ``_load`` erfuellt die Zusicherung nicht.
    """
    _kaputt(tmp_path, inhalt)
    store = BriefingSlotStore("user-a", data_dir=tmp_path)

    with caplog.at_level(logging.ERROR, logger="briefing_slots"):
        store.repair_if_corrupt(moment=NOW)

    beiseite = quarantaene(tmp_path, SLOTS_DATEI)
    assert len(beiseite) == 1
    zeilen = error_zeilen(caplog, SLOTS_DATEI, beiseite[0].name)
    assert len(zeilen) == 1, [
        (r.levelname, r.getMessage()) for r in caplog.records
    ]


# ---------------------------------------------------------------------------
# AC-8 — Mandantentrennung
# ---------------------------------------------------------------------------


def test_ac8_nur_beschaedigter_nutzer_wird_repariert(tmp_path):
    """GIVEN A beschaedigt, B intakt
    WHEN beide reparieren und reservieren
    THEN nur A bekommt ``.corrupt-*`` und Marker; B bleibt byte-identisch
         und reserviert normal.
    """
    a_dir, b_dir = tmp_path / "a", tmp_path / "b"
    a_dir.mkdir()
    b_dir.mkdir()
    _kaputt(a_dir, KAPUTT_ABBRUCH)
    b_datei = b_dir / SLOTS_DATEI
    b_datei.write_text(json.dumps({"entries": []}), encoding="utf-8")
    b_vorher = b_datei.read_bytes()
    a = BriefingSlotStore("user-a", data_dir=a_dir)
    b = BriefingSlotStore("user-b", data_dir=b_dir)

    assert a.repair_if_corrupt(moment=NOW) is True
    assert b.repair_if_corrupt(moment=NOW) is False

    assert len(quarantaene(a_dir, SLOTS_DATEI)) == 1
    assert lies_json(a_dir / SLOTS_DATEI).get(MARKER) == NOW.isoformat()
    assert quarantaene(b_dir, SLOTS_DATEI) == []
    assert b_datei.read_bytes() == b_vorher
    assert a.reserve("t1", "morning", DAY, moment=NOW) is True
    assert b.reserve("t1", "morning", DAY, moment=NOW) is True
    assert MARKER not in lies_json(b_datei)


# ---------------------------------------------------------------------------
# Fix-Loop 1: Schreibpfad-Reparatur, fail-closed bei Rename-Fehler, Zeuge-ERROR
# ---------------------------------------------------------------------------


def test_reserve_ohne_vorherige_reparatur_repariert_im_schreibpfad(tmp_path):
    """F001: ``reserve`` direkt auf kaputter Datei (kein ``repair_if_corrupt``)
    repariert unter der Sperre statt ``False`` zu liefern."""
    _kaputt(tmp_path, KAPUTT_ABBRUCH)
    store = BriefingSlotStore("user-a", data_dir=tmp_path)

    assert store.reserve("t1", "morning", DAY, moment=NOW) is True

    assert len(quarantaene(tmp_path, SLOTS_DATEI)) == 1
    assert MARKER in lies_json(tmp_path / SLOTS_DATEI)


def _rename_scheitert(monkeypatch):
    def _kaputt_rename(src, dst):
        raise OSError(18, "Invalid cross-device link (injiziert)")

    monkeypatch.setattr(os, "rename", _kaputt_rename)


def test_f005_rename_fehler_ist_fail_closed_ohne_absturz(tmp_path, monkeypatch, caplog):
    """F005: scheitert das Beiseitelegen, bleibt die Datei byte-identisch,
    ``repair_if_corrupt`` liefert False ohne Ausnahme, ``reserve`` bleibt
    False, genau die ERROR-Zeile nennt die Datei."""
    p = _kaputt(tmp_path, KAPUTT_ABBRUCH)
    vorher = p.read_bytes()
    store = BriefingSlotStore("user-a", data_dir=tmp_path)
    _rename_scheitert(monkeypatch)

    with caplog.at_level(logging.ERROR):
        assert store.repair_if_corrupt(moment=NOW) is False
        assert store.reserve("t1", "morning", DAY, moment=NOW) is False

    assert p.read_bytes() == vorher
    assert quarantaene(tmp_path, SLOTS_DATEI) == []
    assert error_zeilen(caplog, SLOTS_DATEI, "scheiterte")


def test_f005_rename_fehler_im_takt_stuerzt_den_sammellauf_nicht_ab():
    """F005: ``_collect_due_trips`` laeuft ohne Ausnahme durch, nichts geht raus."""
    from freezegun import freeze_time

    from tests.helpers.briefing_imminent_fixtures import write_trip

    jetzt = datetime(2026, 3, 15, 7, 5, tzinfo=timezone.utc)
    mp = pytest.MonkeyPatch()
    try:
        with freeze_time(jetzt):
            uid = nutzer("f005takt")
            write_trip(uid, "t-2231-f005", morgen_stunde=7, abend_stunde=18)
            slots = pfad(uid, SLOTS_DATEI)
            slots.write_text(KAPUTT_ABBRUCH, encoding="utf-8")
            vorher = slots.read_bytes()
            s = zaehlender_scheduler(uid, ["sent"])
            _rename_scheitert(mp)
            takt(strategie(uid, s), jetzt)
    finally:
        mp.undo()

    assert s.versandversuche == []
    assert slots.read_bytes() == vorher


def test_f002_kaputtes_protokoll_hinter_repariertem_vermerk_loggt_error(tmp_path, caplog):
    """F002: Datei mit Marker + unlesbares Protokoll ⇒ ``is_recorded`` nennt
    das Protokoll in einer ERROR-Zeile."""
    (tmp_path / SLOTS_DATEI).write_text(
        json.dumps({"entries": [], MARKER: NOW.isoformat()}), encoding="utf-8",
    )
    (tmp_path / LOG_DATEI).write_text(KAPUTT_ABBRUCH, encoding="utf-8")
    store = BriefingSlotStore("user-a", data_dir=tmp_path)

    with caplog.at_level(logging.ERROR):
        assert store.is_recorded("t1", "morning", DAY) is False

    assert error_zeilen(caplog, LOG_DATEI)
