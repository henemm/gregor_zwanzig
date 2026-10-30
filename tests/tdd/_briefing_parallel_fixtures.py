"""Gemeinsamer Aufbau der S5-Tests (Issue #1539, Briefing-Abrufe parallel).

SPEC: docs/specs/modules/feat_1539_s5_briefing_parallel.md

Kein Test-Modul (fuehrender Unterstrich). Geteilt von
``test_briefing_parallel_warnungen.py``, ``test_briefing_parallel_trend.py``,
``test_briefing_parallel_fehler.py`` und ``test_briefing_parallel_mandanten.py``.

Grundsaetze (Projekt-Testpolitik, kein Mock-Theater):

* **Wetter-Rand:** ``EtappenRand`` ersetzt den Open-Meteo-Provider
  (``providers.base.get_provider``). Er delegiert an den offline
  ``FixtureProvider`` (echte Fixture-Daten) und erfasst Thread, Zeitpunkte,
  Gleichzeitigkeit JE ETAPPE, Verzoegerung und gezielte Fehler. Die Etappe
  eines Abrufs ergibt sich aus dem DATUM des Abruf-Fensters (``start.date()``),
  nicht aus der Aufrufreihenfolge (die aendert sich mit der Parallelisierung)
  und nicht aus dem Segment-Namen ("Segment 1" gibt es in jeder Etappe).
  ``_enrich_ensemble_for_trip`` kehrt mit diesem Provider frueh zurueck (kein
  ``OpenMeteoProvider``) -- es laeuft trotzdem echt durch den Pruefling.
* **Warn-Rand:** ``Warnquelle`` ist eine echte amtliche Quelle in der ECHTEN
  Registry (``services.official_alerts.base._REGISTERED_SOURCES``) und erfasst
  dort Koordinate, Thread, Verzoegerung, Fehler.
* **Warum Gleichzeitigkeit JE ETAPPE:** ``_fetch_weather`` ruft die Segmente
  EINER Etappe schon heute ueber ``fetch_ordered`` in Worker-Threads ab
  (#2439). "lief im Worker" und "zwei Abrufe gleichzeitig" sind fuer Trend und
  Gewitter-Fallback daher KEIN Nachweis -- erst Abrufe VERSCHIEDENER Etappen,
  die sich ueberlappen, belegen S5.

Vertrag fuer GREEN (wie S3/S4): die Frist ist
``services.trip_report_scheduler.FETCH_WEATHER_DEADLINE_SECONDS`` und wird zur
LAUFZEIT ueber das Modul gelesen (nicht als Default-Argument oder Kopie
gebunden); die Tests verkuerzen sie per ``monkeypatch``.

Pfadregel #1409: der Pruefling wird relativ zu DIESER Datei aufgeloest.
"""
from __future__ import annotations

import os
import threading
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional

import pytest

WORKTREE = Path(__file__).resolve().parents[2]
ZEITSCHRANKE = 20.0  # Sekunden: harte Obergrenze gegen haengende Tests

# Echte Uhr, vor jedem Patch gefasst.
_ECHT = (lambda f: (lambda: f()))(time.monotonic)


def pruefling_aus_worktree() -> None:
    """Der Pruefling muss aus DIESEM Worktree kommen (nicht aus einem
    anderen Checkout im Pfad)."""
    import services.trip_report_scheduler as trs

    pfad = Path(trs.__file__).resolve()
    assert pfad.is_relative_to(WORKTREE), (
        f"Pruefling {pfad} liegt nicht im Worktree {WORKTREE}")


def neue_kennung(tag: str) -> str:
    return f"tdd-1539s5-{tag}-{uuid.uuid4().hex[:6]}"


_breiten_zaehler = [0]


def neue_breite() -> float:
    """Eindeutige Breite je Etappe/Ort: kein Treffer im geteilten Wetter-Cache
    zwischen Tests und Etappen. Abstand 0,05 Grad > Rundung (3 Stellen)."""
    _breiten_zaehler[0] += 1
    return round(46.30 + 0.05 * _breiten_zaehler[0], 4)


