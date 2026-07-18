"""TDD RED — Issue #1142: echter GeoSphere-Direktprovider fuer AT.

Spec: docs/specs/modules/issue_1142_geosphere_direct_fallback.md (AC-1..AC-4;
AC-2 der urspruenglichen Spec-Fassung — Coverage-Box-Schaerfung — wurde
PO-seitig ersatzlos gestrichen, siehe Spec-Changelog. `region_routing.py`
bleibt in diesem Slice unveraendert.)

Der in #1141 verdrahtete Stub `at_direct` (wirft immer
`ProviderNotImplementedError`) soll durch einen duennen Adapter ersetzt
werden, der an die bestehende, produktiv genutzte `GeoSphereProvider`-Klasse
delegiert — bewusst OHNE die versteckte Open-Meteo-Wolken-Abfrage
(`include_cloud_layers=False`), sonst wuerde der Fallback fuer einen
Open-Meteo-Totalausfall ausgerechnet wieder Open-Meteo kontaktieren.
Zusaetzlich muss der Fallback-Seam in `openmeteo.py:884` auch
`ProviderRequestError`/`ProviderNotFoundError` fangen (F001-Fix aus #1141),
nicht mehr nur `ProviderNotImplementedError`.

MOCK-FREI (KRITISCHE PROJEKT-REGEL):
Kein `Mock()`, kein `patch()`, kein `MagicMock`.
- AC-1/AC-2: echte GeoSphere-API-Calls (kein Mock der Antwort).
- AC-3/AC-4: echte lokale `ThreadingHTTPServer` (Vorbild
  `test_issue_1141_cross_provider_fallback.py`) fuer Open-Meteo-Totalausfall
  UND fuer den GeoSphere-eigenen 5xx-Fall; `monkeypatch.setattr` nur auf
  Host/URL-Konstanten, nie auf Verhalten/Exceptions selbst.

AC-Test-Mapping (Pflicht, aus Spec Abschnitt "Test-Strategie"):
| AC   | Testfunktion                                              |
|------|------------------------------------------------------------|
| AC-1 | test_at_direct_returns_valid_geosphere_timeseries          |
| AC-2 | test_at_direct_skips_openmeteo_cloud_call                  |
| AC-3 | test_geosphere_5xx_preserves_original_error_and_retry      |
| AC-4 | test_seam_catches_provider_request_and_not_found_error     |

RED heute (Sammel-Grund): `providers.regional_stubs.make_at_direct` liefert
weiterhin `RegionalStubProvider("at_direct")`, dessen `fetch_forecast` IMMER
`ProviderNotImplementedError` wirft — kein echter GeoSphere-Adapter ist
registriert. Der Seam in `openmeteo.py:884` faengt ausserdem nur
`ProviderNotImplementedError`, nicht `ProviderRequestError`/
`ProviderNotFoundError` — jede Testfunktion dokumentiert individuell, ob sie
an der Stub-Exception (AC-1/AC-2) oder am zu enger gefassten `except`-Block
(AC-3/AC-4) scheitert.
"""
from __future__ import annotations

import json
import sys
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import httpx
import pytest
import tenacity

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from app.config import Location
from app.models import NormalizedTimeseries
from providers.base import ProviderNotFoundError, ProviderRequestError
from providers.geosphere import RETRY_ATTEMPTS, GeoSphereProvider
from providers.openmeteo import OpenMeteoProvider

# Innsbruck (47.26, 11.39): bekannte AT-Koordinate, empirisch bestaetigt
# (2026-07-09, echter Diagnose-Call gegen
# dataset.api.hub.geosphere.at/v1/timeseries/forecast/nwp-v1-1h-2500m):
# HTTP 200, 58/58 nicht-null t2m-Werte. Liegt innerhalb der (unveraenderten)
# AT-Router-Box aus #1141 (46.3-49.1 lat, 9.5-17.2 lon).
_INNSBRUCK = Location(latitude=47.26, longitude=11.39, name="Innsbruck")

