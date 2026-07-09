"""TDD RED — Issue #1115: Intra-Open-Meteo-Modell-Fallback bei Quell-Ausfall.

Root Cause (Incident 07./08.07., 14 h, 203x HTTP 503 **ausschliesslich** auf
dem DWD-Kanal `/v1/dwd-icon`): `OpenMeteoProvider.fetch_forecast` bleibt stur
beim regional gewaehlten Modell-Endpoint. Faellt genau dieser eine Kanal mit
5xx/Timeout aus (waehrend Meteo-France/ECMWF parallel 200 liefern), propagiert
die `ProviderRequestError` und **alle** Trip-Briefings fallen aus, obwohl ein
nachrangiges Modell dieselbe Koordinate abdeckt.

Diese Datei beweist die Ziel-Verhalten der Spec
`docs/specs/modules/issue_1115_openmeteo_model_fallback.md` (AC-1..AC-5):
Automatisches Ausweichen bei 5xx (feinste Aufloesung zuerst bis global ECMWF),
KEIN Ausweichen bei 4xx (kein Quell-Roulette), und lueckenlose Markierung des
Ausweichens (`meta.fallback_model`).

MOCK-FREI (KRITISCHE PROJEKT-REGEL):
Kein `Mock()`, kein `patch()`, kein `MagicMock`. Die Ausfall-Simulation laeuft
ueber einen **echten** lokalen `ThreadingHTTPServer` in einem Thread, der je
nach Request-Pfad echte HTTP-Status (200/400/503) mit echten Bodies liefert.
`fetch_forecast` sendet dagegen echte `httpx`-GET-Requests (der Provider-
Basishost wird per `monkeypatch.setattr("providers.openmeteo.BASE_HOST", ...)`
auf `http://127.0.0.1:<port>` umgebogen). Der Server protokolliert die
kontaktierten Pfade — Grundlage der Single-Contact-/Reihenfolge-Asserts.

AC-4 (Health-Signal in `/api/scheduler/status` bzw. `briefing_health.go`) ist
NICHT Teil dieser Datei: es ist ein Go-seitiges Health-Aggregat, das erst in
der Implementierungsphase (Phase 6) mit dem Provider-Fehler-Log verdrahtet
wird. Eine echte, mock-freie Pruefung braucht den dann existierenden
Go-Endpoint und wird dort abgedeckt. Hier nur als Kommentar vermerkt.

Der Test-Server liefert eine VALIDE **rohe** Open-Meteo-Antwort im exakten
Format, das `openmeteo._parse_response` erwartet (`{"hourly": {"time": [...],
"temperature_2m": [...], ...}}`) — NICHT das bereits normalisierte
`fixtures/openmeteo/*.json`-Format (Keys dort: timezone/meta/data).
"""
from __future__ import annotations

import json
import sys
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import pytest
import tenacity

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from app.config import Location
from app.models import NormalizedTimeseries
from providers.base import ProviderRequestError
from providers.openmeteo import OpenMeteoProvider

# Bekannte Open-Meteo-Modell-Forecast-Endpoints (fuer Single-Contact-Asserts:
# Air-Quality/Ensemble werden in den Tests gar nicht kontaktiert, da
# start/end=None den UV-Call und enrich_ensemble=False den Ensemble-Call
# unterdruecken).
_FORECAST_ENDPOINTS = {"/v1/meteofrance", "/v1/dwd-icon", "/v1/metno", "/v1/ecmwf"}

_ALL_MODEL_IDS = [
    "meteofrance_arome", "icon_d2", "metno_nordic", "icon_eu", "ecmwf_ifs04",
]


