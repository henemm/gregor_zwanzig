"""TDD RED -- Feature #1539 (S4): Radar-Abrufe laufen parallel.

SPEC: docs/specs/modules/feat_1539_s4_radar_parallel.md (AC-1 .. AC-12)

Trip-Radar (Zonenpunkte ``_punkte[1:]``) und Ortsvergleich-Radar
(``_detect_triggered_locations``) rufen den Regen-Nowcast heute strikt
nacheinander ab. S4 stellt beide auf ``parallel_fetch.fetch_ordered`` um und
beseitigt dabei: geteilten Instanzzustand, nicht-atomares Budget, doppelte
Upstream-Calls je Kachel.

Aufbau (Kern-Schicht, deterministisch, kein Netz): echte Dienste
(``TripAlertService``, ``CompareRadarAlertService``, ``RadarNowcastService``),
echter Radar-Cache, echtes Budget-Gate, echtes Journal und Ausfall-Protokoll.
Nur der HTTP-RAND ist ersetzt (``httpx.Client`` -> ``_Rand``): er zaehlt Calls,
erfasst Thread, Gleichzeitigkeit und Zeitpunkte, verzoegert und scheitert
gezielt je Punkt/Ort. Zaehler und Verzoegerungen sitzen dort -- NICHT im
Pruefling. Es wird KEIN Radar-Dienst injiziert: der Pruefling baut seine
Dienst-Instanzen selbst (je Abruf eine eigene).

Warum die Vorbedingung "lief im Worker" (``_assert_in_workern``): ohne sie
waeren etliche ACs schon im heutigen seriellen Ablauf gruen (Reihenfolge,
Einzel-Call je Kachel, Thread-Kennung) und bewachten die Parallelisierung nicht.

Uhr: ``_Uhr`` ersetzt ``time.monotonic`` (auch unter ``freeze_time``, dessen
``fake_monotonic`` sonst die Zeit anhaelt) durch eine echte Uhr mit
verschiebbarem Versatz. Damit laesst sich "die Frist laeuft waehrend des
Abrufs ab" deterministisch herstellen (``uhr.sprung``), ohne auf Mikrosekunden-
Wettlaeufe zu bauen.

Pfadregel #1409: Prueflinge werden relativ zu DIESER Datei aufgeloest.
"""
from __future__ import annotations

import json
import logging
import sys
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from app.loader import get_briefings_dir, get_data_dir, load_trip  # noqa: E402
from services import alert_log, parallel_fetch, trip_alert  # noqa: E402
from services import radar_service as radar_service_mod  # noqa: E402
from services.compare_radar_alert import CompareRadarAlertService  # noqa: E402
from services.forecast_budget import ForecastBudgetGate  # noqa: E402
from services.radar_cache import reset_shared_radar_cache_for_tests  # noqa: E402
from services.radar_service import RadarDeadlineExceeded  # noqa: E402
from services.trip_alert import TripAlertService  # noqa: E402
from utils.geo import haversine_km  # noqa: E402

from tests.helpers.alarm_pruefstrecke import AlarmPruefstrecke  # noqa: E402
from tests.helpers.alert_log_fixtures import settings_email_only  # noqa: E402
from tests.helpers.arrival_window_fixtures import stage_date  # noqa: E402
from tests.tdd.test_952_onset_alert_fidelity import _clean_user  # noqa: E402
from tests.tdd.test_alarm_pruefstrecke_selbstschutz import (  # noqa: E402
    _settings_all_channels, _write_premium_profile,
)
from tests.tdd.test_regen_ausdehnung_textstellen import (  # noqa: E402
    _UHR_TIROL, _ZONEN_LAT0, _ZONEN_LAT1, _ZONEN_LON0, _ZONEN_LON1,
)

# Echte Uhr VOR jedem freeze_time gefasst (Messung der Laufdauer).
# Per Closure versteckt: freezegun tauscht Modul-Attribute, die der echten
# ``time.monotonic`` entsprechen, gegen sein Fake aus (-> Rekursion in ``_Uhr``).
_ECHT = (lambda f: (lambda: f()))(time.monotonic)
_HAUPTFADEN = threading.main_thread().ident

_UHR_GESTELLT = datetime.fromisoformat(_UHR_TIROL)  # 12:00 Ortszeit (Mallorca/Provence)

# Strecken (gleiche Geometrie wie die Tirol-Strecke des Zonen-Tests, verschoben):
# Mallorca = nur die Open-Meteo-Schlusskette (EIN Schritt je Punkt);
# Provence = AROME-HD vor Open-Meteo (ZWEI Schritte je Punkt -- die Grenze wird
# zwischen den Schritten geprueft).
_MALLORCA = (39.70, 2.80)
_PROVENCE = (43.30, 5.40)
_ORTE_MALLORCA = (39.60, 2.60)
_ORTE_PROVENCE = (43.00, 5.00)

_DELTA_LAT = _ZONEN_LAT1 - _ZONEN_LAT0
_DELTA_LON = _ZONEN_LON1 - _ZONEN_LON0


# ---------------------------------------------------------------------------
# Uhr, Umgebung
# ---------------------------------------------------------------------------

class _Uhr:
    """Echte Monotonic-Uhr mit Versatz (``sprung``)."""

    def __init__(self) -> None:
        self.versatz = 0.0
        self.__name__ = "monotonic"  # freezegun liest den Namen beim Start

    def __call__(self) -> float:
        return _ECHT() + self.versatz

    def sprung(self, sekunden: float) -> None:
        self.versatz += sekunden


@pytest.fixture
def uhr(monkeypatch):
    u = _Uhr()
    monkeypatch.setattr(time, "monotonic", u)
    # freeze_time ersetzt time.monotonic durch freezegun.api.fake_monotonic
    # (Zeit steht still) -- hier auf unsere echte Uhr umbiegen.
    monkeypatch.setattr("freezegun.api.fake_monotonic", u)
    return u


def _warte_auf_worker(timeout_s: float = 30.0) -> None:
    """Verwaiste Worker (Fristablauf, Ergebnis verworfen) laufen weiter und
    schreiben Budget-/Journal-Dateien. Vor JEDEM Abraeumen eines Nutzer- oder
    Datenordners abwarten -- auch Worker frueherer, per ``_reset_for_tests``
    ersetzter Executoren (daher ueber die Thread-Namen, nicht ``_executor``)."""
    if parallel_fetch._executor is not None:
        parallel_fetch._executor.shutdown(wait=True)
    ende = _ECHT() + timeout_s
    for faden in threading.enumerate():
        if faden.name.startswith("parallel-fetch"):
            faden.join(timeout=max(ende - _ECHT(), 0.0))
    # Alle Executoren sind beendet (aktueller oben, fruehere per
    # ``_reset_for_tests``) -- ihre Threads enden nach der letzten Aufgabe.
    haengend = [f.name for f in threading.enumerate()
                if f.name.startswith("parallel-fetch") and f.is_alive()]
    assert not haengend, f"Testaufbau: Worker laufen noch nach {timeout_s}s: {haengend}"
    parallel_fetch._reset_for_tests()  # beendeten Executor verwerfen (lazy neu)


@pytest.fixture(autouse=True)
def _umgebung(monkeypatch):
    # Der Offline-Fixture-Schalter schluege den Open-Meteo-Pfad (Budget + HTTP)
    # komplett kurz -- hier soll genau dieser Pfad laufen.
    monkeypatch.delenv("GZ_TEST_FIXTURE_DIR", raising=False)
    reset_shared_radar_cache_for_tests()
    parallel_fetch._reset_for_tests()
    yield
    _warte_auf_worker()
    reset_shared_radar_cache_for_tests()
    parallel_fetch._reset_for_tests()


