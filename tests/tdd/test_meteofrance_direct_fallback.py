"""TDD RED — #1143: echter Météo-France-AROME-Direktprovider fuer FR.

Spec: docs/specs/modules/provider_meteofrance.md (AC-1..AC-7).

Der in #1141 verdrahtete Stub `fr_direct` (`RegionalStubProvider`, wirft
immer `ProviderNotImplementedError`) soll durch die neue Klasse
`MeteoFranceDirectProvider` (CREATE `src/providers/meteofrance.py`) ersetzt
werden. Zusaetzlich wird die FR-Router-Box in `region_routing.py` von
`max_lon=8.3` auf `max_lon=9.7` erweitert, damit Korsika/GR20 ueberhaupt auf
`fr_direct` geroutet wird.

MOCK-FREI (KRITISCHE PROJEKT-REGEL):
Kein `Mock()`, kein `patch()`, kein `MagicMock`.
- AC-2/AC-5: rein deterministische Aufrufe von `direct_provider_for`, kein
  HTTP noetig.
- AC-3/AC-4: echte lokale `ThreadingHTTPServer` (Vorbild
  `test_issue_1142_geosphere_direct_fallback.py`), `monkeypatch.setattr` nur
  auf Host/URL-Konstanten, nie auf Verhalten/Exceptions selbst.
- AC-6/AC-7: reine Unit-Tests gegen Hilfsfunktionen, kein HTTP.
- AC-1: aufgezeichnetes GRIB2-Response-Fixture (wird ERST in der
  GREEN-Phase echt bei Météo-France aufgezeichnet), ueber einen lokalen
  Server ausgeliefert.

AC-Test-Mapping (Pflicht, aus Spec):
| AC       | Testfunktion                                                     |
|----------|-------------------------------------------------------------------|
| AC-2     | test_direct_provider_for_fr_box_after_korsika_widening (Teil 1)   |
| AC-5     | test_direct_provider_for_fr_box_after_korsika_widening (Teil 2+3) |
| AC-3     | test_fetch_forecast_4xx_propagates_without_retry                  |
| AC-4     | test_fetch_forecast_503_exhausts_five_retries_then_raises         |
| AC-4 e2e | test_seam_falls_back_past_meteofrance_5xx_to_openmeteo_error      |
| AC-6     | test_vector_to_speed_kmh_matches_geosphere_formula                 |
| AC-1     | test_fetch_forecast_parses_recorded_arome_grib2_fixture            |

Fix-Schleife (Adversary #1143, Runde 1, 2026-07-23):
- F003: AC-7 entfaellt als eigener Test — die empirisch gemessene
  TOTAL_PRECIPITATION-Semantik (Rate kg/(m^2*s) je 1h-Fenster, s.
  `meteofrance.py`-Moduldocstring) ist keine kumulierte Reihe, die
  AC-7-Hilfsfunktion `_precip_1h_from_cumulative` war toter Code und
  wurde entfernt; die spec-AC-7 wurde entsprechend korrigiert
  (`docs/specs/modules/provider_meteofrance.md`).
- F001: `test_fetch_forecast_parses_recorded_arome_grib2_fixture` liefert
  jetzt PFAD-/PARAMETER-abhaengig vier unterschiedliche, echt
  aufgezeichnete Fixtures (Temp/U/V/Precip) statt eines einzigen
  Temperatur-Fixtures fuer alle Coverages, plus Plausibilitaets-Bounds.
- F002: `test_fetch_forecast_500_is_retried_like_503` deckt 500 zusaetzlich
  zu 503 ab (`RETRY_STATUS_CODES` erweitert).
- F004: `test_fetch_forecast_exceeds_wall_clock_deadline_then_raises`
  deckt das neue Gesamt-Zeitbudget (`FETCH_DEADLINE_SECONDS`) ab.

Fix-Schleife (Adversary #1143, Runde 2, 2026-07-23):
- F003 (Nachbesserung): die Runde-1-Analyse ("`rate * 3600` ergibt korrekt
  mm") war FALSCH — das GDAL-Tag `kg/(m^2*s)` ist ein generisches
  Fehletikett, tatsaechlich ist der Rohwert laut GRIB-PDS
  (`typeOfStatisticalProcessing=1`, Accumulation, `lengthOfTimeRange=1h`)
  bereits die 1h-Regenmenge in mm. Beweis: Alpenzelle 44.04N/7.84E,
  2026-07-23T15:00Z, Rohwert `5.178` -> `*3600` = 18641,6 mm/h (unmoeglich)
  vs. Direktwert `5.2` mm/h (plausibel). `precip_mm = round(p, 1)` statt
  `round(p * 3600, 1)`. Neuer Regressionstest
  `test_fetch_forecast_uses_recorded_nonzero_precip_fixture_without_rate_conversion`
  gegen ein echt aufgezeichnetes NICHT-NULL-Precip-Fixture (das
  urspruengliche Bug war mit dem 0,0-Paris-Fixture unsichtbar).

Hinweis AC-2/AC-5-Kombination: AC-2 ("außerhalb aller Boxen → != fr_direct")
ist fuer sich genommen bereits HEUTE gruen — die Box-Erweiterung fuegt nur
Flaeche hinzu, entfernt keine; ein Punkt, der auch nach der Erweiterung
außerhalb liegt, lag also schon vorher außerhalb. Isoliert waere AC-2 damit
kein echter RED-Test. Er wird deshalb mit den (heute echt roten)
AC-5-Assertions in einer Funktion kombiniert, wie von der Workflow-Vorgabe
("alle Tests ROT") verlangt.

RED heute (Sammel-Grund): `src/providers/meteofrance.py` existiert noch
nicht (ImportError/ModuleNotFoundError in jedem AC-1/3/4/6/7-Test), und die
FR-Router-Box in `region_routing.py` steht noch bei `max_lon=8.3`
(AssertionError in AC-5).
"""
from __future__ import annotations