# --------------------------------------------------------------------------- #
# Aufraeumen: verwaiste Worker, Baustein, Cache
# --------------------------------------------------------------------------- #
def warte_auf_worker(timeout_s: float = 30.0) -> None:
    """Nach einer Frist laufen verworfene Abrufe im Worker weiter (zulaessig,
    Spec "Known Limitations"). Vor dem naechsten Test abwarten."""
    from services import parallel_fetch

    if parallel_fetch._executor is not None:
        parallel_fetch._executor.shutdown(wait=True)
    ende = _ECHT() + timeout_s
    for faden in threading.enumerate():
        if faden.name.startswith("parallel-fetch"):
            faden.join(timeout=max(ende - _ECHT(), 0.0))
    parallel_fetch._reset_for_tests()


@pytest.fixture
def umgebung():
    """Baustein und geteilten Wetter-Cache je Test frisch aufsetzen."""
    from services import parallel_fetch
    from services.weather_cache import reset_shared_weather_cache_for_tests

    parallel_fetch._reset_for_tests()
    reset_shared_weather_cache_for_tests()
    yield
    warte_auf_worker()
    reset_shared_weather_cache_for_tests()


@pytest.fixture
def thread_fehler():
    """Sammelt unbehandelte Thread-Ausnahmen ein (pytest meldet sie sonst nur
    als Warnung) und prueft sie am Ende."""
    gesammelt: list = []
    alt = threading.excepthook
    threading.excepthook = lambda args: gesammelt.append(args)
    yield gesammelt
    threading.excepthook = alt
    assert not gesammelt, f"unbehandelte Thread-Ausnahmen: {gesammelt!r}"


def slots_setzen(monkeypatch, provider: str, anzahl: int) -> None:
    """Slotzahl eines Provider-Schluessels setzen (ADR-0103-Stellschraube)
    und den Baustein neu aufsetzen."""
    from services import parallel_fetch

    monkeypatch.setenv(f"GZ_PARALLEL_FETCH_SLOTS_{provider.upper()}", str(anzahl))
    parallel_fetch._reset_for_tests()


def frist_setzen(monkeypatch, sekunden: float) -> None:
    """Die EINE Frist-Konstante des Schedulers verkuerzen (kein neuer Wert)."""
    import services.trip_report_scheduler as trs

    assert hasattr(trs, "FETCH_WEATHER_DEADLINE_SECONDS")
    monkeypatch.setattr(trs, "FETCH_WEATHER_DEADLINE_SECONDS", sekunden)


# --------------------------------------------------------------------------- #
# Treffpunkt: gibt erst frei, wenn mindestens zwei Abrufe gleichzeitig laufen
# --------------------------------------------------------------------------- #
class Treffpunkt:
    """Einweg-Riegel: ``eintreten(schluessel)`` meldet einen laufenden Abruf
    an; sobald Abrufe von mindestens ZWEI verschiedenen Schluesseln
    (Etappen/Koordinaten) gleichzeitig laufen, oeffnet der Riegel fuer immer.
    ``warten()`` wartet hoechstens ``timeout`` und liefert, ob er offen ist --
    ein serieller Ablauf erreicht das nie (jeder Abruf wartet vergeblich).
    Bewusst kein ``threading.Barrier``: dessen Bruch wuerde als Provider-
    Ausnahme in den Pruefling durchschlagen."""

    def __init__(self, timeout: float = 1.0) -> None:
        self.timeout = timeout
        self._lock = threading.Lock()
        self._aktiv: dict = {}
        self._offen = threading.Event()
        self.ergebnisse: list[bool] = []

    def eintreten(self, schluessel) -> None:
        with self._lock:
            self._aktiv[schluessel] = self._aktiv.get(schluessel, 0) + 1
            if sum(1 for v in self._aktiv.values() if v > 0) >= 2:
                self._offen.set()

    def austreten(self, schluessel) -> None:
        with self._lock:
            self._aktiv[schluessel] -= 1

    def warten(self) -> None:
        ok = self._offen.wait(self.timeout)
        with self._lock:
            self.ergebnisse.append(ok)


