"""TDD RED -- Feature #1539 (S5): Ausblick-Trend und Gewitter-Fallback parallel.

SPEC: docs/specs/modules/feat_1539_s5_briefing_parallel.md (AC-2, AC-3, AC-6 Trend-Teil)

``_build_stage_trend`` (bis zu drei Folge-Etappen) und
``_collect_future_stage_weather`` (bis zu zwei) holen das Etappenwetter heute
Etappe fuer Etappe. S5: Phase 1 (``_convert_trip_to_segments``, Trip-
Fortschreibung) bleibt seriell im Hauptfaden, Phase 2 (``_fetch_weather`` +
``_enrich_ensemble_for_trip`` je Etappe) laeuft ueber den gemeinsamen Helfer
``_abrufe_fuer_etappen`` parallel, Phase 3 (Zeilenbau) seriell in
Etappenreihenfolge.

Aufbau (Kern-Schicht, kein Netz): echter Scheduler, echter
``SegmentWeatherService``, echter Wetter-Cache; nur der Open-Meteo-Provider
ist ``EtappenRand`` (Fixture-Daten, Verzoegerung/Treffpunkt/Zeitstempel je
Etappe). Beobachtet werden ``_convert_trip_to_segments`` und
``_enrich_ensemble_for_trip`` ueber eine Unterklasse, die nur MITSCHREIBT und
an die echte Methode delegiert (kein Ersatz).

Nachweis der Parallelitaet ueber Abrufe VERSCHIEDENER Etappen (siehe
``_briefing_parallel_fixtures``): die Segmente einer Etappe laufen schon heute
in Workern parallel.
"""
from __future__ import annotations

# Fixtures kommen per Import aus _briefing_parallel_fixtures; ihre Namen als
# Testparameter sind fuer ruff Umdefinitionen (F811), fuer pytest der Normalfall.
# ruff: noqa: F811

import threading
from datetime import timedelta

from services.trip_report_scheduler import TripReportSchedulerService
from tests.tdd._briefing_parallel_fixtures import (  # noqa: F401
    Treffpunkt,
    _ECHT,
    assert_etappen_ueberlappen,
    etappen_tage,
    fallback_lauf,
    heute_utc,
    neue_kennung,
    pruefling_aus_worktree,
    rand,
    settings_ohne_transport,
    slots_setzen,
    thread_fehler,
    trend_lauf,
    trend_trip,
    umgebung,
    zeilen_kern,
)

pruefling_aus_worktree()  # Pfadregel #1409: Pruefling aus DIESEM Worktree

HELFER = "_abrufe_fuer_etappen"


class _Beobachter(TripReportSchedulerService):
    """Echter Scheduler; schreibt Aufrufe von Umwandlung, Anreicherung und
    gemeinsamem Helfer mit und delegiert unveraendert."""

    def _convert_trip_to_segments(self, trip, target_date, **kw):
        rein = id(trip)
        segmente = super()._convert_trip_to_segments(trip, target_date, **kw)
        self.__dict__.setdefault("umwandlungen", []).append({
            "tag": target_date, "rein": rein, "raus": id(self._last_converted_trip),
            "thread": threading.get_ident(),
        })
        return segmente

    def _enrich_ensemble_for_trip(self, trip, weather_data):
        tag = weather_data[0].segment.start_time.date() if weather_data else None
        self.__dict__.setdefault("anreicherungen", []).append((tag, id(trip)))
        return super()._enrich_ensemble_for_trip(trip, weather_data)


def _mit_helferzaehler():
    """Unterklasse, die den gemeinsamen Helfer zaehlt (nur wenn es ihn gibt)."""
    assert hasattr(TripReportSchedulerService, HELFER), (
        f"TripReportSchedulerService.{HELFER} fehlt -- Trend und Gewitter-Fallback "
        "muessen den Netzteil ueber EINEN gemeinsamen privaten Helfer abrufen.")

    class _Zaehler(_Beobachter):
        def _abrufe_fuer_etappen(self, *args, **kwargs):
            self.__dict__["helfer_aufrufe"] = self.__dict__.get("helfer_aufrufe", 0) + 1
            return getattr(super(), HELFER)(*args, **kwargs)

    return _Zaehler


def _dienst(klasse=_Beobachter, tag="trend"):
    return klasse(settings=settings_ohne_transport(), user_id=neue_kennung(tag))


