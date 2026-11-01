"""Gemeinsamer Aufbau der S6-Tests (Issue #1539, Ortsvergleich-Alarme parallel).

SPEC: docs/specs/modules/feat_1539_s6_compare_parallel.md

Kein Test-Modul (fuehrender Unterstrich). Geteilt von den fuenf Dateien
``test_compare_alert_parallel_*.py`` und ``test_compare_official_alert_parallel_*.py``.

Grundsaetze (Projekt-Testpolitik, kein Mock-Theater):

* **Wetter-Rand:** ``WetterRand`` ist eine echte ``LocationWeatherSource``
  (Konstruktor-Naht ``weather_source`` des Dienstes). Er erfasst Thread,
  Zeitpunkte, Gleichzeitigkeit, Verzoegerung, ``user_id`` und gezielte Fehler.
  Die Auswertung (Anker laden, ``DeviationAlertEngine``, Protokoll) laeuft echt.
* **Warn-Rand:** ``WarnRand`` ist eine echte amtliche Quelle in der ECHTEN
  Registry (``services.official_alerts.base._REGISTERED_SOURCES``).
* **Nachweis "parallel":** Abrufe laufen im Worker-Thread des Bausteins
  (Thread-Name ``parallel-fetch*``) UND ueberlappen sich (Zaehler / Treffpunkt).

Vertrag fuer GREEN (wie S3/S4/S5): die Frist-Konstanten sind
``services.trip_alert.FRESH_WEATHER_DEFAULT_DEADLINE_SECONDS`` (60 s je Preset)
und ``services.trip_alert.ALERT_RUN_DEADLINE_SECONDS`` (180 s je Lauf) und werden
zur LAUFZEIT ueber das Modul ``services.trip_alert`` gelesen (nicht als Kopie
oder Default-Argument gebunden); die Tests verkuerzen sie per ``monkeypatch``.
Die Lauf-Frist steht als optionales Attribut ``_run_deadline_at`` (``None`` =
keine Lauf-Frist) am Dienst; die Tests setzen es direkt.

Pfadregel #1409: der Pruefling wird relativ zu DIESER Datei aufgeloest.
"""
from __future__ import annotations

import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import pytest

WORKTREE = Path(__file__).resolve().parents[2]
ZEITSCHRANKE = 20.0


def pruefling_aus_worktree() -> None:
    import services.compare_alert as ca
    import services.compare_official_alert as coa

    for modul in (ca, coa):
        pfad = Path(modul.__file__).resolve()
        assert pfad.is_relative_to(WORKTREE), (
            f"Pruefling {pfad} liegt nicht im Worktree {WORKTREE}")


def neue_kennung(tag: str) -> str:
    return f"tdd-1539s6-{tag}-{uuid.uuid4().hex[:6]}"


_breiten_zaehler = [0]


def neue_breite() -> float:
    """Eindeutige Breite je Ort: kein Treffer im Wetter-Cache zwischen Tests."""
    _breiten_zaehler[0] += 1
    return round(46.10 + 0.07 * _breiten_zaehler[0], 4)


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture
def umgebung():
    """Baustein und geteilten Wetter-Cache je Test frisch aufsetzen."""
    from services import parallel_fetch
    from services.weather_cache import reset_shared_weather_cache_for_tests

    parallel_fetch._reset_for_tests()
    reset_shared_weather_cache_for_tests()
    yield
    parallel_fetch._reset_for_tests()
    reset_shared_weather_cache_for_tests()


@pytest.fixture
def thread_fehler():
    gesammelt: list = []
    alt = threading.excepthook
    threading.excepthook = lambda args: gesammelt.append(args)
    yield gesammelt
    threading.excepthook = alt
    assert not gesammelt, f"unbehandelte Thread-Ausnahmen: {gesammelt!r}"


def slots_setzen(monkeypatch, provider: str, anzahl: int) -> None:
    from services import parallel_fetch

    monkeypatch.setenv(f"GZ_PARALLEL_FETCH_SLOTS_{provider.upper()}", str(anzahl))
    parallel_fetch._reset_for_tests()


def frist_setzen(monkeypatch, sekunden: float) -> None:
    """Die EINE Preset-Frist-Konstante verkuerzen (kein neuer Wert)."""
    import services.trip_alert as ta

    assert hasattr(ta, "FRESH_WEATHER_DEFAULT_DEADLINE_SECONDS")
    monkeypatch.setattr(ta, "FRESH_WEATHER_DEFAULT_DEADLINE_SECONDS", sekunden)


