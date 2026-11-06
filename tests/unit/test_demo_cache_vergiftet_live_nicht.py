"""Issue #2581 — Demo-Vorschau darf Cache, Single-Flight und Prognose-Archiv
echter Abrufe nicht vergiften (AC-1..AC-6).

SPEC: docs/specs/modules/fix_2581_demo_cache_vergiftung.md
Ausfuehrung:
    uv run pytest tests/unit/test_demo_cache_vergiftet_live_nicht.py -v

Kern-Schicht, netzfrei, KEIN Mock/patch/MagicMock. Echte `FixtureProvider` auf
zwei Verzeichnissen (Satz 1 = 2 C "Demo", Satz 2 = 22 C "live"). Der
Live-Gegenpart ist eine Unterklasse OHNE `cache_namespace` (Name bleibt
"openmeteo", wie der Open-Meteo-Rueckfall) und zaehlt seine Abrufe. Der
Wetter-Cache ist der geteilte Prozess-Singleton und wird INNERHALB eines
Laufs nie geleert; die autouse-Fixture unten raeumt nur zwischen Tests.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.models import GPXPoint, TripSegment
from providers.fixture import FixtureProvider
from services.segment_weather import SegmentWeatherService, fetch_night_weather
from services.weather_cache import (
    get_shared_weather_cache,
    reset_shared_weather_cache_for_tests,
)

WORKTREE = Path(__file__).resolve().parents[2]

DEMO_TEMP = 2.0
LIVE_TEMP = 22.0
LAT, LON = 47.2692, 11.4041  # Innsbruck (naechster Fixture-Ort)


# --- Pruefling relativ zur Testdatei (Pfadregel #1409) ---------------------
def test_pruefling_stammt_aus_diesem_checkout():
    import services.segment_weather as modul

    assert Path(modul.__file__).resolve().is_relative_to(WORKTREE), (
        f"Pruefling stammt aus einem fremden Checkout: {modul.__file__}"
    )


# --- Testdaten --------------------------------------------------------------
class _LiveGegenpart(FixtureProvider):
    """Simuliert den echten Provider im Rueckfall: Name "openmeteo", KEIN
    Namensraum. `cache_namespace = None` wird ausdruecklich gesetzt, damit die
    Unterklasse das (kuenftige) Klassenmerkmal des FixtureProvider nicht erbt."""

    cache_namespace = None

    def __init__(self, fixture_dir: str) -> None:
        super().__init__(fixture_dir)
        self.abrufe = 0

    def fetch_forecast(self, *args, **kwargs):
        self.abrufe += 1
        return super().fetch_forecast(*args, **kwargs)


class _ZaehlenderDemo(FixtureProvider):
    """Echter FixtureProvider (erbt `cache_namespace`), nur mit Abrufzaehler."""

    def __init__(self, fixture_dir: str) -> None:
        super().__init__(fixture_dir)
        self.abrufe = 0

    def fetch_forecast(self, *args, **kwargs):
        self.abrufe += 1
        return super().fetch_forecast(*args, **kwargs)


def _fixture_verzeichnis(basis: Path, name: str, temperatur: float) -> str:
    ziel = basis / name
    ziel.mkdir(parents=True, exist_ok=True)
    daten = [
        {"t2m_c": temperatur, "wind10m_kmh": 10.0, "gust_kmh": 20.0,
         "precip_1h_mm": 0.0}
        for _ in range(72)
    ]
    for datei in ("innsbruck.json", "stubai.json", "zillertal.json"):
        (ziel / datei).write_text(json.dumps({"data": daten}), encoding="utf-8")
    return str(ziel)


@pytest.fixture
def demo(tmp_path):
    return _ZaehlenderDemo(_fixture_verzeichnis(tmp_path, "satz1", DEMO_TEMP))


@pytest.fixture
def live(tmp_path):
    return _LiveGegenpart(_fixture_verzeichnis(tmp_path, "satz2", LIVE_TEMP))


@pytest.fixture(autouse=True)
def _cache_und_archiv_zwischen_tests_raeumen(monkeypatch):
    from services import forecast_capture

    monkeypatch.setenv("GZ_FORECAST_CAPTURE", "1")
    reset_shared_weather_cache_for_tests()
    forecast_capture.reset_capture_state()
    yield
    reset_shared_weather_cache_for_tests()
    forecast_capture.reset_capture_state()


def _segment(segment_id=1) -> TripSegment:
    # Sichere Tagesstunde: nie ueber Mitternacht, unabhaengig von der Uhrzeit.
    beginn = datetime.now(timezone.utc).replace(
        hour=10, minute=0, second=0, microsecond=0
    )
    punkt = GPXPoint(lat=LAT, lon=LON, elevation_m=1200.0)
    return TripSegment(
        segment_id=segment_id, start_point=punkt, end_point=punkt,
        start_time=beginn, end_time=beginn + timedelta(hours=2),
        duration_hours=2.0, distance_km=0.0, ascent_m=0, descent_m=0,
    )


def _abruf(provider, user_id="nutzer-a", segment=None):
    service = SegmentWeatherService(provider)  # geteilter Cache, wie in Prod
    return service.fetch_segment_weather(
        segment or _segment(), enrich_ensemble=False, enrich_snow=False,
        user_id=user_id,
    )


def _archiv_zeilen() -> list[dict]:
    from app.loader import get_data_root

    ordner = get_data_root() / "diagnostics"
    zeilen: list[dict] = []
    for pfad in sorted(ordner.glob("forecast_capture_*.jsonl")):
        zeilen += [json.loads(z) for z in pfad.read_text(encoding="utf-8").splitlines()
                   if z.strip()]
    return zeilen


# --- AC-1: beide Reihenfolgen, ohne Cache-Leeren dazwischen ----------------
def test_ac1_erst_demo_dann_live_liefert_je_eigene_werte(demo, live):
    d = _abruf(demo)
    l = _abruf(live)

    assert d.aggregated.temp_max_c == DEMO_TEMP
    assert l.aggregated.temp_max_c == LIVE_TEMP, (
        f"Live-Abruf erbt Demo-Beispielwerte aus dem Cache: {l.aggregated.temp_max_c}"
    )
    assert live.abrufe == 1, "Live muss einen EIGENEN Anbieter-Abruf verbrauchen"


def test_ac1_erst_live_dann_demo_liefert_je_eigene_werte(demo, live):
    l = _abruf(live)
    d = _abruf(demo)

    assert l.aggregated.temp_max_c == LIVE_TEMP
    assert d.aggregated.temp_max_c == DEMO_TEMP, (
        f"Demo zeigt echte Live-Werte aus dem Cache: {d.aggregated.temp_max_c}"
    )
    assert demo.abrufe == 1, "Demo muss einen EIGENEN Abruf verbrauchen"


# --- AC-2: Prognose-Archiv -------------------------------------------------
def test_ac2_demo_schreibt_nichts_live_schreibt_genau_eine_zeile(demo, live):
    vorher = len(_archiv_zeilen())

    _abruf(demo)
    nach_demo = _archiv_zeilen()
    assert len(nach_demo) == vorher, (
        f"Demo-Abruf schrieb {len(nach_demo) - vorher} Zeile(n) ins Prognose-Archiv"
    )

    _abruf(live)
    nach_live = _archiv_zeilen()
    assert len(nach_live) == vorher + 1
    assert nach_live[-1]["provider"] == "openmeteo"


# --- AC-3: Trennung entlang der Datenquelle, nicht des Nutzers -------------
def test_ac3_zwei_nutzer_live_teilt_cache_demo_bleibt_getrennt(demo, live):
    d_a = _abruf(demo, user_id="nutzer-a")
    l_b = _abruf(live, user_id="nutzer-b")
    l_a = _abruf(live, user_id="nutzer-a")

    assert d_a.aggregated.temp_max_c == DEMO_TEMP
    assert l_b.aggregated.temp_max_c == LIVE_TEMP, "Live von B zeigt Beispielwerte"
    assert l_a.aggregated.temp_max_c == LIVE_TEMP, "Live von A zeigt Beispielwerte"
    assert live.abrufe == 1, (
        f"B und A teilen sich EINEN Live-Eintrag, tatsaechlich {live.abrufe} Abrufe"
    )
    assert demo.abrufe == 1


# --- AC-4: Nachtabruf der Demo-Vorschau ------------------------------------
def _letztes_segment(provider):
    return _abruf(provider, user_id="nutzer-a")


def test_ac4_nacht_demo_nach_live_enthaelt_nur_fixture_werte(demo, live):
    ziel = _letztes_segment(live)  # fuellt den Live-Eintrag am Ankunftspunkt
    nacht_live = fetch_night_weather(ziel, provider=live, user_id="nutzer-a")
    nacht_demo = fetch_night_weather(ziel, provider=demo, user_id="nutzer-a")

    assert nacht_live is not None and nacht_live.data
    assert nacht_demo is not None and nacht_demo.data
    assert {p.t2m_c for p in nacht_live.data} == {LIVE_TEMP}
    assert {p.t2m_c for p in nacht_demo.data} == {DEMO_TEMP}, (
        f"Demo-Nacht enthaelt Live-Werte: {sorted({p.t2m_c for p in nacht_demo.data})}"
    )
    schluessel = list(get_shared_weather_cache()._cache.keys())
    assert any("fixture:" in k for k in schluessel), (
        f"Kein Cache-Schluessel mit Namensraum 'fixture:': {schluessel}"
    )


def test_ac4_nacht_live_nach_demo_enthaelt_nie_fixture_werte(demo, live):
    ziel = _letztes_segment(demo)
    nacht_demo = fetch_night_weather(ziel, provider=demo, user_id="nutzer-a")
    nacht_live = fetch_night_weather(ziel, provider=live, user_id="nutzer-a")

    assert nacht_demo is not None and nacht_live is not None
    assert {p.t2m_c for p in nacht_demo.data} == {DEMO_TEMP}
    assert {p.t2m_c for p in nacht_live.data} == {LIVE_TEMP}, (
        f"Live-Nacht enthaelt Demo-Werte: {sorted({p.t2m_c for p in nacht_live.data})}"
    )


# --- AC-5: Name bleibt, nur der interne Schluessel traegt den Namensraum ----
def test_ac5_name_bleibt_openmeteo_modellkennung_traegt_namensraum(demo):
    assert FixtureProvider(".").name == "openmeteo"
    assert demo.name == "openmeteo"
    assert getattr(FixtureProvider, "cache_namespace", None) == "fixture"

    ergebnis = _abruf(demo)
    assert ergebnis.provider == "openmeteo"

    assert SegmentWeatherService(demo)._resolve_model_id(LAT, LON) == "fixture:openmeteo"


# --- AC-6: Provider ohne Merkmal bleiben unveraendert ----------------------
class _OhneMerkmal:
    @property
    def name(self) -> str:
        return "openmeteo"


class _NamensraumNone:
    cache_namespace = None

    @property
    def name(self) -> str:
        return "geosphere"


class _NamensraumLeer:
    cache_namespace = ""

    @property
    def name(self) -> str:
        return "openmeteo"


class _MitSelectModel:
    @property
    def name(self) -> str:
        return "openmeteo"

    def select_model(self, lat, lon):
        return "icon_d2", 2.2, "grid_point"


def test_ac6_provider_ohne_namensraum_behalten_ihre_modellkennung():
    assert SegmentWeatherService(_OhneMerkmal())._resolve_model_id(LAT, LON) == "openmeteo"
    assert SegmentWeatherService(_NamensraumNone())._resolve_model_id(LAT, LON) == "geosphere"
    assert SegmentWeatherService(_NamensraumLeer())._resolve_model_id(LAT, LON) == "openmeteo"
    assert SegmentWeatherService(_MitSelectModel())._resolve_model_id(LAT, LON) == "icon_d2"


def test_ac6_provider_mit_namensraum_und_select_model_bekommt_praefix():
    class _Beides(_MitSelectModel):
        cache_namespace = "fixture"

    assert SegmentWeatherService(_Beides())._resolve_model_id(LAT, LON) == "fixture:icon_d2"


def test_ac6_live_gegenpart_schreibt_weiter_ins_archiv(live):
    vorher = len(_archiv_zeilen())
    _abruf(live)
    assert len(_archiv_zeilen()) == vorher + 1
