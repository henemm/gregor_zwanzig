"""TDD RED -- Feature #1539 (S5): Fehler, Frist und Hauptfaden im parallelen Briefing.

SPEC: docs/specs/modules/feat_1539_s5_briefing_parallel.md (AC-4, AC-5, AC-9)

* AC-4: Teilausfall bleibt fail-soft wie bisher (Trend: Etappe entfaellt,
  Zustand nach #1486; Fallback: wie im Lauf mit einem Slot; Warnung: ``[]``
  mit ``official_alerts_unavailable=True``, nie Entwarnung).
* AC-5: Endliche Frist ``FETCH_WEATHER_DEADLINE_SECONDS`` (kein neuer Wert) fuer
  Etappen- und Warn-Abruf; nicht abgeschlossene Etappen/Koordinaten zaehlen
  als gescheitert und stehen mit Grund im Log.
* AC-9: ``_last_converted_trip``, die Warn-Felder der Segmente und das Bauen
  von ``official_queries`` geschehen nur im Hauptfaden; ueber Wiederholungen
  stimmt das Ergebnis mit dem seriellen ueberein.

Aufbau wie in ``_briefing_parallel_fixtures`` beschrieben (Rand-Provider,
echte Registry, echte Briefing-Laeufe). Frist-Tests: ein Slot; Etappen Frist
0,7 s bei 0,4 s je Etappe, Warnungen Frist 0,45 s bei 0,3 s je Abruf -> nur
der erste Abruf passt (je rund 0,2 s bzw. 0,15 s Luft zu beiden Seiten). Heute bekommt jede Etappe eine
EIGENE frische Frist (``_fetch_weather`` je Etappe) und die Warnungen laufen
ohne Frist -- daher kommt heute alles durch.
"""
from __future__ import annotations

# Fixtures kommen per Import aus _briefing_parallel_fixtures; ihre Namen als
# Testparameter sind fuer ruff Umdefinitionen (F811), fuer pytest der Normalfall.
# ruff: noqa: F811

import logging
import re
import threading

from services.trip_report_scheduler import TripReportSchedulerService
from tests.tdd._briefing_parallel_fixtures import (  # noqa: F401
    Warnquelle,
    assert_etappen_ueberlappen,
    assert_warnabrufe_in_workern,
    briefing_lauf,
    briefing_rand,
    etappen_tage,
    fallback_lauf,
    frist_setzen,
    koord,
    neue_breite,
    neue_kennung,
    pruefling_aus_worktree,
    query_reihenfolge,
    rand,
    segment_wetter,
    settings_ohne_transport,
    slots_setzen,
    thread_fehler,
    trend_lauf,
    trend_trip,
    umgebung,
    warn_label,
    warn_trip,
    warnquellen,
    zeilen_kern,
)

pruefling_aus_worktree()  # Pfadregel #1409: Pruefling aus DIESEM Worktree

GRUND = re.compile(r"deadline|timeout|frist", re.I)


def _warnzeilen(caplog, *muster: str) -> list[str]:
    return [
        r.getMessage() for r in caplog.records
        if r.levelno >= logging.WARNING and all(re.search(m, r.getMessage()) for m in muster)
    ]


def _dienst(tag: str, klasse=TripReportSchedulerService):
    return klasse(settings=settings_ohne_transport(), user_id=neue_kennung(tag))


# --------------------------------------------------------------------------- #
# AC-4 Teilausfall
# --------------------------------------------------------------------------- #
def test_ac4_trend_etappe_mit_ausnahme_und_etappe_mit_leerem_wetter_entfallen_einzeln(
    rand, caplog, thread_fehler,
):
    """AC-4: GIVEN drei Folge-Etappen, bei denen alle Abrufe der zweiten mit
    Ausnahme scheitern und die dritte leere Zeitreihen liefert;
    WHEN der Trend parallel gebaut wird;
    THEN bleibt nur die Zeile der ersten Etappe, der Zustand ist FOUND, und
    beide ausgefallenen Etappen stehen mit ihrer Kennung im Warn-Log."""
    trip = trend_trip(3)
    prov = rand(etappen_tage(trip), fehler={1}, leer={2},
                verzoegerung=lambda idx, label: 0.1)
    with caplog.at_level(logging.WARNING):
        ergebnis = trend_lauf(_dienst("ac4t"), trip)

    assert zeilen_kern(ergebnis.rows) == [(trip.stages[0].date, trip.stages[0].name)]
    assert ergebnis.state.name == "FOUND"
    assert _warnzeilen(caplog, r"\bS2\b"), "Ausfall der Etappe S2 nicht im Log"
    assert _warnzeilen(caplog, r"\bS3\b"), "Ausfall der Etappe S3 nicht im Log"
    assert_etappen_ueberlappen(prov)


