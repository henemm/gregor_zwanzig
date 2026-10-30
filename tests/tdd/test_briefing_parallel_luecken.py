"""Fix-Loop 1 -- Feature #1539 (S5): Test-Luecken aus dem Adversary-Verdict.

SPEC: docs/specs/modules/feat_1539_s5_briefing_parallel.md (AC-2, AC-3, AC-4, AC-5)

* F001: ``get_official_alerts_with_status`` wirft WIRKLICH (nicht intern
  geschluckt) -> Segment ``[]`` + ``official_alerts_unavailable=True``,
  Warn-Log mit Grund (Quellenausfall ist nie Entwarnung, #1348).
* F002: Trend, alle Etappen ``skipped`` (Frist) -> Zustand UNAVAILABLE
  (am Zustand geprueft, nicht am Log).
* F003: Gewitter-Fallback schreibt den Trip je Etappe fort (wie AC-2 beim
  Trend).
* F004: Zeilenbau des Trends nutzt die Konfiguration des Trip-Stands SEINER
  Etappe, nicht die des zuletzt fortgeschriebenen Trips.

Aufbau wie in ``_briefing_parallel_fixtures`` (Rand-Provider, echte Registry,
echte Laeufe). Pfadregel #1409: Pruefling aus DIESEM Worktree.
"""
from __future__ import annotations

# Fixtures kommen per Import aus _briefing_parallel_fixtures; ihre Namen als
# Testparameter sind fuer ruff Umdefinitionen (F811), fuer pytest der Normalfall.
# ruff: noqa: F811

import copy
import logging
import threading
from datetime import timedelta

from services.trip_report_scheduler import TripReportSchedulerService
from tests.tdd._briefing_parallel_fixtures import (  # noqa: F401
    briefing_lauf,
    briefing_rand,
    etappen_tage,
    fallback_lauf,
    frist_setzen,
    heute_utc,
    neue_breite,
    neue_kennung,
    pruefling_aus_worktree,
    rand,
    settings_ohne_transport,
    slots_setzen,
    thread_fehler,
    trend_lauf,
    trend_trip,
    umgebung,
    warn_trip,
    warnquellen,
    zeilen_kern,
)

pruefling_aus_worktree()  # Pfadregel #1409


def _dienst(tag: str, klasse=TripReportSchedulerService):
    return klasse(settings=settings_ohne_transport(), user_id=neue_kennung(tag))


# --------------------------------------------------------------------------- #
# F001 Warn-Abruf wirft wirklich
# --------------------------------------------------------------------------- #
def test_f001_warnabruf_mit_echter_ausnahme_ergibt_leer_und_unavailable(
    briefing_rand, monkeypatch, caplog, thread_fehler,
):
    """F001/AC-4: GIVEN der Warn-Eingang ``get_official_alerts_with_status``
    wirft fuer jede Koordinate (z. B. kaputte Quelle, die NICHT intern
    abgefangen wird); WHEN das Briefing die Warnungen parallel laedt;
    THEN traegt jedes Segment ``[]`` mit ``official_alerts_unavailable=True``
    (nie Entwarnung), und der Grund steht im Warn-Log."""
    import services.official_alerts as oa

    def _kaputt(lat, lon, **kwargs):
        raise RuntimeError("Rand: Warndienst kaputt")

    monkeypatch.setattr(oa, "get_official_alerts_with_status", _kaputt)
    p = [(neue_breite(), 11.40) for _ in range(3)]
    trip = warn_trip(p)

    with caplog.at_level(logging.WARNING):
        dienst, _ = briefing_lauf(trip, neue_kennung("f001"))

    assert dienst.__dict__["im_request"] == [
        ("1", [], True), ("2", [], True), ("Ziel", [], True),
    ]
    zeilen = [r.getMessage() for r in caplog.records
              if r.levelno >= logging.WARNING and "official" in r.getMessage()
              and "Warndienst kaputt" in r.getMessage()]
    assert len(zeilen) >= 3, f"Je Koordinate eine Warnzeile mit Grund erwartet: {zeilen!r}"


# --------------------------------------------------------------------------- #
# F002 Trend: alle Etappen skipped -> UNAVAILABLE
# --------------------------------------------------------------------------- #
def test_f002_trend_mit_nur_uebersprungenen_etappen_ist_unavailable(
    rand, monkeypatch, thread_fehler,
):
    """F002/AC-5: GIVEN ein ``open_meteo``-Slot, Frist 0,05 s und je Etappe
    0,4 s am Rand (keine Etappe wird rechtzeitig fertig); WHEN der Trend
    gebaut wird; THEN gibt es keine Zeile und der Zustand ist UNAVAILABLE
    (der Fristausfall zaehlt als Stoerung, nicht als "keine Etappen")."""
    slots_setzen(monkeypatch, "open_meteo", 1)
    frist_setzen(monkeypatch, 0.05)
    trip = trend_trip(3)
    rand(etappen_tage(trip), verzoegerung=lambda idx, label: 0.4 if label == "1" else 0.0)

    ergebnis = trend_lauf(_dienst("f002"), trip)

    assert ergebnis.rows is None
    assert ergebnis.state.name == "UNAVAILABLE", ergebnis.state


