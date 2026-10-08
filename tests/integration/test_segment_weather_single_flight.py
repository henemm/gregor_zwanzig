"""Issue #1539 (S1b+S2): Single-flight im Wetterabruf (`segment_weather`).

SPEC: docs/specs/modules/feat_1539_s1b_s2_abruf_baustein.md
      (Abschnitt F, AC-11, AC-13 bis AC-18)
KONTEXT: docs/context/feat-1539-s1b-s2-abruf-baustein.md
         ("Schnittstellen-Festlegungen fuer TDD RED")

Ausfuehrung:
    uv run pytest tests/integration/test_segment_weather_single_flight.py -v -rA --disable-socket

RED-Erwartung (vor /50-implement):
  * AC-11  GRUEN  -- Waechter: heute bucht `allow()` nichts und die
                     Validierung scheitert vor `record_call()`. Wird relevant,
                     sobald `reserve()` (bucht) eingebaut wird: dann MUSS
                     `_validate_segment` davor liegen (Mutation 6 der Spec).
  * AC-13  ROT    -- N parallele Abrufe => N `fetch_forecast` statt 1.
  * AC-14  ROT    -- zwei Nutzer: beide rufen den Provider, kein Cache-Hit.
  * AC-15  ROT    -- Cache-Inhalt selbst ist heute schon roh; rot wird der
                     Test an der Provider-Zaehlung des Zwei-Nutzer-Laufs.
  * AC-16  GRUEN  -- Waechter; die Ueberlappung (Wartender haengt am Flug des
                     gedrosselten Leaders) wird seit Fix-Loop 1 ueber einen
                     Haken im echten Cache (`_HakenCache`) erzwungen.
  * AC-17  ROT    -- Leader-Fehler: jeder Thread macht eigenen Retry-Zyklus.
  * AC-18  Folge (a) ROT (seriell 1, parallel N), (b) und (c) je nach
           Ueberlappung; Budget-erschoepft-Fall GRUEN (Waechter).

Provider-Injektion: `SegmentWeatherService(provider, cache=cache)` mit einem
ECHTEN, zaehlenden Fake-Provider (Klasse `ZaehlenderProvider`, kein
Mock/patch). Er sitzt am Provider-Rand, zaehlt `fetch_forecast` unter einem
Lock und haelt jeden Abruf `ABRUF_DAUER_S` offen, damit die uebrigen Threads
deterministisch am Flug des Leaders haengen. Jeder Test baut EIN geteiltes
`WeatherCacheService` (so wie der Prozess-Singleton) und je Nutzer einen
eigenen `SegmentWeatherService`. Budget- und Cache-Daten liegen in der durch
`tests/conftest.py` umgeleiteten Wegwerf-Datenwurzel.

Nebenlaeufigkeit: `Barrier`, Thread-Ausnahmen werden selbst eingesammelt und
asserted (C4-62), `join(timeout=...)` + `assert not t.is_alive()`.
"""
from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest

from app.loader import get_data_root
from app.models import (
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    TripSegment,
)
from providers.base import ProviderRequestError
from services.forecast_budget import PROVIDER, ForecastBudgetGate
from services.segment_weather import SegmentWeatherService
from services.weather_cache import WeatherCacheService
from tests.helpers.ortstag import utc_tag

NUTZER_A = "nutzer-a"
NUTZER_B = "nutzer-b"
NUTZER_C = "nutzer-c"

# So lange haelt der Provider-Rand jeden Abruf offen. Gross gegen die
# Streuung beim Barrier-Release (ms), klein gegen das Testbudget.
ABRUF_DAUER_S = 0.6
JOIN_FRIST_S = 30.0


# --- Fake-Provider am Provider-Rand --------------------------------------