import json
import sys
import threading
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
import tenacity

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from app.config import Location
from app.models import NormalizedTimeseries
from providers.base import ProviderRequestError
from providers.openmeteo import OpenMeteoProvider
from providers.region_routing import direct_provider_for

# Paris (48.8566, 2.3522): eindeutig innerhalb der FR-Router-Box UND
# innerhalb der tatsaechlichen AROME-Coverage (Spec AC-1-Beispiel).
_PARIS = Location(latitude=48.8566, longitude=2.3522, name="Paris")

# Korsika/GR20-Kernroute (Spec AC-5-Beispiel): 42.0N/9.0E — liegt erst nach
# der Box-Erweiterung (max_lon 8.3 -> 9.7) innerhalb der FR-Router-Box.
_CORSICA = Location(latitude=42.0, longitude=9.0, name="Korsika (GR20)")

_FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "meteofrance"
# F001-Fixtures (Adversary #1143 Runde 1): echte, einzeln aufgezeichnete
# GRIB2-Antworten je Parameter -- vorher wurde fuer TEMP/U/V/PRECIP
# ununterschieden dieselbe Temperatur-Antwort ausgeliefert.
_FIXTURE_TEMP = _FIXTURE_DIR / "arome_paris_20260722.grib2"
_FIXTURE_U10 = _FIXTURE_DIR / "arome_paris_u10_20260723.grib2"
_FIXTURE_V10 = _FIXTURE_DIR / "arome_paris_v10_20260723.grib2"
_FIXTURE_PRECIP = _FIXTURE_DIR / "arome_paris_precip_20260723.grib2"
# F003-Regressionsfixture (Adversary #1143 Runde 2): das obige
# `_FIXTURE_PRECIP` (Paris) ist 0,0 -- damit war der `*3600`-Bug unsichtbar.
# Echt aufgezeichnet gegen die Live-API: Alpenzelle 44.04N/7.84E,
# AROME-Lauf 2026-07-23T00:00Z, Zeitschritt 2026-07-23T15:00Z, Rohwert
# 5.17822265625 (kraeftiger Gewitterregen, plausibel als mm/h-Direktwert,
# physikalisch unmoeglich als Rate*3600).
_FIXTURE_ALPS_PRECIP_NONZERO = _FIXTURE_DIR / "arome_alps_precip_nonzero_20260723.grib2"
_ALPS_PRECIP_CELL = Location(latitude=44.04, longitude=7.84, name="Alpenzelle (F003)")