def test_ac4_trend_ohne_jede_zeile_wird_unavailable(rand, thread_fehler):
    """AC-4/#1486: GIVEN alle drei Folge-Etappen scheitern am Rand; WHEN der
    Trend gebaut wird; THEN gibt es keine Zeile und der Zustand ist
    UNAVAILABLE (Stoerung, nicht "keine Etappen")."""
    trip = trend_trip(3)
    rand(etappen_tage(trip), fehler={0, 1, 2})
    ergebnis = trend_lauf(_dienst("ac4u"), trip)
    assert ergebnis.rows is None
    assert ergebnis.state.name == "UNAVAILABLE"


def test_ac4_fallback_mit_gescheiterter_etappe_gleicht_dem_lauf_mit_einem_slot(
    rand, monkeypatch, thread_fehler,
):
    """AC-4: GIVEN zwei Fallback-Etappen, deren zweite am Rand scheitert;
    WHEN der Gewitter-Fallback parallel und danach mit einem Slot laeuft;
    THEN liefern beide dasselbe (Bestand: die Fehler-Platzhalter der
    gescheiterten Etappe bleiben enthalten, die TH+-Auswertung sieht sie wie
    bisher), und der parallele Lauf ueberlappte die Etappen."""
    from services.weather_cache import reset_shared_weather_cache_for_tests

    trip = trend_trip(3)
    prov = rand(etappen_tage(trip), fehler={1}, verzoegerung=lambda idx, label: 0.1)
    parallel = fallback_lauf(_dienst("ac4fp"), trip)
    assert_etappen_ueberlappen(prov)

    reset_shared_weather_cache_for_tests()
    slots_setzen(monkeypatch, "open_meteo", 1)
    rand(etappen_tage(trip), fehler={1})
    seriell = fallback_lauf(_dienst("ac4fs"), trip)

    def kern(daten):
        return [(w.segment.start_time.date(), str(w.segment.segment_id), w.has_error)
                for w in daten]

    tage = etappen_tage(trip)
    assert kern(parallel) == [(tage[0], "1", False), (tage[0], "Ziel", False),
                              (tage[1], "1", True), (tage[1], "Ziel", True)]
    assert kern(parallel) == kern(seriell)


def test_ac4_ausgefallene_warnquelle_ergibt_leer_mit_unavailable_nie_entwarnung(
    briefing_rand, warnquellen, thread_fehler,
):
    """AC-4: GIVEN drei Warn-Koordinaten, deren zweite am Quellen-Rand mit
    HTTP 503 scheitert; WHEN das Briefing die Warnungen parallel laedt;
    THEN traegt nur dieses Segment ``[]`` mit
    ``official_alerts_unavailable=True`` (Quellenausfall ist nie Entwarnung),
    die anderen ihre Warnung."""
    p = [(neue_breite(), 11.40) for _ in range(3)]
    trip = warn_trip(p)
    quelle = warnquellen(Warnquelle(
        tag=trip.stages[0].date, fehler={koord(*p[1])},
        verzoegerung={koord(*x): 0.1 for x in p}))

    dienst, outcome = briefing_lauf(trip, neue_kennung("ac4w"))

    assert_warnabrufe_in_workern(quelle)
    assert dienst.__dict__["im_request"] == [
        ("1", [warn_label(koord(*p[0]))], False),
        ("2", [], True),
        ("Ziel", [warn_label(koord(*p[2]))], False),
    ]