# --------------------------------------------------------------------------- #
# Wetter-Rand
# --------------------------------------------------------------------------- #
class EtappenRand:
    """Open-Meteo-Rand fuer Trend/Fallback-Tests (siehe Moduldoc).

    ``etappen_tage``: Etappen-Datum je Index (Zuordnung ueber ``start.date()``).
    ``verzoegerung(idx, label)`` -> Sekunden; ``fehler``: Etappen-Indizes,
    deren Abrufe werfen; ``leer``: Etappen-Indizes mit leerer Zeitreihe;
    ``treffpunkt``: optional, nur fuer Abrufe mit ``label == "1"``.
    ``bei_abruf(idx, label)``: optional, laeuft am Rand vor der Verzoegerung
    (z. B. ``user_id``-Erfassung durch den Aufrufer)."""

    name = "openmeteo"

    def __init__(self, etappen_tage: list, *, verzoegerung: Optional[Callable] = None,
                 fehler=(), leer=(), treffpunkt: Optional[Treffpunkt] = None) -> None:
        from providers.fixture import FixtureProvider

        self._inner = FixtureProvider(os.environ["GZ_TEST_FIXTURE_DIR"])
        self._tage = list(etappen_tage)
        self._verzoegerung = verzoegerung or (lambda idx, label: 0.0)
        self._fehler = set(fehler)
        self._leer = set(leer)
        self.treffpunkt = treffpunkt
        self._lock = threading.Lock()
        self._aktiv_je_etappe: dict[int, int] = {}
        self.max_etappen_gleichzeitig = 0
        self.aufrufe: list[dict] = []

    def __getattr__(self, item):  # alles andere wie der echte Provider
        return getattr(self._inner, item)

    def _etappe(self, start) -> int:
        tag = start.date() if isinstance(start, datetime) else start
        assert tag in self._tage, (
            f"Testaufbau: Abruf fuer {tag} passt zu keiner Etappe {self._tage}")
        return self._tage.index(tag)

    def fetch_forecast(self, location, start=None, end=None,
                       enrich_ensemble=True, enrich_snow=True):
        idx = self._etappe(start)
        label = location.name.rsplit(" ", 1)[-1]
        eintrag = {
            "etappe": idx, "label": label, "lat": location.latitude,
            "thread": threading.get_ident(),
            "thread_name": threading.current_thread().name, "t0": _ECHT(),
        }
        with self._lock:
            self.aufrufe.append(eintrag)
            self._aktiv_je_etappe[idx] = self._aktiv_je_etappe.get(idx, 0) + 1
            self.max_etappen_gleichzeitig = max(
                self.max_etappen_gleichzeitig,
                sum(1 for v in self._aktiv_je_etappe.values() if v > 0))
        mit_treffpunkt = self.treffpunkt is not None and label == "1"
        if mit_treffpunkt:
            self.treffpunkt.eintreten(idx)
        try:
            if mit_treffpunkt:
                self.treffpunkt.warten()
            pause = self._verzoegerung(idx, label)
            if pause:
                time.sleep(pause)
            if idx in self._fehler:
                raise RuntimeError(f"boom-etappe-{idx}")
            ts = self._inner.fetch_forecast(location, start, end, enrich_ensemble, enrich_snow)
            if idx in self._leer:
                import dataclasses

                ts = dataclasses.replace(ts, data=[])
            return ts
        finally:
            if mit_treffpunkt:
                self.treffpunkt.austreten(idx)
            with self._lock:
                self._aktiv_je_etappe[idx] -= 1
                eintrag["t1"] = _ECHT()

    def etappen_mit_abruf(self) -> list[int]:
        return sorted({a["etappe"] for a in self.aufrufe})


@pytest.fixture
def rand(monkeypatch, umgebung):
    """Fabrik ``installiere(etappen_tage, **kw) -> EtappenRand``."""
    installiert: list[EtappenRand] = []

    def installiere(etappen_tage, **kwargs) -> EtappenRand:
        prov = EtappenRand(etappen_tage, **kwargs)
        installiert.append(prov)
        monkeypatch.setattr("providers.base.get_provider", lambda name, _p=prov: prov)
        return prov
    yield installiere


def assert_etappen_ueberlappen(prov: EtappenRand) -> None:
    """Abrufe VERSCHIEDENER Etappen liefen gleichzeitig (S5-Nachweis)."""
    assert prov.aufrufe, "Setup: es gab keinen einzigen Wetter-Abruf am Rand"
    assert prov.max_etappen_gleichzeitig >= 2, (
        f"Es lief nie mehr als {prov.max_etappen_gleichzeitig} Etappe gleichzeitig -- "
        "die Etappen-Abrufe laufen noch nacheinander (erwartet: fetch_ordered ueber "
        "die Etappen, Provider open_meteo).")


