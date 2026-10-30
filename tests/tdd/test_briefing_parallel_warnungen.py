"""TDD RED -- Feature #1539 (S5): amtliche Warnungen im Trip-Briefing parallel.

SPEC: docs/specs/modules/feat_1539_s5_briefing_parallel.md (AC-1, AC-6 Warn-Teil, AC-8)

Der Warnungsblock in ``_briefing_bauen_und_senden`` fragt die eindeutigen
Etappen-Startpunkte heute strikt nacheinander im Briefing-Faden ab. S5 stellt
ihn auf ``fetch_ordered(..., provider="official_alerts")`` um; Zuweisung an die
Segmente und ``official_queries`` bleiben im Hauptfaden in Koordinaten-
reihenfolge.

Aufbau (Kern-Schicht, kein Netz): echter Briefing-Lauf
(``_send_trip_report_outcome``), echte Registry mit der Test-Quelle
``Warnquelle`` am Rand (Verzoegerung, Treffpunkt, Thread-Erfassung). Das
Zieltag-Wetter kommt aus der Fixture-Unterklasse (Muster #1614), der Transport
ist ``EmailOutput.send`` ohne Netz. ``official_queries`` wird am Eingang des
Entwarnungspfads (``settle_official_alerts_after_briefing``) delegierend
mitgelesen.

Warum die Vorbedingung "lief im Worker" (``assert_warnabrufe_in_workern``):
ohne sie waeren Reihenfolge- und Zuordnungstests schon im heutigen seriellen
Ablauf gruen und bewachten die Parallelisierung nicht.
"""
from __future__ import annotations

# Fixtures kommen per Import aus _briefing_parallel_fixtures; ihre Namen als
# Testparameter sind fuer ruff Umdefinitionen (F811), fuer pytest der Normalfall.
# ruff: noqa: F811

from tests.tdd._briefing_parallel_fixtures import (  # noqa: F401
    Treffpunkt,
    Warnquelle,
    assert_warnabrufe_in_workern,
    briefing_lauf,
    briefing_rand,
    frist_setzen,
    koord,
    neue_breite,
    neue_kennung,
    pruefling_aus_worktree,
    query_reihenfolge,
    slots_setzen,
    thread_fehler,
    umgebung,
    warn_label,
    warn_trip,
    warnquellen,
)

pruefling_aus_worktree()  # Pfadregel #1409: Pruefling aus DIESEM Worktree


def _punkte(n: int) -> list:
    return [(neue_breite(), 11.40) for _ in range(n)]


def _erwartet_ac1(p: list) -> list:
    """Serielle Semantik (Bestand): Segment 3 hat Fehler -> uebersprungen, kein
    Abruf; Segment 4 startet an derselben Koordinate wie Segment 1 -> kein
    zweiter Abruf, Felder bleiben auf dem Default."""
    return [
        ("1", [warn_label(koord(*p[0]))], False),
        ("2", [warn_label(koord(*p[1]))], False),
        ("3", [], False),
        ("4", [], False),
        ("5", [warn_label(koord(*p[3]))], False),
        ("Ziel", [warn_label(koord(*p[4]))], False),
    ]