def _uid(tag: str) -> str:
    return f"tdd-s4-{tag}-{uuid.uuid4().hex[:6]}"


# ---------------------------------------------------------------------------
# HTTP-Rand
# ---------------------------------------------------------------------------

class _Rand:
    """Ersatz fuer ``httpx.Client`` am Open-Meteo-Rand.

    ``soll``: Liste (lat, lon) der erwarteten Punkte/Orte; der Index einer
    Anfrage ist der naechste Soll-Punkt (Steuerung nach KOORDINATE, nicht nach
    Aufrufreihenfolge -- die aendert sich mit der Parallelisierung).
    ``verzoegerung(idx, modell)`` / ``fehler(idx, modell)`` / ``regen(idx)``
    steuern je Punkt. Anfragen MIT ``models``-Parameter (AROME-HD) liefern
    standardmaessig lauter ``None`` (ausserhalb des Gitters) -> die Kette faellt
    zum naechsten Schritt durch.
    """

    def __init__(self, soll, *, verzoegerung=None, fehler=None, regen=None,
                 bei_anfrage=None) -> None:
        self.soll = list(soll)
        self.verzoegerung = verzoegerung or (lambda idx, modell: 0.0)
        self.fehler = fehler or (lambda idx, modell: False)
        self.regen = regen or (lambda idx: False)
        self.bei_anfrage = bei_anfrage  # (idx, modell) vor der Verzoegerung
        self.calls: list[dict] = []
        self._lock = threading.Lock()
        self._aktiv = 0
        self.max_aktiv = 0

    # -- Zuordnung -----------------------------------------------------
    def index(self, lat: float, lon: float) -> int:
        abstaende = [haversine_km(lat, lon, s[0], s[1]) for s in self.soll]
        i = min(range(len(abstaende)), key=abstaende.__getitem__)
        assert abstaende[i] < 0.3, (
            f"Testaufbau: Anfrage ({lat}, {lon}) liegt {abstaende[i]:.2f} km "
            f"neben dem naechsten Soll-Punkt."
        )
        return i

    # -- Installation ---------------------------------------------------
    def installiere(self, monkeypatch) -> "_Rand":
        rand = self

        class _Antwort:
            def __init__(self, daten): self._d = daten
            def raise_for_status(self): return None
            def json(self): return self._d

        class _Client:
            def __init__(self, *a, **k): pass
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def get(self, url, *a, **k): return _Antwort(rand._antwort(url))

        monkeypatch.setattr(httpx, "Client", _Client)
        return self

    # -- Antwort --------------------------------------------------------
    def _antwort(self, url: str) -> dict:
        q = parse_qs(urlparse(url).query)
        lat, lon = float(q["latitude"][0]), float(q["longitude"][0])
        modell = q.get("models", [None])[0]
        idx = self.index(lat, lon)
        eintrag = {
            "idx": idx, "lat": lat, "lon": lon, "modell": modell,
            "thread": threading.get_ident(), "thread_name": threading.current_thread().name,
            "t0": _ECHT(),
        }
        with self._lock:
            self.calls.append(eintrag)
            self._aktiv += 1
            self.max_aktiv = max(self.max_aktiv, self._aktiv)
        try:
            if self.bei_anfrage is not None:
                self.bei_anfrage(idx, modell)
            pause = self.verzoegerung(idx, modell)
            if pause:
                time.sleep(pause)
            if self.fehler(idx, modell):
                raise httpx.ConnectError(f"Rand-Fehler Punkt {idx}")
        finally:
            with self._lock:
                self._aktiv -= 1
                eintrag["t1"] = _ECHT()
        return self._daten(idx, modell)

    def _daten(self, idx: int, modell) -> dict:
        jetzt = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        jetzt -= timedelta(minutes=jetzt.minute % 15)
        zeiten = [(jetzt + timedelta(minutes=15 * i)).strftime("%Y-%m-%dT%H:%M")
                  for i in range(96)]
        if modell is not None:
            return {"minutely_15": {"time": zeiten, "precipitation": [None] * 96,
                                    "weather_code": [None] * 96}}
        regen = [0.0] * 96
        regen[0] = _etikett(idx)  # Kennung je Punkt (trocken, unter der Schwelle)
        if self.regen(idx):
            for i in range(2, 24):
                regen[i] = 2.0
        return {"minutely_15": {"time": zeiten, "precipitation": regen,
                                "weather_code": [0] * 96}}

    # -- Auswertung -----------------------------------------------------
    def calls_von(self, idx: int, modell=None) -> list[dict]:
        return [c for c in self.calls if c["idx"] == idx and c["modell"] == modell]

    def hauptabrufe(self) -> list[dict]:
        """Calls der minutely_15-Schlusskette (ohne ``models``-Parameter)."""
        return [c for c in self.calls if c["modell"] is None]


def _etikett(idx: int) -> float:
    return 0.0005 * (idx + 1)  # mm je 15 min -> rund 0,002 mm/h *(idx+1): trocken


def _idx_aus_ergebnis(ergebnis) -> int | None:
    if ergebnis is None or not getattr(ergebnis, "frames", None):
        return None
    return int(round(ergebnis.frames[0].precip_mm_h / 4.0 / 0.0005)) - 1


def _assert_in_workern(rand: _Rand, *, ab_index: int = 0) -> None:
    """Vorbedingung: die Hauptabrufe ab ``ab_index`` liefen NICHT im Hauptfaden."""
    im_haupt = [c["idx"] for c in rand.hauptabrufe()
                if c["idx"] >= ab_index and c["thread"] == _HAUPTFADEN]
    assert not im_haupt, (
        f"Vorbedingung: die Abrufe der Punkte/Orte {im_haupt} liefen im Hauptfaden "
        f"-- der Abruf ist (noch) nicht parallel (fetch_ordered)."
    )


# ---------------------------------------------------------------------------
# Spione (durchreichend -- das Echte laeuft, es wird nur beobachtet)
# ---------------------------------------------------------------------------

class _Spion:
    def __init__(self, monkeypatch, ziel, name: str) -> None:
        self.aufrufe: list[dict] = []
        original = getattr(ziel, name)
        spion = self

        def _durch(*a, **k):
            spion.aufrufe.append({"args": a, "kwargs": k, "thread": threading.get_ident()})
            return original(*a, **k)

        monkeypatch.setattr(ziel, name, _durch)

    @property
    def nur_hauptfaden(self) -> bool:
        return all(a["thread"] == _HAUPTFADEN for a in self.aufrufe)


# ---------------------------------------------------------------------------
# Ortsvergleich-Aufbau
# ---------------------------------------------------------------------------

class _Ort:
    def __init__(self, ort_id: str, lat: float, lon: float) -> None:
        self.id, self.name, self.lat, self.lon = ort_id, f"Ort {ort_id}", lat, lon
        self.elevation_m = 100


def _orte(n: int, basis=_ORTE_MALLORCA, *, praefix: str = "o") -> list[_Ort]:
    return [_Ort(f"{praefix}{i}", basis[0] + 0.07 * i, basis[1]) for i in range(n)]


def _compare_lauf(uid: str, orte: list[_Ort], *, deadline_s: float = 30.0,
                  preset_id: str = "preset-s4"):
    """Ein Detect-Lauf des Ortsvergleich-Radars OHNE injizierten Radar-Dienst."""
    dienst = CompareRadarAlertService(settings=settings_email_only(), user_id=uid)
    return dienst._detect_triggered_locations(
        preset_id, [o.id for o in orte], {o.id: o for o in orte},
        effective_channels=("email",), deadline_at=time.monotonic() + deadline_s,
    )


def _soll(orte: list[_Ort]):
    return [(o.lat, o.lon) for o in orte]


