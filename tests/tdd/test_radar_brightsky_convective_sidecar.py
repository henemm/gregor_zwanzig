"""TDD RED — Issue #2464: Konvektions-Sidecar fuer den DE-Radar-Nowcast
(BrightSky/RADOLAN) und `convective_checked` im Radar-Cache.

SPEC: docs/specs/modules/fix_2464_brightsky_konvektions_sidecar.md

Bisher liefert `_fetch_brightsky` nur Niederschlagsmengen; `is_convective`/
`hail` bleiben fuer JEDEN DE-Frame `False` (INCA und Korsika haben einen
Sidecar, DE nicht). Ausserdem wird `convective_checked` nicht mitgecacht: ein
Cache-Treffer meldet immer "geprueft".

Mock-frei im Sinn der Test-Politik: es gibt EINE Aussengrenze — den HTTP-Client
(`httpx.Client`). Hinter ihr laufen BrightSky-Parser (auf der aufgezeichneten,
gekuerzten Fixture `tests/fixtures/brightsky/radar_de_kurz.json`),
Open-Meteo-Parser, `_merge_convective`, Cache, Ableitung und Renderer real.

Die Fixture: Muenchen (48,14 / 11,58), Live-Antwort vom 2026-09-30, 25 Frames
ab 16:45 UTC im 5-Min-Takt, auf 5x5 Zellen gekuerzt; die Zielzelle
(`latlon_position` x=2,y=2) traegt ab 17:20 UTC bis 18:10 UTC den Rohwert 1
(= 0,01 mm/5 min = 0,12 mm/h).

Pfadregel #1409: alles relativ zu DIESER Datei.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from services.radar_cache import (  # noqa: E402
    RadarNowcastCacheService,
    reset_shared_radar_cache_for_tests,
)
from services.radar_service import RadarNowcastService  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "brightsky" / "radar_de_kurz.json"

# Muenchen -- innerhalb RADOLAN, ausserhalb INCA/Korsika.
_DE_LAT, _DE_LON = 48.14, 11.58
# Hamburg -- zweiter DE-Ort (AC-6).
_HH_LAT, _HH_LON = 53.55, 9.99
# Wien (INCA) und Vizzavona (Korsika) fuer AC-4.
_AT_LAT, _AT_LON = 48.21, 16.37
_KORS_LAT, _KORS_LON = 42.1244, 9.1339

# Gestellte Uhr: 5 Minuten nach dem ersten Fixture-Frame (16:45 UTC).
_NOW = datetime(2026, 9, 30, 16, 50, tzinfo=timezone.utc)

# Sidecar: 15-Min-Raster. Nasse Fixture-Frames: 17:20 .. 18:10 UTC.
#   17:15 -> 0 | 17:30 -> 95 | 17:45 -> 96 | 18:00 -> 99 | danach KEIN Wert
_SIDECAR_CODES = {
    "2026-09-30T17:15": 0,
    "2026-09-30T17:30": 95,
    "2026-09-30T17:45": 96,
    "2026-09-30T18:00": 99,
}
_SIDECAR_KEINE_GEWITTER = {k: 0 for k in _SIDECAR_CODES}


@pytest.fixture(autouse=True)
def _isolation(monkeypatch):
    """Kein Offline-Schalter (der conftest setzt ihn autouse und wuerde den
    Pfad kurzschliessen), frischer Prozess-Cache."""
    monkeypatch.delenv("GZ_TEST_FIXTURE_DIR", raising=False)
    reset_shared_radar_cache_for_tests()
    yield
    reset_shared_radar_cache_for_tests()


# ---------------------------------------------------------------------------
# Aussengrenze: httpx.Client
# ---------------------------------------------------------------------------

class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def _install_http(monkeypatch, sidecar, brightsky="fixture"):
    """Ersetzt `httpx.Client` durch einen Client, der BrightSky aus der
    Fixture und Open-Meteo gemaess `sidecar` beantwortet.

    sidecar: dict {zeit: code} | "leer" | "fehler"
    brightsky: "fixture" | "leer" | "fehler"
    Gibt den Aufrufzaehler {"brightsky": n, "openmeteo": n} zurueck.
    """
    import httpx

    zaehler = {"brightsky": 0, "openmeteo": 0, "openmeteo_urls": []}
    fixture_payload = json.loads(FIXTURE.read_text())

    class _Client:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url, *a, **kw):
            if "brightsky" in url:
                zaehler["brightsky"] += 1
                if brightsky == "fehler":
                    raise httpx.ConnectError("brightsky down")
                if brightsky == "leer":
                    return _Resp({"radar": [], "latlon_position": {"x": 0, "y": 0}})
                return _Resp(fixture_payload)
            zaehler["openmeteo"] += 1
            zaehler["openmeteo_urls"].append(url)
            if sidecar == "fehler":
                raise httpx.ConnectError("open-meteo down")
            if sidecar == "leer":
                return _Resp({"minutely_15": {"time": [], "precipitation": [], "weather_code": []}})
            zeiten = list(sidecar)
            return _Resp({"minutely_15": {
                "time": zeiten,
                "precipitation": [0.0] * len(zeiten),
                "weather_code": [sidecar[z] for z in zeiten],
            }})

    monkeypatch.setattr(httpx, "Client", _Client)
    return zaehler


def _service(cache=None):
    return RadarNowcastService(now_fn=lambda: _NOW, cache=cache)


def _frame_at(frames, hhmm):
    h, m = map(int, hhmm.split(":"))
    ts = datetime(2026, 9, 30, h, m, tzinfo=timezone.utc)
    return next(f for f in frames if f.timestamp == ts)


# ===========================================================================
# AC-7: gekuerzte, aufgezeichnete Fixture wird vom Parser verarbeitet
# ===========================================================================

def test_ac7_fixture_ist_klein_und_parser_liefert_frames(monkeypatch):
    """AC-7: Fixture < 1 MB; Parser macht daraus 25 Frames mit korrekt
    umgerechnetem `precip_mm_h` (Rohwert 1 -> 0,12 mm/h) und Zeitstempeln."""
    assert FIXTURE.exists(), "tests/fixtures/brightsky/radar_de_kurz.json fehlt"
    assert FIXTURE.stat().st_size < 1_000_000

    from providers.brightsky import BrightSkyProvider

    _install_http(monkeypatch, _SIDECAR_CODES)
    frames = BrightSkyProvider().fetch_radar(_DE_LAT, _DE_LON)

    assert len(frames) == 25
    assert frames[0].timestamp == datetime(2026, 9, 30, 16, 45, tzinfo=timezone.utc)
    assert frames[-1].timestamp == datetime(2026, 9, 30, 18, 45, tzinfo=timezone.utc)
    assert _frame_at(frames, "17:15").precip_mm_h == pytest.approx(0.0)
    assert _frame_at(frames, "17:20").precip_mm_h == pytest.approx(0.12)
    assert _frame_at(frames, "18:10").precip_mm_h == pytest.approx(0.12)
    assert _frame_at(frames, "18:15").precip_mm_h == pytest.approx(0.0)


# ===========================================================================
# AC-1: Gewitter/Hagel aus dem Sidecar erreichen den DE-Radar-Frame
# ===========================================================================

def test_ac1_sidecar_setzt_is_convective_und_hail_auf_de_frames(monkeypatch):
    """AC-1: 95 -> Gewitter, 96/99 -> Gewitter + Hagel; Frames ausserhalb des
    Sidecar-Fensters (18:10) und mit Code 0 (17:20) bleiben False."""
    _install_http(monkeypatch, _SIDECAR_CODES)

    frames = _service()._fetch_brightsky(_DE_LAT, _DE_LON)

    assert _frame_at(frames, "17:30").is_convective is True
    assert _frame_at(frames, "17:30").hail is False, "95 ist Gewitter OHNE Hagel (#2205)"
    assert _frame_at(frames, "17:45").is_convective is True
    assert _frame_at(frames, "17:45").hail is True
    assert _frame_at(frames, "18:00").is_convective is True
    assert _frame_at(frames, "18:00").hail is True, "99 traegt Hagel"
    assert _frame_at(frames, "17:20").is_convective is False, "Code 0 -> kein Gewitter"
    assert _frame_at(frames, "18:10").is_convective is False, (
        "ausserhalb des Sidecar-Fensters (> 5 Min) bleibt False"
    )


def test_ac1_nowcast_ergebnis_meldet_gewitter_und_hagel(monkeypatch):
    """AC-1 am Ergebnis: `NowcastResult.is_convective`, Intensitaet
    'Gewitter mit Hagel', `convective_checked` True, Quelle 'radar'."""
    _install_http(monkeypatch, _SIDECAR_CODES)

    result = _service().get_nowcast(_DE_LAT, _DE_LON)

    assert result.source == "radar"
    assert result.is_convective is True
    assert result.convective_checked is True
    from services.radar_service import INTENSITY_CONVECTIVE
    assert result.intensity_label == INTENSITY_CONVECTIVE


def test_ac1_ohne_gewittercode_kein_gewitter(monkeypatch):
    """Gegenprobe: Sidecar OK, aber nur Code 0 -> kein Gewitter, geprueft."""
    _install_http(monkeypatch, _SIDECAR_KEINE_GEWITTER)

    result = _service().get_nowcast(_DE_LAT, _DE_LON)

    assert result.is_convective is False
    assert result.convective_checked is True


# ===========================================================================
# AC-2: Sidecar leer / gedrosselt / Fehler -> nie als "kein Gewitter" kaschiert
# ===========================================================================

def _ac2_pruefen(result, referenz):
    assert result.convective_checked is False
    assert result.is_convective is False
    assert result.data_unavailable is False, "BrightSky-Regen ist da, nicht 'nicht verfuegbar'"
    assert result.throttled is False
    assert result.onset_minutes == referenz.onset_minutes
    assert result.window_precip_mm == pytest.approx(referenz.window_precip_mm)
    text = _service().format_now_text(result, englisch=True)
    text_de = _service().format_now_text(result)
    assert "Storm check not available." in text
    assert "Gewitter-Check nicht verfügbar." in text_de


@pytest.fixture
def _referenz(monkeypatch):
    """Erfolgsfall ohne Gewitter: Niederschlag/Beginn als Vergleichswert."""
    _install_http(monkeypatch, _SIDECAR_KEINE_GEWITTER)
    ref = _service().get_nowcast(_DE_LAT, _DE_LON)
    reset_shared_radar_cache_for_tests()
    assert ref.onset_minutes is not None, "Fixture muss Regen im Fenster liefern"
    return ref


def test_ac2_leerer_sidecar(monkeypatch, _referenz):
    _install_http(monkeypatch, "leer")
    _ac2_pruefen(_service().get_nowcast(_DE_LAT, _DE_LON), _referenz)


def test_ac2_sidecar_wirft_exception(monkeypatch, _referenz):
    _install_http(monkeypatch, "fehler")
    _ac2_pruefen(_service().get_nowcast(_DE_LAT, _DE_LON), _referenz)


def test_ac2_sidecar_vom_budget_gate_gedrosselt(monkeypatch, _referenz):
    from services.forecast_budget import ForecastBudgetGate

    zaehler = _install_http(monkeypatch, _SIDECAR_CODES)
    monkeypatch.setattr(ForecastBudgetGate, "allow", lambda self, priority, now=None: False)

    result = _service().get_nowcast(_DE_LAT, _DE_LON)

    assert zaehler["openmeteo"] == 0, "gedrosselt -> kein Open-Meteo-Call"
    _ac2_pruefen(result, _referenz)


def test_ac1_hoehe_erreicht_den_sidecar_request(monkeypatch):
    """Die Hoehe aus get_nowcast() muss als elevation=1800 im Open-Meteo-
    Sidecar-Request stehen; ohne Hoehe kein elevation-Parameter."""
    zaehler = _install_http(monkeypatch, _SIDECAR_CODES)
    _service().get_nowcast(_DE_LAT, _DE_LON, elevation_m=1800)
    assert zaehler["openmeteo"] == 1
    assert "elevation=1800" in zaehler["openmeteo_urls"][0]

    reset_shared_radar_cache_for_tests()
    ohne = _install_http(monkeypatch, _SIDECAR_CODES)
    _service().get_nowcast(_DE_LAT, _DE_LON)
    assert ohne["openmeteo"] == 1
    assert "elevation" not in ohne["openmeteo_urls"][0]


# ===========================================================================
# AC-3: kein Sidecar ohne Frames; Offline-Modus bleibt netzfrei
# ===========================================================================

def test_ac3_kein_sidecar_bei_leerer_brightsky_antwort(monkeypatch):
    zaehler = _install_http(monkeypatch, _SIDECAR_CODES, brightsky="leer")
    assert _service()._fetch_brightsky(_DE_LAT, _DE_LON) == []
    assert zaehler["openmeteo"] == 0


def test_ac3_kein_sidecar_bei_brightsky_fehler(monkeypatch):
    zaehler = _install_http(monkeypatch, _SIDECAR_CODES, brightsky="fehler")
    assert _service()._fetch_brightsky(_DE_LAT, _DE_LON) == []
    assert zaehler["openmeteo"] == 0


def test_ac3_offline_modus_netzfrei(monkeypatch):
    monkeypatch.setenv("GZ_TEST_FIXTURE_DIR", str(ROOT / "tests" / "fixtures"))
    zaehler = _install_http(monkeypatch, _SIDECAR_CODES)
    assert _service()._fetch_brightsky(_DE_LAT, _DE_LON) == []
    assert (zaehler["brightsky"], zaehler["openmeteo"]) == (0, 0)


# ===========================================================================
# AC-4: convective_checked ueberlebt den Cache (alle Regionen)
# ===========================================================================

def test_ac4_cache_entry_traegt_flag_direkt():
    """Direkttest put/get: Flag wird gespeichert; Default True."""
    from providers.brightsky import RadarFrame

    cache = RadarNowcastCacheService()
    frames = [RadarFrame(timestamp=_NOW, precip_mm_h=1.0)]
    cache.put(1.0, 2.0, "radolan", frames, "radar", now=_NOW, convective_checked=False)
    assert cache.get(1.0, 2.0, "radolan", now=_NOW).convective_checked is False

    cache.put(3.0, 4.0, "radolan", frames, "radar", now=_NOW)
    assert cache.get(3.0, 4.0, "radolan", now=_NOW).convective_checked is True


def _zweimal_abfragen(lat, lon, monkeypatch, sidecar):
    zaehler = _install_http(monkeypatch, sidecar)
    cache = RadarNowcastCacheService()
    erster = _service(cache).get_nowcast(lat, lon)
    calls_nach_erstem = dict(zaehler)
    zweiter = _service(cache).get_nowcast(lat, lon)
    assert zaehler == calls_nach_erstem, "zweiter Aufruf muss ein Cache-Treffer sein"
    return erster, zweiter


def test_ac4_de_cache_treffer_bei_sidecar_ausfall(monkeypatch):
    erster, zweiter = _zweimal_abfragen(_DE_LAT, _DE_LON, monkeypatch, "fehler")
    assert erster.convective_checked is False
    assert zweiter.convective_checked is False, "Treffer darf nicht 'geprueft' behaupten"


def test_ac4_de_cache_treffer_bei_erfolg(monkeypatch):
    erster, zweiter = _zweimal_abfragen(_DE_LAT, _DE_LON, monkeypatch, _SIDECAR_CODES)
    assert erster.convective_checked is True
    assert zweiter.convective_checked is True
    assert zweiter.is_convective is True


def test_ac4_inca_cache_treffer_bei_sidecar_ausfall(monkeypatch):
    """INCA: GeoSphere-Frames als Double am Provider-Rand, Sidecar faellt aus."""
    from providers.brightsky import RadarFrame
    from providers.geosphere import GeoSphereProvider

    zaehler = _install_http(monkeypatch, "fehler")
    rufe_inca = {"n": 0}

    class _TS:
        class _DP:
            def __init__(self, ts):
                self.ts = ts
                self.precip_1h_mm = 1.0

        def __init__(self):
            self.data = [self._DP(_NOW + timedelta(minutes=15 * i)) for i in range(1, 6)]

    def _fake_nowcast(self, lat, lon):
        rufe_inca["n"] += 1
        return _TS()

    monkeypatch.setattr(GeoSphereProvider, "fetch_nowcast", _fake_nowcast)
    # AT-Ort ausserhalb RADOLAN: BrightSky wird gar nicht gefragt.
    cache = RadarNowcastCacheService()
    erster = _service(cache).get_nowcast(_AT_LAT, _AT_LON)
    zweiter = _service(cache).get_nowcast(_AT_LAT, _AT_LON)

    assert erster.source == "INCA" and rufe_inca["n"] == 1, "zweiter Aufruf = Cache-Treffer"
    assert erster.convective_checked is False
    assert zweiter.convective_checked is False
    del zaehler, RadarFrame


def test_ac4_korsika_cache_treffer_bei_sidecar_ausfall(monkeypatch):
    """Korsika: AROME-FR liefert Frames, ARPAE-Sidecar faellt aus (leer)."""
    from providers.brightsky import RadarFrame

    rufe = {"arome": 0}

    def _arome(self, lat, lon, elevation_m=None):
        rufe["arome"] += 1
        return [RadarFrame(timestamp=_NOW + timedelta(minutes=15 * i), precip_mm_h=2.0)
                for i in range(1, 6)]

    def _arpae(self, lat, lon, elevation_m=None):
        return []

    monkeypatch.setattr(RadarNowcastService, "_fetch_arome_france_hd", _arome)
    monkeypatch.setattr(RadarNowcastService, "_fetch_italy_arpae", _arpae)

    cache = RadarNowcastCacheService()
    erster = _service(cache).get_nowcast(_KORS_LAT, _KORS_LON)
    zweiter = _service(cache).get_nowcast(_KORS_LAT, _KORS_LON)

    assert rufe["arome"] == 1, "zweiter Aufruf = Cache-Treffer"
    assert erster.convective_checked is False
    assert zweiter.convective_checked is False


# ===========================================================================
# AC-5: Alarm und Briefing aus demselben NowcastResult
# ===========================================================================

def test_ac5_gewitter_und_marker_aus_demselben_ergebnis(monkeypatch):
    from services.trip_alert import radar_alert_due

    _install_http(monkeypatch, _SIDECAR_CODES)
    ergebnis = _service().get_nowcast(_DE_LAT, _DE_LON)

    # Alarm-Pfad: Gewitter/Hagel kommt aus demselben Ergebnis an.
    assert ergebnis.is_convective is True
    assert radar_alert_due(ergebnis, 240) is True
    # Renderer: bei geprueft-Ergebnis KEIN Marker, reine Daten.
    text = _service().format_now_text(ergebnis, englisch=True)
    text_de = _service().format_now_text(ergebnis)
    assert "Storm check not available." not in text
    assert "Gewitter-Check nicht verfügbar." not in text_de

    reset_shared_radar_cache_for_tests()
    _install_http(monkeypatch, "fehler")
    ungeprueft = _service().get_nowcast(_DE_LAT, _DE_LON)
    assert ungeprueft.convective_checked is False
    assert "Storm check not available." in _service().format_now_text(ungeprueft, englisch=True)
    assert "Gewitter-Check nicht verfügbar." in _service().format_now_text(ungeprueft)


# ===========================================================================
# AC-6: keine Vermischung zwischen Orten / Nutzern
# ===========================================================================

def test_ac6_zwei_orte_teilen_kein_ergebnis(monkeypatch):
    """Ort A (Muenchen) mit Gewitter-Sidecar, Ort B (Hamburg) ohne, geteilter
    Cache: Ort B bleibt ungestoert, je Ort korrektes `convective_checked`."""
    import httpx

    fixture_payload = json.loads(FIXTURE.read_text())

    class _Client:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url, *a, **kw):
            if "brightsky" in url:
                return _Resp(fixture_payload)
            # Open-Meteo: Gewitter nur fuer Muenchen (lat=48.14), Hamburg faellt aus.
            if "latitude=48.14" in url:
                zeiten = list(_SIDECAR_CODES)
                return _Resp({"minutely_15": {
                    "time": zeiten, "precipitation": [0.0] * len(zeiten),
                    "weather_code": [_SIDECAR_CODES[z] for z in zeiten]}})
            raise httpx.ConnectError("sidecar hamburg down")

    monkeypatch.setattr(httpx, "Client", _Client)
    cache = RadarNowcastCacheService()

    a = _service(cache).get_nowcast(_DE_LAT, _DE_LON, user_id="user-a")
    b = _service(cache).get_nowcast(_HH_LAT, _HH_LON, user_id="user-b")

    assert a.is_convective is True and a.convective_checked is True
    assert b.is_convective is False and b.convective_checked is False


def test_ac6_cache_schluessel_enthaelt_region_und_hoehe():
    """Schluessel bleibt Koordinate + Region + Hoehe (unveraendert)."""
    cache = RadarNowcastCacheService()
    k1 = cache._key(48.14, 11.58, "radolan", 500)
    assert k1 != cache._key(48.14, 11.58, "inca", 500)
    assert k1 != cache._key(48.14, 11.58, "radolan", 900)
    assert k1 != cache._key(53.55, 9.99, "radolan", 500)
