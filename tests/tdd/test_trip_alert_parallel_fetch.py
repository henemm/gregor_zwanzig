"""TDD RED -- Feature #1539 (S3): Trip-Alarm ruft die Etappen parallel ab.

SPEC: docs/specs/modules/feat_1539_s3_trip_alarm_parallel.md (AC-1 .. AC-12)

``TripAlertService._fetch_fresh_weather`` ruft die faelligen Etappen heute strikt
nacheinander ab. S3 stellt das auf den Baustein ``parallel_fetch.fetch_ordered``
um, ohne Reihenfolge, Teilausfall-Semantik, Herkunftsbuchung, Mandantentrennung
und Zahl der Upstream-Calls zu veraendern.

Aufbau (Kern-Schicht, kein Netz): echter ``TripAlertService`` + echter
``SegmentWeatherService`` + echtes Diagnose-Journal + echte Budget-Gates. Nur der
PROVIDER-RAND ist ein Test-Provider (``_RandProvider``): er delegiert an den
offline ``FixtureProvider`` (Fixture-Daten), bucht wie der echte Provider jeden
Upstream-Call ins Journal (``log_api_call``) und erfasst Thread, Gleichzeitigkeit,
Verzoegerung und gezielte Fehler. Zaehler/Verzoegerungen sitzen dort -- NICHT in
``_fetch_fresh_weather``.

Warum die Vorbedingung "lief im Worker-Thread" (``_assert_in_workern``): ohne sie
waere ein Teil der ACs schon im heutigen seriellen Ablauf gruen und bewachte die
Parallelisierung nicht (Reihenfolge, Journal-Herkunft, Nutzer-Trennung).

Vertrag fuer GREEN: die Tests lesen die an den Baustein uebergebene Frist ueber
einen Spion auf ``services.parallel_fetch.fetch_ordered`` (und, falls das Modul
den Namen direkt importiert, ``services.trip_alert.fetch_ordered``). Die
Implementierung muss den Baustein daher ueber das Modul bzw. per Import
innerhalb der Funktion aufrufen, nicht ueber eine vorab gebundene Kopie in
einem dritten Modul.

AC-5-Hinweis (Befund an die Implementierung): ``alert_preview_hours._within``
fuehrt ``_fetch_fresh_weather`` in einem Hilfsfaden aus. Dessen Stapel kennt
``render_sms_preview`` NICHT -- die stapelbasierte Erkennung liefert dort schon
heute "alarm". Der Test belegt daher, dass eine im Aufrufer-Kontext gesetzte
Herkunft "vorschau" den Hilfsfaden UND den Worker ueberlebt (ContextVar).
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from services.trip_alert import ALERT_RUN_DEADLINE_SECONDS, TripAlertService

# Wiederverwendete Aufbau-Helfer (gleiche Naht wie der Zeitgrenzen-Test #1447).
from tests.tdd.test_alert_run_deadline import (  # noqa: F401
    LAT,
    LON,
    _active_trip,
    _isolated_official_alert_sources,  # autouse Fixture (Registry leeren)
    _save_cached,
    _settings,
    _weather_data,
)

WORKTREE = Path(__file__).resolve().parents[2]
BASIS = "https://api.open-meteo.com/v1/forecast?seg="
ZEITSCHRANKE = 20.0  # Sekunden: harte Obergrenze gegen haengende Tests

_koordinaten_zaehler = [0]


def _neue_breite() -> float:
    """Eindeutige Breite je Etappe: kein Cache-Treffer zwischen Tests/Etappen."""
    _koordinaten_zaehler[0] += 1
    return 40.0 + 0.0123 * _koordinaten_zaehler[0]


# --------------------------------------------------------------------------- #
# Provider-Rand
# --------------------------------------------------------------------------- #
class _RandProvider:
    """Test-Provider am Rand: Fixture-Daten, echtes Journal, Beobachtung."""

    name = "openmeteo"

    def __init__(self, verzoegerung=None, fehler=(), standard_verzoegerung=0.0):
        from providers.fixture import FixtureProvider

        self._inner = FixtureProvider(os.environ["GZ_TEST_FIXTURE_DIR"])
        self._verzoegerung = verzoegerung or {}
        self._standard = standard_verzoegerung
        self._fehler = set(fehler)
        self._lock = threading.Lock()
        self._aktiv = 0
        self.max_gleichzeitig = 0
        self.aufrufe: list[str] = []          # Etappen-Label je Upstream-Call
        self.threads: list[int] = []          # Thread-Kennung je Upstream-Call
        self.thread_namen: list[str] = []     # Thread-Name je Upstream-Call

    def __getattr__(self, item):  # alles andere wie der echte Provider
        return getattr(self._inner, item)

    def fetch_forecast(self, location, start=None, end=None,
                       enrich_ensemble=True, enrich_snow=True):
        from providers.call_log import log_api_call

        label = location.name.rsplit(" ", 1)[-1]  # "Segment 7" -> "7"
        with self._lock:
            self._aktiv += 1
            self.max_gleichzeitig = max(self.max_gleichzeitig, self._aktiv)
            self.aufrufe.append(label)
            self.threads.append(threading.get_ident())
            self.thread_namen.append(threading.current_thread().name)
        try:
            time.sleep(self._verzoegerung.get(label, self._standard))
            if label in self._fehler:
                log_api_call(f"{BASIS}{label}", 500, error="boom")
                raise RuntimeError(f"boom-{label}")
            log_api_call(f"{BASIS}{label}", 200)
            return self._inner.fetch_forecast(
                location, start, end, enrich_ensemble, enrich_snow)
        finally:
            with self._lock:
                self._aktiv -= 1


@pytest.fixture
def rand(monkeypatch):
    """Installiert einen ``_RandProvider`` als Open-Meteo-Provider; liefert
    eine Fabrik ``installiere(**kwargs) -> _RandProvider``."""
    installiert: list[_RandProvider] = []

    def installiere(**kwargs) -> _RandProvider:
        prov = _RandProvider(**kwargs)
        installiert.append(prov)
        monkeypatch.setattr("providers.base.get_provider", lambda name, _p=prov: prov)
        return prov
    yield installiere
    # Nach einer Frist laeuft ein abgelaufener Abruf im Worker weiter (zulaessig,
    # Spec "Known Limitations"). Sein spaeter Journal-Eintrag darf nicht in den
    # naechsten Test fallen -> hier abwarten, solange noch ein Abruf aktiv ist.
    ende = time.monotonic() + 5.0
    while any(p._aktiv for p in installiert) and time.monotonic() < ende:
        time.sleep(0.02)


@pytest.fixture
def journal(tmp_path, monkeypatch):
    """Diagnose-Journal auf eine Wegwerf-Datei; Leser: Endpunkt -> Quelle."""
    from providers import call_log

    assert Path(call_log.__file__).resolve().is_relative_to(WORKTREE), call_log.__file__
    pfad = tmp_path / "openmeteo_calls.jsonl"
    monkeypatch.setattr(call_log, "DIAGNOSTICS_PATH", pfad)

    def lesen() -> dict[str, str]:
        zeilen = pfad.read_text().splitlines() if pfad.exists() else []
        return {e["endpoint"]: e["source"] for e in map(json.loads, zeilen)}
    return lesen


@pytest.fixture
def slot_eins(monkeypatch):
    """Open-Meteo auf EINEN Slot begrenzen (Frist-Tests), Baustein neu aufsetzen."""
    from services import parallel_fetch

    monkeypatch.setenv("GZ_PARALLEL_FETCH_SLOTS_OPEN_METEO", "1")
    parallel_fetch._reset_for_tests()
    yield
    parallel_fetch._reset_for_tests()


@pytest.fixture
def thread_fehler():
    """Sammelt unbehandelte Thread-Ausnahmen ein (pytest meldet sie sonst nur
    als Warnung, C4-62) und prueft sie am Ende."""
    gesammelt: list = []
    alt = threading.excepthook
    threading.excepthook = lambda args: gesammelt.append(args)
    yield gesammelt
    threading.excepthook = alt
    assert not gesammelt, f"unbehandelte Thread-Ausnahmen: {gesammelt!r}"


# --------------------------------------------------------------------------- #
# Bausteine
# --------------------------------------------------------------------------- #
def _etappen(ids, *, breiten=None):
    """Zwischengespeicherte Etappen (faellig: laufen jetzt) mit eindeutigen Orten."""
    return [
        _weather_data(i, lat=(breiten[k] if breiten else _neue_breite()), lon=LON)
        for k, i in enumerate(ids)
    ]


def _dienst(user_id=None) -> TripAlertService:
    return TripAlertService(
        settings=_settings(),
        user_id=user_id or f"tdd-1539s3-{uuid.uuid4().hex[:6]}",
        mail_sink=lambda *_: None,
    )


def _ids(wetter) -> list:
    return [w.segment.segment_id for w in wetter]


def _assert_in_workern(prov: _RandProvider, hauptfaden: int | None = None) -> None:
    """Vorbedingung: die Upstream-Calls liefen in Worker-Threads, nicht im
    Aufrufer-Thread (sonst bewacht der Test die Parallelisierung nicht)."""
    haupt = hauptfaden if hauptfaden is not None else threading.get_ident()
    assert prov.threads, "Setup: es gab keinen einzigen Upstream-Call"
    assert haupt not in prov.threads, (
        "Die Etappen werden im Aufrufer-Thread seriell abgerufen -- erwartet "
        "wird der Abruf ueber fetch_ordered in Worker-Threads."
    )
    # Die Threads des Bausteins heissen "parallel-fetch_*" (ThreadPoolExecutor);
    # Hilfsfaeden der Vorschau/Test-Threads zaehlen NICHT als Worker.
    fremd = [n for n in prov.thread_namen if not n.startswith("parallel-fetch")]
    assert not fremd, f"Abrufe liefen nicht in Baustein-Workern: {fremd!r}"


def _assert_gleichzeitig(prov: _RandProvider) -> None:
    assert prov.max_gleichzeitig >= 2, (
        f"Es lief nie mehr als {prov.max_gleichzeitig} Abruf gleichzeitig -- "
        "die Etappen werden seriell abgerufen."
    )


class _FristSpion:
    """Zeichnet die an ``fetch_ordered`` uebergebene Frist auf und delegiert."""

    def __init__(self, monkeypatch, *, vorher=None, abbruch: type | None = None):
        from services import parallel_fetch

        self.fristen: list[float] = []
        self.aufrufzeit: list[float] = []
        self.dienst_feld: list = []
        self._original = parallel_fetch.fetch_ordered
        self._vorher = vorher
        self._abbruch = abbruch

        def spion(items, fn, *, provider, deadline_at, **kw):
            self.fristen.append(deadline_at)
            self.aufrufzeit.append(time.monotonic())
            if self._vorher:
                self._vorher()
            if self._abbruch:
                raise self._abbruch("Abbruch im Lauf")
            return self._original(
                items, fn, provider=provider, deadline_at=deadline_at, **kw)

        monkeypatch.setattr(parallel_fetch, "fetch_ordered", spion)
        monkeypatch.setattr(
            "services.trip_alert.fetch_ordered", spion, raising=False)


# --------------------------------------------------------------------------- #
# AC-1 Reihenfolge
# --------------------------------------------------------------------------- #
def test_ac1_ergebnis_folgt_der_eingabereihenfolge_nicht_der_fertigstellung(rand):
    """AC-1: Fuenf faellige Etappen, deren Abrufe in UMGEKEHRTER Reihenfolge
    fertig werden (Etappe 1 am langsamsten) -> die Liste bleibt 1..5."""
    prov = rand(verzoegerung={"1": 0.40, "2": 0.32, "3": 0.24, "4": 0.16, "5": 0.08})
    dienst = _dienst()
    wetter = dienst._fetch_fresh_weather(_etappen([1, 2, 3, 4, 5]))
    assert _ids(wetter) == [1, 2, 3, 4, 5]
    _assert_gleichzeitig(prov)
    _assert_in_workern(prov)


# --------------------------------------------------------------------------- #
# AC-2 Teilausfall
# --------------------------------------------------------------------------- #
def test_ac2_ausfall_einer_etappe_laesst_die_uebrigen_durch(rand, caplog):
    """AC-2: Etappe 2 scheitert -> 1, 3, 4 kommen, 2 fehlt, Stand (4, 1),
    Fehler mit Etappe im Log."""
    prov = rand(fehler={"2"}, standard_verzoegerung=0.15)
    dienst = _dienst()
    with caplog.at_level(logging.INFO):
        wetter = dienst._fetch_fresh_weather(_etappen([1, 2, 3, 4]))
    assert _ids(wetter) == [1, 3, 4]
    assert dienst._fetch_stats == (4, 1)
    fehlerzeilen = [
        r.getMessage() for r in caplog.records
        if r.levelno >= logging.ERROR and re.search(r"\b2\b", r.getMessage())
    ]
    assert len(fehlerzeilen) == 1 and "boom" in fehlerzeilen[0], fehlerzeilen
    _assert_gleichzeitig(prov)


# --------------------------------------------------------------------------- #
# AC-3 Frist
# --------------------------------------------------------------------------- #
def test_ac3_fristablauf_zaehlt_uebersprungene_als_gescheitert_mit_grund(
    rand, slot_eins, caplog,
):
    """AC-3: Ein Slot, Frist 0,45 s, jeder Abruf 0,3 s -> Etappe 1 passt, die
    uebrigen werden uebersprungen. Jede fehlende Etappe: gescheitert gezaehlt,
    nicht in der Liste, genau eine Fehlerzeile mit Grund -- nichts still."""
    prov = rand(standard_verzoegerung=0.30)
    dienst = _dienst()
    dienst._run_deadline_at = time.monotonic() + 0.45
    with caplog.at_level(logging.INFO):
        wetter = dienst._fetch_fresh_weather(_etappen([1, 2, 3, 4]))
    gelungen = _ids(wetter)
    assert set(gelungen) <= {1}, f"Nach Fristablauf darf nur Etappe 1 durch sein: {gelungen}"
    fehlend = [i for i in (1, 2, 3, 4) if i not in gelungen]
    assert {3, 4} <= set(fehlend), "Etappen 3 und 4 konnten die Frist nicht erreichen"
    assert dienst._fetch_stats == (4, len(fehlend))
    for i in fehlend:
        zeilen = [
            r.getMessage() for r in caplog.records
            if r.levelno >= logging.ERROR and re.search(rf"\b{i}\b", r.getMessage())
        ]
        assert len(zeilen) == 1, f"Etappe {i}: erwartet genau eine Fehlerzeile, {zeilen!r}"
        assert re.search(r"deadline|timeout|frist|zeit", zeilen[0], re.I), (
            f"Etappe {i}: Fehlerzeile nennt keinen Grund: {zeilen[0]!r}"
        )
    _assert_in_workern(prov)


# --------------------------------------------------------------------------- #
# AC-4 / AC-5 Herkunft im Journal
# --------------------------------------------------------------------------- #
def test_ac4_alarmabrufe_in_workern_werden_als_alarm_gebucht(rand, journal):
    """AC-4: Jeder Worker-Abruf des Alarmpfads steht im Journal als "alarm",
    keiner als "unbekannt"."""
    prov = rand()
    dienst = _dienst()
    dienst._fetch_fresh_weather(_etappen([1, 2, 3, 4]))
    _assert_in_workern(prov)
    gebucht = journal()
    assert set(gebucht) == {f"{BASIS}{i}" for i in (1, 2, 3, 4)}, gebucht
    assert set(gebucht.values()) == {"alarm"}, (
        f"Herkunft je Abruf: {gebucht} -- im Worker fehlt der Marker "
        "_fetch_fresh_weather; die Quelle muss im Aufrufer-Thread aufgeloest "
        "und im Worker per override_call_source gesetzt werden."
    )


def test_ac5_vorschauabrufe_in_workern_bleiben_vorschau(rand, journal):
    """AC-5: Ueber den Hilfsfaden der Vorschau (``_within``) und die Worker
    bleibt die Herkunft "vorschau" -- NICHT "alarm" (feste Ueberschreibung
    waere falsch) und nicht "unbekannt"."""
    from providers.call_log import override_call_source
    from services.alert_preview_hours import _within

    prov = rand()
    dienst = _dienst()
    cached = _etappen([1, 2, 3])
    with override_call_source("vorschau"):
        wetter = _within(time.monotonic() + ZEITSCHRANKE, dienst._fetch_fresh_weather, cached)
    assert _ids(wetter) == [1, 2, 3]
    _assert_in_workern(prov)
    gebucht = journal()
    assert set(gebucht.values()) == {"vorschau"}, gebucht
    assert len(gebucht) == 3


# --------------------------------------------------------------------------- #
# AC-6 Frist durchreichen
# --------------------------------------------------------------------------- #
def test_ac6_gesetzte_laufgrenze_erreicht_den_baustein_unveraendert(rand, monkeypatch):
    """AC-6: ``_run_deadline_at`` gesetzt -> genau dieser Wert kommt an."""
    rand()
    spion = _FristSpion(monkeypatch)
    dienst = _dienst()
    frist = time.monotonic() + 123.0
    dienst._run_deadline_at = frist
    dienst._fetch_fresh_weather(_etappen([1, 2]))
    assert spion.fristen == [frist], (
        f"Baustein-Aufrufe mit Fristen {spion.fristen!r}, erwartet [{frist}] "
        "(fetch_ordered wurde nicht oder mit anderer Frist aufgerufen)."
    )


def test_ac6_ohne_laufgrenze_gilt_eine_endliche_frist_von_etwa_60_sekunden(rand, monkeypatch):
    """AC-6: kein Feld (Vorschau, Einzelaufruf) -> ~60 s ab Aufruf, nie unbegrenzt."""
    rand()
    spion = _FristSpion(monkeypatch)
    dienst = _dienst()
    vorher = time.monotonic()
    dienst._fetch_fresh_weather(_etappen([1, 2]))
    assert len(spion.fristen) == 1, "fetch_ordered wurde nicht genau einmal aufgerufen"
    rest = spion.fristen[0] - vorher
    assert 55.0 <= rest <= 65.0, f"Standardfrist {rest:.1f} s, erwartet etwa 60 s (endlich)"


def _lauf_mit_trip(user_id: str) -> TripAlertService:
    trip = _active_trip(f"trip-{uuid.uuid4().hex[:6]}")
    from app.loader import save_trip

    save_trip(trip, user_id=user_id)
    _save_cached(user_id, trip.id, _etappen([1, 2, 3], breiten=[LAT + 0.01 * n for n in (1, 2, 3)]))
    return _dienst(user_id)


def test_ac6_check_all_trips_setzt_die_frist_und_setzt_sie_danach_zurueck(monkeypatch):
    """AC-6: Im Lauf steht ``_run_deadline_at`` ~ Lauf-Start + 180 s und wird
    genau diese Frist an den Baustein gereicht; nach dem Lauf ist das Feld leer."""
    user_id = f"tdd-1539s3-{uuid.uuid4().hex[:6]}"
    dienst = _lauf_mit_trip(user_id)
    spion = _FristSpion(monkeypatch, vorher=lambda: spion.dienst_feld.append(
        getattr(dienst, "_run_deadline_at", None)))
    vorher = time.monotonic()
    dienst.check_all_trips()
    assert spion.fristen, "Der Alarmlauf rief fetch_ordered nie auf"
    assert spion.dienst_feld[0] is not None, "_run_deadline_at war im Lauf nicht gesetzt"
    assert spion.fristen[0] == spion.dienst_feld[0]
    assert abs(spion.fristen[0] - (vorher + ALERT_RUN_DEADLINE_SECONDS)) < 5.0
    assert getattr(dienst, "_run_deadline_at", None) is None, "Feld nach dem Lauf nicht zurueckgesetzt"


def test_ac6_laufgrenze_wird_auch_nach_einer_ausnahme_im_lauf_zurueckgesetzt(monkeypatch):
    """AC-6: Eine Ausnahme, die ``check_all_trips`` verlaesst (BaseException
    passiert die ``except Exception``-Handler der Trip-Schleife), laesst kein
    Feld stehen -- sonst erbte der naechste Aufruf (Vorschau) die Alt-Frist."""
    class Abbruch(BaseException):
        pass

    user_id = f"tdd-1539s3-{uuid.uuid4().hex[:6]}"
    dienst = _lauf_mit_trip(user_id)
    spion = _FristSpion(monkeypatch, abbruch=Abbruch, vorher=lambda: spion.dienst_feld.append(
        getattr(dienst, "_run_deadline_at", None)))
    with pytest.raises(Abbruch):
        dienst.check_all_trips()
    assert spion.dienst_feld and spion.dienst_feld[0] is not None, (
        "Vorbedingung: im Lauf war die Frist gesetzt und der Baustein wurde erreicht")
    assert getattr(dienst, "_run_deadline_at", None) is None, (
        "Nach der Ausnahme steht noch die Frist des abgebrochenen Laufs im Feld")


# --------------------------------------------------------------------------- #
# AC-7 Schreibzugriffe nur im Hauptfaden
# --------------------------------------------------------------------------- #
class _SchreibWaechter(TripAlertService):
    """Erfasst die Thread-Kennung jedes Schreibzugriffs auf ``_fetch_stats``."""

    def __setattr__(self, name, value):
        if name == "_fetch_stats":
            self.__dict__.setdefault("_schreiber", []).append(threading.get_ident())
        super().__setattr__(name, value)


def test_ac7_stand_und_ergebnis_entstehen_nur_im_hauptfaden(rand, thread_fehler):
    """AC-7: ``_fetch_stats`` wird nur vom aufrufenden Thread geschrieben; ueber
    viele Wiederholungen mit gemischtem Erfolg/Fehler stimmt der Stand immer
    mit der Zahl faelliger und gescheiterter Etappen ueberein."""
    haupt = threading.get_ident()
    for wiederholung in range(25):
        prov = rand(
            fehler={"3", "6"}, standard_verzoegerung=0.002,
            verzoegerung={"1": 0.01, "5": 0.01},
        )
        dienst = _SchreibWaechter(
            settings=_settings(), user_id=f"tdd-1539s3-{uuid.uuid4().hex[:6]}",
            mail_sink=lambda *_: None)
        wetter = dienst._fetch_fresh_weather(_etappen([1, 2, 3, 4, 5, 6]))
        assert set(dienst.__dict__["_schreiber"]) == {haupt}, (
            f"Wiederholung {wiederholung}: _fetch_stats aus fremdem Thread geschrieben")
        assert dienst._fetch_stats == (6, 2), (wiederholung, dienst._fetch_stats)
        assert _ids(wetter) == [1, 2, 4, 5], (wiederholung, _ids(wetter))
        _assert_in_workern(prov, haupt)


# --------------------------------------------------------------------------- #
# AC-8 Zwei Nutzer
# --------------------------------------------------------------------------- #
def test_ac8_zwei_nutzer_gleichzeitig_bleiben_getrennt(rand, thread_fehler):
    """AC-8: Zwei Nutzer rufen gleichzeitig ab -> jeder bucht seine Calls in den
    eigenen Budget-Topf (je 3), nichts im Topf "default", keine Etappe des einen
    im Ergebnis des anderen."""
    from services.forecast_budget import ForecastBudgetGate

    prov = rand(standard_verzoegerung=0.05)
    ua = f"tdd-1539s3-a-{uuid.uuid4().hex[:6]}"
    ub = f"tdd-1539s3-b-{uuid.uuid4().hex[:6]}"
    vorher_default = ForecastBudgetGate("default").snapshot().get("user_calls_today", 0)
    treffpunkt = threading.Barrier(2)

    def lauf(user_id, ids):
        treffpunkt.wait(timeout=ZEITSCHRANKE)
        return _ids(_dienst(user_id)._fetch_fresh_weather(_etappen(ids)))

    with ThreadPoolExecutor(max_workers=2) as pool:
        fa = pool.submit(lauf, ua, [11, 12, 13])
        fb = pool.submit(lauf, ub, [21, 22, 23])
        ergebnis_a, ergebnis_b = fa.result(timeout=ZEITSCHRANKE), fb.result(timeout=ZEITSCHRANKE)

    assert ergebnis_a == [11, 12, 13]
    assert ergebnis_b == [21, 22, 23]
    assert ForecastBudgetGate(ua).snapshot()["user_calls_today"] == 3
    assert ForecastBudgetGate(ub).snapshot()["user_calls_today"] == 3
    assert ForecastBudgetGate("default").snapshot().get("user_calls_today", 0) == vorher_default, (
        "Es wurde im Topf 'default' gebucht -- user_id ging im Worker verloren")
    _assert_in_workern(prov)


# --------------------------------------------------------------------------- #
# AC-9 Keine zusaetzlichen Upstream-Calls
# --------------------------------------------------------------------------- #
def test_ac9_parallel_ruft_nicht_oefter_upstream_ab_als_seriell(rand):
    """AC-9: Gleiche Form (zwei Etappen am SELBEN Ort, zwei weitere) einmal
    seriell (direkter Schleifenaufruf des echten Dienstes) und einmal ueber
    ``_fetch_fresh_weather``: die Upstream-Calls am Provider-Rand sind
    parallel <= seriell, und der parallele Lauf war wirklich parallel."""
    from services.segment_weather import SegmentWeatherService

    def form():
        basis = _neue_breite()
        return [basis, basis, _neue_breite(), _neue_breite()]

    seriell = rand(standard_verzoegerung=0.05)
    dienst_s = SegmentWeatherService(seriell)  # derselbe Provider-Rand wie im Betrieb
    for etappe in _etappen([1, 2, 3, 4], breiten=form()):
        dienst_s.fetch_segment_weather(
            etappe.segment, enrich_ensemble=False, enrich_snow=False,
            priority="alert_check", user_id="tdd-1539s3-seriell")
    calls_seriell = len(seriell.aufrufe)

    parallel = rand(standard_verzoegerung=0.05)
    _dienst()._fetch_fresh_weather(_etappen([1, 2, 3, 4], breiten=form()))
    assert 0 < len(parallel.aufrufe) <= calls_seriell, (
        f"parallel {len(parallel.aufrufe)} Calls, seriell {calls_seriell}")
    _assert_gleichzeitig(parallel)
    _assert_in_workern(parallel)


# --------------------------------------------------------------------------- #
# AC-10 Zeitfilter / Bestand
# --------------------------------------------------------------------------- #
def test_ac10_beendete_und_kuenftige_etappen_werden_nicht_abgerufen(rand):
    """AC-10: Eine beendete und eine erst morgen beginnende Etappe werden weder
    abgerufen noch in ``versucht`` gezaehlt; die beiden faelligen schon."""
    import dataclasses

    jetzt = datetime.now(timezone.utc)
    faellig = _etappen([2, 3])
    beendet = _etappen([1])[0]
    beendet = dataclasses.replace(beendet, segment=dataclasses.replace(
        beendet.segment, start_time=jetzt - timedelta(hours=6), end_time=jetzt - timedelta(hours=2)))
    morgen = _etappen([4])[0]
    morgen = dataclasses.replace(morgen, segment=dataclasses.replace(
        morgen.segment, start_time=jetzt + timedelta(hours=30), end_time=jetzt + timedelta(hours=34)))

    prov = rand(standard_verzoegerung=0.05)
    dienst = _dienst()
    wetter = dienst._fetch_fresh_weather([beendet, faellig[0], faellig[1], morgen])
    assert _ids(wetter) == [2, 3]
    assert sorted(prov.aufrufe) == ["2", "3"], prov.aufrufe
    assert dienst._fetch_stats == (2, 0)
    _assert_in_workern(prov)


def test_ac10_trip_ohne_faellige_etappe_meldet_null_null(rand):
    """AC-10: Nur beendete/kuenftige Etappen -> leere Liste, (0, 0), kein Abruf."""
    import dataclasses

    jetzt = datetime.now(timezone.utc)
    beendet = _etappen([1])[0]
    beendet = dataclasses.replace(beendet, segment=dataclasses.replace(
        beendet.segment, start_time=jetzt - timedelta(hours=6), end_time=jetzt - timedelta(hours=2)))
    prov = rand()
    dienst = _dienst()
    assert dienst._fetch_fresh_weather([beendet]) == []
    assert dienst._fetch_stats == (0, 0)
    assert prov.aufrufe == []


# --------------------------------------------------------------------------- #
# AC-11 Dauerzeile je Etappe
# --------------------------------------------------------------------------- #
def _dauerzeilen(caplog, nummer: int) -> list[str]:
    return [
        r.getMessage() for r in caplog.records
        if re.search(rf"Etappe\s+{nummer}:\s*Abruf in \d+(?:\.\d+)?\s*s\b", r.getMessage())
    ]


def test_ac11_genau_eine_dauerzeile_je_etappe_auch_bei_ausfall(rand, caplog):
    """AC-11: Parallel, Etappe 2 scheitert -> fuer 1..4 je GENAU eine Zeile."""
    prov = rand(fehler={"2"}, standard_verzoegerung=0.05)
    dienst = _dienst()
    with caplog.at_level(logging.INFO):
        dienst._fetch_fresh_weather(_etappen([1, 2, 3, 4]))
    for n in (1, 2, 3, 4):
        assert len(_dauerzeilen(caplog, n)) == 1, (n, _dauerzeilen(caplog, n))
    _assert_in_workern(prov)


def test_ac11_genau_eine_dauerzeile_je_etappe_auch_bei_uebersprungenen(
    rand, slot_eins, caplog,
):
    """AC-11: Auch uebersprungene (Frist) Etappen haben genau eine Zeile."""
    prov = rand(standard_verzoegerung=0.30)
    dienst = _dienst()
    dienst._run_deadline_at = time.monotonic() + 0.45
    with caplog.at_level(logging.INFO):
        dienst._fetch_fresh_weather(_etappen([1, 2, 3, 4]))
    for n in (1, 2, 3, 4):
        assert len(_dauerzeilen(caplog, n)) == 1, (n, _dauerzeilen(caplog, n))
    _assert_in_workern(prov)


# --------------------------------------------------------------------------- #
# AC-12 ADR-0103
# --------------------------------------------------------------------------- #
def test_ac12_adr_0103_nennt_zahl_methode_stellschraube_und_pruefdatum():
    # doc-compliance-test
    """AC-12: ADR-0103 legt Slotzahl 3, Messmethode (503/429, p50/p95, Prod-Journal),
    die Stellschraube und das Pruefdatum 2027-01-26 fest; Index-Zeile vorhanden."""
    adr_dir = WORKTREE / "docs" / "adr"
    adr = adr_dir / "0103-parallele-abrufe-semaphorenzahlen.md"
    assert adr.exists(), f"{adr} fehlt"
    text = adr.read_text(encoding="utf-8")
    for pflicht in (
        "GZ_PARALLEL_FETCH_SLOTS_OPEN_METEO", "2027-01-26", "503", "429",
        "p50", "p95", "Journal",
    ):
        assert pflicht in text, f"ADR-0103 nennt '{pflicht}' nicht"
    assert re.search(r"Open-?Meteo[^\n]*\b3\b", text), "Startwert 3 fuer Open-Meteo fehlt"
    index = (adr_dir / "README.md").read_text(encoding="utf-8")
    assert "0103" in index and "parallele-abrufe-semaphorenzahlen" in index


# --------------------------------------------------------------------------- #
# Adversary F001: Budget-Prioritaet und Anreicherungs-Verzicht im Worker
# --------------------------------------------------------------------------- #
def test_worker_ruft_mit_alarm_prioritaet_ohne_anreicherung_und_mit_echter_user_id(
    rand, monkeypatch,
):
    """Die Alarm-Abrufe laufen im Worker weiter als ``alert_check`` (Budget-
    Drosselung, Bug #288: keine Ensemble-/Schnee-Anreicherung) und mit der
    user_id des Dienstes -- die Zeile wurde in den Worker verschoben."""
    from services.segment_weather import SegmentWeatherService

    rand()
    gesehen: list[dict] = []
    echt = SegmentWeatherService.fetch_segment_weather

    def aufzeichnen(self, segment, *args, **kwargs):
        gesehen.append(dict(kwargs))
        return echt(self, segment, *args, **kwargs)

    monkeypatch.setattr(SegmentWeatherService, "fetch_segment_weather", aufzeichnen)
    nutzer = f"tdd-1539s3-prio-{uuid.uuid4().hex[:6]}"
    _dienst(nutzer)._fetch_fresh_weather(_etappen([1, 2, 3]))
    assert len(gesehen) == 3
    for kw in gesehen:
        assert kw["priority"] == "alert_check"
        assert kw["enrich_ensemble"] is False and kw["enrich_snow"] is False
        assert kw["user_id"] == nutzer