# ---------------------------------------------------------------------------
# Trip-Aufbau
# ---------------------------------------------------------------------------

def _lege_trip_an(uid: str, basis=_MALLORCA, *, trip_id: str | None = None):
    """Nutzer (alle Kanaele) + Nord-Strecke (~24 km, bis zu sechs Messpunkte)."""
    _clean_user(uid)
    _write_premium_profile(uid, _UHR_GESTELLT)
    trip_id = trip_id or f"tdd-s4-trip-{uuid.uuid4().hex[:6]}"
    lat0, lon0 = basis
    lat1, lon1 = lat0 + _DELTA_LAT, lon0 + (_ZONEN_LON1 - _ZONEN_LON0)
    luftlinie = haversine_km(lat0, lon0, lat1, lon1)
    verzeichnis = get_briefings_dir(uid)
    verzeichnis.mkdir(parents=True, exist_ok=True)
    pfad = verzeichnis / f"{trip_id}.json"
    from freezegun import freeze_time

    with freeze_time(_UHR_GESTELLT):
        pfad.write_text(json.dumps({
            "id": trip_id, "name": "Radar parallel Trip",
            "stages": [{
                "id": "S1", "name": "Tag 1",
                "date": stage_date(lat0, lon0).isoformat(),
                "waypoints": [
                    {"id": "WP0", "name": "WP0", "lat": lat0, "lon": lon0,
                     "elevation_m": 100.0, "arrival_calculated": "11:00",
                     "distance_from_start_km": 0.0},
                    {"id": "WP1", "name": "WP1", "lat": lat1, "lon": lon1,
                     "elevation_m": 100.0, "arrival_calculated": "17:00",
                     "distance_from_start_km": round(luftlinie, 3)},
                ],
            }],
            "report_config": {
                "trip_id": trip_id, "send_email": True, "send_telegram": True,
                "send_sms": True, "send_premium_sms": True,
                "alert_on_changes": True,
            },
        }))
        return load_trip(pfad, user_id="default")


def _trip_dienst(uid: str) -> TripAlertService:
    return TripAlertService(
        settings=_settings_all_channels(), user_id=uid,
        mail_sink=lambda subject, body: None,
    )


_SOLL_CACHE: dict = {}


def _soll_punkte(basis, monkeypatch):
    """Die Messpunkte der Strecke (nach Breitengrad = Index) aus einem
    trockenen Probelauf (Punkt 0 haengt am Zeitanteil der gestellten Uhr)."""
    if basis in _SOLL_CACHE:
        return _SOLL_CACHE[basis]
    from freezegun import freeze_time

    uid = _uid("soll")
    probe = _Rand([(basis[0], basis[1])])
    probe.index = lambda lat, lon: 0  # Probe: Index egal
    probe.installiere(monkeypatch)
    try:
        _lege_trip_an(uid, basis)
        with freeze_time(_UHR_GESTELLT):
            reset_shared_radar_cache_for_tests()
            _trip_dienst(uid).check_radar_alerts_run()
    finally:
        _warte_auf_worker()
        _clean_user(uid)
    punkte = sorted({(c["lat"], c["lon"]) for c in probe.calls})
    assert len(punkte) >= 5, (
        f"Testvoraussetzung: die Strecke {basis} muss bei der gestellten Uhr "
        f"mindestens fuenf Messpunkte liefern, lieferte {len(punkte)}."
    )
    _SOLL_CACHE[basis] = tuple(punkte)
    return _SOLL_CACHE[basis]


def _trip_lauf(uid: str, rand: _Rand, *, trip=None, dienst=None):
    """Ein Trip-Radar-Lauf unter gestellter Uhr; liefert (Lauf, Trip)."""
    from freezegun import freeze_time

    reset_shared_radar_cache_for_tests()
    with freeze_time(_UHR_GESTELLT):
        dienst = dienst or _trip_dienst(uid)
        return dienst.check_radar_alerts_run()


class _ZonenSpion(_Spion):
    """Beobachtet ``derive_rain_zones`` (Auswertung im Hauptfaden)."""

    def __init__(self, monkeypatch) -> None:
        super().__init__(monkeypatch, trip_alert, "derive_rain_zones")

    @property
    def letzte(self):
        return self.aufrufe[-1]["args"] if self.aufrufe else None


@pytest.fixture
def trip_umgebung(monkeypatch):
    erzeugt: list[str] = []

    def _bau(tag: str, basis=_MALLORCA):
        uid = _uid(tag)
        erzeugt.append(uid)
        trip = _lege_trip_an(uid, basis)
        return uid, trip

    yield _bau
    _warte_auf_worker()  # vor dem Loeschen der Nutzerordner
    for uid in erzeugt:
        _clean_user(uid)


@pytest.fixture
def compare_umgebung():
    erzeugt: list[str] = []

    def _bau(tag: str) -> str:
        uid = _uid(tag)
        erzeugt.append(uid)
        _clean_user(uid)
        return uid

    yield _bau
    _warte_auf_worker()  # vor dem Loeschen der Nutzerordner
    for uid in erzeugt:
        _clean_user(uid)


# ===========================================================================
# AC-1: kein Zustand wandert zwischen parallelen Abrufen
# ===========================================================================

def test_ac1_abrufe_behalten_eigenen_zustand_trotz_ueberlappung(
    monkeypatch, uhr, compare_umgebung
):
    """AC-1: Ort A scheitert (Quelle nicht verfuegbar), Ort B laeuft spaeter an
    (bekommt erst einen Slot, wenn zwei andere fertig sind) und setzt dabei die
    ``*_this_call``-Flags der Instanz zurueck, WAEHREND A noch auswertet. Mit
    EINER geteilten Instanz verliert A seine Markierung ``data_unavailable`` --
    der Ausfall wuerde zu "trocken" (stille Entwarnung). Pro Abruf eine eigene
    Instanz: A bleibt "nicht verfuegbar".

    Die Verzoegerung vor ``_derive_result`` (nur wenn keine Frames da sind)
    weitet das Fenster zwischen Fehlschlag und Auswertung deterministisch."""
    uid = compare_umgebung("ac1")
    orte = _orte(4)  # 0=A (Fehler), 1/2 = langsam, 3 = B (spaet, nass)
    rand = _Rand(
        _soll(orte),
        verzoegerung=lambda idx, m: {0: 0.1, 1: 0.3, 2: 0.3}.get(idx, 0.0),
        fehler=lambda idx, m: idx == 0,
        regen=lambda idx: idx == 3,
    ).installiere(monkeypatch)

    original = radar_service_mod.RadarNowcastService._derive_result

    def _verzoegert(self, frames, source, **kw):
        if not frames:
            time.sleep(0.8)
        return original(self, frames, source, **kw)

    monkeypatch.setattr(radar_service_mod.RadarNowcastService, "_derive_result", _verzoegert)
    ausfaelle = _Spion(monkeypatch, alert_log, "append_suppressed_entry")

    ausgeloest = _compare_lauf(uid, orte)

    _assert_in_workern(rand)
    assert [t[1].id for t in ausgeloest] == ["o3"], (
        f"Nur B (nass) loest aus; A (Ausfall) darf es nicht, war: "
        f"{[t[1].id for t in ausgeloest]}"
    )
    assert len(ausfaelle.aufrufe) == 1, (
        f"A ist ein Quellenausfall und muss GENAU einmal protokolliert werden "
        f"(Zustand von B hat A's Markierung geloescht?), war {len(ausfaelle.aufrufe)}"
    )