def _valid_raw_body() -> dict:
    """VALIDE rohe Open-Meteo-JSON-Antwort im `_parse_response`-Format.

    `_parse_response` verlangt zwingend `data["hourly"]["time"]` (Liste); alle
    weiteren Parameter werden per `hourly.get(...)` optional gelesen. Wir
    liefern eine realistische Stunden-Reihe mit Temperatur/Wind/Niederschlag,
    damit die erzeugte `NormalizedTimeseries` echte Datenpunkte enthaelt.
    """
    base = (datetime.now(timezone.utc) + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0, tzinfo=None
    )
    times = [(base + timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M") for h in range(6)]
    n = len(times)
    return {
        "latitude": 0.0,
        "longitude": 0.0,
        "generationtime_ms": 0.1,
        "utc_offset_seconds": 0,
        "timezone": "GMT",
        "hourly_units": {"temperature_2m": "°C"},
        "hourly": {
            "time": times,
            "temperature_2m": [15.0 + i * 0.5 for i in range(n)],
            "apparent_temperature": [14.0 + i * 0.5 for i in range(n)],
            "relative_humidity_2m": [70 + i for i in range(n)],
            "dewpoint_2m": [9.0 for _ in range(n)],
            "pressure_msl": [1013.0 for _ in range(n)],
            "cloud_cover": [20 + i for i in range(n)],
            "cloud_cover_low": [10 for _ in range(n)],
            "cloud_cover_mid": [5 for _ in range(n)],
            "cloud_cover_high": [5 for _ in range(n)],
            "wind_speed_10m": [5.0 + i for i in range(n)],
            "wind_direction_10m": [180 for _ in range(n)],
            "wind_gusts_10m": [12.0 for _ in range(n)],
            "precipitation": [0.0 for _ in range(n)],
            "weather_code": [1 for _ in range(n)],
            "visibility": [20000.0 for _ in range(n)],
            "precipitation_probability": [5 for _ in range(n)],
            "cape": [0.0 for _ in range(n)],
            "freezing_level_height": [3200.0 for _ in range(n)],
            "uv_index": [3.0 for _ in range(n)],
            "direct_normal_irradiance": [400.0 for _ in range(n)],
            "is_day": [1 for _ in range(n)],
        },
    }


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
        if status == 200:
            payload = json.dumps(_valid_raw_body()).encode("utf-8")
        else:
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
    """Availability-Cache, in dem JEDES Modell alle Metriken hat.

    Damit greift der WEATHER-05b-Metrik-Fallback-Block in `fetch_forecast`
    NICHT (kein zusaetzlicher `_request` fuer fehlende Metriken) — die Tests
    beobachten ausschliesslich den Modell-Endpoint-Fallback (#1115), nicht den
    aelteren Metrik-Fallback (WEATHER-05b).
    """
    from datetime import date

    path.write_text(json.dumps({
        "probe_date": date.today().isoformat(),
        "models": {
            mid: {"available": [], "unavailable": []} for mid in _ALL_MODEL_IDS
        },
    }))


@contextmanager
def _provider_seam(monkeypatch, tmp_path: Path, status_map: dict):
    """Verdrahtet Provider-Host, Availability-Cache und Diagnostics auf die
    Test-Seam und liefert (provider, server)."""
    cache_path = tmp_path / "model_availability.json"
    _write_all_available_cache(cache_path)
    monkeypatch.setattr("providers.openmeteo.AVAILABILITY_CACHE_PATH", cache_path)
    monkeypatch.setattr(
        "providers.openmeteo.DIAGNOSTICS_PATH", tmp_path / "openmeteo_calls.jsonl"
    )
    # Issue #1160: neutralisiert das tenacity-Retry-Backoff auf `_request`
    # (analog zu `_total_outage_seam` aus test_issue_1141_cross_provider_
    # fallback.py) — sonst laeuft jeder dauerhaft fehlschlagende Endpoint
    # real durch das volle Backoff (~30s), was Testlaufzeiten unnoetig
    # aufblaeht. Nur das Timing aendert sich, die fachliche Fallback-Logik
    # bleibt unveraendert.
    monkeypatch.setattr(OpenMeteoProvider._request.retry, "wait", tenacity.wait_none())
    monkeypatch.setattr(
        OpenMeteoProvider._request.retry, "stop", tenacity.stop_after_attempt(1)
    )
    with _fault_server(status_map) as (url, server):
        monkeypatch.setattr("providers.openmeteo.BASE_HOST", url)
        yield OpenMeteoProvider(), server


def _forecast_contacts(server: _FaultServer) -> list[str]:
    """Nur die Modell-Forecast-Endpoints aus dem Pfad-Protokoll."""
    return [p for p in server.contacted if p in _FORECAST_ENDPOINTS]


# Koordinaten:
# - Berlin (52.5, 13.4): meteofrance deckt bis lon 10 nicht ab -> Primaermodell
#   ist icon_d2 (/v1/dwd-icon); Ausweichkette (nach Endpoint-Dedup icon_eu==
#   /v1/dwd-icon) -> ecmwf_ifs04 (/v1/ecmwf).
# - Suedbaden (48.0, 7.0): abgedeckt von meteofrance_arome (1.3 km, Primaer),
#   icon_d2 (2 km), icon_eu (7 km) und ecmwf_ifs04 (40 km).
_BERLIN = Location(latitude=52.5, longitude=13.4, name="Berlin")
_SUEDBADEN = Location(latitude=48.0, longitude=7.0, name="Suedbaden")


# ---------------------------------------------------------------------------
# AC-1 — Ausweichen bei 5xx: der ausgefallene Modell-Kanal darf das Briefing
#         nicht scheitern lassen; das naechstbeste abdeckende Modell liefert.
# ---------------------------------------------------------------------------

def test_ac1_falls_back_to_next_model_on_5xx(monkeypatch, tmp_path):
    """AC-1: Primaermodell (icon_d2 -> /v1/dwd-icon) antwortet 503; Gregor
    weicht automatisch auf das naechstbeste abdeckende Modell aus und liefert
    gueltige Timeseries statt das Segment als Ausfall zu markieren.

    RED heute: `fetch_forecast` bleibt beim Primaer-Endpoint und propagiert die
    `ProviderRequestError` (kein Ausweich-Loop implementiert).
    """
    status_map = {"/v1/dwd-icon": 503}  # alle anderen Endpoints -> 200
    with _provider_seam(monkeypatch, tmp_path, status_map) as (provider, server):
        result = provider.fetch_forecast(_BERLIN, enrich_ensemble=False)

    assert isinstance(result, NormalizedTimeseries), (
        "AC-1: Erwartet gueltige NormalizedTimeseries vom Ersatzmodell nach "
        "503 auf dem Primaer-Endpoint /v1/dwd-icon — heute propagiert "
        "stattdessen die ProviderRequestError (kein Modell-Fallback)."
    )
    assert len(result.data) > 0, (
        "AC-1: Ersatzmodell-Timeseries enthaelt keine Datenpunkte."
    )
    assert "/v1/dwd-icon" in server.contacted, (
        "AC-1: Der ausgefallene Primaer-Endpoint wurde nie kontaktiert — "
        "Test-Seam greift nicht."
    )


# ---------------------------------------------------------------------------
# AC-2 — KEIN Ausweichen bei 4xx: inhaltlicher Fehler (z. B. Datum ausserhalb
#         Vorhersagehorizont, Bug #353) bleibt sichtbar, kein Quell-Roulette.
# ---------------------------------------------------------------------------

def test_ac2_no_fallback_on_4xx_single_endpoint_contacted(monkeypatch, tmp_path):
    """AC-2: Primaer-Endpoint liefert 400; `fetch_forecast` re-raised sofort
    `ProviderRequestError` OHNE weitere Endpoint-Versuche (nachweisbar: nur EIN
    Forecast-Endpoint kontaktiert), und der Fehler traegt den Status-Code 400
    (4xx-Unterscheidung, ueber die die Nicht-Ausweich-Entscheidung laeuft).

    RED heute: `ProviderRequestError` traegt noch keinen `status_code` (die
    4xx/5xx-Unterscheidung fuer die Fallback-Entscheidung ist nicht verdrahtet)
    -> Zugriff auf `.status_code` schlaegt fehl.
    """
    status_map = {"/v1/dwd-icon": 400}
    with _provider_seam(monkeypatch, tmp_path, status_map) as (provider, server):
        with pytest.raises(ProviderRequestError) as exc:
            provider.fetch_forecast(_BERLIN, enrich_ensemble=False)

        contacts = _forecast_contacts(server)

    assert len(contacts) == 1, (
        f"AC-2: Bei 4xx darf NICHT ausgewichen werden — es wurde mehr als ein "
        f"Forecast-Endpoint kontaktiert (Quell-Roulette): {contacts}"
    )
    assert exc.value.status_code == 400, (
        f"AC-2: ProviderRequestError muss den HTTP-Status 400 tragen, damit die "
        f"4xx-vs-5xx-Fallback-Entscheidung getroffen werden kann — "
        f"status_code={getattr(exc.value, 'status_code', '<fehlt>')!r}."
    )


# ---------------------------------------------------------------------------
# AC-3 — Ausweichen wird nie verschwiegen: `meta.fallback_model` markiert das
#         eingesprungene Modell; ohne Ausweichen bleibt es None.
# ---------------------------------------------------------------------------

def test_ac3_fallback_model_recorded_and_none_without_fallback(monkeypatch, tmp_path):
    """AC-3: Nach erzwungenem 503-Fallback ist `result.meta.fallback_model`
    gesetzt und ungleich dem primaer gewaehlten Modell (icon_d2). Kontrolle:
    voller Erfolg ohne 503 -> `fallback_model is None`.

    RED heute: der Fallback-Pfad existiert nicht -> die 503-Anfrage propagiert
    die ProviderRequestError, `fallback_model` wird nie gesetzt.
    """
    # Kontrolle zuerst: voller Erfolg, kein Ausweichen -> fallback_model None.
    with _provider_seam(monkeypatch, tmp_path, {}) as (provider, _server):
        ok = provider.fetch_forecast(_BERLIN, enrich_ensemble=False)
    assert ok.meta.fallback_model is None, (
        "AC-3 Kontrolle: Ohne Ausfall darf kein Ausweichen markiert sein "
        f"(fallback_model={ok.meta.fallback_model!r})."
    )

    # Fallback-Fall: 503 auf dem Primaer-Endpoint erzwingt Ausweichen.
    with _provider_seam(monkeypatch, tmp_path, {"/v1/dwd-icon": 503}) as (provider, _s):
        result = provider.fetch_forecast(_BERLIN, enrich_ensemble=False)

    assert result.meta.fallback_model is not None, (
        "AC-3: Nach erzwungenem 503-Fallback muss `meta.fallback_model` gesetzt "
        "sein (Ausweichen darf nie verschwiegen werden) — heute propagiert die "
        "ProviderRequestError, bevor ueberhaupt ausgewichen wird."
    )
    assert result.meta.fallback_model != "icon_d2", (
        f"AC-3: `fallback_model` muss das eingesprungene Modell sein, ungleich "
        f"dem primaer gewaehlten icon_d2 — war {result.meta.fallback_model!r}."
    )


# ---------------------------------------------------------------------------
# AC-5 — Beste verfuegbare Qualitaet: Ausweichen folgt der Prioritaets-/
#         Aufloesungskette (feiner zuerst), nie auf ein beliebiges Modell.
# ---------------------------------------------------------------------------

def test_ac5_fallback_to_next_finest_model_not_global(monkeypatch, tmp_path):
    """AC-5: Ort (48.0, 7.0) wird von AROME (1.3 km, Primaer), ICON-D2 (2 km)
    und ECMWF (40 km) abgedeckt. 503 auf AROME (/v1/meteofrance) fuehrt zum
    naechstfeineren ICON-D2 (/v1/dwd-icon), NICHT direkt zum globalen ECMWF
    (/v1/ecmwf).

    RED heute: kein Ausweich-Loop -> die 503-Anfrage propagiert.
    """
    status_map = {"/v1/meteofrance": 503}  # icon_d2 & ecmwf antworten 200
    with _provider_seam(monkeypatch, tmp_path, status_map) as (provider, server):
        result = provider.fetch_forecast(_SUEDBADEN, enrich_ensemble=False)

    assert result.meta.fallback_model == "icon_d2", (
        f"AC-5: Nach 503 auf AROME muss auf das naechstfeinere ICON-D2 "
        f"ausgewichen werden (nicht direkt auf globales ECMWF) — "
        f"fallback_model={result.meta.fallback_model!r}."
    )

    contacts = _forecast_contacts(server)
    assert "/v1/dwd-icon" in contacts, (
        f"AC-5: Der naechstfeinere Endpoint /v1/dwd-icon (ICON-D2) wurde nie "
        f"kontaktiert: {contacts}"
    )
    # ICON-D2 muss VOR ECMWF drankommen (Kette nach Aufloesung sortiert). Falls
    # ECMWF ueberhaupt kontaktiert wurde, muss es NACH /v1/dwd-icon liegen.
    if "/v1/ecmwf" in contacts:
        assert contacts.index("/v1/dwd-icon") < contacts.index("/v1/ecmwf"), (
            f"AC-5: Es wurde vor dem naechstfeineren ICON-D2 bereits das globale "
            f"ECMWF kontaktiert (Kette nicht nach Aufloesung sortiert): {contacts}"
        )