# --------------------------------------------------------------------------- #
# Trips
# --------------------------------------------------------------------------- #
def heute_utc() -> date:
    # FixtureProvider verankert seine 72 h am UTC-Tag (#2314 D2).
    from tests.helpers.ortstag import utc_tag

    return utc_tag()


def trend_trip(anzahl: int = 3, *, trip_id: Optional[str] = None):
    """Trip mit ``anzahl`` Etappen (heute, +1, +2 UTC-Tag), je zwei Wegpunkte
    an EIGENER Breite (zwei Segmente: "1" und "Ziel"). Zieltag fuer
    "kuenftig" ist gestern."""
    from app.trip import Stage, Trip, Waypoint

    heute = heute_utc()
    stages = []
    for i in range(anzahl):
        lat = neue_breite()
        stages.append(Stage(
            id=f"S{i + 1}", name=f"Etappe {i + 1}", date=heute + timedelta(days=i),
            waypoints=[
                Waypoint(id=f"A{i}", name="Start", lat=lat, lon=11.40, elevation_m=1000.0,
                         arrival_calculated="08:00"),
                Waypoint(id=f"B{i}", name="Ziel", lat=lat + 0.01, lon=11.41,
                         elevation_m=1300.0, arrival_calculated="12:00"),
            ],
        ))
    return Trip(id=trip_id or f"trend-{uuid.uuid4().hex[:6]}", name="S5-Trend", stages=stages)


def zieltag_gestern() -> date:
    return heute_utc() - timedelta(days=1)


def etappen_tage(trip) -> list:
    return [s.date for s in trip.stages]


def settings_ohne_transport():
    from app.config import Settings

    return Settings(**{
        "smtp_host": "", "smtp_user": "", "smtp_pass": "", "mail_to": "",
        "telegram_bot_token": "", "telegram_chat_id": "",
        "telegram_test_bot_token": "", "telegram_test_chat_id": "",
        "sms_gateway_url": "", "seven_api_key": "", "sms_to": "",
    })


def trend_lauf(dienst, trip):
    return dienst._build_stage_trend(
        trip, zieltag_gestern(), now_utc=datetime.now(timezone.utc))


def fallback_lauf(dienst, trip):
    return dienst._collect_future_stage_weather(
        trip, zieltag_gestern(), now_utc=datetime.now(timezone.utc))


def zeilen_kern(rows) -> list:
    return [(r["date"], r["name"]) for r in (rows or [])]


# --------------------------------------------------------------------------- #
# Warn-Rand
# --------------------------------------------------------------------------- #
QUELLE = "s5-warnquelle"


def koord(lat: float, lon: float) -> tuple:
    return (round(lat, 3), round(lon, 3))


class Warnquelle:
    """Echte amtliche Quelle am Rand (Protocol-Subtyping, kein Mock).

    Liefert je Koordinate GENAU EINE Warnung mit der Koordinate im Label --
    so ist pruefbar, ob eine Warnung am richtigen Segment steht.
    ``verzoegerung``: {koord: s}; ``fehler``: Koordinaten, deren Abruf wirft;
    ``treffpunkt``: optional."""

    def __init__(self, *, tag: date, verzoegerung: Optional[dict] = None,
                 fehler=(), treffpunkt: Optional[Treffpunkt] = None) -> None:
        self.name = QUELLE
        self._tag = tag
        self._verzoegerung = dict(verzoegerung or {})
        self._fehler = set(fehler)
        self.treffpunkt = treffpunkt
        self._lock = threading.Lock()
        self._aktiv = 0
        self.max_gleichzeitig = 0
        self.aufrufe: list[dict] = []

    def covers(self, lat: float, lon: float) -> bool:
        return True

    def fetch(self, lat: float, lon: float) -> list:
        k = koord(lat, lon)
        eintrag = {"koord": k, "thread": threading.get_ident(),
                   "thread_name": threading.current_thread().name, "t0": _ECHT()}
        with self._lock:
            self.aufrufe.append(eintrag)
            self._aktiv += 1
            self.max_gleichzeitig = max(self.max_gleichzeitig, self._aktiv)
        if self.treffpunkt is not None:
            self.treffpunkt.eintreten(k)
        try:
            if self.treffpunkt is not None:
                self.treffpunkt.warten()
            pause = self._verzoegerung.get(k, 0.0)
            if pause:
                time.sleep(pause)
            if k in self._fehler:
                raise RuntimeError(f"Quelle: HTTP 503 fuer {k} (Test-Ausfall)")
            return [warnung_fuer(k, self._tag)]
        finally:
            if self.treffpunkt is not None:
                self.treffpunkt.austreten(k)
            with self._lock:
                self._aktiv -= 1
                eintrag["t1"] = _ECHT()

    def koordinaten(self) -> list:
        return [a["koord"] for a in self.aufrufe]