# --------------------------------------------------------------------------- #
# AC-2 Umwandlung seriell, Netz parallel, Zeilen wie seriell
# --------------------------------------------------------------------------- #
def test_ac2_umwandlung_seriell_im_hauptfaden_netzabruf_parallel(rand, thread_fehler):
    """AC-2: GIVEN ein GR221-Bestandstrip mit drei unvermessenen Folge-Etappen
    (das Umwandeln traegt GPX-Distanzen nach und schreibt
    ``_last_converted_trip`` fort) und absteigende Verzoegerung am Rand;
    WHEN der Ausblick-Trend gebaut wird;
    THEN laeuft ``_convert_trip_to_segments`` im Hauptfaden in Etappen-
    reihenfolge, jede Etappe bekommt den fortgeschriebenen Trip der
    Vorgaengerin, die Anreicherung sieht den Trip nach IHRER Etappe, die
    Netzabrufe verschiedener Etappen ueberlappen, und die Zeilen stehen in
    Etappenreihenfolge."""
    from tests.tdd.test_ausblick_schleife_bewahrt_alle_nachgeruesteten_kilometrierungen import (
        _trip_mit_n_unvermessenen_etappen,
    )

    pruefling_aus_worktree()
    heute = heute_utc()
    tage = [heute + timedelta(days=i) for i in range(3)]
    dienst = _dienst(tag="ac2")
    trip = _trip_mit_n_unvermessenen_etappen(dienst._user_id, tage)
    prov = rand(tage, verzoegerung=lambda idx, label: (0.24, 0.16, 0.08)[idx])
    haupt = threading.get_ident()

    ergebnis = trend_lauf(dienst, trip)

    umw = dienst.__dict__["umwandlungen"]
    assert [u["tag"] for u in umw] == tage, umw
    assert {u["thread"] for u in umw} == {haupt}, (
        "_convert_trip_to_segments lief ausserhalb des Hauptfadens")
    assert all(u["rein"] != u["raus"] for u in umw), (
        "Vorbedingung: die Nachruestung erzeugte je Etappe einen neuen Trip")
    for k in (1, 2):
        assert umw[k]["rein"] == umw[k - 1]["raus"], (
            f"Etappe {k + 1} bekam nicht den fortgeschriebenen Trip der Vorgaengerin")
    anr = dict(dienst.__dict__["anreicherungen"])
    assert [anr.get(t) for t in tage] == [u["raus"] for u in umw], (
        "Die Anreicherung sah nicht den Trip-Stand nach ihrer eigenen Etappe")
    assert_etappen_ueberlappen(prov)
    assert [r["date"] for r in ergebnis.rows or []] == tage
    assert ergebnis.state.name == "FOUND"


def test_ac2_zeilen_gleichen_dem_lauf_mit_einem_slot(rand, monkeypatch, thread_fehler):
    """AC-2: GIVEN derselbe Trip einmal mit drei Slots und absteigender
    Verzoegerung, einmal mit EINEM ``open_meteo``-Slot ohne Verzoegerung;
    WHEN der Trend gebaut wird; THEN sind die Zeilen vollstaendig gleich, und
    der Lauf mit drei Slots ueberlappte die Etappen."""
    from services.weather_cache import reset_shared_weather_cache_for_tests

    trip = trend_trip(3)
    prov = rand(etappen_tage(trip), verzoegerung=lambda idx, label: (0.3, 0.2, 0.1)[idx])
    parallel = trend_lauf(_dienst(tag="ac2p"), trip)
    assert_etappen_ueberlappen(prov)

    reset_shared_weather_cache_for_tests()
    slots_setzen(monkeypatch, "open_meteo", 1)
    rand(etappen_tage(trip))
    seriell = trend_lauf(_dienst(tag="ac2s"), trip)

    assert zeilen_kern(parallel.rows) == [(s.date, s.name) for s in trip.stages]
    assert parallel.rows == seriell.rows
    assert parallel.state == seriell.state


# --------------------------------------------------------------------------- #
# AC-3 Gewitter-Fallback, gemeinsamer Helfer
# --------------------------------------------------------------------------- #
def _fallback_kern(daten) -> list:
    return [(w.segment.start_time.date(), str(w.segment.segment_id), w.has_error) for w in daten]