# --------------------------------------------------------------------------- #
# AC-5 Frist
# --------------------------------------------------------------------------- #
def test_ac5_trend_frist_ueberspringt_spaete_etappen_mit_grund_im_log(
    rand, monkeypatch, caplog, thread_fehler,
):
    """AC-5: GIVEN ein ``open_meteo``-Slot, Frist 0,7 s
    (``FETCH_WEATHER_DEADLINE_SECONDS``), je Etappe 0,4 s am Rand;
    WHEN der Trend gebaut wird;
    THEN passt nur Etappe 1; S2 und S3 zaehlen als gescheitert (keine Zeile)
    und stehen je mit Grund (deadline/timeout) im Warn-Log; Zustand FOUND."""
    slots_setzen(monkeypatch, "open_meteo", 1)
    frist_setzen(monkeypatch, 0.7)
    trip = trend_trip(3)
    rand(etappen_tage(trip), verzoegerung=lambda idx, label: 0.4 if label == "1" else 0.0)

    with caplog.at_level(logging.WARNING):
        ergebnis = trend_lauf(_dienst("ac5t"), trip)

    assert zeilen_kern(ergebnis.rows) == [(trip.stages[0].date, trip.stages[0].name)], (
        "Nach Fristablauf darf nur Etappe 1 eine Zeile haben -- heute bekommt jede "
        "Etappe eine eigene, frische Frist")
    assert ergebnis.state.name == "FOUND"
    for sid in ("S2", "S3"):
        zeilen = _warnzeilen(caplog, rf"\b{sid}\b")
        assert any(GRUND.search(z) for z in zeilen), (
            f"Etappe {sid}: kein Warn-Log mit Grund (deadline/timeout): {zeilen!r}")


def test_ac5_fallback_frist_laesst_spaete_etappe_mit_grund_im_log_entfallen(
    rand, monkeypatch, caplog, thread_fehler,
):
    """AC-5: GIVEN ein Slot, Frist 0,7 s, je Etappe 0,4 s; WHEN der
    Gewitter-Fallback zwei Etappen sammelt; THEN liefert er nur die Daten der
    ersten, und die zweite steht mit Grund im Log
    (``Thunder-forecast fetch failed for stage S2``)."""
    slots_setzen(monkeypatch, "open_meteo", 1)
    frist_setzen(monkeypatch, 0.7)
    trip = trend_trip(3)
    rand(etappen_tage(trip), verzoegerung=lambda idx, label: 0.4 if label == "1" else 0.0)

    with caplog.at_level(logging.WARNING):
        daten = fallback_lauf(_dienst("ac5f"), trip)

    assert {w.segment.start_time.date() for w in daten} == {trip.stages[0].date}, (
        "Nach Fristablauf darf nur Etappe 1 im Fallback stehen")
    zeilen = _warnzeilen(caplog, r"Thunder-forecast fetch failed for stage S2")
    assert any(GRUND.search(z) for z in zeilen), (
        f"Etappe S2: kein Warn-Log mit Grund (deadline/timeout): {zeilen!r}")


def test_ac5_warn_frist_markiert_nicht_abgeschlossene_koordinaten_unavailable(
    briefing_rand, warnquellen, monkeypatch, caplog, thread_fehler,
):
    """AC-5: GIVEN ein ``official_alerts``-Slot, Frist 0,45 s, je Warn-Abruf
    0,3 s; WHEN das Briefing drei Koordinaten laedt; THEN hat nur Segment 1
    seine Warnung, die beiden anderen ``[]`` mit
    ``official_alerts_unavailable=True`` (nichts still weggelassen), und beide
    stehen mit Grund im Warn-Log."""
    slots_setzen(monkeypatch, "official_alerts", 1)
    frist_setzen(monkeypatch, 0.45)
    p = [(neue_breite(), 11.40) for _ in range(3)]
    trip = warn_trip(p)
    warnquellen(Warnquelle(tag=trip.stages[0].date, verzoegerung={koord(*x): 0.3 for x in p}))

    with caplog.at_level(logging.WARNING):
        dienst, _ = briefing_lauf(trip, neue_kennung("ac5w"))

    assert dienst.__dict__["im_request"] == [
        ("1", [warn_label(koord(*p[0]))], False),
        ("2", [], True),
        ("Ziel", [], True),
    ]
    begruendet = [z for z in _warnzeilen(caplog, r"(?i)official|warn") if GRUND.search(z)]
    assert len(begruendet) >= 2, (
        f"Erwartet je uebersprungener Koordinate eine Warnzeile mit Grund: {begruendet!r}")