# ---------------------------------------------------------------------------
# Open-Meteo-Totalausfall-Harness (Vorbild #1141/#1142, hier dupliziert
# damit diese Testdatei self-contained bleibt).
# ---------------------------------------------------------------------------

_OM_FORECAST_ENDPOINTS = {"/v1/meteofrance", "/v1/dwd-icon", "/v1/metno", "/v1/ecmwf"}
_OM_ALL_MODEL_IDS = [
    "meteofrance_arome", "icon_d2", "metno_nordic", "icon_eu", "ecmwf_ifs04",
]
_OM_TOTAL_OUTAGE_STATUS_MAP = {ep: 503 for ep in _OM_FORECAST_ENDPOINTS}


class _OMFaultServer(ThreadingHTTPServer):
    """Echter HTTP-Server mit pfad-abhaengigem Status + Pfad-Protokoll."""

    def __init__(self, server_address, handler, status_map: dict):
        super().__init__(server_address, handler)
        self.status_map = status_map
        self.contacted: list[str] = []
        self._lock = threading.Lock()

    def record(self, path: str) -> None:
        with self._lock:
            self.contacted.append(path)


class _OMFaultHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 (http.server API)
        from urllib.parse import urlparse

        path = urlparse(self.path).path
        self.server.record(path)
        status = self.server.status_map.get(path, 200)
        payload = json.dumps(
            {"error": True, "reason": f"HTTP {status} (test seam)"}
        ).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):  # Ruhe im pytest-Output
        pass


@contextmanager
def _om_fault_server(status_map: dict):
    server = _OMFaultServer(("127.0.0.1", 0), _OMFaultHandler, status_map)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}", server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _write_all_available_cache(path: Path) -> None:
    """Availability-Cache, in dem JEDES Modell alle Metriken hat (verhindert
    den WEATHER-05b-Metrik-Fallback-Block — nur der #1115/#1141/#1142/#1143-
    Endpoint-/Provider-Fallback soll hier beobachtet werden)."""
    from datetime import date

    path.write_text(json.dumps({
        "probe_date": date.today().isoformat(),
        "models": {
            mid: {"available": [], "unavailable": []} for mid in _OM_ALL_MODEL_IDS
        },
    }))


@contextmanager
def _total_outage_seam(monkeypatch, tmp_path: Path):
    """Verdrahtet Open-Meteo-Host, Availability-Cache und Diagnostics auf die
    Test-Seam; ALLE Modell-Endpoints liefern 503 (Total-Ausfall). Liefert
    (provider, server, diagnostics_path)."""
    cache_path = tmp_path / "model_availability.json"
    _write_all_available_cache(cache_path)
    diagnostics_path = tmp_path / "openmeteo_calls.jsonl"
    monkeypatch.setattr("providers.openmeteo.AVAILABILITY_CACHE_PATH", cache_path)
    monkeypatch.setattr("providers.openmeteo.DIAGNOSTICS_PATH", diagnostics_path)
    monkeypatch.setattr(OpenMeteoProvider._request.retry, "wait", tenacity.wait_none())
    monkeypatch.setattr(
        OpenMeteoProvider._request.retry, "stop", tenacity.stop_after_attempt(1)
    )
    with _om_fault_server(_OM_TOTAL_OUTAGE_STATUS_MAP) as (url, server):
        monkeypatch.setattr("providers.openmeteo.BASE_HOST", url)
        yield OpenMeteoProvider(), server, diagnostics_path