# Alle bekannten Open-Meteo-Modell-Forecast-Endpoints (Issue #1115-Vorbild,
# 1:1 aus test_issue_1141_cross_provider_fallback.py uebernommen).
_OM_FORECAST_ENDPOINTS = {"/v1/meteofrance", "/v1/dwd-icon", "/v1/metno", "/v1/ecmwf"}
_OM_ALL_MODEL_IDS = [
    "meteofrance_arome", "icon_d2", "metno_nordic", "icon_eu", "ecmwf_ifs04",
]
_OM_TOTAL_OUTAGE_STATUS_MAP = {ep: 503 for ep in _OM_FORECAST_ENDPOINTS}


# ---------------------------------------------------------------------------
# Open-Meteo-Totalausfall-Harness (Vorbild #1141, hier dupliziert damit diese
# Testdatei self-contained bleibt).
# ---------------------------------------------------------------------------

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
    den WEATHER-05b-Metrik-Fallback-Block — nur der #1115/#1141/#1142-
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
    # Test-only: neutralisiert das tenacity-Retry-Backoff auf `_request`
    # (echte Sleeps wuerden jeden der 5 Total-Ausfall-Endpoints ~30s
    # blockieren) — nur das Timing aendert sich, nicht die Retry-Entscheidung.
    monkeypatch.setattr(OpenMeteoProvider._request.retry, "wait", tenacity.wait_none())
    monkeypatch.setattr(
        OpenMeteoProvider._request.retry, "stop", tenacity.stop_after_attempt(1)
    )
    with _om_fault_server(_OM_TOTAL_OUTAGE_STATUS_MAP) as (url, server):
        monkeypatch.setattr("providers.openmeteo.BASE_HOST", url)
        yield OpenMeteoProvider(), server, diagnostics_path


# ---------------------------------------------------------------------------
# GeoSphere-eigener 5xx-Fault-Server (echter lokaler HTTP-Server, kein Mock).
# ---------------------------------------------------------------------------

class _GeoFaultServer(ThreadingHTTPServer):
    def __init__(self, server_address, handler):
        super().__init__(server_address, handler)
        self.contacted: list[str] = []
        self._lock = threading.Lock()

    def record(self, path: str) -> None:
        with self._lock:
            self.contacted.append(path)


class _GeoFaultHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        path = urlparse(self.path).path
        self.server.record(path)
        payload = json.dumps({"detail": "HTTP 503 (test seam)"}).encode("utf-8")
        self.send_response(503)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


