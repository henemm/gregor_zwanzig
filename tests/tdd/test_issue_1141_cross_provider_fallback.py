"""TDD RED — Issue #1141: Cross-Provider-Fallback bei Open-Meteo-Total-Ausfall.

Spec: docs/specs/modules/issue_1141_cross_provider_routing.md (AC-1..AC-6).

Wenn Open-Meteo als Verteiler KOMPLETT ausfaellt (alle abdeckenden Modelle
inkl. globalem ECMWF mit 5xx erschoepft — der intra-Open-Meteo-Modellfallback
aus #1115 also selbst gescheitert ist), soll Gregor bei bekannter Region
(AT/DE/FR) auf einen infrastruktur-unabhaengigen Direkt-Provider ausweichen,
statt das Segment sofort als Ausfall zu markieren. Dieses Slice liefert den
Unterbau (Region-Routing + Stub-Direktprovider je Region + Einhaengepunkt in
`OpenMeteoProvider.fetch_forecast`) — KEIN echter neuer Wetter-Provider.

MOCK-FREI (KRITISCHE PROJEKT-REGEL):
Kein `Mock()`, kein `patch()`, kein `MagicMock`. Die Ausfall-Simulation laeuft
ueber einen echten lokalen `ThreadingHTTPServer` in einem Thread (identisches
Muster zu `tests/tdd/test_issue_1115_model_fallback.py`), der pfadabhaengig
echte HTTP-Status liefert. `fetch_forecast` sendet dagegen echte `httpx`-GET-
Requests (Host per `monkeypatch.setattr("providers.openmeteo.BASE_HOST", ...)`
umgebogen).

RED heute (Sammel-Grund): `src/providers/region_routing.py` und
`src/providers/regional_stubs.py` existieren noch nicht, `providers.base`
kennt weder `ProviderNotImplementedError` noch die `at_direct`/`de_direct`/
`fr_direct`-Registrierung, und `OpenMeteoProvider.fetch_forecast` hat noch
keinen Einhaengepunkt fuer das Cross-Provider-Routing — jede Testfunktion
dokumentiert individuell, ob sie an einem `ImportError` (Modul/Symbol fehlt)
oder an einer Verhaltens-Assertion (Einhaengepunkt fehlt) scheitert.
"""
from __future__ import annotations

import json
import sys
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import pytest
import tenacity

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from app.config import Location
from app.models import (
    ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries, Provider,
    SegmentWeatherData, SegmentWeatherSummary, TripSegment,
)
from providers.base import ProviderRequestError
from providers.openmeteo import OpenMeteoProvider

# Alle bekannten Open-Meteo-Modell-Forecast-Endpoints (Issue #1115-Vorbild).
_FORECAST_ENDPOINTS = {"/v1/meteofrance", "/v1/dwd-icon", "/v1/metno", "/v1/ecmwf"}

_ALL_MODEL_IDS = [
    "meteofrance_arome", "icon_d2", "metno_nordic", "icon_eu", "ecmwf_ifs04",
]

# Total-Ausfall: ALLE Modell-Endpoints liefern 503 → der #1115-Modellfallback
# selbst scheitert vollstaendig, erst DANN greift das #1141-Cross-Provider-
# Routing (bzw. bleibt bei unveraendertem Verhalten ohne #1141).
_TOTAL_OUTAGE_STATUS_MAP = {ep: 503 for ep in _FORECAST_ENDPOINTS}

# Muenchen (48.14, 11.58): liegt innerhalb der AT-Bounds der Spec (46.3-49.1
# lat, 9.5-17.2 lon) — AT wird laut Pruefreihenfolge AT->DE->FR vor DE
# ausgewertet (Alpenraum faellt bewusst an AT), Ziel-Direktprovider "at_direct".
_MUNICH = Location(latitude=48.14, longitude=11.58, name="Muenchen")

# Lappland (65.0, 18.0): ausserhalb aller drei Bounds-Rechtecke (AT/DE/FR) —
# Regressionsschutz fuer den ganz ueberwiegenden Teil der Weltkarte.
_LAPPLAND = Location(latitude=65.0, longitude=18.0, name="Lappland")