class ZaehlenderProvider:
    """Echter Fake (KEIN Mock/patch): liefert wie der reale OpenMeteo-Provider
    einen vollen UTC-Tag (24 Punkte, `t2m_c == Stunde`), zaehlt jeden
    `fetch_forecast` und haelt ihn `dauer_s` offen. Optional wirft er
    `ProviderRequestError`. `aufrufe` haelt den Ortsnamen
    (`Segment <segment_id>`) in Eintreffreihenfolge -- der erste Eintrag
    identifiziert den Leader."""

    def __init__(self, dauer_s: float = ABRUF_DAUER_S, fehler: bool = False) -> None:
        self._lock = threading.Lock()
        self.aufrufe: list[str] = []
        self._dauer_s = dauer_s
        self._fehler = fehler

    @property
    def name(self) -> str:
        return "openmeteo"

    @property
    def call_count(self) -> int:
        with self._lock:
            return len(self.aufrufe)

    def fetch_forecast(
        self,
        location,
        start=None,
        end=None,
        enrich_ensemble: bool = True,
        enrich_snow: bool = True,
    ) -> NormalizedTimeseries:
        with self._lock:
            self.aufrufe.append(location.name)
        time.sleep(self._dauer_s)
        if self._fehler:
            raise ProviderRequestError("openmeteo", "HTTP 503 (Fake am Provider-Rand)", 503)
        anchor = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        meta = ForecastMeta(
            provider=Provider.OPENMETEO,
            model="icon_d2",
            grid_res_km=2.2,
            run=datetime.now(timezone.utc),
            interp="grid_point",
        )
        data = [
            ForecastDataPoint(ts=anchor + timedelta(hours=h), t2m_c=float(h))
            for h in range(24)
        ]
        return NormalizedTimeseries(meta=meta, data=data)


# --- Arrangement-Helfer ----------------------------------------------------

def _segment(
    segment_id,
    lat: float = 47.05,
    lon: float = 11.10,
    start_hour: int = 10,
    duration_hours: float = 3.0,
    elevation_m: float = 1200.0,
) -> TripSegment:
    start = datetime.now(timezone.utc).replace(
        hour=start_hour, minute=0, second=0, microsecond=0
    )
    point = GPXPoint(lat=lat, lon=lon, elevation_m=elevation_m)
    return TripSegment(
        segment_id=segment_id,
        start_point=point,
        end_point=point,
        start_time=start,
        end_time=start + timedelta(hours=duration_hours),
        duration_hours=duration_hours,
        distance_km=0.0,
        ascent_m=0,
        descent_m=0,
    )


def _dienst(provider, cache) -> SegmentWeatherService:
    return SegmentWeatherService(provider, cache=cache)


def _setze_budget(calls: int, active_users) -> None:
    pfad = get_data_root() / "diagnostics" / "forecast_budget.json"
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps({
        "date": utc_tag().isoformat(),
        "calls": {PROVIDER: calls},
        "cache_hits": 0,
        "cache_misses": 0,
        "active_users": list(active_users),
    }))


def _stand(user_id: str | None) -> dict:
    return ForecastBudgetGate(user_id).snapshot()


def _parallel(aufgaben, join_frist_s: float = JOIN_FRIST_S):
    """Startet jede Aufgabe (Callable ohne Argumente) in einem eigenen Thread,
    gibt sie ueber eine Barrier gleichzeitig frei und sammelt Ergebnisse UND
    Thread-Ausnahmen selbst ein (C4-62). Liefert (ergebnisse, fehler) in
    Aufgabenreihenfolge."""
    n = len(aufgaben)
    barrier = threading.Barrier(n)
    ergebnisse: list = [None] * n
    fehler: list = [None] * n

    def _lauf(i, fn):
        def _inner():
            try:
                barrier.wait(timeout=10)
                ergebnisse[i] = fn()
            except BaseException as exc:  # noqa: BLE001 - bewusst alles einsammeln
                fehler[i] = exc
        return _inner

    threads = [threading.Thread(target=_lauf(i, fn), daemon=True) for i, fn in enumerate(aufgaben)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=join_frist_s)
    haengende = [t for t in threads if t.is_alive()]
    assert not haengende, f"{len(haengende)} Thread(s) haengen nach {join_frist_s}s"
    return ergebnisse, fehler


def _keine_thread_fehler(fehler) -> None:
    assert all(f is None for f in fehler), f"Thread-Ausnahmen: {fehler!r}"


def _baseline(segment: TripSegment):
    """Referenz: dasselbe Segment seriell, frischer Cache, eigener Nutzer."""
    dienst = _dienst(ZaehlenderProvider(dauer_s=0.0), WeatherCacheService())
    return dienst.fetch_segment_weather(segment, user_id="nutzer-referenz")