@contextmanager
def _geosphere_fault_server(monkeypatch):
    """Echter lokaler HTTP-Server, der GeoSphere-Anfragen durchgehend mit 503
    beantwortet (kein Mock). Neutralisiert NUR die tenacity-Wartezeit
    (`wait`) — die Versuchsanzahl (`stop`, `RETRY_ATTEMPTS=5`) bleibt
    unveraendert, das ist Teil des AC-3-Nachweises ("Retry-Verhalten wird
    nicht veraendert")."""
    server = _GeoFaultServer(("127.0.0.1", 0), _GeoFaultHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    monkeypatch.setattr("providers.geosphere.BASE_URL", f"http://{host}:{port}")
    monkeypatch.setattr(GeoSphereProvider._request.retry, "wait", tenacity.wait_none())
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


# ---------------------------------------------------------------------------
# Test-lokaler Nachbau des (noch nicht existierenden) Produktions-Adapters.
# ---------------------------------------------------------------------------

class _FutureAtDirectAdapter:
    """Test-lokaler Nachbau des in der Spec (Implementation Details #2)
    skizzierten `GeoSphereDirectProvider` — existiert in `src/` noch NICHT
    (#1142 ist zum Zeitpunkt dieses RED-Tests nicht implementiert). Delegiert
    an die ECHTE `GeoSphereProvider`-Klasse mit `include_cloud_layers=False`
    und uebernimmt dieselbe httpx->ProviderRequestError-Uebersetzung wie
    `GeoSphereProvider.fetch_forecast` (Spec-Hinweis: `fetch_combined` selbst
    faengt httpx-Fehler NICHT). Kein Mock — ruft echten, per
    `providers.geosphere.BASE_URL` lokal umgebogenen HTTP-Code auf. Dient
    AC-3/AC-4 dazu, den Seam-Bug (F001) unabhaengig von der noch fehlenden
    Produktionsklasse nachzuweisen."""

    def __init__(self) -> None:
        self._inner = GeoSphereProvider()

    @property
    def name(self) -> str:
        return "at_direct"

    def fetch_forecast(self, location, start=None, end=None, enrich_ensemble=True):
        try:
            return self._inner.fetch_combined(
                lat=location.latitude,
                lon=location.longitude,
                start=start,
                end=end,
                include_cloud_layers=False,
            )
        except httpx.HTTPStatusError as e:
            raise ProviderRequestError(
                "geosphere", f"HTTP {e.response.status_code}: {e.response.text}"
            )
        except httpx.RequestError as e:
            raise ProviderRequestError("geosphere", f"Request failed: {e}")


@contextmanager
def _registered_test_direct_provider(region_direct_name: str, factory):
    """Registriert `factory` temporaer unter `region_direct_name` in der
    echten Provider-Registry (`providers.base`) und stellt den Vorzustand
    danach wieder her — kein dauerhafter Seiteneffekt auf andere Tests."""
    import providers.base as base_module

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


@contextmanager
def _unregistered_direct_provider(region_direct_name: str):
    """Entfernt `region_direct_name` temporaer komplett aus der Registry, so
    dass `get_provider(region_direct_name)` `ProviderNotFoundError` wirft —
    stellt danach den Vorzustand wieder her."""
    import providers.base as base_module

    if not base_module._PROVIDER_FACTORIES:
        base_module._load_providers()
    had_key = region_direct_name in base_module._PROVIDER_FACTORIES
    previous = base_module._PROVIDER_FACTORIES.pop(region_direct_name, None)
    try:
        yield
    finally:
        if had_key:
            base_module._PROVIDER_FACTORIES[region_direct_name] = previous


def _count_geosphere_clouds_calls(diagnostics_path: Path) -> int:
    """Zaehlt Diagnose-Eintraege mit source == 'geosphere_clouds'
    (`providers.call_log.resolve_call_source()`-Tag fuer
    `GeoSphereProvider._fetch_openmeteo_clouds`)."""
    if not diagnostics_path.exists():
        return 0
    entries = [
        json.loads(line)
        for line in diagnostics_path.read_text().splitlines()
        if line.strip()
    ]
    return sum(1 for e in entries if e.get("source") == "geosphere_clouds")


# ---------------------------------------------------------------------------
# AC-1 — at_direct liefert ein valides NormalizedTimeseries von GeoSphere.
# ---------------------------------------------------------------------------

# Dialt real (GeoSphere-API) -- #1211 Scheibe 2b Batch 3, nur via Marker ausfuehren.
@pytest.mark.live
def test_at_direct_returns_valid_geosphere_timeseries():
    """AC-1: Given eine Koordinate innerhalb der AT-Router-Box (Innsbruck),
    When der registrierte `at_direct`-Provider aufgerufen wird, Then liefert
    `fetch_forecast` ein valides `NormalizedTimeseries` mit mindestens einem
    Datenpunkt, der `t2m_c`/`wind10m_kmh`/`precip_1h_mm` gesetzt hat.

    Hinweis (PO-Entscheidung): `symbol` ist NICHT Teil dieser Assertion —
    das Feld wird von KEINEM Provider (weder GeoSphere noch Open-Meteo)
    befuellt, und `GeoSphereProvider` bleibt in diesem Slice unveraendert
    (Spec-Quelle-Abschnitt) — eine Assertion darauf waere strukturell nie
    erfuellbar.

    RED heute: `get_provider("at_direct")` liefert `RegionalStubProvider`
    (`providers.regional_stubs`), dessen `fetch_forecast` IMMER
    `ProviderNotImplementedError` wirft, statt echte GeoSphere-Daten zu
    liefern — der Aufruf unten crasht, bevor irgendeine Assertion greift.
    """
    from providers.base import get_provider

    provider = get_provider("at_direct")
    result = provider.fetch_forecast(_INNSBRUCK)

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
        "precip_1h_mm gesetzt haben — erste 3 Punkte: "
        f"{[vars(dp) for dp in result.data[:3]]}"
    )


# ---------------------------------------------------------------------------
# AC-2 — at_direct loest KEINEN Open-Meteo-Wolken-Call aus.
# ---------------------------------------------------------------------------