@contextmanager
def _registered_test_direct_provider(region_direct_name: str, factory):
    """Registriert `factory` temporaer unter `region_direct_name` in der
    echten Provider-Registry (`providers.base`) und stellt den Vorzustand
    danach wieder her — kein dauerhafter Seiteneffekt auf andere Tests."""
    import providers.base as base_module

    if not base_module._PROVIDER_FACTORIES:
        base_module._load_providers()
    had_key = region_direct_name in base_module._PROVIDER_FACTORIES
    previous = base_module._PROVIDER_FACTORIES.get(region_direct_name)
    base_module.register_provider(region_direct_name, factory)
    try:
        yield
    finally:
        if had_key:
            base_module._PROVIDER_FACTORIES[region_direct_name] = previous
        else:
            base_module._PROVIDER_FACTORIES.pop(region_direct_name, None)


# ---------------------------------------------------------------------------
# Lokaler Fault-Server fuer den (noch nicht existierenden) FR-Direktprovider
# — echter HTTP-Server, kein Mock.
# ---------------------------------------------------------------------------

class _FrFaultServer(ThreadingHTTPServer):
    def __init__(self, server_address, handler, status: int, body: bytes):
        super().__init__(server_address, handler)
        self.status = status
        self.body = body
        self.request_count = 0
        self._lock = threading.Lock()

    def record(self) -> None:
        with self._lock:
            self.request_count += 1


class _FrFaultHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        self.server.record()
        self.send_response(self.server.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(self.server.body)))
        self.end_headers()
        self.wfile.write(self.server.body)

    def log_message(self, *args):
        pass


@contextmanager
def _fr_fault_server(status: int, body: bytes):
    server = _FrFaultServer(("127.0.0.1", 0), _FrFaultHandler, status, body)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}/", server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


# ---------------------------------------------------------------------------
# AC-2 + AC-5 — FR-Router-Box: außerhalb bleibt außerhalb, Korsika wird nach
# der Erweiterung erfasst.
# ---------------------------------------------------------------------------

def test_direct_provider_for_fr_box_after_korsika_widening():
    """AC-2: Given eine Koordinate außerhalb aller drei Router-Boxen (Berlin,
    52.52N/13.405E — deutlich außerhalb FR), When `direct_provider_for`
    aufgerufen wird, Then wird NICHT "fr_direct" zurueckgegeben.

    AC-5 (Korsika-Regression): Given eine Koordinate auf einer GR20/Korsika-
    Kernroute (42.0N/9.0E) sowie eine Koordinate zwischen der alten
    (max_lon=8.3) und der neuen (max_lon=9.7) Grenze (42.3N/9.3E), When
    `direct_provider_for` aufgerufen wird, Then wird jeweils "fr_direct"
    zurueckgegeben — nur moeglich nach der Box-Erweiterung.

    RED heute: `region_routing._REGIONS` FR-Zeile steht noch bei
    `max_lon=8.3` — beide Korsika-Koordinaten liegen außerhalb aller drei
    Boxen und `direct_provider_for` liefert `None` statt `"fr_direct"`.
    """
    berlin = direct_provider_for(52.52, 13.405)
    assert berlin != "fr_direct", (
        f"AC-2: Berlin darf niemals auf fr_direct routen — erhalten {berlin!r}."
    )

    corsica = direct_provider_for(_CORSICA.latitude, _CORSICA.longitude)
    assert corsica == "fr_direct", (
        "AC-5: Korsika (42.0N/9.0E) muss nach der Box-Erweiterung "
        f"(max_lon 8.3 -> 9.7) auf fr_direct routen — erhalten {corsica!r}."
    )

    between_old_and_new = direct_provider_for(42.3, 9.3)
    assert between_old_and_new == "fr_direct", (
        "AC-5: 42.3N/9.3E liegt zwischen alter (8.3) und neuer (9.7) "
        f"Lon-Grenze — muss fr_direct sein, erhalten {between_old_and_new!r}."
    )


# ---------------------------------------------------------------------------
# AC-3 — 4xx propagiert sichtbar, kein Retry.
# ---------------------------------------------------------------------------