# --- AC-11 -----------------------------------------------------------------

@pytest.mark.timeout(60)
def test_ac11_validierungsfehler_bucht_keinen_call_und_ruft_keinen_provider():
    """AC-11 (WAECHTER, heute schon gruen -- ehrlich so benannt): ein Segment,
    das `_validate_segment` nicht besteht, laesst den Budgetzaehler
    unveraendert und erreicht den Provider nie. Heute bucht `allow()` nichts
    und die Validierung scheitert vor `record_call()`; der Test bewacht, dass
    das nach dem Einbau von `reserve()` (bucht!) so bleibt -- dann muss
    `_validate_segment` VOR `reserve` laufen."""
    _setze_budget(calls=10, active_users=[NUTZER_A])
    provider = ZaehlenderProvider(dauer_s=0.0)
    dienst = _dienst(provider, WeatherCacheService())

    kaputt = _segment("kaputt")
    kaputt.end_time = kaputt.start_time - timedelta(hours=1)  # Ende vor Start

    vorher_global, vorher_user = _stand(None), _stand(NUTZER_A)
    with pytest.raises(ValueError):
        dienst.fetch_segment_weather(kaputt, user_id=NUTZER_A)
    nachher_global, nachher_user = _stand(None), _stand(NUTZER_A)

    assert provider.call_count == 0
    assert nachher_global["calls_today"] == vorher_global["calls_today"] == 10
    assert nachher_user["user_calls_today"] == vorher_user["user_calls_today"] == 0


# --- AC-13 -----------------------------------------------------------------

@pytest.mark.timeout(60)
def test_ac13_n_parallele_gleiche_segmente_genau_ein_fetch_forecast():
    """AC-13: N parallele Abrufe desselben Segments (gleicher Bucket, gleiches
    Fenster) => genau EIN `fetch_forecast` am Provider-Rand, alle N bekommen
    ein Ergebnis."""
    n = 6
    provider = ZaehlenderProvider()
    cache = WeatherCacheService()
    dienst = _dienst(provider, cache)
    segment = _segment("gleich")

    ergebnisse, fehler = _parallel([
        (lambda: dienst.fetch_segment_weather(segment, user_id=NUTZER_A)) for _ in range(n)
    ])

    _keine_thread_fehler(fehler)
    assert all(isinstance(e, SegmentWeatherData) for e in ergebnisse)
    assert all(not e.has_error and e.timeseries is not None for e in ergebnisse)
    assert provider.call_count == 1, (
        f"{provider.call_count} fetch_forecast statt 1 bei {n} parallelen gleichen Segmenten"
    )


# --- AC-14 -----------------------------------------------------------------

@pytest.mark.timeout(60)
def test_ac14_zwei_nutzer_call_auf_leader_gate_hit_auf_eigenem_gate_des_wartenden():
    """AC-14: zwei echte Nutzer rufen parallel dasselbe Segment. Der Call wird
    auf dem Gate des Leaders gebucht, der Wartende bucht einen Cache-Hit auf
    SEINEM Gate (kein eigener Call) und erhaelt die EIGENE `segment_id` samt
    eigenem Aggregat.

    Hinweis: `cache_hits` liegt nur im globalen Topf; die Zuordnung zum
    Nutzer laeuft daher ueber `user_calls_today` (Call nur beim Leader)
    plus globales Delta `calls == +1`, `cache_hits == +1`."""
    provider = ZaehlenderProvider()
    cache = WeatherCacheService()
    dienst_a, dienst_b = _dienst(provider, cache), _dienst(provider, cache)
    seg_a = _segment("seg-a")
    seg_b = _segment("seg-b")  # gleicher Bucket+Fenster, eigene Identitaet

    erwartet_a = _baseline(seg_a)
    erwartet_b = _baseline(seg_b)
    vorher = _stand(None)

    (res_a, res_b), fehler = _parallel([
        lambda: dienst_a.fetch_segment_weather(seg_a, user_id=NUTZER_A),
        lambda: dienst_b.fetch_segment_weather(seg_b, user_id=NUTZER_B),
    ])

    _keine_thread_fehler(fehler)
    assert provider.call_count == 1
    leader_user = NUTZER_A if provider.aufrufe[0] == "Segment seg-a" else NUTZER_B
    wartender_user = NUTZER_B if leader_user == NUTZER_A else NUTZER_A

    assert _stand(leader_user)["user_calls_today"] == 1
    assert _stand(wartender_user)["user_calls_today"] == 0
    nachher = _stand(None)
    assert nachher["calls_today"] - vorher["calls_today"] == 1
    assert nachher["cache_hits"] - vorher["cache_hits"] == 1

    # Eigene Identitaet und eigenes Aggregat -- nie die des Leaders.
    assert res_a.segment.segment_id == "seg-a"
    assert res_b.segment.segment_id == "seg-b"
    for res, ref in ((res_a, erwartet_a), (res_b, erwartet_b)):
        assert res.aggregated.temp_min_c == ref.aggregated.temp_min_c
        assert res.aggregated.temp_max_c == ref.aggregated.temp_max_c