# Dialt real (GeoSphere-API) -- #1211 Scheibe 2b Batch 3, nur via Marker ausfuehren.
@pytest.mark.live
def test_at_direct_skips_openmeteo_cloud_call(monkeypatch, tmp_path):
    """AC-2: Given der `at_direct`-Provider laeuft, When er GeoSphere-Daten
    fuer Innsbruck abruft, Then erfolgt KEIN Call gegen `api.open-meteo.com`
    (`_fetch_openmeteo_clouds` wird nicht erreicht) — Nachweis ueber den
    `providers.call_log`-Diagnose-Zaehler fuer den Source-Tag
    'geosphere_clouds' (vorher/nachher gleich).

    RED heute: `get_provider("at_direct")` liefert `RegionalStubProvider`,
    dessen `fetch_forecast` sofort `ProviderNotImplementedError` wirft —
    bevor ueberhaupt ein echter GeoSphere-Call (und damit potenziell ein
    Open-Meteo-Wolken-Call) stattfinden koennte. Der Test crasht daher am
    `fetch_forecast`-Aufruf, statt die (fuer AC-2 eigentlich zu beweisende)
    Abwesenheit des Wolken-Calls bei ECHTEN Daten zu zeigen.
    """
    diagnostics_path = tmp_path / "openmeteo_calls.jsonl"
    monkeypatch.setattr("providers.call_log.DIAGNOSTICS_PATH", diagnostics_path)

    from providers.base import get_provider

    before = _count_geosphere_clouds_calls(diagnostics_path)
    provider = get_provider("at_direct")
    result = provider.fetch_forecast(_INNSBRUCK)
    after = _count_geosphere_clouds_calls(diagnostics_path)

    assert isinstance(result, NormalizedTimeseries) and result.data, (
        "AC-2 Vorbedingung: at_direct muss echte Daten liefern (sonst "
        "beweist der Zaehler-Vergleich nichts) — heute wirft der Stub "
        "stattdessen ProviderNotImplementedError."
    )
    assert after == before, (
        f"AC-2: geosphere_clouds-Zaehler darf sich nicht aendern "
        f"(vorher={before}, nachher={after}) — at_direct darf keinen "
        "Open-Meteo-Wolken-Call ausloesen (include_cloud_layers=False)."
    )


# ---------------------------------------------------------------------------
# AC-3 — GeoSphere-5xx: urspruengliche Open-Meteo-Fehler + Retry bleiben.
# ---------------------------------------------------------------------------

def test_geosphere_5xx_preserves_original_error_and_retry(monkeypatch, tmp_path):
    """AC-3: Given Open-Meteo hat einen Totalausfall (alle Modelle 5xx) UND
    GeoSphere selbst antwortet am `at_direct`-Aufruf durchgehend mit 503
    (Retry ausgeschoepft), When das Segment verarbeitet wird, Then wirft
    `fetch_forecast` am Ende die URSPRUENGLICHE Open-Meteo-
    `ProviderRequestError` (nicht die GeoSphere-eigene), und das
    GeoSphere-Retry-Verhalten (RETRY_ATTEMPTS Versuche) bleibt unveraendert.

    RED heute: `at_direct` ist noch der `ProviderNotImplementedError`-Stub,
    nicht der hier per `_FutureAtDirectAdapter` simulierte echte
    GeoSphere-Adapter. Um den ZUKUENFTIGEN Adapter UND den heutigen
    Seam-Bug (F001, openmeteo.py:884 faengt nur `ProviderNotImplementedError`)
    unabhaengig von der noch fehlenden Produktionsklasse zu beweisen,
    registriert dieser Test `_FutureAtDirectAdapter` (echte Delegation an
    `GeoSphereProvider`, kein Mock) temporaer unter "at_direct". Die
    resultierende `ProviderRequestError` (provider='geosphere') durchbricht
    den Seam heute UNGEFANGEN, statt dass `last_error` (Open-Meteo) greift —
    die Assertion `exc.value.provider == "openmeteo"` schlaegt daher fehl.
    """
    with _geosphere_fault_server(monkeypatch) as geo_server:
        with _registered_test_direct_provider("at_direct", _FutureAtDirectAdapter):
            with _total_outage_seam(monkeypatch, tmp_path) as (provider, _om, _diag):
                with pytest.raises(ProviderRequestError) as exc:
                    provider.fetch_forecast(_INNSBRUCK, enrich_ensemble=False)

    assert exc.value.provider == "openmeteo", (
        "AC-3: die letztlich geworfene ProviderRequestError muss vom "
        "urspruenglichen Open-Meteo-Total-Ausfall stammen "
        f"(provider='openmeteo') — war provider={exc.value.provider!r}."
    )
    assert len(geo_server.contacted) == RETRY_ATTEMPTS, (
        f"AC-3: GeoSphere-Retry-Verhalten ({RETRY_ATTEMPTS} Versuche) muss "
        f"unveraendert bleiben — kontaktiert={len(geo_server.contacted)}x."
    )


