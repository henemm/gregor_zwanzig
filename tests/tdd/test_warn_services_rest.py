"""TDD RED — Issue #1348 AC-11: die vier übrigen Warn-Dienste auf ``warn_egress``.

SPEC: docs/specs/modules/warn_service_consumption_rest.md (AC-1 bis AC-6)
Vorbild-Test: tests/tdd/test_warn_service_egress.py (Scheibe 2a, geteilter Helfer)
Vorbild-Migration: src/services/official_alerts/meteoalarm.py

Deckt die vier noch NICHT migrierten amtlichen Warn-Dienste ab:

    vigilance · geosphere_warn · meteo_forets · massif_closure

In der RED-Phase sind die AC-Tests ABSICHTLICH rot: heute ist ``CACHE_TTL ==
300.0``, der 429-Pfad läuft über ``raise_for_status()`` in einen generischen
``except`` (kein Backoff, kein 429-lauter Log) und es wird KEINE
``warn_service_calls.jsonl``-Zeile geschrieben. Nach der Migration auf
``warn_egress.cached_fetch`` werden sie grün.

Kein Mock-Theater (CLAUDE.md Test-Politik „Zwei Schichten"):
- Der „Netz-Sentinel" ist ein ECHTER lokaler HTTP-Server (kein Netz, kein Mock
  der HTTP-Bibliothek, wie ``test_meteoalarm_source.py``). Er zählt jeden
  eingehenden Request; ein Cache-Hit darf ihn nie erreichen (``request_count==0``
  beweist „kein echter Call").
- 429/200-Antworten kommen als ECHTE HTTP-Antworten dieses lokalen Servers.
- Die jsonl-Zähler-Datei wird real geschrieben (temp-Pfad via ``monkeypatch``)
  und real zurückgelesen.
- Zeit wird deterministisch gesteuert, indem der Cache-Eintrag mit einem
  ``fetched_at`` in der Vergangenheit vorbelegt wird (kein echtes Warten).

Der erste Test ist ein CHARAKTERISIERUNGS-ANKER des HEUTIGEN Zustands
(``CACHE_TTL == 300.0``) und bewusst GRÜN. Er wird in der GREEN-Phase durch die
Migration rot und ist dann zu entfernen (Regressions-Anker, kein Dauertest).
"""
from __future__ import annotations

import http.server
import json
import threading
import time
from contextlib import contextmanager

import pytest

from services.official_alerts import (
    geosphere_warn,
    massif_closure,
    meteo_forets,
    vigilance,
    warn_egress,
)

# Zwei verschiedene französische Orte -> zwei verschiedene Départements (06/13),
# beide vom Mapper auflösbar (siehe test_issue_1035_vigilance_source.py).
NICE = (43.7102, 7.2620)
MARSEILLE = (43.2965, 5.3698)


# ---------------------------------------------------------------------------
# Echter lokaler HTTP-Server als Netz-Sentinel (kein Mock, kein externes Netz).
# ---------------------------------------------------------------------------

@contextmanager
def _local_server(status: int, *, body: bytes = b"{}", retry_after: str | None = None):
    """Startet einen echten HTTP-Server auf 127.0.0.1, der für jeden Pfad
    ``status`` (+ optional ``Retry-After``) liefert und Requests zählt."""

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 - stdlib-Signatur
            self.server.request_count += 1  # type: ignore[attr-defined]
            self.send_response(status)
            if retry_after is not None:
                self.send_header("Retry-After", retry_after)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):  # Testlauf-Output nicht zumüllen
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
    srv.request_count = 0  # type: ignore[attr-defined]
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        yield srv
    finally:
        srv.shutdown()
        thread.join(timeout=2)


def _reset_keyed(mod) -> None:
    """Modul-Cache der keyed Dienste leeren (Cache-State lebt über Tests hinweg)."""
    mod._cache.clear()


def _reset_vigilance(mod) -> None:
    """Vigilance-Cache neutralisieren — funktioniert für den heutigen flachen
    Cache (``{"data","fetched_at","ttl"}``) UND einen künftigen keyed Adapter."""
    cache = mod._cache
    if isinstance(cache, dict) and "fetched_at" in cache:
        cache["data"] = None
        cache["fetched_at"] = None
        cache["ttl"] = mod.CACHE_TTL
    elif isinstance(cache, dict):
        cache.clear()