# --- AC-15 -----------------------------------------------------------------

@pytest.mark.timeout(60)
def test_ac15_cache_nach_zwei_nutzer_lauf_nur_rohzeitreihen_kein_identitaetsleck():
    """AC-15 (ergaenzt fix_1329 AC-9): nach Single-flight-Laeufen mit zwei
    Nutzern enthaelt der Cache ausschliesslich Rohzeitreihen -- weder
    Nutzerkennung noch Segmentidentitaet noch Aggregat. Ein dritter Aufrufer
    mit ABWEICHENDER (schmalerer) Fensterdauer bekommt aus dem Cache nie
    Identitaet oder Aggregat des Ersten, sondern seine eigenen."""
    provider = ZaehlenderProvider()
    cache = WeatherCacheService()
    seg_a = _segment("breit-a", start_hour=10, duration_hours=4.0)
    seg_b = _segment("breit-b", start_hour=10, duration_hours=4.0)
    seg_c = _segment("schmal-c", start_hour=11, duration_hours=1.0)
    erwartet_c = _baseline(seg_c)

    (res_a, res_b), fehler = _parallel([
        lambda: _dienst(provider, cache).fetch_segment_weather(seg_a, user_id=NUTZER_A),
        lambda: _dienst(provider, cache).fetch_segment_weather(seg_b, user_id=NUTZER_B),
    ])
    _keine_thread_fehler(fehler)
    # Zugleich der Beweis, dass der Cache ueberhaupt genau einmal befuellt wurde.
    assert provider.call_count == 1

    res_c = _dienst(provider, cache).fetch_segment_weather(seg_c, user_id=NUTZER_C)
    assert provider.call_count == 1  # Hit ueber "covers"-Regel

    assert cache.stats()["total_entries"] == 1
    for eintrag in cache._cache.values():
        assert isinstance(eintrag.timeseries, NormalizedTimeseries)
        for wert in list(vars(eintrag).values()) + list(vars(eintrag.timeseries).values()):
            assert not isinstance(wert, (SegmentWeatherData, TripSegment))
        text = repr(eintrag)
        for kennung in (NUTZER_A, NUTZER_B, NUTZER_C, "breit-a", "breit-b", "schmal-c"):
            assert kennung not in text, f"{kennung!r} im Cache-Eintrag"
    for schluessel in cache._cache:
        for kennung in (NUTZER_A, NUTZER_B, NUTZER_C, "breit-a", "breit-b", "schmal-c"):
            assert kennung not in schluessel

    assert res_c.segment.segment_id == "schmal-c"
    assert res_c.aggregated.temp_min_c == erwartet_c.aggregated.temp_min_c
    assert res_c.aggregated.temp_max_c == erwartet_c.aggregated.temp_max_c
    # Das Aggregat des breiten Fensters waere ein anderes.
    assert res_a.aggregated.temp_max_c != res_c.aggregated.temp_max_c


# --- AC-16 -----------------------------------------------------------------