# --------------------------------------------------------------------------- #
# AC-1 Zuordnung und Reihenfolge
# --------------------------------------------------------------------------- #
def test_ac1_warnungen_am_richtigen_segment_trotz_umgekehrter_fertigstellung(
    briefing_rand, warnquellen, thread_fehler,
):
    """AC-1: GIVEN ein Trip mit vier eindeutigen Startkoordinaten (dazu eine
    doppelte und ein Segment mit Wetterfehler), deren Warn-Abrufe in
    UMGEKEHRTER Reihenfolge fertig werden (erste Koordinate am langsamsten);
    WHEN das Briefing die amtlichen Warnungen laedt;
    THEN steht jede Warnung am Segment ihrer Koordinate, ``official_queries``
    folgt der Koordinatenreihenfolge, die doppelte Koordinate wurde nur einmal
    und die Fehler-Koordinate gar nicht abgefragt -- und die Abrufe liefen in
    Baustein-Workern."""
    pruefling_aus_worktree()
    p = _punkte(5)
    trip = warn_trip([p[0], p[1], p[2], p[0], p[3], p[4]])
    verz = {koord(*p[0]): 0.40, koord(*p[1]): 0.30, koord(*p[3]): 0.20, koord(*p[4]): 0.10}
    quelle = warnquellen(Warnquelle(tag=trip.stages[0].date, verzoegerung=verz))

    dienst, outcome = briefing_lauf(trip, neue_kennung("ac1"), fehler_segmente={"3"})

    assert outcome == "sent", f"Vorbedingung: Briefing zugestellt ({outcome!r})"
    assert_warnabrufe_in_workern(quelle)
    assert sorted(quelle.koordinaten()) == sorted(verz), (
        f"Abgefragt: {quelle.koordinaten()} -- erwartet genau einmal je eindeutiger, "
        "fehlerfreier Koordinate")
    assert dienst.__dict__["im_request"] == _erwartet_ac1(p)
    assert len(briefing_rand["settle"]) == 1, briefing_rand["settle"]
    assert query_reihenfolge(briefing_rand["settle"][0][1]) == [
        ("1",), ("2",), ("5",), ("Ziel",)], (
        "official_queries nicht in Koordinatenreihenfolge (Fertigstellungs-"
        "reihenfolge waere Ziel, 5, 2, 1)")


def test_ac1_paralleler_lauf_gleicht_dem_lauf_mit_einem_slot(
    briefing_rand, warnquellen, monkeypatch, thread_fehler,
):
    """AC-1: GIVEN dieselbe Eingabe einmal mit absteigender Verzoegerung (3
    Slots) und einmal mit EINEM Slot fuer ``official_alerts`` (nacheinander);
    WHEN beide Briefings laufen;
    THEN sind Warnungen je Segment und ``official_queries`` identisch, und
    beide Laeufe fragten in Workern ab."""
    p = _punkte(5)
    punkte = [p[0], p[1], p[2], p[0], p[3], p[4]]
    trip = warn_trip(punkte)
    verz = {koord(*p[0]): 0.30, koord(*p[1]): 0.20, koord(*p[3]): 0.10, koord(*p[4]): 0.05}

    quelle_p = warnquellen(Warnquelle(tag=trip.stages[0].date, verzoegerung=verz))
    dienst_p, _ = briefing_lauf(trip, neue_kennung("ac1p"), fehler_segmente={"3"})
    assert_warnabrufe_in_workern(quelle_p)

    slots_setzen(monkeypatch, "official_alerts", 1)
    quelle_s = warnquellen(Warnquelle(tag=trip.stages[0].date))
    dienst_s, _ = briefing_lauf(warn_trip(punkte), neue_kennung("ac1s"), fehler_segmente={"3"})
    assert_warnabrufe_in_workern(quelle_s)

    assert dienst_p.__dict__["im_request"] == dienst_s.__dict__["im_request"]
    assert [query_reihenfolge(q) for _, q in briefing_rand["settle"]] == [
        [("1",), ("2",), ("5",), ("Ziel",)]] * 2
    assert [[q.scope for q in qs] for _, qs in briefing_rand["settle"]][0] == \
        [[q.scope for q in qs] for _, qs in briefing_rand["settle"]][1]