# Pro Dienst: Modul, URL-Konstante (zum Umlenken), Aufruf der Cache-Fetch-Fn,
# erwarteter jsonl-``service``-Name + Host, Cache-Reset, Cache-Key (keyed).
_CONFIGS = [
    {
        "id": "geosphere_warn",
        "mod": geosphere_warn,
        "url_attr": "GEOSPHERE_WARN_URL",
        "local_url": lambda port: f"http://127.0.0.1:{port}/w",
        "call": lambda mod: mod._get_cached_warnings(47.0, 13.0),
        "reset": _reset_keyed,
        "service": "geosphere_warn",
        "host": "warnungen.zamg.at",
        "keyed": True,
        "cache_key": lambda mod: mod._round_coord(47.0, 13.0),
        "needs_mf_key": False,
    },
    {
        "id": "meteo_forets",
        "mod": meteo_forets,
        "url_attr": "METEO_FORETS_URL",
        "local_url": lambda port: f"http://127.0.0.1:{port}/f",
        "call": lambda mod: mod._get_cached_departement("83"),
        "reset": _reset_keyed,
        "service": "meteo_forets",
        "host": "public-api.meteofrance.fr",
        "keyed": True,
        "cache_key": lambda mod: "83",
        "needs_mf_key": True,
    },
    {
        "id": "massif_closure",
        "mod": massif_closure,
        "url_attr": "_ENDPOINT",
        "local_url": lambda port: f"http://127.0.0.1:{port}/s/{{src}}/{{ymd}}.json",
        "call": lambda mod: mod._get_cached_daily_json("83"),
        "reset": _reset_keyed,
        "service": "massif_closure",
        "host": "www.risque-prevention-incendie.fr",
        "keyed": True,
        "cache_key": lambda mod: "83",
        "needs_mf_key": False,
    },
    {
        "id": "vigilance",
        "mod": vigilance,
        "url_attr": "VIGILANCE_URL",
        "local_url": lambda port: f"http://127.0.0.1:{port}/v",
        "call": lambda mod: mod._get_cached_cartevigilance(),
        "reset": _reset_vigilance,
        "service": "vigilance",
        "host": "public-api.meteofrance.fr",
        "keyed": False,
        "cache_key": None,
        "needs_mf_key": True,
    },
]

ALL = [pytest.param(cfg, id=cfg["id"]) for cfg in _CONFIGS]
KEYED = [pytest.param(cfg, id=cfg["id"]) for cfg in _CONFIGS if cfg["keyed"]]


# ---------------------------------------------------------------------------
# Schritt 0 — CHARAKTERISIERUNGS-ANKER: nach der Migration (Issue #1348)
# ENTFERNT. Er nagelte den Vor-Umbau-Wert ``CACHE_TTL == 300.0`` fest; sein
# Zweck (Regressions-Anker vor dem Umbau) ist mit der Migration erfüllt. Den
# neuen Sollwert (1800s) deckt jetzt ``test_ttl_ist_dreissig_minuten`` (AC-1).
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# AC-1 — Erfolgs-TTL == 1800s (über warn_egress.WARN_SUCCESS_TTL), Failure 60s
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("cfg", ALL)
def test_ttl_ist_dreissig_minuten(cfg):
    """AC-1: GIVEN jeder der vier Dienste, WHEN das Modul importiert wird, THEN
    ist der Erfolgs-Cache-TTL 1800.0s (== ``warn_egress.WARN_SUCCESS_TTL``) und
    der Failure-TTL bleibt 60.0s.

    RED heute: ``CACHE_TTL == 300.0`` -> erste Assertion schlägt fehl."""
    mod = cfg["mod"]
    assert mod.CACHE_TTL == warn_egress.WARN_SUCCESS_TTL == 1800.0, (
        f"{cfg['id']}: Erfolgs-TTL muss auf 1800.0s (30 min) steigen, war {mod.CACHE_TTL}"
    )
    assert mod.FAILURE_CACHE_TTL == warn_egress.WARN_FAILURE_TTL == 60.0, (
        f"{cfg['id']}: Failure-TTL bleibt 60.0s, war {mod.FAILURE_CACHE_TTL}"
    )


