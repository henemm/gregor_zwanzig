"""TDD RED -- Feature #1539 (S6): Fehler, Frist und Hauptfaden beim parallelen Warn-Alarm.

SPEC: docs/specs/modules/feat_1539_s6_compare_parallel.md (AC-5, AC-8, AC-10)

* AC-5: endliche Frist (60 s je Preset, hoechstens 180 s Lauf-Frist, Konstanten aus
  ``services.trip_alert``); ein nicht abgeschlossener Ort (``skipped``) zaehlt als
  gescheitertes Preset und steht mit Grund im Log.
* AC-8: Fehler/Fristablauf eines Ortes geht wie bisher als Ausnahme aus
  ``_fetch_locations`` hoch (nach Abschluss ALLER Abrufe), das Preset zaehlt in
  ``last_failed_count``, Folge-Presets laufen weiter, es entsteht nie eine Teilmenge
  ohne Entwarnungs-Basis und kein Warn-Stand wird veraendert.
* AC-10: ``_day_window_end`` und alle Schreibzugriffe im Hauptfaden; im Worker nur
  ``get_official_alerts_for_location``; Ergebnis stimmt ueber Wiederholungen mit dem
  seriellen ueberein.

Frist-Test: ein Slot, Frist 0,7 s, 0,4 s je Ort -> der zweite Abruf scheitert an der
Frist. Heute gibt es keine Frist und der Ortsfehler stoppt die Schleife vor dem
letzten Ort.
"""
from __future__ import annotations

# ruff: noqa: F811
import logging
import re
import threading
import time
from datetime import datetime, timezone

import pytest

from services.compare_official_alert import CompareOfficialAlertService
from tests.tdd._compare_alert_parallel_fixtures import (  # noqa: F401
    WarnRand,
    dateien_schreiben,
    frist_setzen,
    ist_worker,
    neue_kennung,
    neue_orte,
    preset_dict,
    pruefling_aus_worktree,
    settings_dummy,
    slots_setzen,
    thread_fehler,
    umgebung,
    warn_ergebnis,
    warnquelle_registriert,
)

pruefling_aus_worktree()

GRUND = re.compile(r"deadline|timeout|frist", re.I)


def _dienst(tag: str, **kw) -> CompareOfficialAlertService:
    return CompareOfficialAlertService(
        settings=settings_dummy(), user_id=neue_kennung(tag), **kw)


def _abruf_scheitert_fuer(monkeypatch, lat: float) -> None:
    """Am Warn-Rand (echte Funktion, nur dieser eine Ort wirft)."""
    import services.compare_official_alert as coa

    original = coa.get_official_alerts_for_location

    def abruf(la, lo, **kw):
        if la == lat:
            raise RuntimeError("Warnabruf gescheitert")
        return original(la, lo, **kw)

    monkeypatch.setattr(coa, "get_official_alerts_for_location", abruf)


# --------------------------------------------------------------------------- #
# AC-8
# --------------------------------------------------------------------------- #
def test_ac8_ortsfehler_wird_nach_allen_abrufen_hochgeworfen_nie_teilmenge(
    umgebung, thread_fehler, monkeypatch,
):
    orte = neue_orte(3, "ac8a")
    slots_setzen(monkeypatch, "official_alerts", 3)
    _abruf_scheitert_fuer(monkeypatch, orte[1].lat)
    quelle = WarnRand(verzoegerung={o.lat: 0.1 for o in orte})
    dienst = _dienst("ac8a")

    with warnquelle_registriert(quelle):
        with pytest.raises(RuntimeError, match="Warnabruf gescheitert"):
            dienst._fetch_locations("p-1539", orte, datetime.now(timezone.utc))

    assert sorted(quelle.lats_abgerufen()) == sorted([orte[0].lat, orte[2].lat]), (
        "die uebrigen Orte werden vollstaendig abgerufen, bevor der Fehler hochgeht")
    assert quelle.max_gleichzeitig >= 2, "Abrufe laufen noch nacheinander"


def test_ac8_fristablauf_geht_als_ausnahme_hoch_mit_grund_im_log(
    umgebung, thread_fehler, monkeypatch, caplog,
):
    orte = neue_orte(3, "ac8b")
    slots_setzen(monkeypatch, "official_alerts", 1)
    frist_setzen(monkeypatch, 0.7)
    quelle = WarnRand(verzoegerung={o.lat: 0.4 for o in orte})
    dienst = _dienst("ac8b")

    with caplog.at_level(logging.ERROR), warnquelle_registriert(quelle):
        with pytest.raises(Exception):
            dienst._fetch_locations("p-1539", orte, datetime.now(timezone.utc))

    assert any(GRUND.search(r.getMessage()) for r in caplog.records
               if r.levelno >= logging.ERROR), "Fristablauf muss mit Grund im Log stehen"


def test_ac8_gescheitertes_preset_zaehlt_folgepreset_laeuft_stand_bleibt_unveraendert(
    umgebung, thread_fehler, monkeypatch,
):
    from app.loader import get_data_root
    from services.alert_state import AlertStateService
    from tests.helpers.compare_briefings import write_compare_briefings

    uid = neue_kennung("ac8c")
    orte = neue_orte(3, "ac8c")  # loc-1/loc-2 im ersten Preset, loc-3 im zweiten
    p1 = preset_dict("p-eins", ["loc-1", "loc-2"])
    p2 = preset_dict("p-zwei", ["loc-3"])
    p1["official_alert_triggers_enabled"] = p2["official_alert_triggers_enabled"] = True
    dateien_schreiben(uid, p1, orte)
    write_compare_briefings(get_data_root() / "users" / uid, [p1, p2])
    slots_setzen(monkeypatch, "official_alerts", 3)
    _abruf_scheitert_fuer(monkeypatch, orte[1].lat)
    mails: list = []
    dienst = CompareOfficialAlertService(
        settings=settings_dummy(), user_id=uid,
        mail_sink=lambda **kw: mails.append(kw))

    with warnquelle_registriert(WarnRand()):
        gesendet = dienst.check_all_compare_presets()

    assert dienst.last_failed_count == 1, "genau das Preset mit dem Ortsfehler gilt als gescheitert"
    assert gesendet == 1 and len(mails) == 1, "das Folge-Preset laeuft weiter und versendet"
    stand = AlertStateService(user_id=uid)
    assert stand.load("p-eins:loc-1") == {} and stand.load("p-eins:loc-2") == {}, (
        "gescheitertes Preset: kein Warn-Stand veraendert")