# Berlin (52.52, 13.40): liegt in der DE-Box (47.2-55.1 lat, 5.8-15.1 lon),
# NICHT in der AT-Box (lat 52.52 > 49.1 max_lat) -> direct_provider_for
# liefert "de_direct". Seit #1144 ist "de_direct" kein Stub mehr (echter
# `DwdDirectProvider`, #1144) -- die unten stehenden Tests biegen ihn
# bewusst auf einen echten Fehlschlag (503) statt eines Stub-Fehlers, um
# weiterhin den Original-Fehler-Durchreiche-Pfad zu pruefen.
_BERLIN = Location(latitude=52.52, longitude=13.40, name="Berlin")


class _FaultServer(ThreadingHTTPServer):
    """Echter HTTP-Server mit pfad-abhaengigem Status + Pfad-Protokoll."""

    def __init__(self, server_address, handler, status_map: dict):
        super().__init__(server_address, handler)
        self.status_map = status_map
        self.contacted: list[str] = []
        self._lock = threading.Lock()

    def record(self, path: str) -> None:
        with self._lock:
            self.contacted.append(path)


class _FaultHandler(BaseHTTPRequestHandler):
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
def _fault_server(status_map: dict):
    """Startet einen echten lokalen HTTP-Server (Thread), gibt (url, server)."""
    server = _FaultServer(("127.0.0.1", 0), _FaultHandler, status_map)
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
    den aelteren WEATHER-05b-Metrik-Fallback-Block — nur der #1115/#1141-
    Endpoint-/Provider-Fallback soll hier beobachtet werden)."""
    from datetime import date

    path.write_text(json.dumps({
        "probe_date": date.today().isoformat(),
        "models": {
            mid: {"available": [], "unavailable": []} for mid in _ALL_MODEL_IDS
        },
    }))


@contextmanager
def _total_outage_seam(monkeypatch, tmp_path: Path):
    """Verdrahtet Provider-Host, Availability-Cache und Diagnostics auf die
    Test-Seam; ALLE Modell-Endpoints liefern 503 (Total-Ausfall). Liefert
    (provider, server, diagnostics_path)."""
    cache_path = tmp_path / "model_availability.json"
    _write_all_available_cache(cache_path)
    diagnostics_path = tmp_path / "openmeteo_calls.jsonl"
    monkeypatch.setattr("providers.openmeteo.AVAILABILITY_CACHE_PATH", cache_path)
    monkeypatch.setattr("providers.openmeteo.DIAGNOSTICS_PATH", diagnostics_path)
    # Test-only: neutralisiert das tenacity-Retry-Backoff auf `_request`
    # (@retry mit stop_after_attempt(5) + wait_exponential(2..60s), Issue
    # #1128 macht 5xx retryable) — ohne dies wuerde jeder der 5 Total-
    # Ausfall-Endpoints ~30s durch echte Sleeps blockieren. Nur das Timing
    # aendert sich (echte tenacity-Config, kein Mock/Patch von Verhalten);
    # die fachliche Aussage (Kandidatenkette erschoepft -> Cross-Provider-
    # Weiche) bleibt unveraendert.
    monkeypatch.setattr(OpenMeteoProvider._request.retry, "wait", tenacity.wait_none())
    monkeypatch.setattr(
        OpenMeteoProvider._request.retry, "stop", tenacity.stop_after_attempt(1)
    )
    with _fault_server(_TOTAL_OUTAGE_STATUS_MAP) as (url, server):
        monkeypatch.setattr("providers.openmeteo.BASE_HOST", url)
        yield OpenMeteoProvider(), server, diagnostics_path


def _read_diagnostics(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


class _DwdAlwaysFailServer(ThreadingHTTPServer):
    """Liefert fuer JEDEN Pfad denselben Status (Stellvertreter fuer einen
    ausgefallenen `de_direct`/DwdDirectProvider-Endpoint, #1144) -- anders
    als `_FaultServer` (pfadabhaengige Status-Map fuer Open-Meteo-Endpoints)
    reicht hier ein einzelner Status, da jeder ICON-D2-Parameter/Zeitschritt-
    Request gleichermassen fehlschlagen soll."""

    def __init__(self, server_address, handler, status: int):
        super().__init__(server_address, handler)
        self.status = status
        self.request_count = 0
        self._lock = threading.Lock()

    def record(self) -> None:
        with self._lock:
            self.request_count += 1


class _DwdAlwaysFailHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        self.server.record()
        body = json.dumps(
            {"error": True, "reason": f"HTTP {self.server.status} (test seam)"}
        ).encode("utf-8")
        self.send_response(self.server.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # Ruhe im pytest-Output
        pass


@contextmanager
def _dwd_always_fail_server(status: int = 503):
    """Echter lokaler HTTP-Server, gegen den `DwdDirectProvider.BASE_URL`
    umgebogen wird -- verhindert einen echten (vom Egress-Guard geblockten)
    Call auf `opendata.dwd.de` und macht `de_direct` deterministisch als
    ECHTEN, aber fehlschlagenden Provider verhalten (ProviderRequestError
    statt ProviderNotImplementedError)."""
    server = _DwdAlwaysFailServer(("127.0.0.1", 0), _DwdAlwaysFailHandler, status)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}/", server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


class _TestDirectProvider:
    """Test-Direktprovider (KEIN Mock) fuer AC-1/AC-3 — erfuellt strukturell
    das `WeatherProvider`-Protocol und liefert deterministisch eine gueltige
    `NormalizedTimeseries`, unabhaengig vom (in diesem Slice noch nicht
    existierenden) echten regionalen Direkt-Provider."""

    @property
    def name(self) -> str:
        return "at_direct"

    def fetch_forecast(self, location, start=None, end=None, enrich_ensemble=True):
        meta = ForecastMeta(
            provider=Provider.GEOSPHERE,
            model="test_direct_stub",
            grid_res_km=1.0,
        )
        data = [ForecastDataPoint(ts=datetime.now(timezone.utc), t2m_c=12.0)]
        return NormalizedTimeseries(meta=meta, data=data)


@contextmanager
def _registered_test_direct_provider(region_direct_name: str):
    """Registriert `_TestDirectProvider` temporaer unter `region_direct_name`
    in der echten Provider-Registry (`providers.base`) und stellt den
    Vorzustand danach wieder her — kein dauerhafter Seiteneffekt auf andere
    Tests."""
    from providers.base import register_provider
    import providers.base as base_module

    had_key = region_direct_name in base_module._PROVIDER_FACTORIES
    previous = base_module._PROVIDER_FACTORIES.get(region_direct_name)
    register_provider(region_direct_name, _TestDirectProvider)
    try:
        yield
    finally:
        if had_key:
            base_module._PROVIDER_FACTORIES[region_direct_name] = previous
        else:
            base_module._PROVIDER_FACTORIES.pop(region_direct_name, None)


def _make_meta(model: str = "meteofrance_arome", fallback_model=None, fallback_metrics=None) -> ForecastMeta:
    return ForecastMeta(
        provider=Provider.OPENMETEO,
        model=model,
        run=datetime(2026, 7, 8, 0, 0, tzinfo=timezone.utc),
        grid_res_km=1.3,
        interp="grid_point",
        fallback_model=fallback_model,
        fallback_metrics=fallback_metrics or [],
    )


def _make_segment_data(fallback_model=None, fallback_metrics=None) -> SegmentWeatherData:
    """AC-4-Fixture: 1:1-Vorbild `tests/unit/test_model_metric_fallback.py::
    TestFooterFallbackInfo._make_segment_data` — echter `TripSegment` +
    `NormalizedTimeseries` mit gesetztem Fallback-Meta."""
    from datetime import date

    today = date.today()
    meta = _make_meta(fallback_model=fallback_model, fallback_metrics=fallback_metrics)
    ts = NormalizedTimeseries(
        meta=meta,
        data=[ForecastDataPoint(ts=datetime(today.year, today.month, today.day, 8, 0, tzinfo=timezone.utc), t2m_c=10.0)],
    )
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=48.14, lon=11.58, elevation_m=520.0),
        end_point=GPXPoint(lat=48.20, lon=11.65, elevation_m=600.0),
        start_time=datetime(today.year, today.month, today.day, 8, 0, tzinfo=timezone.utc),
        end_time=datetime(today.year, today.month, today.day, 10, 0, tzinfo=timezone.utc),
        duration_hours=2.0,
        distance_km=5.0,
        ascent_m=100.0,
        descent_m=20.0,
    )
    return SegmentWeatherData(
        segment=seg,
        timeseries=ts,
        aggregated=SegmentWeatherSummary(
            temp_min_c=8.0, temp_max_c=14.0, wind_max_kmh=15.0,
            gust_max_kmh=25.0, precip_sum_mm=0.0, cloud_avg_pct=50,
        ),
        fetched_at=datetime.now(timezone.utc),
        provider="openmeteo",
    )


# ---------------------------------------------------------------------------
# AC-1 — Total-Ausfall routet auf den Direkt-Provider der Zielregion.
# ---------------------------------------------------------------------------

def test_total_outage_routes_to_region_direct_provider(monkeypatch, tmp_path):
    """AC-1: Given Open-Meteo hat ALLE abdeckenden Modelle (inkl. globalem
    ECMWF) mit 5xx erschoepft (echter lokaler Test-Server liefert 503 auf
    jedem Forecast-Endpoint), When `fetch_forecast` fuer eine AT-Koordinate
    (Muenchen) laeuft, Then wird die Region bestimmt und ein registrierter
    Direkt-Provider ("at_direct") aufgerufen — `fetch_forecast` gibt dessen
    `NormalizedTimeseries` zurueck statt eine Exception zu werfen.

    RED heute: `from providers.region_routing import direct_provider_for`
    schlaegt mit ImportError fehl — `src/providers/region_routing.py`
    existiert noch nicht (kein Cross-Provider-Routing implementiert).
    """
    from providers.region_routing import direct_provider_for

    region_direct_name = direct_provider_for(_MUNICH.latitude, _MUNICH.longitude)
    assert region_direct_name == "at_direct", (
        f"AC-1 Vorbedingung: Muenchen (48.14, 11.58) muss auf 'at_direct' "
        f"routen — direct_provider_for lieferte {region_direct_name!r}."
    )

    with _registered_test_direct_provider(region_direct_name):
        with _total_outage_seam(monkeypatch, tmp_path) as (provider, server, _diag):
            result = provider.fetch_forecast(_MUNICH, enrich_ensemble=False)

    assert isinstance(result, NormalizedTimeseries), (
        "AC-1: Erwartet gueltige NormalizedTimeseries vom Regions-"
        "Direktprovider nach Total-Ausfall — heute propagiert stattdessen "
        "die ProviderRequestError (kein Cross-Provider-Routing)."
    )
    assert result.meta.model == "test_direct_stub", (
        f"AC-1: Ergebnis muss vom registrierten Test-Direktprovider stammen "
        f"— meta.model={result.meta.model!r}."
    )


# ---------------------------------------------------------------------------
# AC-2 — Ausserhalb AT/DE/FR bleibt das Verhalten unveraendert (Regression).
# ---------------------------------------------------------------------------

def test_total_outage_outside_regions_raises_original_error(monkeypatch, tmp_path):
    """AC-2: Given keine Region-Zuordnung existiert (Koordinate ausserhalb
    AT/DE/FR, z.B. Lappland 65.0/18.0), When der Total-Ausfall eintritt,
    Then wird weiterhin die urspruengliche `ProviderRequestError` geworfen
    (kein Verhaltensbruch fuer den ueberwiegenden Teil der Weltkarte).

    RED heute: `from providers.region_routing import direct_provider_for`
    schlaegt mit ImportError fehl — ohne dieses Modul kann die Test-
    Vorbedingung (Lappland liegt ausserhalb aller drei Bounds) gar nicht
    bewiesen werden, obwohl `fetch_forecast` selbst zufaellig noch identisch
    reagiert (kein Routing implementiert).
    """
    from providers.region_routing import direct_provider_for

    assert direct_provider_for(_LAPPLAND.latitude, _LAPPLAND.longitude) is None, (
        "AC-2 Vorbedingung: Lappland (65.0, 18.0) darf keiner der drei "
        "Regionen (AT/DE/FR) zugeordnet werden."
    )

    with _total_outage_seam(monkeypatch, tmp_path) as (provider, server, _diag):
        with pytest.raises(ProviderRequestError):
            provider.fetch_forecast(_LAPPLAND, enrich_ensemble=False)


# ---------------------------------------------------------------------------
# AC-3 — Erfolgreicher Direkt-Provider markiert das Ausweichen sichtbar.
# ---------------------------------------------------------------------------

def test_successful_direct_provider_sets_fallback_meta(monkeypatch, tmp_path):
    """AC-3: Given ein Direkt-Provider liefert nach Total-Ausfall erfolgreich
    ein `NormalizedTimeseries`, When das Ergebnis zurueckkommt, Then traegt
    `meta.fallback_reason == "cross_provider_total_outage"` und
    `meta.fallback_model == "at_direct"` (Nicht-Kaschieren-Prinzip aus
    #1115/ADR-0018, hier fuer den Cross-Provider-Fall fortgefuehrt).

    RED heute: `from providers.region_routing import direct_provider_for`
    schlaegt mit ImportError fehl — der Einhaengepunkt in `fetch_forecast`
    (Zeile 864), der `meta.fallback_reason`/`meta.fallback_model` setzen
    wuerde, existiert noch nicht.
    """
    from providers.region_routing import direct_provider_for

    region_direct_name = direct_provider_for(_MUNICH.latitude, _MUNICH.longitude)

    with _registered_test_direct_provider(region_direct_name):
        with _total_outage_seam(monkeypatch, tmp_path) as (provider, server, _diag):
            result = provider.fetch_forecast(_MUNICH, enrich_ensemble=False)

    assert result.meta.fallback_reason == "cross_provider_total_outage", (
        f"AC-3: fallback_reason muss 'cross_provider_total_outage' sein — "
        f"war {result.meta.fallback_reason!r}."
    )
    assert result.meta.fallback_model == "at_direct", (
        f"AC-3: fallback_model muss den genutzten Direkt-Provider-Namen "
        f"tragen ('at_direct') — war {result.meta.fallback_model!r}."
    )


# ---------------------------------------------------------------------------
# AC-4 — Plain-Text-Footer: keine fuehrende-Doppelpunkt-Artefakt bei leeren
#         fallback_metrics (kosmetischer Bug aus #1115, hier fixpflichtig).
# ---------------------------------------------------------------------------

def test_plain_email_footer_no_leading_colon_on_empty_metrics():
    """AC-4: Given ein Cross-Provider-Fallback lief (leere `fallback_metrics`,
    gesetztes `fallback_model`), When die Plain-Text-Mail via
    `TripReportFormatter.format_email` gerendert wird (echter Render-Aufruf,
    kein String-Content-Check auf Quellcode), Then enthaelt der Footer
    "Fallback: at_direct" OHNE fuehrendes Leerzeichen-vor-Doppelpunkt-
    Artefakt ("Fallback : at_direct").

    RED heute: `src/output/renderers/email/plain.py` Zeile 288 rendert
    `f"Fallback {', '.join(fb.fallback_metrics)}: {fb.fallback_model}"` — bei
    leerer `fallback_metrics`-Liste ergibt das "Fallback : at_direct" (Leer-
    zeichen VOR dem Doppelpunkt statt direkt danach) — die Ziel-Assertion
    "Fallback: at_direct" ist im gerenderten Text heute NICHT enthalten.
    """
    from output.renderers.trip_report import TripReportFormatter

    seg = _make_segment_data(fallback_model="at_direct", fallback_metrics=[])
    formatter = TripReportFormatter()
    report = formatter.format_email([seg], "Test Trip", "morning")

    assert "Fallback: at_direct" in report.email_plain, (
        "AC-4: Footer muss 'Fallback: at_direct' (kein fuehrendes "
        "Doppelpunkt-Leerzeichen-Artefakt) enthalten — gerenderter Text:\n"
        f"{report.email_plain}"
    )
    assert "Fallback : at_direct" not in report.email_plain, (
        "AC-4: Footer darf NICHT das Artefakt 'Fallback : at_direct' "
        "(Leerzeichen vor dem Doppelpunkt bei leeren fallback_metrics) "
        f"enthalten — gerenderter Text:\n{report.email_plain}"
    )


# ---------------------------------------------------------------------------
# AC-5 — Stub-Direktprovider darf den urspruenglichen Fehler nicht verdecken.
# ---------------------------------------------------------------------------

def test_stub_provider_reraises_original_error(monkeypatch, tmp_path):
    """AC-5: Given der Regions-Direktprovider ist seit #1144 ein echter
    Provider (`DwdDirectProvider`), hier bewusst auf einen Fehlschlag (503)
    gebogen, When der Total-Ausfall fuer diese Region (Berlin -> de_direct)
    eintritt, Then wird die urspruengliche `ProviderRequestError` des zuletzt
    gescheiterten Open-Meteo-Modells unveraendert weitergereicht — NICHT die
    `ProviderRequestError` des Direktprovider-Fehlschlags selbst, keine neue
    Ersatz-Exception.

    Seit #1142/#1143/#1144 ist keiner der drei Regions-Direktprovider mehr
    ein Stub -- dieser Test biegt `de_direct` (`DwdDirectProvider`) daher
    ueber einen lokalen 503-Server auf einen echten Fehlschlag, um weiterhin
    den Original-Fehler-Durchreiche-Pfad (F001, #1141) zu pruefen.
    """
    from providers.base import ProviderNotImplementedError  # noqa: F401 (Existenz-Beweis)
    from providers.dwd import DwdDirectProvider
    from providers.region_routing import direct_provider_for

    assert direct_provider_for(_BERLIN.latitude, _BERLIN.longitude) == "de_direct", (
        "AC-5 Vorbedingung: Berlin (52.52, 13.40) muss auf 'de_direct' "
        "routen (DE-Box, ausserhalb AT-Box)."
    )

    with _dwd_always_fail_server() as (dwd_url, _dwd_server):
        monkeypatch.setattr("providers.dwd.BASE_URL", dwd_url)
        monkeypatch.setattr(DwdDirectProvider._request.retry, "wait", tenacity.wait_none())

        with _total_outage_seam(monkeypatch, tmp_path) as (provider, server, _diag):
            with pytest.raises(ProviderRequestError) as exc:
                provider.fetch_forecast(_BERLIN, enrich_ensemble=False)

    assert not isinstance(exc.value, ProviderNotImplementedError), (
        "AC-5: Der Direktprovider-Fehlschlag darf niemals unveraendert bis "
        "zum Aufrufer durchsickern — es muss die urspruengliche "
        "ProviderRequestError des Open-Meteo-Total-Ausfalls sein."
    )
    assert exc.value.provider == "openmeteo", (
        "AC-5: die sichtbare ProviderRequestError muss vom urspruenglichen "
        f"Open-Meteo-Total-Ausfall stammen (provider='openmeteo') — war "
        f"provider={exc.value.provider!r}."
    )


# ---------------------------------------------------------------------------
# AC-6 — Total-Ausfall speist weiterhin die Log-Grundlage fuer
#         `provider_error_streak` (Go-Health-Signal, hier nur Python-Beweis).
# ---------------------------------------------------------------------------

def test_total_outage_keeps_feeding_error_log(monkeypatch, tmp_path):
    """AC-6: Given Open-Meteo UND der Direkt-Provider (seit #1144 ein echter,
    hier bewusst auf 503 gebogener `DwdDirectProvider`) fallen aus, When das
    Segment verarbeitet wird, Then bleiben die 5xx-Calls wie bisher in der
    (auf tmp umgebogenen) `openmeteo_calls.jsonl` protokolliert (Log-
    Grundlage fuer `provider_error_streak`, Go-seitig, bleibt erhalten — kein
    Log-Eintrag wird durch das Cross-Provider-Routing unterdrueckt).

    Seit #1142/#1143/#1144 ist keiner der drei Regions-Direktprovider mehr
    ein Stub — dieser Test biegt `de_direct` daher ueber einen lokalen
    503-Server auf einen echten Fehlschlag, analog
    `test_stub_provider_reraises_original_error`.
    """
    from providers.base import ProviderNotImplementedError  # noqa: F401
    from providers.dwd import DwdDirectProvider
    from providers.region_routing import direct_provider_for

    assert direct_provider_for(_BERLIN.latitude, _BERLIN.longitude) == "de_direct", (
        "AC-6 Vorbedingung: Berlin (52.52, 13.40) muss auf 'de_direct' "
        "routen (DE-Box, ausserhalb AT-Box)."
    )

    with _dwd_always_fail_server() as (dwd_url, _dwd_server):
        monkeypatch.setattr("providers.dwd.BASE_URL", dwd_url)
        monkeypatch.setattr(DwdDirectProvider._request.retry, "wait", tenacity.wait_none())

        with _total_outage_seam(monkeypatch, tmp_path) as (provider, server, diag_path):
            with pytest.raises(ProviderRequestError):
                provider.fetch_forecast(_BERLIN, enrich_ensemble=False)

    entries = _read_diagnostics(diag_path)
    server_5xx_entries = [e for e in entries if e.get("status") == 503]
    assert server_5xx_entries, (
        "AC-6: openmeteo_calls.jsonl muss weiterhin 503-Eintraege enthalten "
        f"(Log-Grundlage fuer provider_error_streak) — gefunden: {entries!r}."
    )
    assert len(server_5xx_entries) == len(server.contacted), (
        "AC-6: Jeder kontaktierte (503-antwortende) Forecast-Endpoint muss "
        f"einen 503-Log-Eintrag hinterlassen — kontaktiert={server.contacted!r}, "
        f"geloggt={server_5xx_entries!r}."
    )