# ---------------------------------------------------------------------------
# AC-2 — Cache-Hit im TTL-Fenster löst KEINEN echten Call aus (Netz-Sentinel)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("cfg", KEYED)
def test_cache_hit_kein_call(cfg, monkeypatch):
    """AC-2: GIVEN ein erfolgreicher Cache-Eintrag, 900s alt und mit dem
    Erfolgs-TTL des Diensts hinterlegt, WHEN die Cache-Fetch-Fn erneut mit
    demselben Schlüssel läuft, THEN erreicht der lokale Server 0 Requests
    (Netz-Sentinel-Beweis) und die gecachten Daten kommen zurück.

    RED heute: mit ``CACHE_TTL == 300`` gilt ein 900s alter Eintrag als
    abgelaufen -> echter Call -> ``request_count == 1``. Nach Migration
    (``CACHE_TTL == 1800``) ist 900s < 1800s -> Cache-Hit, kein Call.

    Vigilance ist hier ausgenommen (flacher National-Cache) und wird durch
    ``test_vigilance_ein_national_call_fuer_alle`` (AC-5) abgedeckt."""
    mod = cfg["mod"]
    if cfg["needs_mf_key"]:
        monkeypatch.setenv("GZ_METEOFRANCE_APIKEY", "dummy-test-token-ac2")
    cfg["reset"](mod)
    marker = {"_cached_marker": cfg["id"]}
    key = cfg["cache_key"](mod)
    with _local_server(200) as srv:
        monkeypatch.setattr(mod, cfg["url_attr"], cfg["local_url"](srv.server_port))
        # Eintrag mit dem Erfolgs-TTL des Diensts (heute 300, nach Umbau 1800),
        # 900s alt -> unter neuem TTL ein Treffer, unter altem ein Miss.
        mod._cache[key] = {
            "data": marker,
            "fetched_at": time.monotonic() - 900.0,
            "ttl": mod.CACHE_TTL,
        }
        result = cfg["call"](mod)
        request_count = srv.request_count
    cfg["reset"](mod)

    assert request_count == 0, (
        f"{cfg['id']}: Cache-Hit im TTL-Fenster darf KEINEN echten Call auslösen "
        f"(Netz-Sentinel), lokaler Server sah {request_count} Request(s)."
    )
    assert result == marker, (
        f"{cfg['id']}: Cache-Hit muss die gecachten Daten liefern, war {result!r}"
    )


# ---------------------------------------------------------------------------
# AC-3 — 429 -> Backoff max(retry_after, 1800), LAUT geloggt ("429" + Dauer)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("cfg", ALL)
def test_429_backoff_laut(cfg, monkeypatch, caplog):
    """AC-3: GIVEN eine echte HTTP-429-Antwort mit ``Retry-After: 120``, WHEN
    die Cache-Fetch-Fn sie verarbeitet, THEN wird das Backoff-Fenster auf
    ``max(120, 1800) = 1800`` gesetzt und LAUT geloggt (WARNING enthält "429"
    UND die Backoff-Dauer 1800).

    RED heute: der 429 läuft über ``raise_for_status()`` in den generischen
    ``except`` -> Log-Text nennt weder "429" noch "1800"."""
    mod = cfg["mod"]
    monkeypatch.setenv("GZ_METEOFRANCE_APIKEY", "dummy-test-token-ac3")
    cfg["reset"](mod)
    with _local_server(429, retry_after="120") as srv:
        monkeypatch.setattr(mod, cfg["url_attr"], cfg["local_url"](srv.server_port))
        with caplog.at_level("WARNING"):
            result = cfg["call"](mod)
    cfg["reset"](mod)

    assert result is None, f"{cfg['id']}: 429 ist kein Erfolg -> None, war {result!r}"
    warnings = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
    assert any("429" in m for m in warnings), (
        f"{cfg['id']}: 429 muss LAUT geloggt werden (Text '429'). "
        f"RED heute: generischer Fehler-Log ohne '429'. Records: {warnings}"
    )
    assert any("1800" in m for m in warnings), (
        f"{cfg['id']}: 429-Log muss die Backoff-Dauer 1800s nennen (max(120,1800)). "
        f"RED heute: kein Backoff berechnet. Records: {warnings}"
    )


