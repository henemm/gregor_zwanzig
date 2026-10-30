"""TDD RED -- Feature #1539 (S5): Mandantentrennung im parallelen Briefing.

SPEC: docs/specs/modules/feat_1539_s5_briefing_parallel.md (AC-7)

Zwei verschiedene Nutzer fuehren gleichzeitig Trend, Gewitter-Fallback und das
Briefing mit amtlichen Warnungen aus. Die Worker lesen ``self._user_id`` nur;
jeder Abruf muss die ``user_id`` SEINES Nutzers tragen (nie ``"default"`` oder
``None``), und nichts des einen Nutzers darf im Ergebnis des anderen stehen.

Erfasst am Rand: ``user_id`` je Wetter-Abruf (``SegmentWeatherService.
fetch_segment_weather``, delegierend mitgelesen, wie S3) und die Budget-Toepfe
je Nutzer (``ForecastBudgetGate``, echte Buchung beim Cache-Fehlschlag);
Warnungen und ``official_queries`` am Entwarnungs-Eingang.

Vorbedingung "lief parallel": ohne sie waere der Test schon im heutigen
seriellen Ablauf gruen und bewachte die Worker nicht. Die Ueberlappung wird
JE NUTZER aus den Zeitstempeln des Rands bestimmt (zwei Nutzer gleichzeitig
sind kein Beleg fuer parallele Etappen eines Nutzers).
"""
from __future__ import annotations

# Fixtures kommen per Import aus _briefing_parallel_fixtures; ihre Namen als
# Testparameter sind fuer ruff Umdefinitionen (F811), fuer pytest der Normalfall.
# ruff: noqa: F811

import dataclasses
import threading
from concurrent.futures import ThreadPoolExecutor

from tests.tdd._briefing_parallel_fixtures import (  # noqa: F401
    ZEITSCHRANKE,
    Warnquelle,
    assert_warnabrufe_in_workern,
    briefing_lauf,
    briefing_rand,
    etappen_tage,
    fallback_lauf,
    koord,
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
    warn_label,
    warn_trip,
    warnquellen,
)

pruefling_aus_worktree()  # Pfadregel #1409: Pruefling aus DIESEM Worktree


def _breiten(trip) -> set:
    return {round(w.lat, 3) for s in trip.stages for w in s.waypoints}


def _etappen_ueberlappen(aufrufe: list) -> bool:
    """Gibt es zwei Abrufe VERSCHIEDENER Etappen, deren Zeitspannen sich
    schneiden?"""
    for i, a in enumerate(aufrufe):
        for b in aufrufe[i + 1:]:
            if a["etappe"] != b["etappe"] and a["t0"] < b["t1"] and b["t0"] < a["t1"]:
                return True
    return False