def test_ac1_zustand_haelt_nach_vielen_wiederholungen(
    monkeypatch, uhr, compare_umgebung
):
    """AC-1 (Wiederholung): zwei ueberlappende Abrufe, einer scheitert, einer ist
    nass -- 60 Runden mit minimalem Thread-Wechselintervall. Jede Runde muss
    exakt das Ergebnis zeigen; Thread-Fehler werden selbst eingesammelt."""
    uid = compare_umgebung("ac1w")
    orte = _orte(2)
    rand = _Rand(
        _soll(orte),
        verzoegerung=lambda idx, m: 0.004,
        fehler=lambda idx, m: idx == 0,
        regen=lambda idx: idx == 1,
    ).installiere(monkeypatch)
    ausfaelle = _Spion(monkeypatch, alert_log, "append_suppressed_entry")

    altes_intervall = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        for runde in range(60):
            reset_shared_radar_cache_for_tests()
            vorher = len(ausfaelle.aufrufe)
            ausgeloest = _compare_lauf(uid, orte)
            assert [t[1].id for t in ausgeloest] == ["o1"], f"Runde {runde}: {ausgeloest}"
            assert len(ausfaelle.aufrufe) - vorher == 1, f"Runde {runde}: Ausfall verloren"
    finally:
        sys.setswitchinterval(altes_intervall)
    _assert_in_workern(rand)


# ===========================================================================
# AC-2: Reihenfolge, erster Punkt seriell zuerst
# ===========================================================================

def test_ac2_zonen_in_eingabereihenfolge_erster_punkt_zuerst(
    monkeypatch, uhr, trip_umgebung
):
    """AC-2: Die Abrufe der Punkte 1..5 werden in UMGEKEHRTER Reihenfolge fertig
    (je spaeter, desto kuerzer); die Zonen werden trotzdem aus der Eingabe-
    reihenfolge abgeleitet. Punkt 0 laeuft seriell VOR allen anderen im
    Hauptfaden."""
    uid, trip = trip_umgebung("ac2")
    soll = _soll_punkte(_MALLORCA, monkeypatch)
    rand = _Rand(
        soll, verzoegerung=lambda idx, m: 0.0 if idx == 0 else (6 - idx) * 0.12,
    ).installiere(monkeypatch)
    zonen = _ZonenSpion(monkeypatch)

    _trip_lauf(uid, rand)

    _assert_in_workern(rand, ab_index=1)
    p0 = rand.calls_von(0)[0]
    folge = [c for c in rand.hauptabrufe() if c["idx"] != 0]
    assert len(folge) >= 4, f"Folgepunkte fehlen: {len(folge)}"
    assert p0["t1"] <= min(c["t0"] for c in folge), (
        "Punkt 0 muss VOR allen weiteren Punkten fertig sein (seriell zuerst)"
    )
    fertig = [c["idx"] for c in sorted(folge, key=lambda c: c["t1"])]
    assert fertig != sorted(fertig), (
        f"Testvoraussetzung: die Folgepunkte muessen aus der Reihenfolge fertig "
        f"werden, wurden aber der Reihe nach fertig: {fertig}"
    )
    assert zonen.aufrufe, "derive_rain_zones wurde nicht aufgerufen"
    ergebnisse = zonen.letzte[1]
    idxe = [_idx_aus_ergebnis(e) for e in ergebnisse]
    assert idxe == list(range(len(idxe))), (
        f"Ergebnisse muessen in Reihenfolge der Zonenpunkte stehen, war {idxe}"
    )


# ===========================================================================
# AC-3: ein gescheiterter Punkt ist nur eine Luecke
# ===========================================================================

def test_ac3_gescheiterter_punkt_ist_luecke_ohne_abbruch(
    monkeypatch, uhr, trip_umgebung, caplog
):
    uid, trip = trip_umgebung("ac3")
    soll = _soll_punkte(_MALLORCA, monkeypatch)
    rand = _Rand(soll, fehler=lambda idx, m: idx == 2).installiere(monkeypatch)
    zonen = _ZonenSpion(monkeypatch)
    caplog.set_level(logging.DEBUG)

    lauf = _trip_lauf(uid, rand)

    _assert_in_workern(rand, ab_index=1)
    assert zonen.aufrufe, "Der Lauf brach ab, die Zonen wurden nicht abgeleitet"
    ergebnisse = zonen.letzte[1]
    assert ergebnisse[2] is None or getattr(ergebnisse[2], "data_unavailable", False) is False \
        or ergebnisse[2] is None
    verwertbar = [i for i, e in enumerate(ergebnisse) if e is not None]
    luecken = [i for i, e in enumerate(ergebnisse) if e is None]
    assert luecken == [2], f"Nur Punkt 2 darf fehlen, Luecken: {luecken}"
    assert 0 in verwertbar and 3 in verwertbar
    lat, lon = soll[2]
    zeilen = [r.getMessage() for r in caplog.records
              if r.levelno >= logging.WARNING and f"{lat:.4f}" in r.getMessage()]
    assert zeilen, "Der Ausfall steht nicht mit dem Punkt im Log"
    assert lauf.alerts_sent == 0
    assert alert_log.read_undelivered(
        uid, entity_id=trip.id, entity_type="trip",
        since=datetime.now(timezone.utc) - timedelta(minutes=5),
    ) == [], "Weder Alarm unterdrueckt noch Entwarnung: es darf nichts protokolliert sein"


# ===========================================================================
# AC-4: Grenzabbruch im Worker wird im Hauptfaden neu geworfen (Trip)
# ===========================================================================

def test_ac4_trip_grenzabbruch_im_worker_bricht_die_einheit_ab(
    monkeypatch, uhr, trip_umgebung
):
    """AC-4: Die Frist laeuft waehrend des Abrufs eines weiteren Zonenpunkts ab
    (``uhr.sprung`` in dessen erster Anfrage; Provence: AROME-HD vor Open-Meteo,
    die Grenze wird zwischen den Schritten geprueft). Die Ausnahme muss im
    Hauptfaden neu geworfen werden: Einheit abgebrochen -- keine Luecke, kein
    Quellenausfall, keine Entwarnung."""
    uid, trip = trip_umgebung("ac4", _PROVENCE)
    soll = _soll_punkte(_PROVENCE, monkeypatch)
    rand = _Rand(
        soll,
        bei_anfrage=lambda idx, m: uhr.sprung(1000.0) if (idx == 2 and m) else None,
        verzoegerung=lambda idx, m: 0.1 if idx >= 1 and m else 0.0,
    ).installiere(monkeypatch)
    zonen = _ZonenSpion(monkeypatch)

    lauf = _trip_lauf(uid, rand)

    _assert_in_workern(rand, ab_index=1)
    assert lauf.hit_deadline is True, "Die Einheit muss an der Grenze abgebrochen sein"
    assert not zonen.aufrufe, (
        "Nach dem Grenzabbruch darf nichts mehr ausgewertet werden (keine Zonen)"
    )
    assert lauf.alerts_sent == 0
    assert alert_log.read_undelivered(
        uid, entity_id=trip.id, entity_type="trip",
        since=datetime.now(timezone.utc) - timedelta(minutes=5),
    ) == [], "Grenzabbruch ist weder Quellenausfall noch Entwarnung"


# ===========================================================================
# AC-5: Ortsvergleich -- Grenzabbruch hochgereicht, Ausfaelle sonst protokolliert
# ===========================================================================