# ---------------------------------------------------------------------------
# AC-4 — Zähler-jsonl-Zeile mit korrektem service-Namen + Host/status/cache_hit
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("cfg", ALL)
def test_zaehler_service_name(cfg, monkeypatch, tmp_path):
    """AC-4: GIVEN ein echter Call über ``cached_fetch``, WHEN er läuft, THEN
    hängt ``warn_service_calls.jsonl`` GENAU eine Zeile an mit korrektem
    ``service``-Namen (vigilance|geosphere_warn|meteo_forets|massif_closure),
    Host, ``status=200``, ``cache_hit=false`` und vorhandenem ``retry_after``.

    RED heute: der Dienst schreibt gar keine jsonl-Zeile -> 0 Zeilen."""
    mod = cfg["mod"]
    monkeypatch.setenv("GZ_METEOFRANCE_APIKEY", "dummy-test-token-ac4")
    jsonl = tmp_path / "warn_service_calls.jsonl"
    monkeypatch.setattr(warn_egress, "WARN_CALLS_PATH", jsonl)
    cfg["reset"](mod)
    with _local_server(200) as srv:
        monkeypatch.setattr(mod, cfg["url_attr"], cfg["local_url"](srv.server_port))
        cfg["call"](mod)
    cfg["reset"](mod)

    lines = (
        [ln for ln in jsonl.read_text(encoding="utf-8").splitlines() if ln.strip()]
        if jsonl.exists()
        else []
    )
    assert len(lines) == 1, (
        f"{cfg['id']}: genau eine Zähler-Zeile erwartet, war {len(lines)}. "
        f"RED heute: der Dienst schreibt keine warn_service_calls.jsonl-Zeile."
    )
    rec = json.loads(lines[0])
    assert rec["service"] == cfg["service"], (
        f"{cfg['id']}: jsonl-service muss '{cfg['service']}' sein, war {rec['service']!r}"
    )
    assert rec["host"] == cfg["host"], (
        f"{cfg['id']}: jsonl-host muss '{cfg['host']}' sein, war {rec['host']!r}"
    )
    assert rec["status"] == 200
    assert rec["cache_hit"] is False
    assert "retry_after" in rec


# ---------------------------------------------------------------------------
# AC-5 — Vigilance-Sonderfall: EIN nationaler Call bedient alle Orts-Lookups
# ---------------------------------------------------------------------------

def test_vigilance_ein_national_call_fuer_alle(monkeypatch):
    """AC-5: GIVEN Vigilance (flacher National-Cache), WHEN zwei Lookups für
    VERSCHIEDENE Koordinaten (Nice/06, Marseille/13) im TTL-Fenster erfolgen,
    THEN löst nur der erste einen echten Call aus, der zweite ist ein Cache-Hit
    (fester National-Key bewahrt das „ein Call bedient alle Orte"-Verhalten).

    GRÜN heute (Regressions-/Charakterisierungs-Guard). Die Migration darf diese
    Invariante NICHT brechen — ein pro-Koordinate-Key würde zwei Calls erzeugen."""
    from services.official_alerts.vigilance import VigilanceSource

    monkeypatch.setenv("GZ_METEOFRANCE_APIKEY", "dummy-test-token-ac5")
    _reset_vigilance(vigilance)
    body = b'{"product": {"periods": []}}'
    with _local_server(200, body=body) as srv:
        monkeypatch.setattr(
            vigilance, "VIGILANCE_URL", f"http://127.0.0.1:{srv.server_port}/v"
        )
        source = VigilanceSource()
        source.fetch(*NICE)
        source.fetch(*MARSEILLE)
        request_count = srv.request_count
    _reset_vigilance(vigilance)

    assert request_count == 1, (
        "Vigilance: EIN nationaler Call muss beide Orts-Lookups im TTL-Fenster "
        f"bedienen (fester National-Key) — der zweite muss ein Cache-Hit sein, "
        f"war {request_count} echte Call(s)."
    )
