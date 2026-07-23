"""TDD RED — #1144: echter DWD-ICON-D2-Direktprovider fuer DE (Slice 3/4 von
Epic #1127).

Spec: docs/specs/modules/provider_dwd.md (AC-1..AC-8).

Der in #1141 verdrahtete Stub `de_direct` (`RegionalStubProvider`, wirft
immer `ProviderNotImplementedError`) soll durch die neue Klasse
`DwdDirectProvider` (CREATE `src/providers/dwd.py`) ersetzt werden. Anders
als bei AROME-WCS (#1143) liefert die ICON-D2-Open-Data-API KEINEN
serverseitigen Punkt-Query — pro Parameter/Zeitschritt wird die volle
Rasterdatei (`.grib2.bz2`) geladen, weshalb die hier aufgezeichneten
Fixtures deutlich groesser sind als die FR-Punkt-Subsets.

MOCK-FREI (KRITISCHE PROJEKT-REGEL):
Kein `Mock()`, kein `patch()`, kein `MagicMock`.
- AC-2: rein deterministische Aufrufe von `direct_provider_for`, kein HTTP.
- AC-3/AC-4: echte lokale `ThreadingHTTPServer` (Vorbild
  `test_meteofrance_direct_fallback.py`), `monkeypatch.setattr` nur auf
  Host/URL-Konstanten, nie auf Verhalten/Exceptions selbst.
- AC-6: reiner Unit-Test gegen die Wind-Hilfsfunktion, kein HTTP.
- AC-1/AC-5/AC-7/AC-8: echte, einmalig aufgezeichnete ICON-D2-GRIB2-`.bz2`-
  Response-Fixtures, ueber einen lokalen Server ausgeliefert.

AC-Test-Mapping (Pflicht, aus Spec):
| AC       | Testfunktion                                                     |
|----------|-------------------------------------------------------------------|
| AC-1     | test_fetch_forecast_parses_recorded_icon_d2_grib2_fixture         |
| AC-2     | test_direct_provider_for_de_box_routing                          |
| AC-3     | test_fetch_forecast_4xx_propagates_without_retry                  |
| AC-4     | test_fetch_forecast_503_exhausts_five_retries_then_raises         |
| AC-4 e2e | test_seam_catches_dwd_5xx_and_keeps_segment_has_error             |
| AC-5     | test_fetch_forecast_precip_uses_recorded_nonzero_fixture_pair     |
| AC-6     | test_vector_to_speed_kmh_matches_meteofrance_formula               |
| AC-7     | test_seam_renders_full_segment_from_dwd_on_total_outage           |
| AC-8     | test_seam_catches_dwd_5xx_and_keeps_segment_has_error (s.o.)      |

Fixture-Aufzeichnung (2026-07-23, echt gegen opendata.dwd.de abgerufen,
ICON-D2-Lauf 2026-07-22T21:00Z, Grid `regular-lat-lon`):
- AC-1-Basisfixtures (Zeitschritt `_001_` = Lauf+1h): `t_2m`/`u_10m`/
  `v_10m`/`tot_prec`, volle Deutschland-Rasterdatei je Parameter (~0,4-1,1
  MB komprimiert — anders als FR gibt es keinen serverseitigen Punkt-Query,
  s. Moduldocstring `provider_dwd.md`).
- AC-5-Precip-Fixture-PAAR (F003-Pflicht, Nicht-Null): Ostsee-Kuestenzelle
  53,70N/14,94E (innerhalb der DE-Router-Box, 47,2-55,1N/5,8-15,1E),
  Zeitschritte `_003_`/`_004_` (Lauf+3h/+4h). Rohwerte (kumuliert seit
  Laufbeginn, PDS `typeOfStatisticalProcessing`-Template mit waechsender
  `lengthOfTimeRange` 0/60/120min besaetigt die Kumulations-Annahme aus der
  Spec): prev(+3h)=`3.138671875`, curr(+4h)=`15.4853515625`, Differenz
  `12.3466796875` (kraeftiger Landregen an der Ostseekueste, plausibel).
  Die genauen Rohwerte werden unten je Testlauf erneut aus dem Fixture
  gelesen (kein Hardcoding), s. `_raw_value_at`.

Empirischer Befund fuer die Implementierung (F003-analoge Vorwarnung,
KEIN eigener Test noetig — die Bounds-Pruefung in AC-1 faengt einen
Fehlgriff bereits ab): GDAL taggt `t_2m` bereits mit `GRIB_UNIT=[C]`
("Temperature [C]"), NICHT Kelvin — anders als die Spec-Implementation-
Details-Annahme ("`t2m_c = round(kelvin - 273.15, 1)`"). Gemessener
Rohwert bei Muenchen 48,14N/11,57E, Lauf+1h: `18.11` — als Kelvin-573,15
waere das physikalisch unmoeglich (-255 C), als Direktwert in Celsius
plausibel (Sommerabend). Muss im Implementierungsschritt gegen die
GRIB-PDS-Metadaten verifiziert werden (analog AROME-Precip-Lehre F003).

RED heute (Sammel-Grund): `src/providers/dwd.py` existiert noch nicht
(ModuleNotFoundError in jedem AC-1/3/4/5/6/7/8-Test). AC-2 ist bereits
heute gruen (Router-Box unveraendert, reiner Waechter-Test).
"""
from __future__ import annotations