def test_ac5_compare_grenzabbruch_wird_hochgereicht_ohne_ausfallspur(
    monkeypatch, uhr, compare_umgebung
):
    uid = compare_umgebung("ac5a")
    orte = _orte(3, _ORTE_PROVENCE)
    rand = _Rand(
        _soll(orte),
        fehler=lambda idx, m: idx == 0 and m is None,  # Ort 0: echter Ausfall
        bei_anfrage=lambda idx, m: (time.sleep(0.4), uhr.sprung(1000.0))
        if (idx == 1 and m) else None,
    ).installiere(monkeypatch)
    ausfaelle = _Spion(monkeypatch, alert_log, "append_suppressed_entry")

    with pytest.raises(RadarDeadlineExceeded):
        _compare_lauf(uid, orte)

    _assert_in_workern(rand)
    assert ausfaelle.aufrufe == [], (
        "Bei Grenzabbruch gilt das Preset als nicht erreicht: keine Spur im "
        f"Ausfall-Protokoll, war {len(ausfaelle.aufrufe)} Eintraege"
    )


def test_ac5_compare_teilausfall_wird_nach_der_schleife_protokolliert(
    monkeypatch, uhr, compare_umgebung
):
    uid = compare_umgebung("ac5b")
    orte = _orte(4)
    rand = _Rand(_soll(orte), fehler=lambda idx, m: idx in (1, 3)).installiere(monkeypatch)
    ausfaelle = _Spion(monkeypatch, alert_log, "append_suppressed_entry")

    _compare_lauf(uid, orte)

    _assert_in_workern(rand)
    assert len(ausfaelle.aufrufe) == 2, (
        f"Beide gescheiterten Orte muessen protokolliert werden, war {len(ausfaelle.aufrufe)}"
    )


def test_ac2_compare_ergebnisse_und_ausfaelle_in_eingabereihenfolge(
    monkeypatch, uhr, compare_umgebung
):
    """AC-2 (Ortsvergleich, Adversary F002a): die Orte werden in UMGEKEHRTER
    Reihenfolge fertig; Ausloesungen und Ausfall-Protokoll folgen trotzdem
    der Eingabereihenfolge der Orte."""
    uid = compare_umgebung("ac2c")
    monkeypatch.setenv("GZ_PARALLEL_FETCH_SLOTS_OPEN_METEO", "6")
    parallel_fetch._reset_for_tests()
    orte = _orte(6)
    # Deterministische Kette statt Zeitsteuerung: Ort k antwortet erst, wenn
    # Ort k+1 geantwortet hat (alle sechs laufen gleichzeitig, sechs Slots).
    geantwortet = [threading.Event() for _ in orte]
    fertig: list[int] = []
    fertig_lock = threading.Lock()

    def _warte_auf_nachfolger(idx, m):
        if idx + 1 < len(orte):
            assert geantwortet[idx + 1].wait(10), f"Ort {idx + 1} antwortete nie"

    def _melde_antwort(idx, m):
        with fertig_lock:
            fertig.append(idx)
        geantwortet[idx].set()
        return 0.0

    rand = _Rand(
        _soll(orte), bei_anfrage=_warte_auf_nachfolger, verzoegerung=_melde_antwort,
        fehler=lambda idx, m: idx in (1, 4), regen=lambda idx: idx in (0, 2, 5),
    ).installiere(monkeypatch)
    protokoll = _Spion(monkeypatch, CompareRadarAlertService, "_protokolliere_quellenausfall")

    ausgeloest = _compare_lauf(uid, orte)

    _assert_in_workern(rand)
    assert fertig == [5, 4, 3, 2, 1, 0], (
        f"Testvoraussetzung: umgekehrte Fertigstellung, war {fertig}"
    )
    assert [t[1].id for t in ausgeloest] == ["o0", "o2", "o5"]
    assert [a["args"][2] for a in protokoll.aufrufe] == ["o1", "o4"]


def test_ac4_compare_frist_schon_abgelaufen_cache_treffer_liefern_seriell(
    monkeypatch, uhr, compare_umgebung
):
    """Adversary F002b: ist die Frist schon VOR dem Abruf abgelaufen,
    entscheidet wie im seriellen Ablauf der Dienst je Ort -- Cache-Treffer
    liefern weiter (kein Abbruch, kein Upstream-Call). Der Baustein allein
    haette alle Orte als "deadline" uebersprungen => Grenzabbruch."""
    uid = compare_umgebung("ac4c")
    orte = _orte(3)
    rand = _Rand(_soll(orte), regen=lambda idx: True).installiere(monkeypatch)
    assert len(_compare_lauf(uid, orte)) == 3  # Cache fuellen
    vorher = len(rand.hauptabrufe())

    ausgeloest = _compare_lauf(uid, orte, deadline_s=-1.0)

    assert [t[1].id for t in ausgeloest] == ["o0", "o1", "o2"]
    assert len(rand.hauptabrufe()) == vorher, "Cache-Treffer duerfen nicht upstream gehen"


# ===========================================================================
# AC-6: genau ein Upstream-Call je Kachel
# ===========================================================================

def test_ac6_gleiche_kachel_gleichzeitig_ein_upstream_call(
    monkeypatch, uhr, compare_umgebung
):
    uid = compare_umgebung("ac6")
    a, b, c = _Ort("a", 39.60, 2.60), _Ort("b", 39.60, 2.60), _Ort("c", 39.90, 2.60)
    orte = [a, b, c]
    rand = _Rand(
        _soll(orte), verzoegerung=lambda idx, m: 0.4,
        regen=lambda idx: idx in (0, 1),
    ).installiere(monkeypatch)

    ausgeloest = _compare_lauf(uid, orte)

    _assert_in_workern(rand)
    kachel_ab = [x for x in rand.hauptabrufe() if x["idx"] in (0, 1)]
    assert len(kachel_ab) == 1, (
        f"Zwei gleichzeitige Abrufe derselben Kachel duerfen EINEN Upstream-Call "
        f"erzeugen, waren {len(kachel_ab)}"
    )
    assert sorted(t[1].id for t in ausgeloest) == ["a", "b"], (
        "Beide Orte der Kachel erhalten dasselbe (nasse) Ergebnis"
    )
    seriell = len({(o.lat, o.lon) for o in orte})
    assert len(rand.hauptabrufe()) <= seriell, (
        f"Parallel darf nicht mehr Calls kosten als seriell ({seriell}), "
        f"waren {len(rand.hauptabrufe())}"
    )


def test_ac6_spaeter_leader_liest_den_cache_erneut(monkeypatch, uhr):
    """AC-6 (Adversary F001): B sieht einen Cache-Miss, A laeuft danach
    KOMPLETT durch (Upstream-Call, Cache gefuellt, Flug beendet), erst dann
    fuehrt B seinen eigenen Flug. B muss den Cache erneut lesen statt ein
    zweites Mal upstream zu gehen. Das Fenster wird deterministisch ueber
    einen durchreichenden Halt an B's ERSTEM Cache-Lesen hergestellt."""
    from services.radar_cache import RadarNowcastCacheService

    rand = _Rand([(39.60, 2.60)], regen=lambda idx: True).installiere(monkeypatch)
    lesen = RadarNowcastCacheService.get
    b_hat_miss_gesehen, a_fertig = threading.Event(), threading.Event()

    def _get(self, *a, **k):
        treffer = lesen(self, *a, **k)
        if (treffer is None and threading.current_thread().name == "B"
                and not b_hat_miss_gesehen.is_set()):
            b_hat_miss_gesehen.set()
            assert a_fertig.wait(5), "Testaufbau: A wurde nicht fertig"
        return treffer

    monkeypatch.setattr(RadarNowcastCacheService, "get", _get)
    ergebnisse: dict = {}
    fehler: list = []

    def _lauf(name):
        try:
            dienst = radar_service_mod.RadarNowcastService().fuer_abruf()
            ergebnisse[name] = dienst.get_nowcast(
                39.60, 2.60, elevation_m=100, priority="polling",
                user_id=_uid(name), deadline_at=time.monotonic() + 30,
            )
        except BaseException as exc:  # noqa: BLE001 -- selbst einsammeln
            fehler.append(exc)

    fb = threading.Thread(target=_lauf, args=("B",), name="B")
    fb.start()
    assert b_hat_miss_gesehen.wait(5), "Testaufbau: B sah keinen Cache-Miss"
    fa = threading.Thread(target=_lauf, args=("A",), name="A")
    fa.start()
    fa.join()
    a_fertig.set()
    fb.join()

    assert not fehler, f"Thread-Fehler: {fehler!r}"
    assert len(rand.hauptabrufe()) == 1, (
        f"B ging trotz gefuelltem Cache erneut upstream: {len(rand.hauptabrufe())} Calls"
    )
    assert _idx_aus_ergebnis(ergebnisse["B"]) == 0 and not ergebnisse["B"].data_unavailable