# --------------------------------------------------------------------------- #
# F003 Fallback schreibt den Trip je Etappe fort
# --------------------------------------------------------------------------- #
class _Beobachter(TripReportSchedulerService):
    """Echter Scheduler; schreibt Umwandlung und Anreicherung nur mit."""

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


def test_f003_fallback_schreibt_trip_je_etappe_fort(rand, thread_fehler):
    """F003/AC-3: GIVEN ein Bestandstrip mit unvermessenen Etappen (die
    Umwandlung traegt Distanzen nach und schreibt ``_last_converted_trip``
    fort); WHEN der Gewitter-Fallback zwei Etappen sammelt; THEN laeuft die
    Umwandlung im Hauptfaden, Etappe 2 bekommt den fortgeschriebenen Trip der
    Etappe 1, und die Anreicherung sieht je Etappe den Trip nach IHRER
    Umwandlung."""
    from tests.tdd.test_ausblick_schleife_bewahrt_alle_nachgeruesteten_kilometrierungen import (
        _trip_mit_n_unvermessenen_etappen,
    )

    heute = heute_utc()
    tage = [heute + timedelta(days=i) for i in range(3)]
    dienst = _dienst("f003", klasse=_Beobachter)
    trip = _trip_mit_n_unvermessenen_etappen(dienst._user_id, tage)
    rand(tage, verzoegerung=lambda idx, label: (0.2, 0.05, 0.0)[idx])
    haupt = threading.get_ident()

    daten = fallback_lauf(dienst, trip)

    assert {w.segment.start_time.date() for w in daten} == set(tage[:2])
    umw = dienst.__dict__["umwandlungen"]
    assert [u["tag"] for u in umw] == tage[:2], umw
    assert {u["thread"] for u in umw} == {haupt}
    assert all(u["rein"] != u["raus"] for u in umw), (
        "Vorbedingung: die Nachruestung erzeugte je Etappe einen neuen Trip")
    assert umw[1]["rein"] == umw[0]["raus"], (
        "Etappe 2 bekam nicht den fortgeschriebenen Trip der Etappe 1")
    anr = dict(dienst.__dict__["anreicherungen"])
    assert [anr.get(t) for t in tage[:2]] == [u["raus"] for u in umw], (
        "Die Anreicherung sah nicht den Trip-Stand nach ihrer eigenen Etappe")


# --------------------------------------------------------------------------- #
# F004 Zeilenbau mit der Konfiguration des Etappen-Stands
# --------------------------------------------------------------------------- #
class _FensterJeEtappe(TripReportSchedulerService):
    """Echte Umwandlung; der fortgeschriebene Trip-Stand traegt danach je
    Etappe ein eigenes Tagesfenster (5, 6, 7 Uhr bis 20 Uhr). So ist am
    Ergebnis sichtbar, WELCHER Trip-Stand den Zeilenbau speist."""

    def _convert_trip_to_segments(self, trip, target_date, **kw):
        from app.models import TripReportConfig

        segmente = super()._convert_trip_to_segments(trip, target_date, **kw)
        basis = self._last_converted_trip or trip
        fenster = self.__dict__.setdefault("fenster", [])
        start = 5 + len(fenster)
        fenster.append(start)
        neu = copy.copy(basis)
        neu.report_config = TripReportConfig(
            trip_id=basis.id, day_window_start_hour=start, day_window_end_hour=20)
        self._last_converted_trip = neu
        return segmente


def test_f004_trendzeile_nutzt_konfiguration_ihres_etappenstands(rand, thread_fehler):
    """F004/AC-2: GIVEN drei Folge-Etappen, deren fortgeschriebener Trip-Stand
    je Etappe ein anderes Tagesfenster traegt; WHEN der Trend parallel gebaut
    wird; THEN traegt jede Zeile das Fenster IHRES Etappenstands (5/6/7), nicht
    das des zuletzt fortgeschriebenen Trips (wie im seriellen Ablauf)."""
    trip = trend_trip(3)
    rand(etappen_tage(trip), verzoegerung=lambda idx, label: (0.15, 0.1, 0.05)[idx])
    dienst = _dienst("f004", klasse=_FensterJeEtappe)

    ergebnis = trend_lauf(dienst, trip)

    assert zeilen_kern(ergebnis.rows) == [(s.date, s.name) for s in trip.stages]
    assert [r["day_window_start_hour"] for r in ergebnis.rows] == [5, 6, 7]
    assert [r["day_window_end_hour"] for r in ergebnis.rows] == [20, 20, 20]