import bz2
import json
import sys
import threading
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlparse

import pytest
import tenacity
from rasterio.io import MemoryFile

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from app.config import Location
from app.models import NormalizedTimeseries
from providers.base import ProviderRequestError
from providers.openmeteo import OpenMeteoProvider
from providers.region_routing import direct_provider_for

# Muenchen (48.14, 11.57): SPEC-AC-1-Beispiel, aber innerhalb der AT-Router-
# Box (die Alpenraum-Box umschliesst Sued-Bayern) — fuer AC-1 unerheblich,
# da der isolierte `DwdDirectProvider` direkt (ohne Routing) aufgerufen wird.
_MUNICH = Location(latitude=48.14, longitude=11.57, name="Muenchen")

# Berlin (52.52, 13.405): noerdlich der AT-Box (max_lat=49.1) — eindeutig
# NUR "de_direct" in `direct_provider_for` (Spec AC-7/AC-8-Beispiel).
_BERLIN = Location(latitude=52.52, longitude=13.405, name="Berlin")

# Rom (41.9, 12.5): ausserhalb aller drei Router-Boxen (AT/DE/FR) — Spec
# AC-2-Gegenbeispiel.
_ROME = Location(latitude=41.9, longitude=12.5, name="Rom")

# Ostsee-Kuestenzelle (53.70, 14.94): F003-Regressionskoordinate fuer AC-5
# — innerhalb der DE-Router-Box, echter Nicht-Null-Niederschlag zwischen
# den Zeitschritten +3h/+4h (s. Moduldocstring).
_PRECIP_CELL = Location(latitude=53.70, longitude=14.94, name="Ostsee-Kuestenzelle (AC-5)")

_FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "dwd"
_FIXTURE_T2M = _FIXTURE_DIR / "icon_d2_muenchen_t_2m_2026072221_001.grib2.bz2"
_FIXTURE_U10 = _FIXTURE_DIR / "icon_d2_muenchen_u_10m_2026072221_001.grib2.bz2"
_FIXTURE_V10 = _FIXTURE_DIR / "icon_d2_muenchen_v_10m_2026072221_001.grib2.bz2"
_FIXTURE_PRECIP_BASE = _FIXTURE_DIR / "icon_d2_muenchen_tot_prec_2026072221_001.grib2.bz2"
_FIXTURE_PRECIP_PREV = _FIXTURE_DIR / "icon_d2_precip_nonzero_prev_tot_prec_2026072221_003.grib2.bz2"
_FIXTURE_PRECIP_CURR = _FIXTURE_DIR / "icon_d2_precip_nonzero_curr_tot_prec_2026072221_004.grib2.bz2"


def _raw_value_at(bz2_bytes: bytes, lat: float, lon: float) -> Optional[float]:
    """Test-lokale Referenzimplementierung (bz2 + rasterio), UNABHAENGIG
    von `providers.dwd`-Internals (die noch nicht existieren) — liest den
    Rohwert von Band 1 an (lat, lon) aus einer `.grib2.bz2`-Antwort."""
    raw = bz2.decompress(bz2_bytes)
    with MemoryFile(raw) as memfile, memfile.open() as dataset:
        row, col = dataset.index(lon, lat)
        row = min(max(row, 0), dataset.height - 1)
        col = min(max(col, 0), dataset.width - 1)
        return float(dataset.read(1)[row, col])