def test_fetch_forecast_4xx_propagates_without_retry(monkeypatch):
    """AC-3: Given Météo-France antwortet mit einem 4xx (z. B. Koordinate
    außerhalb der WCS-Domäne), When `fetch_forecast` aufgerufen wird, Then
    wirft es eine `ProviderRequestError` mit `status_code` im 4xx-Bereich,
    und der lokale Test-Server wird GENAU EINMAL kontaktiert (kein
    Retry-Loop, ADR-0018).

    RED heute: `src/providers/meteofrance.py` existiert nicht —
    `monkeypatch.setattr("providers.meteofrance.BASE_URL", ...)` scheitert
    bereits mit `ModuleNotFoundError`, bevor irgendein Server kontaktiert
    werden kann.
    """
    body = json.dumps({"detail": "outside of dataset bounds"}).encode("utf-8")
    with _fr_fault_server(400, body) as (url, server):
        monkeypatch.setattr("providers.meteofrance.BASE_URL", url)

        from providers.meteofrance import MeteoFranceDirectProvider

        provider = MeteoFranceDirectProvider()
        with pytest.raises(ProviderRequestError) as exc:
            provider.fetch_forecast(_PARIS)

        assert exc.value.status_code is not None and 400 <= exc.value.status_code < 500, (
            f"AC-3: status_code muss im 4xx-Bereich liegen — "
            f"erhalten {exc.value.status_code!r}."
        )
        assert server.request_count == 1, (
            "AC-3: bei 4xx darf KEIN Retry stattfinden — kontaktiert="
            f"{server.request_count}x."
        )


# ---------------------------------------------------------------------------
# AC-4 — 5xx erschoepft genau 5 Versuche, dann sichtbare ProviderRequestError.
# ---------------------------------------------------------------------------

def test_fetch_forecast_503_exhausts_five_retries_then_raises(monkeypatch):
    """AC-4: Given Météo-France antwortet durchgehend mit 503, When
    `fetch_forecast` aufgerufen wird, Then wirft es nach genau 5 Versuchen
    eine `ProviderRequestError` (kein Crash mit roher httpx-Exception).

    RED heute: `src/providers/meteofrance.py` existiert nicht —
    `ModuleNotFoundError` beim Import von `MeteoFranceDirectProvider`.
    """
    body = json.dumps({"detail": "HTTP 503 (test seam)"}).encode("utf-8")
    with _fr_fault_server(503, body) as (url, server):
        monkeypatch.setattr("providers.meteofrance.BASE_URL", url)

        from providers.meteofrance import MeteoFranceDirectProvider

        monkeypatch.setattr(
            MeteoFranceDirectProvider._request.retry, "wait", tenacity.wait_none()
        )
        provider = MeteoFranceDirectProvider()
        with pytest.raises(ProviderRequestError):
            provider.fetch_forecast(_PARIS)

        assert server.request_count == 5, (
            "AC-4: genau 5 Retry-Versuche erwartet — kontaktiert="
            f"{server.request_count}x."
        )


def test_seam_falls_back_past_meteofrance_5xx_to_openmeteo_error(monkeypatch, tmp_path):
    """AC-4 (End-to-End, analog #1142-Vorlage): Given Open-Meteo hat einen
    Totalausfall UND der (echte, registrierte) `fr_direct`-Provider
    (`MeteoFranceDirectProvider`) antwortet selbst durchgehend mit 503, When
    das Segment verarbeitet wird, Then propagiert der Seam in `openmeteo.py`
    am Ende die URSPRUENGLICHE Open-Meteo-`ProviderRequestError` — kein
    Crash, Segment bleibt `has_error`.

    RED heute: `from providers.meteofrance import MeteoFranceDirectProvider`
    scheitert mit `ModuleNotFoundError` — die Klasse existiert noch nicht.
    """
    from providers.meteofrance import MeteoFranceDirectProvider

    body = json.dumps({"detail": "HTTP 503 (test seam)"}).encode("utf-8")
    with _fr_fault_server(503, body) as (url, fr_server):
        monkeypatch.setattr("providers.meteofrance.BASE_URL", url)
        monkeypatch.setattr(
            MeteoFranceDirectProvider._request.retry, "wait", tenacity.wait_none()
        )
        with _registered_test_direct_provider("fr_direct", MeteoFranceDirectProvider):
            with _total_outage_seam(monkeypatch, tmp_path) as (provider, _om, _diag):
                with pytest.raises(ProviderRequestError) as exc:
                    provider.fetch_forecast(_CORSICA, enrich_ensemble=False)

    assert exc.value.provider == "openmeteo", (
        "AC-4 e2e: die letztlich sichtbare ProviderRequestError muss vom "
        "urspruenglichen Open-Meteo-Total-Ausfall stammen (provider="
        f"'openmeteo') — war provider={exc.value.provider!r}."
    )
    assert fr_server.request_count > 0, (
        "AC-4 e2e: der fr_direct-Fault-Server muss tatsaechlich kontaktiert "
        "worden sein (sonst beweist der Test den Fallback-Pfad nicht)."
    )