class _HakenCache(WeatherCacheService):
    """Echter Cache mit Haken (KEIN Mock): der Thread namens ``leader`` haelt
    bei seinem ZWEITEN ``get`` -- das ist die Doppelpruefung im Flug, der Flug
    ist also schon registriert -- an, bis ``freigabe`` gesetzt wird. So haengt
    ein spaeter eintreffender Wartender nachweislich am laufenden Flug."""

    def __init__(self) -> None:
        super().__init__()
        self.freigabe = threading.Event()
        self.leader_im_flug = threading.Event()
        self.wartender_hat_geprueft = threading.Event()
        self._zaehler: dict[str, int] = {}
        self._zaehler_lock = threading.Lock()

    def get(self, segment, enrich_ensemble=True, enrich_snow=True, model_id=""):
        name = threading.current_thread().name
        with self._zaehler_lock:
            self._zaehler[name] = self._zaehler.get(name, 0) + 1
            nr = self._zaehler[name]
        if name == "leader" and nr == 2:
            self.leader_im_flug.set()
            assert self.freigabe.wait(timeout=20), "Haken nie freigegeben"
        ergebnis = super().get(segment, enrich_ensemble, enrich_snow, model_id)
        if name == "wartender" and nr == 1:
            self.wartender_hat_geprueft.set()
        return ergebnis


def _starte(name, fn, ergebnisse, fehler) -> threading.Thread:
    def _inner():
        try:
            ergebnisse[name] = fn()
        except BaseException as exc:  # noqa: BLE001 - C4-62: selbst einsammeln
            fehler.append((name, exc))
    t = threading.Thread(target=_inner, name=name, daemon=True)
    t.start()
    return t


@pytest.mark.timeout(60)
def test_ac16_gedrosselter_leader_wartender_mit_hoeherer_prioritaet_ruft_selbst_ab():
    """AC-16 (Wirkstelle, F001): Budget erschoepft (`calls == DAILY_BUDGET`).
    Der Leader laeuft auf niedriger Prioritaet (`polling`) und haelt per Haken
    im Flug an. Erst wenn der Wartende (`user_briefing`) seine Erstpruefung
    hinter sich hat und damit am Flug haengt (0.4 s Vorsprung), wird der Leader
    freigegeben: er wird gedrosselt. Der Wartende darf das Drosselungs-
    Ergebnis NICHT erben, sondern reserviert selbst und ruft ab. Ergebnis:
    genau EIN Provider-Call, gebucht beim Wartenden."""
    _setze_budget(calls=ForecastBudgetGate.DAILY_BUDGET, active_users=[NUTZER_A, NUTZER_B])
    provider = ZaehlenderProvider(dauer_s=0.05)
    cache = _HakenCache()
    seg_leader = _segment("leader-niedrig")
    seg_wartend = _segment("wartend-hoch")
    ergebnisse: dict = {}
    fehler: list = []

    t_leader = _starte("leader", lambda: _dienst(provider, cache).fetch_segment_weather(
        seg_leader, priority="polling", user_id=NUTZER_A), ergebnisse, fehler)
    assert cache.leader_im_flug.wait(timeout=20), "Leader nie im Flug"
    t_wart = _starte("wartender", lambda: _dienst(provider, cache).fetch_segment_weather(
        seg_wartend, priority="user_briefing", user_id=NUTZER_B), ergebnisse, fehler)
    assert cache.wartender_hat_geprueft.wait(timeout=20)
    time.sleep(0.4)  # Wartender ist jetzt nachweislich am Flug des Leaders registriert
    assert provider.call_count == 0 and "wartender" not in ergebnisse
    cache.freigabe.set()
    for t in (t_leader, t_wart):
        t.join(timeout=JOIN_FRIST_S)
    assert not any(t.is_alive() for t in (t_leader, t_wart))
    assert not fehler, f"Thread-Ausnahmen: {fehler!r}"

    assert ergebnisse["leader"].has_error
    assert ergebnisse["leader"].error_message == "budget_throttled"
    assert not ergebnisse["wartender"].has_error, "Wartender erbte die Drosselung des Leaders"
    assert ergebnisse["wartender"].timeseries is not None
    assert ergebnisse["wartender"].segment.segment_id == "wartend-hoch"
    assert provider.call_count == 1
    assert _stand(NUTZER_B)["user_calls_today"] == 1
    assert _stand(NUTZER_A)["user_calls_today"] == 0


# --- F003: Doppelpruefung des Caches im Leader -----------------------------