# ---------------------------------------------------------------------------
# Open-Meteo-Totalausfall-Harness (Vorbild #1141/#1142/#1143, hier dupliziert
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
    den WEATHER-05b-Metrik-Fallback-Block — nur der Endpoint-/Provider-
    Fallback soll hier beobachtet werden)."""
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
# Lokaler Fault-Server fuer den (noch nicht existierenden) DE-Direktprovider
# — echter HTTP-Server, kein Mock.
# ---------------------------------------------------------------------------

class _DwdFaultServer(ThreadingHTTPServer):
    def __init__(self, server_address, handler, status: int, body: bytes):
        super().__init__(server_address, handler)
        self.status = status
        self.body = body
        self.request_count = 0
        self._lock = threading.Lock()

    def record(self) -> None:
        with self._lock:
            self.request_count += 1


class _DwdFaultHandler(BaseHTTPRequestHandler):
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
def _dwd_fault_server(status: int, body: bytes):
    server = _DwdFaultServer(("127.0.0.1", 0), _DwdFaultHandler, status, body)
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
# Lokaler Fixture-Server: dispatcht anhand des Parameter-Ordnernamens im
# URL-Pfad (`/t_2m/`, `/u_10m/`, `/v_10m/`, `/tot_prec/` — 1:1 aus dem
# Spec-URL-Template `<BASE_URL><HH>/<param>/icon-d2_..._<param>.grib2.bz2`),
# UNABHAENGIG von Lauf-Zeitstempel/HH/TTT, die der (noch nicht existierende)
# Provider selbst bestimmt. Fuer `tot_prec` kann die Antwort zusaetzlich
# PRO-PARAMETER sequenziert werden (1. Request -> prev, 2.+ -> curr) — das
# beweist die Differenzbildung (AC-5), ohne die exakte TTT-Zeichenkette
# erraten zu muessen (die Zeitschritte werden nachweislich sequentiell
# 1..24 abgerufen, s. `meteofrance.py:_fetch_series`-Vorbild).
# ---------------------------------------------------------------------------

_PARAMS = ("t_2m", "u_10m", "v_10m", "tot_prec")


def _param_from_path(path: str) -> Optional[str]:
    for param in _PARAMS:
        if f"/{param}/" in path:
            return param
    return None


class _DwdFixtureServer(ThreadingHTTPServer):
    def __init__(self, server_address, handler, fixtures_by_param: dict):
        super().__init__(server_address, handler)
        self.fixtures_by_param = fixtures_by_param  # param -> bytes | Callable[[int], bytes]
        self.request_count_by_param: dict[str, int] = {}
        self._lock = threading.Lock()

    def record(self, param: str) -> int:
        with self._lock:
            n = self.request_count_by_param.get(param, 0) + 1
            self.request_count_by_param[param] = n
            return n


class _DwdFixtureHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        path = urlparse(self.path).path
        param = _param_from_path(path)
        if param is None or param not in self.server.fixtures_by_param:
            self.send_response(404)
            self.end_headers()
            return
        n = self.server.record(param)
        entry = self.server.fixtures_by_param[param]
        body = entry(n) if callable(entry) else entry
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@contextmanager
def _dwd_fixture_server(fixtures_by_param: dict):
    server = _DwdFixtureServer(("127.0.0.1", 0), _DwdFixtureHandler, fixtures_by_param)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}/", server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _basic_fixtures_by_param() -> dict:
    """Statische Basis-Fixtures (ein Zeitschritt, alle vier Parameter) fuer
    AC-1/AC-7 — dieselbe Antwort fuer jeden Zeitschritt-Request (die
    24-Zeitschritt-Sequenz wird dadurch physikalisch nicht realistisch,
    aber das ist fuer diese ACs (Struktur-/Bounds-/Rendering-Nachweis)
    unerheblich)."""
    return {
        "t_2m": _FIXTURE_T2M.read_bytes(),
        "u_10m": _FIXTURE_U10.read_bytes(),
        "v_10m": _FIXTURE_V10.read_bytes(),
        "tot_prec": _FIXTURE_PRECIP_BASE.read_bytes(),
    }


# ---------------------------------------------------------------------------
# AC-2 — DE-Router-Box: ausserhalb bleibt ausserhalb.
# ---------------------------------------------------------------------------

def test_direct_provider_for_de_box_routing():
    """AC-2: Given eine Koordinate ausserhalb der DE-Router-Box (Rom,
    41.9N/12.5E — ausserhalb aller drei Boxen), When `direct_provider_for`
    aufgerufen wird, Then wird NICHT "de_direct" zurueckgegeben.

    Zusaetzliche Positiv-Probe (Waechter): Berlin (52.52N/13.405E, noerdlich
    der AT-Box) routet eindeutig auf "de_direct" — belegt, dass die Box
    ueberhaupt einen erreichbaren Fall hat.

    Dieser Test ist HEUTE bereits gruen (der Router existiert unveraendert
    seit #1141/#1142/#1143) — hier als Waechter gegen versehentliche
    Box-Regressionen aufgenommen (Spec-Hinweis: "das ist ok").
    """
    rome = direct_provider_for(_ROME.latitude, _ROME.longitude)
    assert rome != "de_direct", (
        f"AC-2: Rom darf niemals auf de_direct routen — erhalten {rome!r}."
    )

    berlin = direct_provider_for(_BERLIN.latitude, _BERLIN.longitude)
    assert berlin == "de_direct", (
        f"AC-2-Waechter: Berlin muss auf de_direct routen — erhalten {berlin!r}."
    )


# ---------------------------------------------------------------------------
# AC-3 — 4xx propagiert sichtbar, kein Retry.
# ---------------------------------------------------------------------------

def test_fetch_forecast_4xx_propagates_without_retry(monkeypatch):
    """AC-3: Given DWD antwortet mit einem 4xx (z. B. Zeitschritt-Datei noch
    nicht veroeffentlicht, 404), When `fetch_forecast` aufgerufen wird, Then
    wirft es eine `ProviderRequestError` mit `status_code` im 4xx-Bereich,
    und der lokale Test-Server wird GENAU EINMAL kontaktiert (kein
    Retry-Loop, ADR-0018).

    RED heute: `src/providers/dwd.py` existiert nicht —
    `monkeypatch.setattr("providers.dwd.BASE_URL", ...)` scheitert bereits
    mit `ModuleNotFoundError`, bevor irgendein Server kontaktiert werden
    kann.
    """
    body = json.dumps({"detail": "file not yet published"}).encode("utf-8")
    with _dwd_fault_server(404, body) as (url, server):
        monkeypatch.setattr("providers.dwd.BASE_URL", url)

        from providers.dwd import DwdDirectProvider

        provider = DwdDirectProvider()
        with pytest.raises(ProviderRequestError) as exc:
            provider.fetch_forecast(_MUNICH)

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
    """AC-4: Given DWD antwortet durchgehend mit 503, When `fetch_forecast`
    aufgerufen wird, Then wirft es nach genau 5 Versuchen eine
    `ProviderRequestError` (kein Crash mit roher httpx-Exception).

    RED heute: `src/providers/dwd.py` existiert nicht —
    `ModuleNotFoundError` beim Import von `DwdDirectProvider`.
    """
    body = json.dumps({"detail": "HTTP 503 (test seam)"}).encode("utf-8")
    with _dwd_fault_server(503, body) as (url, server):
        monkeypatch.setattr("providers.dwd.BASE_URL", url)

        from providers.dwd import DwdDirectProvider

        monkeypatch.setattr(
            DwdDirectProvider._request.retry, "wait", tenacity.wait_none()
        )
        provider = DwdDirectProvider()
        with pytest.raises(ProviderRequestError):
            provider.fetch_forecast(_MUNICH)

        assert server.request_count == 5, (
            "AC-4: genau 5 Retry-Versuche erwartet — kontaktiert="
            f"{server.request_count}x."
        )


def test_seam_catches_dwd_5xx_and_keeps_segment_has_error(monkeypatch, tmp_path):
    """AC-4 (End-to-End) + AC-8: Given Open-Meteo hat einen Totalausfall UND
    der (echte, registrierte) `de_direct`-Provider (`DwdDirectProvider`)
    antwortet selbst durchgehend mit 503, When das Segment verarbeitet wird,
    Then propagiert der Seam in `openmeteo.py` am Ende die URSPRUENGLICHE
    Open-Meteo-`ProviderRequestError` (kein Crash mit einer neuen,
    unbehandelten Exception) — Segment bleibt sichtbar `has_error`.

    RED heute: `from providers.dwd import DwdDirectProvider` scheitert mit
    `ModuleNotFoundError` — die Klasse existiert noch nicht.
    """
    from providers.dwd import DwdDirectProvider

    body = json.dumps({"detail": "HTTP 503 (test seam)"}).encode("utf-8")
    with _dwd_fault_server(503, body) as (url, dwd_server):
        monkeypatch.setattr("providers.dwd.BASE_URL", url)
        monkeypatch.setattr(
            DwdDirectProvider._request.retry, "wait", tenacity.wait_none()
        )
        with _registered_test_direct_provider("de_direct", DwdDirectProvider):
            with _total_outage_seam(monkeypatch, tmp_path) as (provider, _om, _diag):
                with pytest.raises(ProviderRequestError) as exc:
                    provider.fetch_forecast(_BERLIN, enrich_ensemble=False)

    assert exc.value.provider == "openmeteo", (
        "AC-4/AC-8 e2e: die letztlich sichtbare ProviderRequestError muss "
        "vom urspruenglichen Open-Meteo-Total-Ausfall stammen (provider="
        f"'openmeteo') — war provider={exc.value.provider!r}."
    )
    assert dwd_server.request_count > 0, (
        "AC-4/AC-8 e2e: der de_direct-Fault-Server muss tatsaechlich "
        "kontaktiert worden sein (sonst beweist der Test den "
        "Fallback-Pfad nicht)."
    )


# ---------------------------------------------------------------------------
# AC-6 — Wind-Vektor -> km/h.
# ---------------------------------------------------------------------------

def test_vector_to_speed_kmh_matches_meteofrance_formula():
    """AC-6: Given ICON-D2 liefert U/V-Windkomponenten in m/s, When die
    Normalisierung laeuft, Then entspricht `wind10m_kmh` `sqrt(u^2+v^2)*3.6`,
    gerundet auf 1 Nachkommastelle (identisch zu
    `meteofrance._vector_to_speed_kmh`/`geosphere._vector_to_speed_kmh`).

    RED heute: `providers.dwd` existiert nicht — `ImportError`.
    """
    from providers.dwd import _vector_to_speed_kmh

    assert _vector_to_speed_kmh(10, 0) == 36.0
    assert _vector_to_speed_kmh(0, 0) == 0.0


# ---------------------------------------------------------------------------
# AC-1 — valides NormalizedTimeseries aus aufgezeichnetem ICON-D2-GRIB2.
# ---------------------------------------------------------------------------

def test_fetch_forecast_parses_recorded_icon_d2_grib2_fixture(monkeypatch):
    """AC-1: Given eine Koordinate innerhalb der tatsaechlichen ICON-D2-
    Domaene (Muenchen), When `DwdDirectProvider.fetch_forecast` gegen vier
    echte, lokal ausgelieferte ICON-D2-`.grib2.bz2`-Fixtures (t_2m/u_10m/
    v_10m/tot_prec, Lauf 2026-07-22T21:00Z +1h) aufgerufen wird, Then
    liefert die Antwort ein valides `NormalizedTimeseries` mit befuellten
    und PHYSIKALISCH PLAUSIBLEN `t2m_c`/`wind10m_kmh`/`precip_1h_mm` fuer
    mindestens einen Datenpunkt (analog F001 aus #1143 — Bounds faengen
    einen Cross-Parameter-Mixup UND eine falsche Kelvin/Celsius-Annahme).

    RED heute: `src/providers/dwd.py` existiert nicht — `ModuleNotFoundError`.
    """
    fixtures = _basic_fixtures_by_param()

    with _dwd_fixture_server(fixtures) as (url, server):
        monkeypatch.setattr("providers.dwd.BASE_URL", url)

        from providers.dwd import DwdDirectProvider

        provider = DwdDirectProvider()
        result = provider.fetch_forecast(_MUNICH)

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
            assert -40 <= dp.t2m_c <= 50, (
                f"AC-1: t2m_c physikalisch unplausibel: {dp.t2m_c} "
                "(Kelvin/Celsius-Verwechslung? s. Moduldocstring)"
            )
            assert 0 <= dp.wind10m_kmh <= 250, (
                f"AC-1: wind10m_kmh physikalisch unplausibel: {dp.wind10m_kmh}"
            )
            assert 0 <= dp.precip_1h_mm <= 100, (
                f"AC-1: precip_1h_mm physikalisch unplausibel: {dp.precip_1h_mm}"
            )
        assert server.request_count_by_param, (
            "AC-1: der Fixture-Server muss tatsaechlich kontaktiert worden "
            "sein (sonst beweist der Test den Parsing-Pfad nicht)."
        )


# ---------------------------------------------------------------------------
# AC-5 — Niederschlag-Differenzbildung gegen ein echtes Nicht-Null-Paar
# (F003-Pflicht: ein 0,0-Paar waere als alleiniger Nachweis untauglich).
# ---------------------------------------------------------------------------

def test_fetch_forecast_precip_uses_recorded_nonzero_fixture_pair(monkeypatch):
    """AC-5: Given ICON-D2 liefert `tot_prec` als seit Laufbeginn
    kumulierten Wert (echt aufgezeichnetes NICHT-NULL-Fixture-Paar,
    Ostsee-Kuestenzelle 53.70N/14.94E, Zeitschritte +3h/+4h), When die
    Normalisierung ueber zwei aufeinanderfolgende Zeitschritte laeuft, Then
    wird `precip_1h_mm` korrekt als Differenz
    `max(0, round(tot_prec[t] - tot_prec[t-1], 1))` berechnet — UND der
    allererste angefragte Zeitschritt (Randfall) liefert den Rohwert direkt
    (Laufbeginn implizit 0).

    Server-Design: `tot_prec`-Requests werden PRO-PARAMETER sequenziert
    (1. Request -> prev-Fixture (+3h), 2.+ Request -> curr-Fixture (+4h)) —
    das beweist die Differenzbildung unabhaengig von der exakten TTT-
    Zeichenkette, die der (noch nicht existierende) Provider verwendet;
    Zeitschritte werden nachweislich sequentiell 1..N abgerufen (Vorbild
    `meteofrance.py:_fetch_series`).

    RED heute: `src/providers/dwd.py` existiert nicht — `ModuleNotFoundError`.
    """
    prev_bytes = _FIXTURE_PRECIP_PREV.read_bytes()
    curr_bytes = _FIXTURE_PRECIP_CURR.read_bytes()

    raw_prev = _raw_value_at(prev_bytes, _PRECIP_CELL.latitude, _PRECIP_CELL.longitude)
    raw_curr = _raw_value_at(curr_bytes, _PRECIP_CELL.latitude, _PRECIP_CELL.longitude)
    assert raw_prev is not None and raw_curr is not None and raw_curr > raw_prev + 1.0, (
        "AC-5-Vorbedingung: das Fixture-Paar muss einen ECHTEN, deutlich "
        f"ansteigenden Nicht-Null-Niederschlag zeigen — gemessen prev={raw_prev!r}, "
        f"curr={raw_curr!r}."
    )

    def _tot_prec_sequence(n: int) -> bytes:
        return prev_bytes if n == 1 else curr_bytes

    fixtures = {
        "t_2m": _FIXTURE_T2M.read_bytes(),
        "u_10m": _FIXTURE_U10.read_bytes(),
        "v_10m": _FIXTURE_V10.read_bytes(),
        "tot_prec": _tot_prec_sequence,
    }

    with _dwd_fixture_server(fixtures) as (url, server):
        monkeypatch.setattr("providers.dwd.BASE_URL", url)

        from providers.dwd import DwdDirectProvider

        provider = DwdDirectProvider()
        result = provider.fetch_forecast(_PRECIP_CELL)

        populated = [dp for dp in result.data if dp.precip_1h_mm is not None]
        assert len(populated) >= 2, (
            "AC-5: mindestens zwei Datenpunkte mit precip_1h_mm noetig, um "
            f"Randfall + Differenzbildung zu pruefen — erhalten {len(populated)}."
        )

        # Randfall: erster angefragter Zeitschritt = Rohwert direkt (Laufbeginn=0).
        first = populated[0]
        assert abs(first.precip_1h_mm - round(raw_prev, 1)) < 0.5, (
            "AC-5 Randfall: precip_1h_mm des ersten Zeitschritts muss dem "
            f"Rohwert ({round(raw_prev, 1)}) entsprechen — erhalten "
            f"{first.precip_1h_mm}."
        )

        # Differenzbildung: zweiter Zeitschritt = curr - prev.
        second = populated[1]
        expected_diff = max(0.0, round(raw_curr - raw_prev, 1))
        assert abs(second.precip_1h_mm - expected_diff) < 0.5, (
            "AC-5: precip_1h_mm des zweiten Zeitschritts muss die Differenz "
            f"({expected_diff}) sein, NICHT der rohe Kumulativwert "
            f"({round(raw_curr, 1)}) — erhalten {second.precip_1h_mm}."
        )
        assert second.precip_1h_mm < round(raw_curr, 1) - 0.5, (
            "AC-5: precip_1h_mm darf NICHT der unveraenderte Kumulativwert "
            f"sein (F003-analoge Regression) — erhalten {second.precip_1h_mm}, "
            f"Kumulativwert waere {round(raw_curr, 1)}."
        )


# ---------------------------------------------------------------------------
# AC-7 — E2E-Totalausfall-Rendering: vollstaendiges Segment aus DWD-Daten.
# ---------------------------------------------------------------------------

def test_seam_renders_full_segment_from_dwd_on_total_outage(monkeypatch, tmp_path):
    """AC-7: Given Open-Meteo hat fuer eine DE-Koordinate (Berlin) einen
    kompletten Totalausfall (alle Modelle 5xx/Timeout) UND der registrierte
    `de_direct`-Provider (`DwdDirectProvider`) liefert echte, aufgezeichnete
    ICON-D2-Fixtures, When das Briefing fuer dieses Segment gerendert wird,
    Then wird ein vollstaendiges Segment aus `DwdDirectProvider`-Daten
    gerendert (Erfolgspfad, nicht nur eine isolierte
    `fetch_forecast`-Rueckgabe): `meta.fallback_reason` ==
    "cross_provider_total_outage", `meta.fallback_model` == "de_direct",
    befuellte Basis-Felder.

    RED heute: `src/providers/dwd.py` existiert nicht — `ModuleNotFoundError`
    beim Import von `DwdDirectProvider`.
    """
    from providers.dwd import DwdDirectProvider

    fixtures = _basic_fixtures_by_param()

    with _dwd_fixture_server(fixtures) as (url, dwd_server):
        monkeypatch.setattr("providers.dwd.BASE_URL", url)
        with _registered_test_direct_provider("de_direct", DwdDirectProvider):
            with _total_outage_seam(monkeypatch, tmp_path) as (provider, _om, _diag):
                result = provider.fetch_forecast(_BERLIN, enrich_ensemble=False)

    assert isinstance(result, NormalizedTimeseries), (
        f"AC-7: Erwartet NormalizedTimeseries — erhalten {type(result)!r}."
    )
    assert result.meta.fallback_reason == "cross_provider_total_outage", (
        "AC-7: fallback_reason muss 'cross_provider_total_outage' sein — "
        f"erhalten {result.meta.fallback_reason!r}."
    )
    assert result.meta.fallback_model == "de_direct", (
        "AC-7: fallback_model muss 'de_direct' sein — erhalten "
        f"{result.meta.fallback_model!r}."
    )

    populated = [
        dp for dp in result.data
        if dp.t2m_c is not None
        and dp.wind10m_kmh is not None
        and dp.precip_1h_mm is not None
    ]
    assert populated, (
        "AC-7: mindestens ein gerendeter Datenpunkt muss t2m_c/wind10m_kmh/"
        "precip_1h_mm gesetzt haben — sonst ist das Segment NICHT "
        "vollstaendig gerendert."
    )
    assert dwd_server.request_count_by_param, (
        "AC-7: der de_direct-Fixture-Server muss tatsaechlich kontaktiert "
        "worden sein (sonst beweist der Test den vollen Rendering-Pfad "
        "nicht)."
    )