def test_ac6_verschiedene_kacheln_je_ein_call(monkeypatch, uhr, compare_umgebung):
    uid = compare_umgebung("ac6b")
    orte = _orte(3)
    rand = _Rand(_soll(orte), verzoegerung=lambda idx, m: 0.2).installiere(monkeypatch)

    _compare_lauf(uid, orte)

    _assert_in_workern(rand)
    assert sorted(c["idx"] for c in rand.hauptabrufe()) == [0, 1, 2]


# ===========================================================================
# AC-7: Budget wird atomar gebucht
# ===========================================================================

def test_ac7_parallele_abrufe_ueberbuchen_das_budget_nicht(
    monkeypatch, uhr, compare_umgebung
):
    """AC-7: Tagesbudget 10, davon 8 schon verbraucht => Restbudget 2. (Ein
    einzelner Nutzer hat in Stufe 1 als fairen Anteil das ganze Tagesbudget,
    die Grenze ist also DAILY_BUDGET, nicht die 80-%-Schwelle.) Zwoelf Orte
    buchen GLEICHZEITIG (zwoelf Slots): gebuchte Calls == tatsaechliche
    Upstream-Calls == Restbudget; der Rest wird gedrosselt (kein Folgeabruf).
    Nicht-atomares ``allow()`` + ``record_call()`` liesse mehrere Abrufe den
    Stand 8/10 lesen und ueberbuchte."""
    uid = compare_umgebung("ac7")
    monkeypatch.setattr(ForecastBudgetGate, "DAILY_BUDGET", 10)
    monkeypatch.setenv("GZ_PARALLEL_FETCH_SLOTS_OPEN_METEO", "12")
    monkeypatch.setenv("GZ_PARALLEL_FETCH_WORKERS", "12")
    parallel_fetch._reset_for_tests()
    vorbelegt = 8
    for _ in range(vorbelegt):
        assert ForecastBudgetGate(uid).reserve("user_briefing")
    rest = ForecastBudgetGate.DAILY_BUDGET - vorbelegt
    # Durchreichende Verzoegerung beim Lesen des Budgetstands (echtes Gate
    # laeuft): weitet das Fenster zwischen Lesen und Buchen deterministisch --
    # eine atomare Buchung haelt dabei die Sperre, eine getrennte ueberbucht.
    _lesen = ForecastBudgetGate._load_for_today

    def _langsam_lesen(self, now=None):
        time.sleep(0.02)
        return _lesen(self, now)

    monkeypatch.setattr(ForecastBudgetGate, "_load_for_today", _langsam_lesen)
    orte = _orte(12)
    rand = _Rand(_soll(orte), verzoegerung=lambda idx, m: 0.05).installiere(monkeypatch)

    _compare_lauf(uid, orte)

    _assert_in_workern(rand)
    stand = ForecastBudgetGate(uid).snapshot()
    gebucht = stand["calls_today"] - vorbelegt
    tatsaechlich = len(rand.hauptabrufe())
    assert gebucht == tatsaechlich, (
        f"Gebuchte Calls ({gebucht}) muessen den tatsaechlichen Upstream-Calls "
        f"({tatsaechlich}) entsprechen"
    )
    assert tatsaechlich <= rest, f"Restbudget {rest} ueberbucht: {tatsaechlich} Calls"
    assert tatsaechlich == rest, f"Das Restbudget soll voll genutzt werden, war {tatsaechlich}"


# ===========================================================================
# AC-8: uebersprungene Abrufe zaehlen als gescheitert und stehen im Log
# ===========================================================================

def test_ac8_compare_nie_gestartete_orte_sind_grenzabbruch_und_stehen_im_log(
    monkeypatch, uhr, compare_umgebung, caplog
):
    uid = compare_umgebung("ac8c")
    monkeypatch.setenv("GZ_PARALLEL_FETCH_SLOTS_OPEN_METEO", "1")
    parallel_fetch._reset_for_tests()
    orte = _orte(4)
    rand = _Rand(_soll(orte), verzoegerung=lambda idx, m: 0.5).installiere(monkeypatch)
    ausfaelle = _Spion(monkeypatch, alert_log, "append_suppressed_entry")
    caplog.set_level(logging.DEBUG)

    # Orchestrator-Entscheid (Option a): Orte, die wegen der Frist NIE
    # gestartet wurden, sind ein Grenzabbruch wie im seriellen Ablauf --
    # Preset nicht erreicht, keine Ausfall-Spur (A-2 S2), aber laut im Log.
    with pytest.raises(RadarDeadlineExceeded):
        _compare_lauf(uid, orte, deadline_s=0.8)

    _assert_in_workern(rand)
    # Ort 0 fertig; Ort 1 Zeitueberschreitung; Orte 2, 3 nie gestartet.
    assert ausfaelle.aufrufe == [], (
        f"Grenzabbruch hinterlaesst keine Ausfall-Spur, war {len(ausfaelle.aufrufe)}"
    )
    for ort in orte[1:]:
        zeilen = [r.getMessage() for r in caplog.records
                  if r.levelno >= logging.WARNING and ort.id in r.getMessage()
                  and any(w in r.getMessage().lower() for w in ("deadline", "timeout", "frist", "zeit"))]
        assert zeilen, f"Fuer {ort.id} fehlt eine Fehlerzeile mit Grund im Log"


def test_ac8_compare_zeitueberschreitung_zaehlt_als_ausfall_und_steht_im_log(
    monkeypatch, uhr, compare_umgebung, caplog
):
    """AC-8 (Gegenstueck zum Grenzabbruch): beide Orte GESTARTET, aber bei
    Fristablauf noch nicht fertig (``skipped="timeout"``) => Ausfall wie
    bisher, protokolliert nach der Schleife, laut im Log -- kein Abbruch."""
    uid = compare_umgebung("ac8to")
    orte = _orte(2)
    rand = _Rand(_soll(orte), verzoegerung=lambda idx, m: 0.6).installiere(monkeypatch)
    ausfaelle = _Spion(monkeypatch, alert_log, "append_suppressed_entry")
    caplog.set_level(logging.DEBUG)

    ausgeloest = _compare_lauf(uid, orte, deadline_s=0.3)

    _assert_in_workern(rand)
    assert ausgeloest == []
    assert len(ausfaelle.aufrufe) == 2, (
        f"Zeitueberschreitung zaehlt als Ausfall (2), war {len(ausfaelle.aufrufe)}"
    )
    for ort in orte:
        assert [r for r in caplog.records if r.levelno >= logging.WARNING
                and ort.id in r.getMessage() and "timeout" in r.getMessage()], (
            f"Fuer {ort.id} fehlt die Fehlerzeile mit Grund"
        )