class _VorgaengerSchreibtCache(WeatherCacheService):
    """Echter Cache: der ERSTE ``get`` liefert Miss, danach schreibt -- wie ein
    Vorgaenger-Flug, der zwischen Erstpruefung und Flugstart endet -- ein
    Eintrag fuer genau dieses Segment in den Cache."""

    def __init__(self, zeitreihe) -> None:
        super().__init__()
        self._zeitreihe = zeitreihe
        self._schon = False

    def get(self, segment, enrich_ensemble=True, enrich_snow=True, model_id=""):
        ergebnis = super().get(segment, enrich_ensemble, enrich_snow, model_id)
        if not self._schon:
            self._schon = True
            self.put(segment, self._zeitreihe, enrich_ensemble, enrich_snow, model_id)
        return ergebnis


@pytest.mark.timeout(60)
def test_f003_vorgaenger_flug_schreibt_zwischen_erstpruefung_und_flugstart_kein_zweiter_abruf():
    """Erstpruefung = Miss, dann ist der Cache befuellt, dann wird der Aufrufer
    Leader: die Doppelpruefung im Leader muss den Treffer finden, der Provider
    wird NICHT gerufen, der Treffer wird als Cache-Hit gebucht."""
    from types import SimpleNamespace

    zeitreihe = ZaehlenderProvider(dauer_s=0.0).fetch_forecast(SimpleNamespace(name="seed"))
    provider = ZaehlenderProvider(dauer_s=0.0)
    cache = _VorgaengerSchreibtCache(zeitreihe)
    vorher = _stand(None)

    ergebnis = _dienst(provider, cache).fetch_segment_weather(
        _segment("doppelpruefung"), user_id=NUTZER_A)

    assert not ergebnis.has_error and ergebnis.timeseries is not None
    assert provider.call_count == 0, "Doppelpruefung fehlt: zweiter Upstream-Abruf"
    nachher = _stand(None)
    assert nachher["calls_today"] == vorher["calls_today"]
    assert nachher["cache_hits"] - vorher["cache_hits"] == 1


# --- F004: Flug-Schluessel enthaelt Fenster und Cache-Instanz --------------

@pytest.mark.timeout(60)
def test_f004_gleicher_bucket_verschiedene_fenster_parallel_zwei_fetches_je_eigenes_fenster():
    """Gleicher Ort/Bucket, aber 4h- und 1h-Fenster gleichzeitig: der Flug-
    Schluessel enthaelt das Fenster, also zwei Fetches; jeder Aufrufer behaelt
    Identitaet und Aggregat seines eigenen Fensters."""
    provider = ZaehlenderProvider()
    cache = WeatherCacheService()
    breit = _segment("fenster-breit", start_hour=10, duration_hours=4.0)
    schmal = _segment("fenster-schmal", start_hour=11, duration_hours=1.0)
    erwartet_breit, erwartet_schmal = _baseline(breit), _baseline(schmal)

    (res_breit, res_schmal), fehler = _parallel([
        lambda: _dienst(provider, cache).fetch_segment_weather(breit, user_id=NUTZER_A),
        lambda: _dienst(provider, cache).fetch_segment_weather(schmal, user_id=NUTZER_B),
    ])

    _keine_thread_fehler(fehler)
    assert provider.call_count == 2, (
        f"{provider.call_count} fetch_forecast statt 2 bei verschiedenen Fenstern"
    )
    assert res_breit.segment.segment_id == "fenster-breit"
    assert res_schmal.segment.segment_id == "fenster-schmal"
    assert res_breit.aggregated.temp_max_c == erwartet_breit.aggregated.temp_max_c
    assert res_schmal.aggregated.temp_max_c == erwartet_schmal.aggregated.temp_max_c
    assert res_breit.aggregated.temp_max_c != res_schmal.aggregated.temp_max_c


@pytest.mark.timeout(60)
def test_f004_zwei_cache_instanzen_gleicher_schluessel_parallel_je_ein_abruf():
    """Zwei verschiedene Cache-Instanzen (z. B. Test vs. Prozess-Singleton)
    mit identischem Schluessel teilen KEINEN Flug: je Cache ein Abruf."""
    provider = ZaehlenderProvider()
    cache_1, cache_2 = WeatherCacheService(), WeatherCacheService()
    segment = _segment("zwei-caches")

    ergebnisse, fehler = _parallel([
        lambda: _dienst(provider, cache_1).fetch_segment_weather(segment, user_id=NUTZER_A),
        lambda: _dienst(provider, cache_2).fetch_segment_weather(segment, user_id=NUTZER_B),
    ])

    _keine_thread_fehler(fehler)
    assert all(not e.has_error for e in ergebnisse)
    assert provider.call_count == 2, (
        f"{provider.call_count} fetch_forecast statt 2 bei zwei Cache-Instanzen"
    )