# ---------------------------------------------------------------------------
# AC-6 — Wind-Vektor -> km/h.
# ---------------------------------------------------------------------------

def test_vector_to_speed_kmh_matches_geosphere_formula():
    """AC-6: Given AROME liefert U/V-Windkomponenten in m/s, When die
    Normalisierung laeuft, Then entspricht `wind10m_kmh` `sqrt(u^2+v^2)*3.6`,
    gerundet auf 1 Nachkommastelle (identisch zu `geosphere._vector_to_speed_kmh`).

    RED heute: `providers.meteofrance` existiert nicht — `ImportError`.
    """
    from providers.meteofrance import _vector_to_speed_kmh

    assert _vector_to_speed_kmh(10, 0) == 36.0
    assert _vector_to_speed_kmh(0, 0) == 0.0


# ---------------------------------------------------------------------------
# F002 — 500 gehoert zu RETRY_STATUS_CODES (Adversary #1143 Runde 1).
# ---------------------------------------------------------------------------

def test_fetch_forecast_500_is_retried_like_503(monkeypatch):
    """F002: Given Météo-France antwortet durchgehend mit 500 (reales
    Live-Symptom des WCS-Backends laut Feasibility-Spike, "backend error"),
    When `fetch_forecast` aufgerufen wird, Then wird — wie bei 503 (AC-4) —
    fuenfmal retried, bevor eine `ProviderRequestError` propagiert (statt 0
    Retries, weil 500 vor dem Fix nicht in `RETRY_STATUS_CODES` war)."""
    body = json.dumps({"detail": "internal server error"}).encode("utf-8")
    with _fr_fault_server(500, body) as (url, server):
        monkeypatch.setattr("providers.meteofrance.BASE_URL", url)

        from providers.meteofrance import MeteoFranceDirectProvider

        monkeypatch.setattr(
            MeteoFranceDirectProvider._request.retry, "wait", tenacity.wait_none()
        )
        provider = MeteoFranceDirectProvider()
        with pytest.raises(ProviderRequestError):
            provider.fetch_forecast(_PARIS)

        assert server.request_count == 5, (
            "F002: 500 muss wie 503 fuenfmal retried werden — kontaktiert="
            f"{server.request_count}x."
        )


# ---------------------------------------------------------------------------
# F004 — Gesamt-Zeitbudget stoppt eine ausufernde Sequenz von Calls.
# ---------------------------------------------------------------------------

def test_fetch_forecast_exceeds_wall_clock_deadline_then_raises(monkeypatch):
    """F004: Given Météo-France antwortet auf jeden Call technisch gueltig,
    aber spuerbar langsam, When das Gesamt-Zeitbudget
    (`FETCH_DEADLINE_SECONDS`) waehrend der bis zu 96 sequentiellen Calls
    ueberschritten wird, Then wirft `fetch_forecast` eine
    `ProviderRequestError` statt unbegrenzt weiterer Calls (Worst-Case ohne
    Deadline: 96 Calls x bis zu 5 Retries x 2-60s Backoff, >90 Min)."""
    grib_bytes = _FIXTURE_TEMP.read_bytes()

    class _SlowHandler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            time.sleep(0.05)
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(grib_bytes)))
            self.end_headers()
            self.wfile.write(grib_bytes)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), _SlowHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        monkeypatch.setattr("providers.meteofrance.BASE_URL", f"http://{host}:{port}/")
        monkeypatch.setattr("providers.meteofrance.FETCH_DEADLINE_SECONDS", 0.12)

        from providers.meteofrance import MeteoFranceDirectProvider

        provider = MeteoFranceDirectProvider()
        with pytest.raises(ProviderRequestError):
            provider.fetch_forecast(_PARIS)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