def test_ac8_trip_uebersprungene_punkte_sind_luecken_und_stehen_im_log(
    monkeypatch, uhr, trip_umgebung, caplog
):
    uid, trip = trip_umgebung("ac8t")
    monkeypatch.setenv("GZ_PARALLEL_FETCH_SLOTS_OPEN_METEO", "1")
    parallel_fetch._reset_for_tests()
    monkeypatch.setattr(trip_alert, "RADAR_RUN_DEADLINE_SECONDS", 1.0)
    soll = _soll_punkte(_MALLORCA, monkeypatch)
    rand = _Rand(soll, verzoegerung=lambda idx, m: 0.4).installiere(monkeypatch)
    zonen = _ZonenSpion(monkeypatch)
    caplog.set_level(logging.DEBUG)

    _trip_lauf(uid, rand)

    _assert_in_workern(rand, ab_index=1)
    assert zonen.aufrufe, "Die Zonen wurden nicht abgeleitet"
    ergebnisse = zonen.letzte[1]
    luecken = [i for i, e in enumerate(ergebnisse) if e is None]
    assert len(luecken) >= 3, f"Uebersprungene Punkte muessen Luecken sein: {luecken}"
    zeilen = [r for r in caplog.records
              if r.levelno >= logging.WARNING
              and any(w in r.getMessage().lower() for w in ("deadline", "timeout", "frist", "zeit"))]
    assert len(zeilen) >= len(luecken) - 1, (
        f"Fuer jeden uebersprungenen Punkt muss eine Fehlerzeile mit Grund stehen "
        f"({len(luecken)} Luecken, {len(zeilen)} Zeilen)"
    )


# ===========================================================================
# AC-9: Mandantentrennung
# ===========================================================================

def test_ac9_compare_zwei_nutzer_gleichzeitig_getrennt(
    monkeypatch, uhr, compare_umgebung
):
    ua, ub = compare_umgebung("ac9a"), compare_umgebung("ac9b")
    orte_a = _orte(3, (39.60, 2.60), praefix="a")
    orte_b = _orte(4, (39.60, 3.40), praefix="b")
    rand = _Rand(
        _soll(orte_a + orte_b), verzoegerung=lambda idx, m: 0.15,
        regen=lambda idx: True,
    ).installiere(monkeypatch)
    ergebnisse: dict = {}
    fehler: list = []

    aufrufer: set = set()

    def _lauf(uid, orte):
        aufrufer.add(threading.get_ident())
        try:
            ergebnisse[uid] = _compare_lauf(uid, orte, preset_id=f"p-{uid}")
        except BaseException as exc:  # noqa: BLE001 -- selbst einsammeln
            fehler.append(exc)

    faeden = [threading.Thread(target=_lauf, args=(ua, orte_a)),
              threading.Thread(target=_lauf, args=(ub, orte_b))]
    for f in faeden: f.start()
    for f in faeden: f.join()

    assert not fehler, f"Thread-Fehler: {fehler!r}"
    assert not [c for c in rand.hauptabrufe() if c["thread"] in aufrufer], (
        "Vorbedingung: die Abrufe liefen im Aufrufer-Thread -- nicht parallel (fetch_ordered)"
    )
    assert sorted(t[1].id for t in ergebnisse[ua]) == ["a0", "a1", "a2"]
    assert sorted(t[1].id for t in ergebnisse[ub]) == ["b0", "b1", "b2", "b3"]
    assert ForecastBudgetGate(ua).snapshot()["user_calls_today"] == 3
    assert ForecastBudgetGate(ub).snapshot()["user_calls_today"] == 4
    assert ForecastBudgetGate("default").snapshot().get("user_calls_today", 0) == 0, (
        "Nichts darf auf 'default' gebucht werden (Cross-User-Leck)"
    )


def test_ac9_single_flight_vererbt_keine_drosselung_zwischen_nutzern(
    monkeypatch, uhr, compare_umgebung
):
    """AC-9 (Single-flight): Nutzer A ist ueber seinem fairen Anteil
    (gedrosselt), Nutzer B nicht; beide fragen GLEICHZEITIG dieselbe Kachel ab,
    A fuehrt den Flug. Die Drosselung ist eine Entscheidung je Nutzer: B darf
    sie nicht erben, sondern holt selbst ab und bekommt seinen Alarm.

    Budget: Tagesbudget 10, A hat 6, B 2 verbraucht (global 8 = 80 %, zwei
    aktive Nutzer => fairer Anteil 5). Die Verzoegerung in A's Buchung (am
    echten Gate durchgereicht) haelt den Flug offen, bis B wartet."""
    ua, ub = compare_umgebung("ac9sfa"), compare_umgebung("ac9sfb")
    monkeypatch.setattr(ForecastBudgetGate, "DAILY_BUDGET", 10)
    for uid, n in ((ua, 6), (ub, 2)):
        for _ in range(n):
            assert ForecastBudgetGate(uid).reserve("user_briefing")
    original = ForecastBudgetGate.reserve
    a_im_flug, b_im_flug = threading.Event(), threading.Event()

    def _haelt_a_im_flug(self, priority, units=1, now=None):
        # A (Leader) bucht erst, wenn B den Flug betreten hat; die kurze
        # Nachfrist laesst B sich als Wartender einreihen (Vorbedingung unten).
        if self._user_id == ua:
            a_im_flug.set()
            assert b_im_flug.wait(10), "Testaufbau: B betrat den Flug nie"
            time.sleep(0.2)
        return original(self, priority, units=units, now=now)

    monkeypatch.setattr(ForecastBudgetGate, "reserve", _haelt_a_im_flug)
    fluege = radar_service_mod._KACHEL_FLUEGE
    flug_lauf = fluege.run
    flug_ergebnisse: list = []

    def _run(key, leader_fn, *, wait_timeout_s):
        if a_im_flug.is_set():
            b_im_flug.set()
        ergebnis = flug_lauf(key, leader_fn, wait_timeout_s=wait_timeout_s)
        flug_ergebnisse.append(ergebnis)
        return ergebnis

    monkeypatch.setattr(fluege, "run", _run)
    ort_a, ort_b = _Ort("a", 39.60, 2.60), _Ort("b", 39.60, 2.60)
    rand = _Rand([(39.60, 2.60)], regen=lambda idx: True).installiere(monkeypatch)
    ergebnisse: dict = {}
    fehler: list = []

    def _lauf(uid, ort):
        try:
            ergebnisse[uid] = _compare_lauf(uid, [ort], preset_id=f"p-{uid}")
        except BaseException as exc:  # noqa: BLE001 -- selbst einsammeln
            fehler.append(exc)

    fa = threading.Thread(target=_lauf, args=(ua, ort_a))
    fb = threading.Thread(target=_lauf, args=(ub, ort_b))
    fa.start()
    assert a_im_flug.wait(10), "Testaufbau: A erreichte die Buchung nie"
    fb.start()
    fa.join()
    fb.join()

    assert not fehler, f"Thread-Fehler: {fehler!r}"
    assert sorted(f.is_leader for f in flug_ergebnisse) == [False, True], (
        f"Vorbedingung: B muss als WARTENDER auf A's Flug gelaufen sein, war "
        f"{[(f.is_leader, f.timed_out) for f in flug_ergebnisse]}"
    )
    assert ergebnisse[ua] == [], "A ist gedrosselt: kein Alarm"
    assert [t[1].id for t in ergebnisse[ub]] == ["b"], (
        "B hat die Drosselung von A geerbt (Single-flight) -- Alarm fehlt"
    )
    assert len(rand.hauptabrufe()) == 1, "Genau B's eigener Upstream-Call"
    assert ForecastBudgetGate(ua).snapshot()["user_calls_today"] == 6
    assert ForecastBudgetGate(ub).snapshot()["user_calls_today"] == 3


