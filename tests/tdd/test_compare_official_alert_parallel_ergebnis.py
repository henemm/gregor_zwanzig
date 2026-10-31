"""TDD RED -- Feature #1539 (S6): Warn-Alarm des Ortsvergleichs ruft die Orte parallel ab.

SPEC: docs/specs/modules/feat_1539_s6_compare_parallel.md (AC-6, AC-7)

* AC-6: ``raw`` in Eingabereihenfolge, je Ort eigene ``AllClearQuery`` (eigene
  Quellen-Senke, kein Vermischen), identisch zum seriellen Lauf (Slots = 1).
* AC-7: Abrufe ueberlappen (Treffpunkt), Gesamtdauer < 80 % der Summe, Provider-
  Schluessel ``official_alerts`` (Env-Slotzahl 2 deckelt die Gleichzeitigkeit auf 2;
  ein belegter ``open_meteo``-Slot blockiert den Warn-Abruf nicht).

Echter ``CompareOfficialAlertService._fetch_locations``, echte Warnquelle in der
echten Registry. Heute laufen die Orte nacheinander im aufrufenden Faden.
"""
from __future__ import annotations

# ruff: noqa: F811
import threading
import time
from datetime import datetime, timezone

from services.compare_official_alert import CompareOfficialAlertService
from tests.tdd._compare_alert_parallel_fixtures import (  # noqa: F401
    WarnRand,
    ist_worker,
    neue_kennung,
    neue_orte,
    pruefling_aus_worktree,
    settings_dummy,
    slots_setzen,
    thread_fehler,
    umgebung,
    warn_ergebnis,
    warnquelle_registriert,
)

pruefling_aus_worktree()


def _lauf(orte, quelle, tag: str):
    dienst = CompareOfficialAlertService(settings=settings_dummy(), user_id=neue_kennung(tag))
    jetzt = datetime.now(timezone.utc)
    with warnquelle_registriert(quelle):
        return dienst._fetch_locations("p-1539", orte, jetzt), jetzt


def test_ac6_reihenfolge_und_senken_je_ort_identisch_zum_seriellen_lauf(
    umgebung, thread_fehler, monkeypatch,
):
    orte = neue_orte(3, "ac6")
    verz = {orte[0].lat: 0.45, orte[1].lat: 0.25, orte[2].lat: 0.05}  # absteigend
    dienst = CompareOfficialAlertService(settings=settings_dummy(), user_id=neue_kennung("ac6"))
    jetzt = datetime.now(timezone.utc)

    slots_setzen(monkeypatch, "official_alerts", 1)
    with warnquelle_registriert(WarnRand(verzoegerung=verz)):
        seriell = dienst._fetch_locations("p-1539", orte, jetzt)

    slots_setzen(monkeypatch, "official_alerts", 3)
    quelle = WarnRand(verzoegerung=verz)
    with warnquelle_registriert(quelle):
        parallel = dienst._fetch_locations("p-1539", orte, jetzt)

    roh, abfragen = warn_ergebnis(*parallel)
    assert roh == [(f"Sturm {o.lat}", (o.id,)) for o in orte], "raw in Eingabereihenfolge der Orte"
    assert list(abfragen) == [o.id for o in orte]
    for o in orte:  # jede Abfrage gehoert zu ihrem Ort und zeigt genau dessen Warnung
        (scope, scope_ids, _end, _src, gezeigt), = abfragen[o.id]
        assert (scope, scope_ids, gezeigt) == (o.id, (o.id,), (f"Sturm {o.lat}",))
    # F001: auch die Quellen-Senke gehoert dem Ort (eigene Warnung, nicht die des
    # zuletzt fertigen Ortes).
    assert _quellen_je_ort(parallel[1]) == {
        o.id: {quelle.name: (True, (f"Sturm {o.lat}",))} for o in orte}
    assert warn_ergebnis(*parallel) == warn_ergebnis(*seriell), "identisch zum seriellen Lauf"
    assert quelle.max_gleichzeitig >= 2, (
        "Warn-Abrufe laufen noch nacheinander (erwartet: fetch_ordered, Provider official_alerts)")


def _quellen_je_ort(queries_by_loc: dict) -> dict:
    """``sources`` je Ort in vergleichbarer Form: Name -> (ok, Warnungs-Labels)."""
    ergebnis = {}
    for loc_id, (q,) in queries_by_loc.items():
        ergebnis[loc_id] = {
            name: (ok, tuple(a.label for a in alerts))
            for name, (ok, alerts) in (q.sources or {}).items()
        }
    return ergebnis