def test_ac7_zwei_nutzer_trend_und_fallback_gleichzeitig_getrennt(
    rand, monkeypatch, thread_fehler,
):
    """AC-7: GIVEN zwei Nutzer mit je eigenem Trip (eigene Orte, eigene
    Etappennamen) starten gleichzeitig Trend und Gewitter-Fallback;
    WHEN die Worker laufen;
    THEN traegt jeder Wetter-Abruf die user_id seines Nutzers (nie
    ``"default"``/``None``), jeder Budget-Topf zaehlt genau die Abrufe seines
    Nutzers, der Topf ``"default"`` bleibt unberuehrt, und Zeilen/Etappenwetter
    enthalten nur Etappen des eigenen Trips."""
    from services.forecast_budget import ForecastBudgetGate
    from services.segment_weather import SegmentWeatherService
    from services.trip_report_scheduler import TripReportSchedulerService

    ua, ub = neue_kennung("ac7a"), neue_kennung("ac7b")
    trip_a, trip_b = trend_trip(3), trend_trip(3)
    for t, praefix in ((trip_a, "A"), (trip_b, "B")):
        t.stages = [dataclasses.replace(s, name=f"{praefix}-{s.name}") for s in t.stages]
    assert etappen_tage(trip_a) == etappen_tage(trip_b)
    # Sechs Slots: beide Nutzer duerfen ihre drei Etappen gleichzeitig abrufen,
    # sonst haengt die Ueberlappung JE NUTZER an der Slot-Vergabe.
    slots_setzen(monkeypatch, "open_meteo", 6)
    prov = rand(etappen_tage(trip_a), verzoegerung=lambda idx, label: 0.15)

    gesehen: list[tuple] = []
    echt = SegmentWeatherService.fetch_segment_weather

    def mitlesen(self, segment, *args, **kwargs):
        gesehen.append((round(segment.start_point.lat, 3), kwargs.get("user_id")))
        return echt(self, segment, *args, **kwargs)

    monkeypatch.setattr(SegmentWeatherService, "fetch_segment_weather", mitlesen)
    vorher_default = ForecastBudgetGate("default").snapshot().get("user_calls_today", 0)
    treffpunkt = threading.Barrier(2)

    def lauf(uid, trip):
        dienst = TripReportSchedulerService(settings=settings_ohne_transport(), user_id=uid)
        treffpunkt.wait(timeout=ZEITSCHRANKE)
        return trend_lauf(dienst, trip), fallback_lauf(dienst, trip)

    with ThreadPoolExecutor(max_workers=2) as pool:
        fa, fb = pool.submit(lauf, ua, trip_a), pool.submit(lauf, ub, trip_b)
        (trend_a, fb_a), (trend_b, fb_b) = (
            fa.result(timeout=ZEITSCHRANKE), fb.result(timeout=ZEITSCHRANKE))

    breiten_a, breiten_b = _breiten(trip_a), _breiten(trip_b)
    for nutzer, breiten in ((ua, breiten_a), (ub, breiten_b)):
        ids = {u for lat, u in gesehen if lat in breiten}
        assert ids == {nutzer}, f"Abrufe fuer {nutzer} trugen user_id {ids}"
    eigene_a = [a for a in prov.aufrufe if round(a["lat"], 3) in breiten_a]
    eigene_b = [a for a in prov.aufrufe if round(a["lat"], 3) in breiten_b]
    assert _etappen_ueberlappen(eigene_a) and _etappen_ueberlappen(eigene_b), (
        "Vorbedingung: je Nutzer liefen Etappen-Abrufe parallel -- heute nacheinander")
    assert ForecastBudgetGate(ua).snapshot()["user_calls_today"] == len(eigene_a)
    assert ForecastBudgetGate(ub).snapshot()["user_calls_today"] == len(eigene_b)
    assert ForecastBudgetGate("default").snapshot().get("user_calls_today", 0) == vorher_default, (
        "Es wurde im Topf 'default' gebucht -- user_id ging im Worker verloren")

    assert [r["name"] for r in trend_a.rows] == [s.name for s in trip_a.stages]
    assert [r["name"] for r in trend_b.rows] == [s.name for s in trip_b.stages]
    assert {round(w.segment.start_point.lat, 3) for w in fb_a} <= breiten_a
    assert {round(w.segment.start_point.lat, 3) for w in fb_b} <= breiten_b
    assert fb_a and fb_b


def test_ac7_zwei_nutzer_warnungen_und_queries_gleichzeitig_getrennt(
    briefing_rand, warnquellen, thread_fehler,
):
    """AC-7: GIVEN zwei Nutzer mit je eigenem Trip (eigene Warn-Koordinaten)
    fuehren gleichzeitig das Briefing aus;
    WHEN die Warn-Worker laufen;
    THEN erreicht jeder Entwarnungs-Eingang die user_id seines Nutzers (nie
    ``"default"``/``None``), und Warnungen sowie ``official_queries`` jedes
    Nutzers enthalten ausschliesslich die eigenen Koordinaten."""
    ua, ub = neue_kennung("ac7wa"), neue_kennung("ac7wb")
    pa = [(neue_breite(), 11.40) for _ in range(3)]
    pb = [(neue_breite(), 11.40) for _ in range(3)]
    trip_a, trip_b = warn_trip(pa), warn_trip(pb)
    quelle = warnquellen(Warnquelle(
        tag=trip_a.stages[0].date, verzoegerung={koord(*x): 0.1 for x in pa + pb}))
    treffpunkt = threading.Barrier(2)

    def lauf(uid, trip):
        treffpunkt.wait(timeout=ZEITSCHRANKE)
        dienst, outcome = briefing_lauf(trip, uid)
        return dienst.__dict__["im_request"], outcome

    with ThreadPoolExecutor(max_workers=2) as pool:
        fa, fb = pool.submit(lauf, ua, trip_a), pool.submit(lauf, ub, trip_b)
        (req_a, out_a), (req_b, out_b) = (
            fa.result(timeout=ZEITSCHRANKE), fb.result(timeout=ZEITSCHRANKE))

    assert out_a == "sent" and out_b == "sent", (out_a, out_b)
    assert_warnabrufe_in_workern(quelle)
    assert req_a == [(sid, [warn_label(koord(*x))], False)
                     for sid, x in zip(("1", "2", "Ziel"), pa)]
    assert req_b == [(sid, [warn_label(koord(*x))], False)
                     for sid, x in zip(("1", "2", "Ziel"), pb)]

    settle = dict(briefing_rand["settle"])
    assert set(settle) == {ua, ub}, (
        f"Entwarnungs-Eingang erreichte user_ids {sorted(map(str, settle))}")
    from services.official_alert_allclear import scope_token

    assert [q.scope for q in settle[ua]] == [scope_token(*x) for x in pa]
    assert [q.scope for q in settle[ub]] == [scope_token(*x) for x in pb]