def test_ac9_trip_zwei_nutzer_gleichzeitig_getrennt(monkeypatch, uhr):
    from freezegun import freeze_time

    ua, ub = _uid("ac9ta"), _uid("ac9tb")
    basis_a, basis_b = _MALLORCA, (39.70, 3.40)
    try:
        _lege_trip_an(ua, basis_a)
        _lege_trip_an(ub, basis_b)
        soll_a = _soll_punkte(basis_a, monkeypatch)
        soll_b = _soll_punkte(basis_b, monkeypatch)
        rand = _Rand(
            list(soll_a) + list(soll_b),
            verzoegerung=lambda idx, m: 0.1,
        ).installiere(monkeypatch)
        fehler: list = []
        laeufe: dict = {}
        aufrufer: set = set()

        def _lauf(uid):
            aufrufer.add(threading.get_ident())
            try:
                laeufe[uid] = _trip_dienst(uid).check_radar_alerts_run()
            except BaseException as exc:  # noqa: BLE001
                fehler.append(exc)

        reset_shared_radar_cache_for_tests()
        with freeze_time(_UHR_GESTELLT):
            faeden = [threading.Thread(target=_lauf, args=(u,)) for u in (ua, ub)]
            for f in faeden: f.start()
            for f in faeden: f.join()

        assert not fehler, f"Thread-Fehler: {fehler!r}"
        n_a = len([c for c in rand.hauptabrufe() if c["idx"] < len(soll_a)])
        n_b = len([c for c in rand.hauptabrufe() if c["idx"] >= len(soll_a)])
        assert n_a >= 5 and n_b >= 5
        with freeze_time(_UHR_GESTELLT):  # Budget-Tag = gestellter Tag
            assert ForecastBudgetGate(ua).snapshot()["user_calls_today"] == n_a
            assert ForecastBudgetGate(ub).snapshot()["user_calls_today"] == n_b
            assert ForecastBudgetGate("default").snapshot().get("user_calls_today", 0) == 0
        assert [c for c in rand.hauptabrufe() if c["thread"] in aufrufer
                and c["idx"] not in (0, len(soll_a))] == [], (
            "Vorbedingung: die Folgepunkte liefen nicht in Workern (nicht parallel)"
        )
    finally:
        _warte_auf_worker()
        _clean_user(ua)
        _clean_user(ub)


# ===========================================================================
# AC-10: erster Punkt bleibt serielle Auslöseentscheidung
# ===========================================================================

def test_ac10_erster_punkt_loest_aus_wie_im_seriellen_ablauf(
    monkeypatch, uhr, tmp_path
):
    """AC-10: Punkt 0 ist nass => genau ein Alarm (Entscheidung wie seriell), die
    Folgepunkte (trocken) aendern daran nichts; Punkt 0 lief seriell VOR den
    parallelen Folgepunkten."""
    uid = _uid("ac10")
    try:
        _lege_trip_an(uid)
        soll = _soll_punkte(_MALLORCA, monkeypatch)
        rand = _Rand(soll, regen=lambda idx: idx == 0,
                     verzoegerung=lambda idx, m: 0.05).installiere(monkeypatch)
        trip = load_trip(next(get_briefings_dir(uid).glob("*.json")), user_id="default")
        strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())

        lauf = strecke.lauf(at=_UHR_GESTELLT, zweig="radar", trip=trip)

        assert lauf.triggered_count == 1, (
            f"Punkt 0 nass => genau ein Alarm, war {lauf.triggered_count}"
        )
        assert lauf.mail, "Der Alarm muss die Mail erreicht haben"
        _assert_in_workern(rand, ab_index=1)
        p0 = rand.calls_von(0)[0]
        folge = [c for c in rand.hauptabrufe() if c["idx"] != 0]
        assert folge and p0["t1"] <= min(c["t0"] for c in folge), (
            "Punkt 0 muss vor allen parallelen Folgepunkten abgeschlossen sein"
        )
    finally:
        _warte_auf_worker()
        _clean_user(uid)


# ===========================================================================
# AC-11: Zaehler und Ausfallsammlung nur im Hauptfaden
# ===========================================================================

def test_ac11_compare_ausfallsammlung_nur_im_hauptfaden_nach_vielen_runden(
    monkeypatch, uhr, compare_umgebung
):
    uid = compare_umgebung("ac11c")
    orte = _orte(5)
    gescheitert = {1, 3}
    rand = _Rand(
        _soll(orte), verzoegerung=lambda idx, m: 0.003 * (5 - idx),
        fehler=lambda idx, m: idx in gescheitert,
    ).installiere(monkeypatch)
    ausfaelle = _Spion(monkeypatch, alert_log, "append_suppressed_entry")

    for runde in range(25):
        reset_shared_radar_cache_for_tests()
        vorher = len(ausfaelle.aufrufe)
        _compare_lauf(uid, orte)
        assert len(ausfaelle.aufrufe) - vorher == len(gescheitert), (
            f"Runde {runde}: Ausfallzahl stimmt nicht mit gescheiterten Orten ueberein"
        )

    _assert_in_workern(rand)
    assert ausfaelle.nur_hauptfaden, "Ausfaelle wurden aus einem Worker-Thread geschrieben"


def test_ac11_trip_lueckenzaehlung_nur_im_hauptfaden_nach_vielen_runden(
    monkeypatch, uhr, trip_umgebung
):
    uid, trip = trip_umgebung("ac11t")
    soll = _soll_punkte(_MALLORCA, monkeypatch)
    gescheitert = {2, 4}
    rand = _Rand(
        soll, verzoegerung=lambda idx, m: 0.003 * (6 - idx),
        fehler=lambda idx, m: idx in gescheitert,
    ).installiere(monkeypatch)
    zonen = _ZonenSpion(monkeypatch)

    for runde in range(15):
        vorher = len(zonen.aufrufe)
        _trip_lauf(uid, rand)
        assert len(zonen.aufrufe) - vorher == 1, f"Runde {runde}: Zonen nicht abgeleitet"
        ergebnisse = zonen.letzte[1]
        luecken = {i for i, e in enumerate(ergebnisse) if e is None}
        assert luecken == gescheitert, f"Runde {runde}: Luecken {luecken} != {gescheitert}"

    _assert_in_workern(rand, ab_index=1)
    assert zonen.nur_hauptfaden, "Auswertung lief nicht im Hauptfaden"


# ===========================================================================
# AC-12: Laufdauer sinkt unter 60 % der Summe der Einzelverzoegerungen
# ===========================================================================

def test_ac12_trip_laufdauer_unter_60_prozent_der_einzelverzoegerungen(
    monkeypatch, uhr, trip_umgebung
):
    uid, trip = trip_umgebung("ac12")
    soll = _soll_punkte(_MALLORCA, monkeypatch)
    sechs = soll[:6]
    assert len(sechs) == 6, f"Testvoraussetzung: sechs Zonenpunkte, waren {len(sechs)}"
    rand = _Rand(soll, verzoegerung=lambda idx, m: 0.5).installiere(monkeypatch)

    start = _ECHT()
    lauf = _trip_lauf(uid, rand)
    gemessen = _ECHT() - start

    _assert_in_workern(rand, ab_index=1)
    summe = 0.5 * len(rand.hauptabrufe())
    assert len(rand.hauptabrufe()) == 6, f"Sechs Abrufe erwartet, waren {len(rand.hauptabrufe())}"
    assert lauf.duration_s < 0.6 * summe, (
        f"duration_s {lauf.duration_s:.2f}s muss unter 60 % der Summe der "
        f"Einzelverzoegerungen ({summe:.1f}s) liegen"
    )
    assert gemessen < 0.6 * summe, f"Gemessene Dauer {gemessen:.2f}s >= {0.6 * summe:.2f}s"