def warn_label(k: tuple) -> str:
    return f"Hitzewarnung {k[0]:.3f}/{k[1]:.3f}"


def warnung_fuer(k: tuple, tag: date):
    from services.official_alerts.models import OfficialAlert

    von = datetime(tag.year, tag.month, tag.day, tzinfo=timezone.utc) - timedelta(days=1)
    return OfficialAlert(
        source=QUELLE, hazard="extreme_heat", level=2, label=warn_label(k),
        region_label=f"Region {k[0]:.3f}", valid_from=von, valid_to=von + timedelta(days=3),
    )


@pytest.fixture
def warnquellen():
    """Registry leeren, nur die Test-Quelle registrieren, danach Bestand zurueck."""
    import services.official_alerts.base as base
    from services.official_alerts import register_official_alert_source

    sicherung = list(base._REGISTERED_SOURCES)

    def registriere(quelle: Warnquelle) -> Warnquelle:
        base._REGISTERED_SOURCES.clear()
        register_official_alert_source(quelle)
        return quelle
    try:
        yield registriere
    finally:
        base._REGISTERED_SOURCES.clear()
        base._REGISTERED_SOURCES.extend(sicherung)


def assert_warnabrufe_in_workern(quelle: Warnquelle) -> None:
    """Vorbedingung: die Warn-Abrufe liefen in Baustein-Workern, nicht im
    Briefing-Faden (sonst bewacht der Test die Parallelisierung nicht)."""
    assert quelle.aufrufe, "Setup: die Warnquelle wurde nie abgefragt"
    fremd = [a["thread_name"] for a in quelle.aufrufe
             if not a["thread_name"].startswith("parallel-fetch")]
    assert not fremd, (
        f"Warn-Abrufe liefen nicht in Baustein-Workern, sondern in {fremd!r} -- "
        "erwartet: fetch_ordered(..., provider='official_alerts').")


# --------------------------------------------------------------------------- #
# Briefing-Lauf fuer den Warnungsblock
# --------------------------------------------------------------------------- #
WARN_FELDER = ("official_alerts", "official_alerts_unavailable")


def _bewachtes_wetter_klasse():
    from app.models import SegmentWeatherData

    class BewachtesWetter(SegmentWeatherData):
        """Echtes ``SegmentWeatherData``; erfasst nur, WELCHER Thread die
        Warn-Felder schreibt (AC-9)."""

        def __setattr__(self, name, value):
            if name in WARN_FELDER:
                self.__dict__.setdefault("_schreiber", []).append(
                    (name, threading.get_ident(), threading.current_thread().name))
            super().__setattr__(name, value)

    return BewachtesWetter


def wetter_fuer(segment, *, fehler: bool = False):
    """Fixture-Wetter fuer ein ECHTES Etappensegment (Muster #1614/#1656)."""
    from app.models import ForecastMeta, NormalizedTimeseries, Provider, SegmentWeatherSummary

    klasse = _bewachtes_wetter_klasse()
    if fehler:
        return klasse(
            segment=segment, timeseries=None, aggregated=SegmentWeatherSummary(),
            fetched_at=datetime.now(timezone.utc), provider="unknown",
            has_error=True, error_message="Test: Segment ohne Wetter",
        )
    return klasse(
        segment=segment,
        timeseries=NormalizedTimeseries(
            meta=ForecastMeta(provider=Provider.OPENMETEO, model="test", grid_res_km=1.0),
            data=[]),
        aggregated=SegmentWeatherSummary(gust_max_kmh=20.0),
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )


def briefing_scheduler_klasse():
    """Echte Unterklasse (kein Mock): Wetter aus der Fixture (Muster #1614),
    Beobachtung des Requests. Der Warnungsblock laeuft unveraendert echt."""
    from services.trip_report_scheduler import TripReportSchedulerService

    class BriefingBeobachter(TripReportSchedulerService):
        fehler_segmente: set = set()

        def _fetch_weather(self, segments, provider=None):
            daten = [wetter_fuer(s, fehler=str(s.segment_id) in self.fehler_segmente)
                     for s in segments]
            self.__dict__.setdefault("geliefert", []).append(daten)
            return daten

        def _build_trip_report_request(self, **kwargs):
            self.__dict__["im_request"] = [
                (str(sw.segment.segment_id), [a.label for a in (sw.official_alerts or [])],
                 bool(sw.official_alerts_unavailable))
                for sw in kwargs["segment_weather"]
            ]
            return super()._build_trip_report_request(**kwargs)

    return BriefingBeobachter


def warn_trip(punkte: list, *, trip_id: Optional[str] = None):
    """Trip mit EINER Etappe morgen (Ortstag) ueber die Wegpunkte ``punkte``
    [(lat, lon), ...]. Segmente: "1".."n-1" starten an punkte[0..n-2],
    "Ziel" am letzten Punkt."""
    from app.models import TripReportConfig
    from app.trip import Stage, Trip, Waypoint
    from tests.helpers.ortstag import ortstag

    tag = ortstag(*punkte[0]) + timedelta(days=1)
    wps = [
        Waypoint(id=f"G{i}", name=f"Punkt {i}", lat=lat, lon=lon, elevation_m=800.0 + 50 * i,
                 arrival_calculated=f"{7 + i:02d}:00")
        for i, (lat, lon) in enumerate(punkte)
    ]
    tid = trip_id or f"warn-{uuid.uuid4().hex[:6]}"
    trip = Trip(id=tid, name="S5-Warnungen",
                stages=[Stage(id="T1", name="Tag 1", date=tag, waypoints=wps)])
    trip.report_config = TripReportConfig(trip_id=tid, send_email=True)
    trip.alert_cooldown_minutes = 0
    return trip


def briefing_settings():
    from app.config import Settings

    return Settings(**{
        "smtp_host": "dummy.invalid", "smtp_user": "dummy", "smtp_pass": "dummy",
        "mail_to": "dummy@example.com",
        "telegram_bot_token": "", "telegram_chat_id": "",
        "telegram_test_bot_token": "", "telegram_test_chat_id": "",
        "sms_gateway_url": "", "seven_api_key": "", "sms_to": "",
    })


@pytest.fixture
def briefing_rand(monkeypatch, umgebung):
    """Transport-Rand (``EmailOutput.send`` ohne Netz) und Beobachtung des
    Entwarnungs-Eingangs ``settle_official_alerts_after_briefing`` (echte
    Funktion, delegierend). Liefert ein Dict mit ``mails`` und ``settle``
    (Liste von (user_id, queries))."""
    import services.alert_briefing_anchor as anchor
    from output.channels.email import EmailOutput

    mitschrift: dict = {"mails": [], "settle": []}

    def _senden(self, *, subject, body, **kwargs):
        mitschrift["mails"].append(subject)

    monkeypatch.setattr(EmailOutput, "send", _senden)
    echt = anchor.settle_official_alerts_after_briefing

    def _settle(*, user_id, entity_id, queries, **kw):
        mitschrift["settle"].append((user_id, list(queries)))
        return echt(user_id=user_id, entity_id=entity_id, queries=queries, **kw)

    monkeypatch.setattr(anchor, "settle_official_alerts_after_briefing", _settle)
    return mitschrift


def briefing_lauf(trip, user_id: str, *, fehler_segmente=()):
    """Echtes Abend-Briefing (Zieltag = Etappentag) ueber
    ``_send_trip_report_outcome``. Liefert (Dienst, Outcome)."""
    klasse = briefing_scheduler_klasse()
    dienst = klasse(settings=briefing_settings(), user_id=user_id)
    dienst.fehler_segmente = {str(s) for s in fehler_segmente}
    outcome = dienst._send_trip_report_outcome(
        trip, "evening", on_demand=False, target_date=trip.stages[0].date)
    return dienst, outcome


def segment_wetter(dienst) -> list:
    """Die vom Briefing benutzten Segmentdaten (erster ``_fetch_weather``-Aufruf)."""
    assert dienst.__dict__.get("geliefert"), "Setup: _fetch_weather wurde nie gerufen"
    return dienst.__dict__["geliefert"][0]


def query_reihenfolge(queries) -> list:
    return [tuple(q.scope_ids) for q in queries]