# --------------------------------------------------------------------------- #
# AC-5 (Lauf-Frist)
# --------------------------------------------------------------------------- #
def test_ac5_lauf_frist_begrenzt_die_wirksame_frist(
    umgebung, thread_fehler, monkeypatch, caplog,
):
    orte = neue_orte(3, "ac5a")
    slots_setzen(monkeypatch, "official_alerts", 1)
    quelle = WarnRand(verzoegerung={o.lat: 0.3 for o in orte})
    dienst = _dienst("ac5a")
    dienst._run_deadline_at = time.monotonic() + 0.45  # Preset-Marke bleibt 60 s

    with caplog.at_level(logging.ERROR), warnquelle_registriert(quelle):
        with pytest.raises(Exception):
            dienst._fetch_locations("p-1539", orte, datetime.now(timezone.utc))

    assert any(GRUND.search(r.getMessage()) for r in caplog.records
               if r.levelno >= logging.ERROR), "Fristablauf nie still"


def test_ac5_lauf_frist_verlaengert_die_60s_marke_nie(umgebung, thread_fehler, monkeypatch):
    orte = neue_orte(3, "ac5b")
    slots_setzen(monkeypatch, "official_alerts", 1)
    frist_setzen(monkeypatch, 0.45)
    quelle = WarnRand(verzoegerung={o.lat: 0.3 for o in orte})
    dienst = _dienst("ac5b")
    dienst._run_deadline_at = time.monotonic() + 1000.0

    with warnquelle_registriert(quelle):
        with pytest.raises(Exception):
            dienst._fetch_locations("p-1539", orte, datetime.now(timezone.utc))


def test_ac5_check_all_setzt_lauf_frist_hoechstens_180s_und_loest_sie_am_ende(
    umgebung, thread_fehler, monkeypatch,
):
    import services.trip_alert as ta

    uid = neue_kennung("ac5c")
    orte = neue_orte(2, "ac5c")
    preset = preset_dict("p-ac5c", [o.id for o in orte])
    preset["official_alert_triggers_enabled"] = True
    dateien_schreiben(uid, preset, orte)
    gesehen: list = []
    box: list = []
    quelle = WarnRand(beim_abruf=lambda _lat: gesehen.append(
        getattr(box[0], "_run_deadline_at", "fehlt")))
    dienst = CompareOfficialAlertService(
        settings=settings_dummy(), user_id=uid, mail_sink=lambda **kw: None)
    box.append(dienst)
    start = time.monotonic()

    with warnquelle_registriert(quelle):
        dienst.check_all_compare_presets()

    assert gesehen, "Setup: es gab Warn-Abrufe"
    for marke in gesehen:
        assert isinstance(marke, float), "waehrend des Laufs ist eine Lauf-Frist gesetzt"
        assert start < marke <= start + ta.ALERT_RUN_DEADLINE_SECONDS + 5.0
    assert dienst._run_deadline_at is None, "am Laufende wieder None"


# --------------------------------------------------------------------------- #
# AC-10
# --------------------------------------------------------------------------- #
class _Beobachtend(CompareOfficialAlertService):
    """Echter Dienst; zeichnet nur auf, in welchem Faden ``_day_window_end`` laeuft."""

    fenster_threads: list = []

    def _day_window_end(self, preset_id, loc, now):
        type(self).fenster_threads.append(threading.current_thread().name)
        return super()._day_window_end(preset_id, loc, now)


def test_ac10_hauptfaden_schreibt_worker_ruft_nur_den_warnabruf_ergebnis_stabil(
    umgebung, thread_fehler, monkeypatch,
):
    orte = neue_orte(4, "ac10")
    haupt = threading.current_thread().name
    verz = {orte[0].lat: 0.3, orte[1].lat: 0.2, orte[2].lat: 0.1, orte[3].lat: 0.0}
    jetzt = datetime.now(timezone.utc)
    dienst = _Beobachtend(settings=settings_dummy(), user_id=neue_kennung("ac10"))

    slots_setzen(monkeypatch, "official_alerts", 1)
    with warnquelle_registriert(WarnRand(verzoegerung=verz)):
        erwartet = warn_ergebnis(*dienst._fetch_locations("p-1539", orte, jetzt))
    _Beobachtend.fenster_threads.clear()
    slots_setzen(monkeypatch, "official_alerts", 3)

    quelle = WarnRand(verzoegerung=verz)
    with warnquelle_registriert(quelle):
        for _ in range(10):
            assert warn_ergebnis(*dienst._fetch_locations("p-1539", orte, jetzt)) == erwartet

    assert _Beobachtend.fenster_threads and set(_Beobachtend.fenster_threads) == {haupt}, (
        "_day_window_end (Dateizugriff) gehoert in den Hauptfaden")
    assert all(ist_worker(a["thread"]) for a in quelle.aufrufe), "Warn-Abruf laeuft im Worker"
    assert quelle.max_gleichzeitig >= 2