# ---------------------------------------------------------------------------
# AC-1 — valides NormalizedTimeseries aus aufgezeichnetem AROME-GRIB2.
# ---------------------------------------------------------------------------

def test_fetch_forecast_parses_recorded_arome_grib2_fixture(monkeypatch):
    """AC-1 + F001 (Adversary #1143 Runde 1): Given eine Koordinate innerhalb
    der FR-Router-Box UND innerhalb der tatsaechlichen AROME-Coverage
    (Paris), When `MeteoFranceDirectProvider.fetch_forecast` gegen vier
    PFAD-/PARAMETER-abhaengig aufgezeichnete GRIB2-Response-Fixtures (Temp/
    U/V/Precip, lokal ausgeliefert) aufgerufen wird, Then liefert die
    Antwort ein valides `NormalizedTimeseries` mit befuellten und
    PHYSIKALISCH PLAUSIBLEN `t2m_c`/`wind10m_kmh`/`precip_1h_mm` fuer
    mindestens einen Datenpunkt.

    F001-Fix: vorher lieferte der Test-Server fuer JEDE Coverage (TEMP/U/V/
    PRECIP) dieselbe Temperatur-Antwort aus — dadurch wurden z. B.
    Temperaturwerte (~25) als Windkomponenten interpretiert, was zu
    physikalisch unsinnigen Ergebnissen wie `wind10m_kmh=127.4` oder
    `precip_1h_mm=90098.5` fuehrte, waehrend der Test nur `is not None`
    pruefte. Jetzt: Dispatch anhand des `coverageId`-Query-Parameters +
    enge Plausibilitaets-Bounds, die einen erneuten Cross-Parameter-Mixup
    rot machen wuerden.
    """
    fixtures_by_marker = {
        "TEMPERATURE": _FIXTURE_TEMP.read_bytes(),
        "U_COMPONENT_OF_WIND": _FIXTURE_U10.read_bytes(),
        "V_COMPONENT_OF_WIND": _FIXTURE_V10.read_bytes(),
        "TOTAL_PRECIPITATION": _FIXTURE_PRECIP.read_bytes(),
    }

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            query = parse_qs(urlparse(self.path).query)
            coverage_id = query.get("coverageId", [""])[0]
            body = next(
                (
                    payload for marker, payload in fixtures_by_marker.items()
                    if marker in coverage_id
                ),
                None,
            )
            if body is None:
                self.send_response(400)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        monkeypatch.setattr("providers.meteofrance.BASE_URL", f"http://{host}:{port}/")

        from providers.meteofrance import MeteoFranceDirectProvider

        provider = MeteoFranceDirectProvider()
        result = provider.fetch_forecast(_PARIS)

        assert isinstance(result, NormalizedTimeseries), (
            f"AC-1: Erwartet NormalizedTimeseries — erhalten {type(result)!r}."
        )
        assert result.data, "AC-1: NormalizedTimeseries.data darf nicht leer sein."

        populated = [
            dp for dp in result.data
            if dp.t2m_c is not None
            and dp.wind10m_kmh is not None
            and dp.precip_1h_mm is not None
        ]
        assert populated, (
            "AC-1: mindestens ein Datenpunkt muss t2m_c/wind10m_kmh/"
            "precip_1h_mm gesetzt haben."
        )

        for dp in populated:
            assert -40 <= dp.t2m_c <= 45, (
                f"F001: t2m_c physikalisch unplausibel: {dp.t2m_c}"
            )
            assert 0 <= dp.wind10m_kmh <= 200, (
                f"F001: wind10m_kmh physikalisch unplausibel: {dp.wind10m_kmh}"
            )
            assert 0 <= dp.precip_1h_mm <= 100, (
                f"F001: precip_1h_mm physikalisch unplausibel: {dp.precip_1h_mm}"
            )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