# --- F006: Wartefrist-Ablauf im Segment-Pfad -------------------------------

class _ErsterHaengtProvider(ZaehlenderProvider):
    """Der ERSTE Abruf haengt ``haengt_s`` (haengender Leader), alle weiteren
    laufen sofort."""

    def __init__(self, haengt_s: float) -> None:
        super().__init__(dauer_s=0.0)
        self._haengt_s = haengt_s
        self._entscheid = threading.Lock()
        self._schon = False
        self.erster_drin = threading.Event()

    def fetch_forecast(self, location, **kwargs):
        with self._entscheid:
            erster, self._schon = not self._schon, True
        if erster:
            self.erster_drin.set()
            time.sleep(self._haengt_s)
        return super().fetch_forecast(location, **kwargs)


@pytest.mark.timeout(60)
def test_f006_wartefrist_abgelaufen_wartender_holt_selbst_ab_und_kehrt_fristgerecht_zurueck(
    monkeypatch,
):
    """AC-5 an der Wirkstelle: der Leader haengt 4 s, die Wartefrist ist auf
    0.3 s verkuerzt. Der Wartende holt selbst ab (zweiter Provider-Call), liefert
    ein Ergebnis und kehrt lange vor dem Leader zurueck."""
    import services.segment_weather as sw

    monkeypatch.setattr(sw, "SEGMENT_FLIGHT_WAIT_TIMEOUT_S", 0.3)
    provider = _ErsterHaengtProvider(haengt_s=4.0)
    cache = WeatherCacheService()
    segment = _segment("frist")
    ergebnisse: dict = {}
    fehler: list = []

    t_leader = _starte("leader", lambda: _dienst(provider, cache).fetch_segment_weather(
        segment, user_id=NUTZER_A), ergebnisse, fehler)
    assert provider.erster_drin.wait(timeout=20)
    beginn = time.monotonic()
    t_wart = _starte("wartender", lambda: _dienst(provider, cache).fetch_segment_weather(
        segment, user_id=NUTZER_B), ergebnisse, fehler)
    t_wart.join(timeout=3.0)
    dauer = time.monotonic() - beginn
    wartender_fertig = not t_wart.is_alive()
    t_leader.join(timeout=JOIN_FRIST_S)
    t_wart.join(timeout=JOIN_FRIST_S)

    assert wartender_fertig and dauer < 3.0, "Wartender kehrte nicht fristgerecht zurueck"
    assert not fehler, f"Thread-Ausnahmen: {fehler!r}"
    assert not ergebnisse["wartender"].has_error
    assert ergebnisse["wartender"].timeseries is not None
    assert provider.call_count == 2


# --- AC-17 -----------------------------------------------------------------

@pytest.mark.timeout(60)
def test_ac17_leader_provider_fehler_alle_wartenden_derselbe_fehler_ein_fetch():
    """AC-17: der Leader wirft `ProviderRequestError` => alle Wartenden
    erhalten denselben Fehler, und es laeuft KEIN zweiter Abruf-Retry-Zyklus
    (`fetch_forecast` genau 1x)."""
    n = 5
    provider = ZaehlenderProvider(fehler=True)
    cache = WeatherCacheService()
    dienst = _dienst(provider, cache)
    segment = _segment("fehler")

    ergebnisse, fehler = _parallel([
        (lambda: dienst.fetch_segment_weather(segment, user_id=NUTZER_A)) for _ in range(n)
    ])

    _keine_thread_fehler(fehler)
    assert all(e is not None and e.has_error for e in ergebnisse)
    meldungen = {e.error_message for e in ergebnisse}
    assert len(meldungen) == 1 and "503" in next(iter(meldungen))
    assert provider.call_count == 1, (
        f"{provider.call_count} fetch_forecast statt 1 nach Leader-Fehler"
    )


# --- AC-18 -----------------------------------------------------------------