def ist_worker(thread_name: str) -> bool:
    return thread_name.startswith("parallel-fetch")


# --------------------------------------------------------------------------- #
# Orte, Presets, Anker
# --------------------------------------------------------------------------- #
def neue_orte(anzahl: int, tag: str, *, gleiche_koordinaten: Optional[tuple] = None):
    from app.user import SavedLocation

    orte = []
    for i in range(1, anzahl + 1):
        lat, lon = gleiche_koordinaten or (neue_breite(), 11.0)
        orte.append(SavedLocation(
            id=f"loc-{i}", name=f"Ort-{tag}-{i}", lat=lat, lon=lon, elevation_m=1000,
        ))
    return orte


def preset_dict(preset_id: str, location_ids: list[str]) -> dict:
    """Aktives Compare-Preset im Bestandsschema (Muster test_compare_alert_metric_gating)."""
    return {
        "id": preset_id, "name": preset_id, "user_id": "default",
        "location_ids": list(location_ids), "schedule": "daily", "weekday": 4,
        "profil": "ALLGEMEIN", "hour_from": 9, "hour_to": 16,
        "empfaenger": ["gregor-test@henemm.com"],
        "letzter_versand": None, "top_ort_letzter_versand": None,
        "created_at": "2026-07-12T00:00:00Z",
    }


def settings_dummy():
    from app.config import Settings

    return Settings(
        smtp_host="dummy.invalid", smtp_user="dummy", smtp_pass="dummy",
        mail_to="dummy@example.com",
    )


def punkt(loc, *, wind: float, fetched_at: Optional[datetime] = None, provider="test-rand"):
    from app.models import SegmentWeatherSummary
    from services.point_weather import PointWeatherData

    return PointWeatherData(
        id=loc.id, name=loc.name, lat=loc.lat, lon=loc.lon, timeseries=None,
        aggregated=SegmentWeatherSummary(wind_max_kmh=wind),
        fetched_at=fetched_at or datetime.now(timezone.utc), provider=provider,
    )


def anker_setzen(uid: str, preset_id: str, loc, *, wind: float = 20.0,
                 alter: Optional[timedelta] = None) -> None:
    from services.compare_weather_snapshot import CompareWeatherSnapshotService

    stand = datetime.now(timezone.utc) - (alter or timedelta(0))
    CompareWeatherSnapshotService(user_id=uid).save(
        preset_id, loc.id, punkt(loc, wind=wind, fetched_at=stand),
    )


def dateien_schreiben(uid: str, preset: dict, orte: list) -> None:
    """Orte und Preset als echte Dateien des Nutzers (fuer ``check_all_*``-Laeufe)."""
    from app.loader import get_data_root, save_location
    from tests.helpers.compare_briefings import write_compare_briefings

    for ort in orte:
        save_location(ort, user_id=uid)
    write_compare_briefings(get_data_root() / "users" / uid, [preset])


def detect(dienst, preset: dict, orte: list) -> list[dict]:
    """Echte Detect-Phase des Aenderungs-Alarms (kein Versand)."""
    alle = {o.id: o for o in orte}
    config = dienst._build_eval_config(preset, 0, alle)
    return dienst._detect_triggered_locations(
        preset["id"], preset["location_ids"], alle, config, (4, 19), preset=preset,
    )


def treffer_ids(treffer: list[dict]) -> list[str]:
    return [t["loc"].id for t in treffer]


# --------------------------------------------------------------------------- #
# Wetter-Rand
# --------------------------------------------------------------------------- #
class WetterRand:
    """Echte ``LocationWeatherSource`` am Provider-Rand (Konstruktor-Naht)."""

    def __init__(self, *, verzoegerung: Optional[dict] = None, fehler=(),
                 wind: float = 50.0, treffpunkt: bool = False,
                 beim_abruf=None) -> None:
        self.verzoegerung = dict(verzoegerung or {})
        self.fehler = set(fehler)
        self.wind = wind
        self.treffpunkt = treffpunkt
        self.beim_abruf = beim_abruf
        self._lock = threading.Lock()
        self._offen = threading.Event()
        self._laufend = 0
        self.max_gleichzeitig = 0
        self.aufrufe: list[dict] = []

    def fetch(self, point_id, lat, lon, start_hour=None, end_hour=None,
              target_date=None, tage_ab_ortstag=None, elevation_m=None, *, user_id):
        from app.models import SegmentWeatherSummary
        from services.point_weather import PointWeatherData

        with self._lock:
            self._laufend += 1
            self.max_gleichzeitig = max(self.max_gleichzeitig, self._laufend)
            self.aufrufe.append({
                "ort": point_id, "thread": threading.current_thread().name,
                "user_id": user_id, "start": time.monotonic(),
            })
            if self._laufend >= 2:
                self._offen.set()
        try:
            if self.beim_abruf is not None:
                self.beim_abruf(point_id)
            if self.treffpunkt:
                self._offen.wait(timeout=1.0)
            pause = self.verzoegerung.get(point_id, 0.0)
            if pause:
                time.sleep(pause)
            if point_id in self.fehler:
                raise RuntimeError(f"Wetterabruf gescheitert: {point_id}")
            return PointWeatherData(
                id=point_id, name=point_id, lat=lat, lon=lon, timeseries=None,
                aggregated=SegmentWeatherSummary(wind_max_kmh=self.wind),
                fetched_at=datetime.now(timezone.utc), provider="test-rand",
            )
        finally:
            with self._lock:
                self._laufend -= 1

    def orte_abgerufen(self) -> list[str]:
        return [a["ort"] for a in self.aufrufe]