# ---------------------------------------------------------------------------
# F003 (Adversary #1143, Runde 2) — Precip-Rohwert ist bereits mm, KEIN
# *3600. Regressionstest gegen ein echt aufgezeichnetes NICHT-NULL-Precip-
# Fixture (der Bug war mit dem 0,0-Paris-Fixture unsichtbar, s. Modul-
# Docstring des Providers).
# ---------------------------------------------------------------------------

def test_fetch_forecast_uses_recorded_nonzero_precip_fixture_without_rate_conversion(monkeypatch):
    """F003: Given ein echt aufgezeichnetes AROME-Precip-GRIB2-Fixture mit
    einem Rohwert deutlich ueber 0 (Alpenzelle 44.04N/7.84E, Rohwert
    5.17822265625), When `fetch_forecast` diesen Rohwert normalisiert, Then
    ist `precip_1h_mm` der PLAUSIBLE Direktwert (~5.2, gerundet), NICHT
    Rohwert*3600 (~18641,6 mm/h, physikalisch unmoegliche Regenmenge).

    Mit der alten `precip_mm = round(p * 3600, 1)`-Formel liefert dieser
    Test `precip_1h_mm ~= 18641.6` -- das reisst sowohl die
    `< 100`-Assertion unten als auch die AC-1-Plausibilitaetsgrenze
    (0<=precip<=100) und wird ROT. Mit dem Fix (`round(p, 1)`) liefert er
    `precip_1h_mm ~= 5.2` und wird GRUEN.
    """
    temp_bytes = _FIXTURE_TEMP.read_bytes()
    u_bytes = _FIXTURE_U10.read_bytes()
    v_bytes = _FIXTURE_V10.read_bytes()
    precip_bytes = _FIXTURE_ALPS_PRECIP_NONZERO.read_bytes()

    fixtures_by_marker = {
        "TEMPERATURE": temp_bytes,
        "U_COMPONENT_OF_WIND": u_bytes,
        "V_COMPONENT_OF_WIND": v_bytes,
        "TOTAL_PRECIPITATION": precip_bytes,
    }

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            query = parse_qs(urlparse(self.path).query)
            coverage_id = query.get("coverageId", [""])[0]
            body = next(
                (
                    payload for marker, payload in fixtures_by_marker.items()
                    if marker in coverage_id
                ),
                None,
            )
            if body is None:
                self.send_response(400)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        monkeypatch.setattr("providers.meteofrance.BASE_URL", f"http://{host}:{port}/")

        from providers.meteofrance import MeteoFranceDirectProvider, _read_point_value

        expected_raw = _read_point_value(
            precip_bytes, _ALPS_PRECIP_CELL.latitude, _ALPS_PRECIP_CELL.longitude,
        )
        assert expected_raw is not None and expected_raw > 1.0, (
            "F003-Vorbedingung: das Nicht-Null-Fixture muss tatsaechlich "
            f"einen Rohwert > 1.0 liefern -- gemessen {expected_raw!r}."
        )

        provider = MeteoFranceDirectProvider()
        result = provider.fetch_forecast(_ALPS_PRECIP_CELL)

        populated = [dp for dp in result.data if dp.precip_1h_mm is not None]
        assert populated, "F003: kein Datenpunkt mit precip_1h_mm gesetzt."

        for dp in populated:
            assert dp.precip_1h_mm < 100, (
                "F003: precip_1h_mm darf NICHT die alte Rate*3600-Groessen"
                f"ordnung erreichen -- erhalten {dp.precip_1h_mm}."
            )
            assert abs(dp.precip_1h_mm - round(expected_raw, 1)) < 0.5, (
                "F003: precip_1h_mm muss der plausible Direktwert (~"
                f"{round(expected_raw, 1)}) sein -- erhalten {dp.precip_1h_mm}."
            )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