# --------------------------------------------------------------------------- #
# AC-6 Ueberlappung der Warn-Abrufe
# --------------------------------------------------------------------------- #
def test_ac6_warn_abrufe_ueberlappen_nachweislich(briefing_rand, warnquellen, thread_fehler):
    """AC-6: GIVEN drei Warn-Koordinaten und ein Treffpunkt am Quellen-Rand, der
    nur freigibt, wenn mindestens zwei Abrufe gleichzeitig laufen;
    WHEN das Briefing die Warnungen laedt;
    THEN hat JEDER Abruf den Treffpunkt offen vorgefunden (seriell wartet
    jeder vergeblich)."""
    p = _punkte(3)
    trip = warn_trip(p)
    treff = Treffpunkt(timeout=1.0)
    quelle = warnquellen(Warnquelle(tag=trip.stages[0].date, treffpunkt=treff))

    _, outcome = briefing_lauf(trip, neue_kennung("ac6t"))

    assert outcome == "sent", outcome
    assert len(treff.ergebnisse) == 3, treff.ergebnisse
    assert all(treff.ergebnisse), (
        f"Treffpunkt-Ergebnisse {treff.ergebnisse}: die Warn-Abrufe liefen nie "
        "gleichzeitig -- sie laufen noch nacheinander.")
    assert_warnabrufe_in_workern(quelle)


def test_ac6_warn_abrufe_dauern_unter_80_prozent_der_summe(
    briefing_rand, warnquellen, thread_fehler,
):
    """AC-6: GIVEN drei Warn-Koordinaten mit je 0,5 s Verzoegerung am Rand
    (Summe 1,5 s); WHEN das Briefing die Warnungen laedt; THEN liegt die
    Spanne vom ersten Start bis zum letzten Ende unter 1,2 s."""
    p = _punkte(3)
    trip = warn_trip(p)
    quelle = warnquellen(Warnquelle(
        tag=trip.stages[0].date, verzoegerung={koord(*x): 0.5 for x in p}))

    briefing_lauf(trip, neue_kennung("ac6d"))

    assert len(quelle.aufrufe) == 3, quelle.koordinaten()
    spanne = max(a["t1"] for a in quelle.aufrufe) - min(a["t0"] for a in quelle.aufrufe)
    assert spanne < 1.2, f"Warn-Abrufe dauerten {spanne:.2f} s (Summe 1,5 s) -- seriell"
    assert quelle.max_gleichzeitig >= 2


# --------------------------------------------------------------------------- #
# AC-8 eigener Provider-Schluessel official_alerts
# --------------------------------------------------------------------------- #
def test_ac8_warnabruf_startet_trotz_ausgelasteter_open_meteo_slots(
    briefing_rand, warnquellen, monkeypatch, thread_fehler,
):
    """AC-8: GIVEN alle drei ``open_meteo``-Slots sind durch gehaltene Abrufe
    belegt und die Frist ist auf 1,5 s verkuerzt;
    WHEN das Briefing die amtlichen Warnungen laedt;
    THEN startet JEDER Warn-Abruf trotzdem in einem Baustein-Worker (eigener
    Schluessel ``official_alerts``) und jede Warnung steht am Segment -- unter
    ``open_meteo`` waeren sie alle als ``skipped`` verworfen worden."""
    from services import parallel_fetch

    frist_setzen(monkeypatch, 1.5)
    parallel_fetch._reset_for_tests()
    belegt = parallel_fetch._get_semaphore("open_meteo")
    gehalten = 0
    try:
        while belegt.acquire(blocking=False):
            gehalten += 1
        assert gehalten == 3, f"Setup: {gehalten} open_meteo-Slots belegt, erwartet 3"
        p = _punkte(3)
        trip = warn_trip(p)
        quelle = warnquellen(Warnquelle(tag=trip.stages[0].date))

        dienst, _ = briefing_lauf(trip, neue_kennung("ac8"))
    finally:
        for _ in range(gehalten):
            belegt.release()

    assert sorted(quelle.koordinaten()) == sorted(koord(*x) for x in p), (
        f"Warn-Abrufe gestartet fuer {quelle.koordinaten()} -- erwartet alle drei "
        "Koordinaten trotz belegter open_meteo-Slots")
    assert_warnabrufe_in_workern(quelle)
    assert dienst.__dict__["im_request"] == [
        ("1", [warn_label(koord(*p[0]))], False),
        ("2", [warn_label(koord(*p[1]))], False),
        ("Ziel", [warn_label(koord(*p[2]))], False),
    ]
