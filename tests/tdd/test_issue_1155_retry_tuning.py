"""TDD RED — Issue #1155 (+ #1160): Retry-Begrenzung pro #1115-Fallback-Kandidat.

Spec: docs/specs/modules/issue_1155_openmeteo_retry_tuning.md (AC-1..AC-7).

Heutiger Ist-Zustand: In der Modell-Fallback-Schleife
(`OpenMeteoProvider.fetch_forecast`, `src/providers/openmeteo.py:841-867`)
durchlaeuft JEDER Kandidat (Primaer UND jeder Folge-Kandidat) den vollen
`tenacity`-Retry auf `self._request(...)` (`RETRY_ATTEMPTS=5`, exponentieller
Backoff). Bei einem Totalausfall aller Modelle kaskadiert das auf
~30s x N Kandidaten (Incident 07./08.07.).

Soll-Zustand (#1155): Nur der ERSTE tatsaechlich angefragte (Primaer-)
Kandidat behaelt den vollen Retry. Jeder Folge-Kandidat wird nur noch
hoechstens `FALLBACK_RETRY_ATTEMPTS` (=1) mal ohne Backoff versucht.

MOCK-FREI (KRITISCHE PROJEKT-REGEL):
Kein `Mock()`, kein `patch()`, kein `MagicMock`. Die Ausfall-Simulation laeuft
ueber einen echten lokalen `ThreadingHTTPServer` in einem Thread (Muster
identisch zu `tests/tdd/test_issue_1115_model_fallback.py`), der pfad- UND
aufruf-abhaengig (Sequenzen) echte HTTP-Status liefert und JEDEN Request pro
Pfad zaehlt (`server.contacted`, Grundlage der Attempt-Zaehl-Asserts).

Retry-Neutralisierung in diesen Tests: NUR das Backoff-`wait` wird auf
`tenacity.wait_none()` gesetzt (Tempo), der `stop`-Teil (`stop_after_attempt`,
Standard `RETRY_ATTEMPTS=5`) bleibt UNVERAENDERT — so bleiben echte
Attempt-Zahlen beobachtbar (Kernaussage von AC-1/AC-2), waehrend die Tests
schnell laufen (kein echtes Warten zwischen Attempts).

AC-7 (#1160-Regressionsschutz) ist der einzige Test in dieser Datei, der den
ORIGINALEN `_provider_seam` aus `test_issue_1115_model_fallback.py`
(WIEDERVERWENDET per Datei-Import, NICHT kopiert/veraendert) durchlaeuft —
dieser Seam hat (noch) KEINEN Backoff-Neutralisierer, daher braucht dieser
eine Test in der RED-Phase real ~10-20s Wall-Clock (volles Backoff auf dem
Primaer-Endpoint), bevor er an der `< 5s`-Assertion scheitert.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import threading
import time
from collections import Counter, defaultdict
from contextlib import contextmanager
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
from providers.openmeteo import RETRY_ATTEMPTS, OpenMeteoProvider

_ALL_MODEL_IDS = [
    "meteofrance_arome", "icon_d2", "metno_nordic", "icon_eu", "ecmwf_ifs04",
]

# Lappland (65.0, 18.0): NICHT von meteofrance/icon_d2 abgedeckt (Bounds), aber
# von metno_nordic (Primaer, /v1/metno), icon_eu (Folge 1, /v1/dwd-icon) und
# ecmwf_ifs04 (Folge 2, /v1/ecmwf) — 3 unterscheidbare Endpoints, 1 Primaer +
# 2 echte Folge-Kandidaten. Ausserdem AUSSERHALB aller AT/DE/FR-Regionsboxen
# (`providers.region_routing._REGIONS`) — Total-Ausfall-Faelle in dieser Datei
# loesen daher NICHT die #1141-Cross-Provider-Weiche aus, sondern werfen
# direkt die urspruengliche `ProviderRequestError` (sauberer, unvermischter
# #1155-Test).
_LAPPLAND = Location(latitude=65.0, longitude=18.0, name="Lappland")


class _FaultServer(ThreadingHTTPServer):
    """Echter HTTP-Server: zaehlt Requests PRO Pfad und liefert je Pfad
    entweder einen konstanten Status (int) oder eine Sequenz (list[int],
    haelt den letzten Wert nach Erschoepfung)."""

    def __init__(self, server_address, handler, status_map: dict):
        super().__init__(server_address, handler)
        self.status_map = status_map
        self.contacted: list[str] = []
        self._counts: dict[str, int] = defaultdict(int)
        self._lock = threading.Lock()

    def record(self, path: str) -> int:
        with self._lock:
            self.contacted.append(path)
            self._counts[path] += 1
            return self._counts[path]

    def status_for(self, path: str, call_index: int) -> int:
        spec = self.status_map.get(path, 200)
        if isinstance(spec, int):
            return spec
        idx = min(call_index - 1, len(spec) - 1)
        return spec[idx]


class _FaultHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 (http.server API)
        path = urlparse(self.path).path
        call_index = self.server.record(path)
        status = self.server.status_for(path, call_index)
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


def _valid_raw_body() -> dict:
    from datetime import datetime, timedelta, timezone

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


@contextmanager
def _fault_server(status_map: dict):
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
    from datetime import date

    path.write_text(json.dumps({
        "probe_date": date.today().isoformat(),
        "models": {
            mid: {"available": [], "unavailable": []} for mid in _ALL_MODEL_IDS
        },
    }))


@contextmanager
def _seam_1155(monkeypatch, tmp_path: Path, status_map: dict):
    """#1155-Test-Seam: identisch zu `_provider_seam` aus #1115, ABER neutralisiert
    NUR das Backoff-`wait` (nicht `stop`) — echte Attempt-Zahlen bleiben
    beobachtbar, die Tests laufen trotzdem schnell (kein echtes Warten)."""
    cache_path = tmp_path / "model_availability.json"
    _write_all_available_cache(cache_path)
    monkeypatch.setattr("providers.openmeteo.AVAILABILITY_CACHE_PATH", cache_path)
    monkeypatch.setattr(
        "providers.openmeteo.DIAGNOSTICS_PATH", tmp_path / "openmeteo_calls.jsonl"
    )
    monkeypatch.setattr(OpenMeteoProvider._request.retry, "wait", tenacity.wait_none())
    with _fault_server(status_map) as (url, server):
        monkeypatch.setattr("providers.openmeteo.BASE_HOST", url)
        yield OpenMeteoProvider(), server


def _ordered_candidate_endpoints(provider: OpenMeteoProvider, location: Location):
    """Dedupliziert die Kandidaten-Endpoints wie `fetch_forecast` es selbst tut
    (`seen_endpoints`-Set), damit die Tests nicht auf hart kodierte
    Pfade angewiesen sind. Gibt (endpoints, model_ids) parallel sortiert."""
    candidates = provider._candidate_models(location.latitude, location.longitude)
    endpoints: list[str] = []
    model_ids: list[str] = []
    for cand_id, _res, endpoint in candidates:
        if endpoint in endpoints:
            continue
        endpoints.append(endpoint)
        model_ids.append(cand_id)
    return endpoints, model_ids


# ---------------------------------------------------------------------------
# AC-1 (MUSS RED sein): Totalausfall — Primaer 5 Requests, JEDER Folge-
# Kandidat genau 1 Request. HEUTE bekommt JEDER Endpoint 5 Requests.
# ---------------------------------------------------------------------------

def test_ac1_only_followup_candidates_get_single_attempt_on_total_outage(
    monkeypatch, tmp_path
):
    """AC-1: Alle Modell-Endpoints liefern dauerhaft 503. Der Primaer-Endpoint
    behaelt den vollen Retry (RETRY_ATTEMPTS=5 Versuche), aber JEDER
    Folge-Kandidat wird nur noch EINMAL angefragt.

    RED heute: die Fallback-Schleife ruft `self._request(cand_endpoint, ...)`
    fuer JEDEN Kandidaten identisch auf (kein `first_request`-Unterschied) —
    Folge-Kandidaten durchlaufen daher ebenfalls den vollen
    RETRY_ATTEMPTS=5-Retry statt nur 1 Versuch.
    """
    probe = OpenMeteoProvider()
    endpoints, _model_ids = _ordered_candidate_endpoints(probe, _LAPPLAND)
    assert len(endpoints) >= 2, (
        f"AC-1-Setup: Lappland braucht mind. 1 Primaer + 1 Folge-Endpoint, "
        f"hatte nur {endpoints!r} — Testort ungeeignet."
    )
    primary_endpoint, followup_endpoints = endpoints[0], endpoints[1:]

    status_map = {ep: 503 for ep in endpoints}
    with _seam_1155(monkeypatch, tmp_path, status_map) as (provider, server):
        with pytest.raises(ProviderRequestError):
            provider.fetch_forecast(_LAPPLAND, enrich_ensemble=False)

    counts = Counter(server.contacted)

    assert counts[primary_endpoint] == RETRY_ATTEMPTS, (
        f"AC-1: Primaer-Endpoint {primary_endpoint!r} muss weiterhin den "
        f"vollen Retry ({RETRY_ATTEMPTS} Versuche) durchlaufen — "
        f"tatsaechlich {counts[primary_endpoint]} Requests."
    )
    for ep in followup_endpoints:
        assert counts[ep] == 1, (
            f"AC-1: Folge-Kandidat-Endpoint {ep!r} darf nur EINMAL angefragt "
            f"werden (kein Retry-Backoff-Kaskadieren) — tatsaechlich "
            f"{counts[ep]} Requests. Alle Zaehlungen: {dict(counts)!r}."
        )


# ---------------------------------------------------------------------------
# AC-2 (Guard): Primaer-Endpoint 503,503,200 -> Primaer liefert erfolgreich,
# voller Retry fuer den ersten Kandidaten unveraendert.
# ---------------------------------------------------------------------------

def test_ac2_primary_candidate_keeps_full_retry(monkeypatch, tmp_path):
    """AC-2: Primaer-Endpoint antwortet 503, 503, 200 (Sequenz). Der Primaer-
    Kandidat liefert am Ende erfolgreich, weil er weiterhin mehrfach
    wiederholt wird — unveraendertes Retry-Verhalten fuer den ersten
    Kandidaten (heute bereits erfuellt, Regressionsschutz)."""
    probe = OpenMeteoProvider()
    endpoints, _model_ids = _ordered_candidate_endpoints(probe, _LAPPLAND)
    primary_endpoint = endpoints[0]

    status_map = {primary_endpoint: [503, 503, 200]}
    with _seam_1155(monkeypatch, tmp_path, status_map) as (provider, server):
        result = provider.fetch_forecast(_LAPPLAND, enrich_ensemble=False)

    counts = Counter(server.contacted)
    assert isinstance(result, NormalizedTimeseries), (
        "AC-2: Primaer-Kandidat haette trotz zweimaligem 503 am Ende "
        "erfolgreich liefern muessen (dritter Versuch = 200)."
    )
    assert result.meta.fallback_model is None, (
        f"AC-2: Kein Fallback noetig (Primaer liefert selbst), aber "
        f"fallback_model={result.meta.fallback_model!r} gesetzt."
    )
    assert counts[primary_endpoint] >= 3, (
        f"AC-2: Primaer-Endpoint haette >=3 Requests sehen muessen "
        f"(503, 503, 200) — tatsaechlich {counts[primary_endpoint]}."
    )


# ---------------------------------------------------------------------------
# AC-3 (Guard): Primaer dauerhaft 404 -> sofortiger Raise, kein Folge-
# Kandidat kontaktiert, kein Retry (4xx-Invariante aus #1115 unveraendert).
# ---------------------------------------------------------------------------

def test_ac3_primary_4xx_raises_immediately_no_followup_no_retry(monkeypatch, tmp_path):
    """AC-3: Primaer-Endpoint liefert dauerhaft 404. `fetch_forecast` wirft
    sofort `ProviderRequestError`, OHNE Folge-Kandidaten zu kontaktieren und
    OHNE Retry auf dem Primaer-Endpoint (4xx-Invariante aus #1115 AC-2)."""
    probe = OpenMeteoProvider()
    endpoints, _model_ids = _ordered_candidate_endpoints(probe, _LAPPLAND)
    primary_endpoint = endpoints[0]

    status_map = {primary_endpoint: 404}
    with _seam_1155(monkeypatch, tmp_path, status_map) as (provider, server):
        with pytest.raises(ProviderRequestError) as exc:
            provider.fetch_forecast(_LAPPLAND, enrich_ensemble=False)

    counts = Counter(server.contacted)
    assert set(counts) == {primary_endpoint}, (
        f"AC-3: Bei 4xx darf KEIN Folge-Kandidat kontaktiert werden — "
        f"kontaktierte Endpoints: {dict(counts)!r}."
    )
    assert counts[primary_endpoint] == 1, (
        f"AC-3: Bei 4xx darf KEIN Retry auf dem Primaer-Endpoint stattfinden "
        f"— tatsaechlich {counts[primary_endpoint]} Requests."
    )
    assert exc.value.status_code == 404, (
        f"AC-3: status_code muss 404 sein — war {exc.value.status_code!r}."
    )


# ---------------------------------------------------------------------------
# AC-4 (Guard): Primaer dauerhaft 503, ein Folge-Kandidat 200 -> Non-
# Concealment-Invariante (fallback_model/fallback_reason) unveraendert.
# ---------------------------------------------------------------------------

def test_ac4_fallback_model_and_reason_recorded(monkeypatch, tmp_path):
    """AC-4: Primaer-Endpoint dauerhaft 503, erster Folge-Kandidat liefert
    200. Ergebnis traegt weiterhin `meta.fallback_reason == "model_5xx"` und
    `meta.fallback_model` = erfolgreicher Folge-Kandidat (Non-Concealment,
    unveraendert)."""
    probe = OpenMeteoProvider()
    endpoints, model_ids = _ordered_candidate_endpoints(probe, _LAPPLAND)
    assert len(endpoints) >= 2, "AC-4-Setup: braucht mind. 1 Folge-Kandidat."
    primary_endpoint, followup_endpoint = endpoints[0], endpoints[1]
    followup_id = model_ids[1]

    status_map = {primary_endpoint: 503, followup_endpoint: 200}
    with _seam_1155(monkeypatch, tmp_path, status_map) as (provider, server):
        result = provider.fetch_forecast(_LAPPLAND, enrich_ensemble=False)

    assert result.meta.fallback_reason == "model_5xx", (
        f"AC-4: fallback_reason muss 'model_5xx' sein — war "
        f"{result.meta.fallback_reason!r}."
    )
    assert result.meta.fallback_model == followup_id, (
        f"AC-4: fallback_model muss der eingesprungene Folge-Kandidat "
        f"{followup_id!r} sein — war {result.meta.fallback_model!r}."
    )


# ---------------------------------------------------------------------------
# AC-7 (#1160, MUSS RED sein): Timing-Regressionsschutz gegen fehlenden
# Backoff-Neutralisierer im #1115-`_provider_seam`.
# ---------------------------------------------------------------------------

def _load_1115_seam_module():
    """Laedt `test_issue_1115_model_fallback.py` als eigenstaendiges Modul
    (kein Paket-Import noetig) und liefert es zurueck — WIEDERVERWENDUNG des
    ORIGINALEN `_provider_seam`, keine Kopie, keine Aenderung (#1160-Fix bleibt
    ausschliesslich in jener Datei; diese RED-Phase aendert sie NICHT)."""
    path = Path(__file__).parent / "test_issue_1115_model_fallback.py"
    spec = importlib.util.spec_from_file_location(
        "_issue_1115_seam_for_1155_ac7", path
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_ac7_provider_seam_timing_regression_1160(monkeypatch, tmp_path):
    """AC-7 (#1160): Ein #1115-Fehlerinjektions-Fall (Primaer-Endpoint
    dauerhaft 503, ueber den ORIGINALEN `_provider_seam` aus
    `test_issue_1115_model_fallback.py`) muss klar unter 5s Wall-Clock-Zeit
    bleiben, sobald `_provider_seam` denselben Backoff-Neutralisierer wie
    `_total_outage_seam` (#1141) anwendet.

    RED heute: `_provider_seam` neutralisiert das tenacity-Backoff NICHT
    (anders als `_total_outage_seam`) — der Primaer-Endpoint durchlaeuft das
    volle exponentielle Backoff (~16s realer Wartezeit fuer 5 Attempts,
    RETRY_WAIT_MIN=2/MAX=60) BEVOR ueberhaupt ausgewichen wird. Der Test
    braucht daher in der RED-Phase tatsaechlich diese Zeit, bevor er an der
    `< 5s`-Assertion scheitert (kein Kuerzel moeglich, ohne den Seam selbst
    zu aendern — das ist der GREEN-Fix fuer #1160, nicht Teil dieser Datei).
    """
    seam_mod = _load_1115_seam_module()
    status_map = {"/v1/dwd-icon": 503}  # Berlin-Primaer (icon_d2) dauerhaft 503

    start = time.monotonic()
    with seam_mod._provider_seam(monkeypatch, tmp_path, status_map) as (
        provider, server,
    ):
        result = provider.fetch_forecast(seam_mod._BERLIN, enrich_ensemble=False)
    elapsed = time.monotonic() - start

    assert isinstance(result, NormalizedTimeseries), (
        "AC-7-Setup: Ausweichen auf ECMWF haette erfolgreich liefern muessen."
    )
    assert elapsed < 5.0, (
        f"AC-7 (#1160): `_provider_seam` ohne Backoff-Neutralisierer liess "
        f"diesen Testfall {elapsed:.1f}s laufen (volles tenacity-Backoff auf "
        f"dem Primaer-Endpoint) — erwartet < 5s nach Einbau des #1141-"
        f"Neutralisierer-Musters (`wait_none()` + `stop_after_attempt(1)`) "
        f"in `_provider_seam`."
    )