# --------------------------------------------------------------------------- #
# Warn-Rand
# --------------------------------------------------------------------------- #
class WarnRand:
    """Echte amtliche Quelle: zustaendig fuer alles, je Koordinate steuerbar."""

    def __init__(self, *, verzoegerung: Optional[dict] = None, treffpunkt: bool = False,
                 beim_abruf=None, name: str = "test-1539s6", ausfall=()) -> None:
        self._name = name
        self.verzoegerung = dict(verzoegerung or {})  # Schluessel: Breite
        # Breiten, an denen die Quelle (nach der Verzoegerung) wirft: der Ort
        # meldet dann Status ``(False, [])`` statt ``(True, [seine Warnung])``.
        self.ausfall = set(ausfall)
        self.treffpunkt = treffpunkt
        self.beim_abruf = beim_abruf
        self._lock = threading.Lock()
        self._offen = threading.Event()
        self._laufend = 0
        self.max_gleichzeitig = 0
        self.aufrufe: list[dict] = []

    @property
    def name(self) -> str:
        return self._name

    def covers(self, lat, lon) -> bool:
        return True

    def fetch(self, lat, lon):
        from services.official_alerts.models import OfficialAlert

        with self._lock:
            self._laufend += 1
            self.max_gleichzeitig = max(self.max_gleichzeitig, self._laufend)
            self.aufrufe.append({
                "lat": lat, "thread": threading.current_thread().name,
                "start": time.monotonic(),
            })
            if self._laufend >= 2:
                self._offen.set()
        try:
            if self.beim_abruf is not None:
                self.beim_abruf(lat)
            if self.treffpunkt:
                self._offen.wait(timeout=1.0)
            pause = self.verzoegerung.get(lat, 0.0)
            if pause:
                time.sleep(pause)
            if lat in self.ausfall:
                raise RuntimeError(f"Warnabruf gescheitert: {lat}")
            jetzt = datetime.now(timezone.utc)
            return [OfficialAlert(
                source=self._name, hazard="wind", level=3, label=f"Sturm {lat}",
                valid_from=jetzt - timedelta(hours=1),
                valid_to=jetzt + timedelta(hours=12), region_label=f"Region {lat}",
            )]
        finally:
            with self._lock:
                self._laufend -= 1

    def lats_abgerufen(self) -> list[float]:
        return [a["lat"] for a in self.aufrufe]


class warnquelle_registriert:
    """Ersetzt die registrierten Warnquellen fuer die Dauer des Blocks (kein Netz)."""

    def __init__(self, quelle) -> None:
        self._quelle = quelle

    def __enter__(self):
        import services.official_alerts.base as b

        self._b = b
        self._backup = list(b._REGISTERED_SOURCES)
        b._REGISTERED_SOURCES.clear()
        b._REGISTERED_SOURCES.append(self._quelle)
        return self._quelle

    def __exit__(self, *exc):
        self._b._REGISTERED_SOURCES.clear()
        self._b._REGISTERED_SOURCES.extend(self._backup)
        return False


def warn_ergebnis(raw: list, queries_by_loc: dict) -> tuple:
    """Vergleichbare Form von ``(raw, queries_by_loc)`` (ohne Objekt-Identitaeten)."""
    roh = [(a.label, tuple(ids)) for a, ids in raw]
    abfragen = {
        loc_id: [(q.scope, q.scope_ids, q.window_end, sorted(q.sources) if q.sources else None,
                  tuple(a.label for a in q.shown)) for q in qs]
        for loc_id, qs in queries_by_loc.items()
    }
    return roh, abfragen