# ---------------------------------------------------------------------------
# AC-4 (F001-Fix) — Seam faengt ProviderRequestError UND ProviderNotFoundError.
# ---------------------------------------------------------------------------

def test_seam_catches_provider_request_and_not_found_error(monkeypatch, tmp_path):
    """AC-4 (F001-Fix): Given der Direktanbieter (GeoSphere) antwortet am
    Seam mit 5xx (Fall a) ODER `at_direct` ist gar nicht registriert (Fall
    b), When das Segment verarbeitet wird, Then wird die jeweils
    resultierende `ProviderRequestError`/`ProviderNotFoundError` im
    `except`-Block des Seams (openmeteo.py:884) gefangen und `raise
    last_error` (Open-Meteo) propagiert — kein Crash mit einer unbehandelten
    Exception aus dem GeoSphere-Zweig selbst.

    RED heute (beide Faelle): der `except`-Block faengt nur
    `ProviderNotImplementedError`.
    - Fall (a): `_FutureAtDirectAdapter` (echte GeoSphere-Delegation, lokaler
      503-Server) wirft `ProviderRequestError(provider='geosphere')` — die
      wird heute NICHT gefangen, sondern erreicht den Aufrufer direkt
      (Assertion auf `provider == 'openmeteo'` schlaegt fehl).
    - Fall (b): `at_direct` wird aus der Registry entfernt —
      `get_provider('at_direct')` wirft `ProviderNotFoundError`, die vom
      `except ProviderNotImplementedError`-Block gar nicht erst abgedeckt
      ist (andere Exception-Klasse) und daher ungefangen bis in den Test
      durchschlaegt — `pytest.raises(ProviderRequestError)` faengt sie NICHT
      (Typ-Mismatch), der Test schlaegt mit der unerwarteten
      `ProviderNotFoundError` fehl.
    """
    # --- Fall (a): GeoSphere selbst antwortet mit 503 ---
    with _geosphere_fault_server(monkeypatch) as _geo_server:
        with _registered_test_direct_provider("at_direct", _FutureAtDirectAdapter):
            with _total_outage_seam(monkeypatch, tmp_path) as (provider, _om, _diag):
                with pytest.raises(ProviderRequestError) as exc_a:
                    provider.fetch_forecast(_INNSBRUCK, enrich_ensemble=False)

    assert exc_a.value.provider == "openmeteo", (
        "AC-4a: last_error (Open-Meteo) muss propagieren, nicht GeoSpheres "
        f"eigene ProviderRequestError — provider={exc_a.value.provider!r}."
    )

    # --- Fall (b): at_direct fehlt komplett in der Registry ---
    with _unregistered_direct_provider("at_direct"):
        with _total_outage_seam(monkeypatch, tmp_path) as (provider, _om, _diag):
            with pytest.raises(ProviderRequestError) as exc_b:
                provider.fetch_forecast(_INNSBRUCK, enrich_ensemble=False)

    assert exc_b.value.provider == "openmeteo", (
        "AC-4b: last_error (Open-Meteo) muss propagieren, auch wenn "
        "'at_direct' in der Registry fehlt (ProviderNotFoundError) — "
        f"provider={exc_b.value.provider!r}."
    )
    assert not isinstance(exc_b.value, ProviderNotFoundError), (
        "AC-4b: die am Ende sichtbare Exception muss die urspruengliche "
        "Open-Meteo-ProviderRequestError sein, nicht die ProviderNotFoundError "
        "aus dem GeoSphere-Zweig."
    )