def test_ac6_quellen_senke_je_ort_traegt_genau_den_status_dieses_ortes(
    umgebung, thread_fehler, monkeypatch,
):
    """AC-6 (Fix-Loop F001): jeder Ort bekommt die Quellen-Bilanz SEINES Abrufs.

    Der mittlere Ort meldet einen Quellen-Ausfall, die anderen je eine eigene
    Warnung. Verzoegerung absteigend: der erste Ort endet zuletzt -- eine
    gemeinsame Senke liefe ueber ``sink[-1]`` fuer alle Orte auf dessen Bilanz."""
    orte = neue_orte(3, "ac6q")
    verz = {orte[0].lat: 0.45, orte[1].lat: 0.25, orte[2].lat: 0.05}  # absteigend
    slots_setzen(monkeypatch, "official_alerts", 3)
    quelle = WarnRand(verzoegerung=verz, ausfall={orte[1].lat})

    (raw, queries_by_loc), _jetzt = _lauf(orte, quelle, "ac6q")

    assert quelle.max_gleichzeitig >= 2, "Setup: Abrufe muessen sich ueberlappen"
    assert _quellen_je_ort(queries_by_loc) == {
        orte[0].id: {quelle.name: (True, (f"Sturm {orte[0].lat}",))},
        orte[1].id: {quelle.name: (False, ())},
        orte[2].id: {quelle.name: (True, (f"Sturm {orte[2].lat}",))},
    }, "Quellen-Bilanz vermischt zwischen den Orten"
    assert [(a.label, tuple(ids)) for a, ids in raw] == [
        (f"Sturm {orte[0].lat}", (orte[0].id,)), (f"Sturm {orte[2].lat}", (orte[2].id,))]


def test_ac7_abrufe_ueberlappen_nachweislich_im_worker(umgebung, thread_fehler, monkeypatch):
    orte = neue_orte(3, "ac7a")
    slots_setzen(monkeypatch, "official_alerts", 3)
    quelle = WarnRand(treffpunkt=True)

    t0 = time.monotonic()
    _lauf(orte, quelle, "ac7a")
    dauer = time.monotonic() - t0

    assert quelle.max_gleichzeitig >= 2, "Treffpunkt nie erreicht -- Abrufe laufen nacheinander"
    assert dauer < 1.0, f"seriell wartete jeder Abruf vergeblich ({dauer:.2f}s)"
    assert all(ist_worker(a["thread"]) for a in quelle.aufrufe)


def test_ac7_gesamtdauer_unter_80_prozent_der_summe(umgebung, thread_fehler, monkeypatch):
    orte = neue_orte(3, "ac7b")
    slots_setzen(monkeypatch, "official_alerts", 3)
    quelle = WarnRand(verzoegerung={o.lat: 0.5 for o in orte})

    t0 = time.monotonic()
    _lauf(orte, quelle, "ac7b")
    dauer = time.monotonic() - t0

    assert dauer < 1.2, f"Gesamtdauer {dauer:.2f}s >= 1,2 s -- nicht parallel"


def test_ac7_provider_schluessel_official_alerts_deckelt_ueber_eigene_slotzahl(
    umgebung, thread_fehler, monkeypatch,
):
    """Env ``GZ_PARALLEL_FETCH_SLOTS_OFFICIAL_ALERTS=2`` wirkt nur beim Schluessel
    ``official_alerts``; unter ``open_meteo`` (3 Slots) wuerden drei Abrufe laufen."""
    orte = neue_orte(3, "ac7c")
    slots_setzen(monkeypatch, "official_alerts", 2)
    quelle = WarnRand(verzoegerung={o.lat: 0.3 for o in orte})

    _lauf(orte, quelle, "ac7c")

    assert quelle.max_gleichzeitig == 2, (
        f"erwartet genau 2 gleichzeitige Warn-Abrufe, war {quelle.max_gleichzeitig}")


def test_ac7_belegte_open_meteo_slots_blockieren_den_warn_abruf_nicht(
    umgebung, thread_fehler, monkeypatch,
):
    from services import parallel_fetch

    orte = neue_orte(3, "ac7d")
    slots_setzen(monkeypatch, "official_alerts", 3)
    sem = parallel_fetch._get_semaphore("open_meteo")
    gehalten = 0
    try:
        while sem.acquire(blocking=False):
            gehalten += 1
        assert gehalten >= 1, "Setup: open_meteo-Slots belegt"
        quelle = WarnRand(verzoegerung={o.lat: 0.3 for o in orte})
        ergebnis: dict = {}
        t0 = time.monotonic()
        faden = threading.Thread(
            target=lambda: ergebnis.setdefault("r", _lauf(orte, quelle, "ac7d")), daemon=True)
        faden.start()
        faden.join(timeout=5.0)
        dauer = time.monotonic() - t0
    finally:
        for _ in range(gehalten):
            sem.release()

    assert "r" in ergebnis, "Warn-Alarm blockiert bei belegten open_meteo-Slots"
    assert dauer < 1.2 and quelle.max_gleichzeitig >= 2