def _folge_a():
    """N gleiche Segmente (ein Nutzer)."""
    return [(NUTZER_A, _segment(f"a{i}")) for i in range(6)], 1


def _folge_b():
    """N paarweise verschiedene Segmente (verschiedene Orte)."""
    return [(NUTZER_A, _segment(f"b{i}", lat=47.0 + 0.1 * i)) for i in range(6)], 6


def _folge_c():
    """Mischung aus gleichen und verschiedenen Segmenten, zwei Nutzer:
    drei verschiedene Orte (X, Y, Z), X und Y mehrfach."""
    x, y, z = (47.00, 11.0), (47.50, 11.5), (48.00, 12.0)
    return [
        (NUTZER_A, _segment("c0", *x)),
        (NUTZER_B, _segment("c1", *x)),
        (NUTZER_A, _segment("c2", *y)),
        (NUTZER_B, _segment("c3", *y)),
        (NUTZER_A, _segment("c4", *x)),
        (NUTZER_B, _segment("c5", *z)),
    ], 3


def _lauf(folge, parallel: bool) -> int:
    """Faehrt die Folge einmal seriell oder parallel mit frischem Provider und
    frischem Cache und liefert die Zahl echter Upstream-Calls."""
    provider = ZaehlenderProvider(dauer_s=0.4 if parallel else 0.0)
    cache = WeatherCacheService()
    if parallel:
        ergebnisse, fehler = _parallel([
            (lambda u=u, s=s: _dienst(provider, cache).fetch_segment_weather(s, user_id=u))
            for u, s in folge
        ])
        _keine_thread_fehler(fehler)
    else:
        ergebnisse = [
            _dienst(provider, cache).fetch_segment_weather(s, user_id=u) for u, s in folge
        ]
    assert all(e is not None and not e.has_error for e in ergebnisse)
    return provider.call_count


@pytest.mark.timeout(60)
@pytest.mark.parametrize(
    "folge_fn",
    [_folge_a, _folge_b, _folge_c],
    ids=["a_gleiche", "b_verschiedene", "c_mischung_zwei_nutzer"],
)
def test_ac18_parallel_nie_mehr_upstream_calls_als_seriell(folge_fn):
    """AC-18: je Abruffolge einmal seriell, einmal parallel (Barrier). Die Zahl
    echter Upstream-Calls parallel ist <= seriell. Folge (a) ist heute
    ehrlich rot (seriell 1, parallel N)."""
    folge, erwartet_eindeutig = folge_fn()
    seriell = _lauf(folge, parallel=False)
    assert seriell == erwartet_eindeutig, "Referenz: ein Call je Bucket+Fenster"
    parallel = _lauf(folge, parallel=True)
    assert parallel <= seriell, f"parallel {parallel} > seriell {seriell}"


@pytest.mark.timeout(60)
def test_ac18_budget_erschoepft_user_briefing_erreicht_trotzdem_den_provider():
    """AC-18 (zweiter Teil, WAECHTER heute gruen): Budgetdatei auf `calls ==
    DAILY_BUDGET`. Ein `user_briefing`-Abruf wird nie gedrosselt, erreicht den
    Provider und wird gebucht; ein `polling`-Abruf an anderer Stelle wird
    dagegen abgewiesen (beweist, dass das Budget wirklich voll ist)."""
    voll = ForecastBudgetGate.DAILY_BUDGET
    _setze_budget(calls=voll, active_users=[NUTZER_A])
    provider = ZaehlenderProvider(dauer_s=0.0)
    cache = WeatherCacheService()
    dienst = _dienst(provider, cache)

    gedrosselt = dienst.fetch_segment_weather(
        _segment("polling-x", lat=46.0), priority="polling", user_id=NUTZER_A
    )
    assert gedrosselt.has_error and gedrosselt.error_message == "budget_throttled"
    assert provider.call_count == 0

    ergebnis = dienst.fetch_segment_weather(
        _segment("briefing-y", lat=45.0), priority="user_briefing", user_id=NUTZER_A
    )
    assert not ergebnis.has_error and ergebnis.timeseries is not None
    assert provider.call_count == 1
    assert _stand(None)["calls_today"] == voll + 1
    assert _stand(NUTZER_A)["user_calls_today"] == 1