# --------------------------------------------------------------------------- #
# AC-9 Schreiben nur im Hauptfaden, Wiederholung
# --------------------------------------------------------------------------- #
class _SchreibWaechter(TripReportSchedulerService):
    """Erfasst die Thread-Kennung jedes Schreibzugriffs auf
    ``_last_converted_trip`` (echter Scheduler, sonst unveraendert)."""

    def __setattr__(self, name, value):
        if name == "_last_converted_trip":
            self.__dict__.setdefault("_schreiber", []).append(threading.get_ident())
        super().__setattr__(name, value)


def test_ac9_trend_schreibt_nur_im_hauptfaden_und_gleicht_seriell(rand, thread_fehler):
    """AC-9: GIVEN wiederholte parallele Trend-Laeufe mit gemischtem Erfolg
    (Etappe 2 scheitert) und wechselnder Verzoegerung;
    WHEN jeder Lauf endet;
    THEN wurde ``_last_converted_trip`` nur vom Hauptfaden geschrieben, die
    Zeilen sind jedes Mal [Etappe 1, Etappe 3] in dieser Reihenfolge (wie
    seriell), und die Etappen-Abrufe ueberlappten."""
    haupt = threading.get_ident()
    for wiederholung in range(8):
        trip = trend_trip(3)
        verz = (0.12, 0.0, 0.04) if wiederholung % 2 else (0.02, 0.06, 0.12)
        prov = rand(etappen_tage(trip), fehler={1},
                    verzoegerung=lambda idx, label, _v=verz: _v[idx] + 0.02)
        dienst = _dienst(f"ac9t{wiederholung}", klasse=_SchreibWaechter)
        ergebnis = trend_lauf(dienst, trip)
        assert set(dienst.__dict__["_schreiber"]) == {haupt}, (
            f"Wiederholung {wiederholung}: _last_converted_trip aus fremdem Thread")
        assert zeilen_kern(ergebnis.rows) == [
            (trip.stages[0].date, trip.stages[0].name),
            (trip.stages[2].date, trip.stages[2].name)], wiederholung
        assert ergebnis.state.name == "FOUND"
        assert_etappen_ueberlappen(prov)


def test_ac9_warnfelder_und_queries_entstehen_nur_im_hauptfaden(
    briefing_rand, warnquellen, monkeypatch, thread_fehler,
):
    """AC-9: GIVEN wiederholte Briefings mit parallelen Warn-Abrufen, gemischt
    aus Erfolg und Quellenausfall;
    WHEN jeder Lauf endet;
    THEN schrieb nur der Hauptfaden die Warn-Felder der Segmente und baute
    ``official_queries`` (``_briefing_queries``), und Ergebnis sowie
    Query-Reihenfolge stimmen jedes Mal mit dem seriellen ueberein."""
    import services.trip_report_scheduler as trs

    haupt = threading.get_ident()
    bauer: list[int] = []
    echt = trs._briefing_queries

    def _beobachtet(sink, sw):
        bauer.append(threading.get_ident())
        return echt(sink, sw)

    monkeypatch.setattr(trs, "_briefing_queries", _beobachtet)

    for wiederholung in range(3):
        p = [(neue_breite(), 11.40) for _ in range(4)]
        trip = warn_trip(p)
        verz = {koord(*x): 0.05 * ((k + wiederholung) % 4) for k, x in enumerate(p)}
        quelle = warnquellen(Warnquelle(tag=trip.stages[0].date, fehler={koord(*p[2])},
                                        verzoegerung=verz))
        bauer.clear()
        dienst, _ = briefing_lauf(trip, neue_kennung(f"ac9w{wiederholung}"))

        assert_warnabrufe_in_workern(quelle)
        fremd = [
            (str(sw.segment.segment_id), name, tname)
            for sw in segment_wetter(dienst)
            for (name, tid, tname) in sw.__dict__.get("_schreiber", [])
            if tid != haupt
        ]
        assert not fremd, f"Wiederholung {wiederholung}: Warn-Felder aus Worker geschrieben: {fremd}"
        assert bauer and set(bauer) == {haupt}, (
            f"Wiederholung {wiederholung}: official_queries im Worker gebaut")
        assert dienst.__dict__["im_request"] == [
            ("1", [warn_label(koord(*p[0]))], False),
            ("2", [warn_label(koord(*p[1]))], False),
            ("3", [], True),
            ("Ziel", [warn_label(koord(*p[3]))], False),
        ], wiederholung
        assert query_reihenfolge(briefing_rand["settle"][-1][1]) == [
            ("1",), ("2",), ("3",), ("Ziel",)], wiederholung