def test_ac3_fallback_liefert_dieselben_daten_in_derselben_reihenfolge(
    rand, monkeypatch, thread_fehler,
):
    """AC-3: GIVEN zwei Folge-Etappen im Prognosehorizont, deren Abrufe in
    umgekehrter Reihenfolge fertig werden; WHEN der Gewitter-Fallback die
    Etappenwetter sammelt; THEN sind Daten und Reihenfolge identisch zum Lauf
    mit einem Slot, und die beiden Etappen wurden ueberlappend abgerufen."""
    from services.weather_cache import reset_shared_weather_cache_for_tests

    trip = trend_trip(3)
    prov = rand(etappen_tage(trip), verzoegerung=lambda idx, label: (0.3, 0.1, 0.0)[idx])
    parallel = fallback_lauf(_dienst(tag="ac3p"), trip)
    assert_etappen_ueberlappen(prov)
    assert prov.etappen_mit_abruf() == [0, 1], "Fallback darf nur heute/+1 abrufen"

    reset_shared_weather_cache_for_tests()
    slots_setzen(monkeypatch, "open_meteo", 1)
    rand(etappen_tage(trip))
    seriell = fallback_lauf(_dienst(tag="ac3s"), trip)

    tage = etappen_tage(trip)
    assert _fallback_kern(parallel) == [
        (tage[0], "1", False), (tage[0], "Ziel", False),
        (tage[1], "1", False), (tage[1], "Ziel", False),
    ]
    assert _fallback_kern(parallel) == _fallback_kern(seriell)
    assert [len(w.timeseries.data) for w in parallel] == [len(w.timeseries.data) for w in seriell]


def test_ac3_trend_und_fallback_benutzen_denselben_helfer(rand, thread_fehler):
    """AC-3: GIVEN der gemeinsame private Helfer ``_abrufe_fuer_etappen``;
    WHEN Trend und Gewitter-Fallback je einmal laufen; THEN ruft JEDER der
    beiden Pfade den Helfer auf (beobachtet ueber einen Zaehler in der
    Unterklasse, kein Dateiinhalt-Check)."""
    klasse = _mit_helferzaehler()
    trip = trend_trip(3)
    rand(etappen_tage(trip))

    trend_dienst = _dienst(klasse, tag="ac3t")
    ergebnis = trend_lauf(trend_dienst, trip)
    assert ergebnis.rows and len(ergebnis.rows) == 3
    assert trend_dienst.__dict__.get("helfer_aufrufe", 0) >= 1, (
        "Der Trend ruft den gemeinsamen Helfer nicht")

    fb_dienst = _dienst(klasse, tag="ac3f")
    daten = fallback_lauf(fb_dienst, trip)
    assert daten, "Vorbedingung: der Fallback lieferte Etappenwetter"
    assert fb_dienst.__dict__.get("helfer_aufrufe", 0) >= 1, (
        "Der Gewitter-Fallback ruft den gemeinsamen Helfer nicht (eigener Abrufcode?)")


# --------------------------------------------------------------------------- #
# AC-6 Ueberlappung und Dauer (Trend)
# --------------------------------------------------------------------------- #
def test_ac6_trend_etappen_ueberlappen_nachweislich(rand, thread_fehler):
    """AC-6: GIVEN drei Folge-Etappen und ein Treffpunkt am Rand, der erst
    freigibt, wenn Abrufe von mindestens zwei Etappen gleichzeitig laufen;
    WHEN der Trend gebaut wird; THEN fand JEDER Etappen-Abruf den Treffpunkt
    offen vor (seriell wartet jeder vergeblich)."""
    trip = trend_trip(3)
    treff = Treffpunkt(timeout=1.0)
    rand(etappen_tage(trip), treffpunkt=treff)

    ergebnis = trend_lauf(_dienst(tag="ac6t"), trip)

    assert len(treff.ergebnisse) == 3, treff.ergebnisse
    assert all(treff.ergebnisse), (
        f"Treffpunkt-Ergebnisse {treff.ergebnisse}: die Etappen-Abrufe liefen nie "
        "gleichzeitig -- sie laufen noch nacheinander.")
    assert zeilen_kern(ergebnis.rows) == [(s.date, s.name) for s in trip.stages]


def test_ac6_trend_dauer_unter_80_prozent_der_summe(rand, thread_fehler):
    """AC-6: GIVEN drei Folge-Etappen mit je 0,5 s Verzoegerung am Rand
    (Summe 1,5 s); WHEN der Trend gebaut wird; THEN dauert er unter 1,2 s und
    liefert alle drei Zeilen in Etappenreihenfolge."""
    trip = trend_trip(3)
    prov = rand(etappen_tage(trip), verzoegerung=lambda idx, label: 0.5 if label == "1" else 0.0)
    dienst = _dienst(tag="ac6d")

    t0 = _ECHT()
    ergebnis = trend_lauf(dienst, trip)
    dauer = _ECHT() - t0

    assert prov.etappen_mit_abruf() == [0, 1, 2]
    assert dauer < 1.2, f"Trend dauerte {dauer:.2f} s bei 1,5 s Summe -- Etappen seriell"
    assert zeilen_kern(ergebnis.rows) == [(s.date, s.name) for s in trip.stages]
