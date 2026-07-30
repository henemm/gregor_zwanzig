"""Jede Journal-Zeile traegt ihren Ausgang: Erfolg, Fehlschlag, eigener Rueckzug.

SPEC: docs/specs/modules/fix_1422_warn_ausfall_alarm.md (Scheibe S1, AC-1..AC-3)

Kein Mock-Theater: Antworten kommen aus einem ECHTEN lokalen HTTP-Server ueber
echte ``httpx.get``-Aufrufe, Fehlschlaege aus einem echten Verbindungsfehler bzw.
einem echten Ausnahme-Objekt des Produktivcodes; die Journal-Zeilen werden real
zurueckgelesen. Pruefling-Aufloesung ueber ``pythonpath`` relativ zur Repo-Wurzel
DIESER Testdatei (Regel #1409).
"""
from __future__ import annotations

import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import pytest


class _StatusStub(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 -- antwortet mit dem Statuscode aus dem Pfad
        body = b'{"features": []}'
        self.send_response(int(self.path.strip("/")))
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass  # Server-Logs stumm halten


@pytest.fixture
def stub_url():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _StatusStub)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture
def journal(tmp_path, monkeypatch):
    from services.official_alerts import warn_egress

    path = tmp_path / "warn_service_calls.jsonl"
    monkeypatch.setattr(warn_egress, "WARN_CALLS_PATH", path)
    return path


def _records(path) -> list[dict]:
    return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def _dead_url() -> str:
    sock = socket.socket()  # geschlossener Port -> echter httpx.ConnectError
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return f"http://127.0.0.1:{port}/200"


def _get(url: str):
    return lambda: httpx.get(url, timeout=5.0)


def _fetch(*, request_fn, cache=None, service="meteoalarm:AT:p1", key="AT", **kwargs):
    from services.official_alerts import warn_egress

    return warn_egress.cached_fetch(
        cache={} if cache is None else cache, cache_key=key, service=service,
        host="127.0.0.1", request_fn=request_fn, parse_fn=lambda r: r.json(),
        clock=lambda: 1000.0, **kwargs)


def test_erfolgreicher_abruf_ist_als_erfolg_erkennbar(journal, stub_url):
    """Ein echter 200er-Abruf ist eindeutig Erfolg -- und kein eigener Rueckzug."""
    _fetch(request_fn=_get(f"{stub_url}/200"))

    rec = _records(journal)[0]
    assert rec.get("ok") is True, f"Erfolg muss als Erfolg markiert sein, war {rec!r}"
    assert rec.get("self_throttled") is False, (
        f"ein Erfolg ist kein selbst auferlegter Rueckzug, war {rec!r}")


def test_fehlgeschlagener_abruf_ist_kein_selbst_auferlegter_rueckzug(journal, stub_url):
    """Anbieter-Fehlschlag (HTTP 500) und echter Verbindungsfehler sind beide
    Fehlschlag UND nicht selbst auferlegt -- sonst alarmiert Teil B falsch."""
    _fetch(request_fn=_get(f"{stub_url}/500"))
    _fetch(request_fn=_get(_dead_url()), key="AT2")

    for rec in _records(journal):
        assert rec.get("ok") is False, f"Fehlschlag muss ok=false tragen, war {rec!r}"
        assert rec.get("self_throttled") is False, (
            f"Anbieter-Ausfall darf nicht als eigener Rueckzug gelten, war {rec!r}")


def test_cache_treffer_auf_erfolg_bleibt_erfolg(journal, stub_url):
    """Ein Treffer auf zuvor erfolgreich geholte Daten ist ein gesunder Zustand."""
    cache: dict = {}
    _fetch(request_fn=_get(f"{stub_url}/200"), cache=cache)
    _fetch(request_fn=_get(f"{stub_url}/500"), cache=cache)  # trifft den Cache

    hit = _records(journal)[1]
    assert hit["cache_hit"] is True
    assert hit.get("ok") is True, f"Treffer auf gute Daten bleibt Erfolg, war {hit!r}"


def test_cache_treffer_auf_fehlgeschlagenen_eintrag_ist_kein_erfolg(journal, stub_url):
    """AC-3: Ein Treffer im laufenden Fehlschlag-Fenster liefert keine Daten, sieht
    heute aber aus wie ein Treffer auf gute Daten (``status: null``) -- sonst
    verschwindet ein Dauerausfall hinter Cache-Treffern."""
    cache: dict = {}
    _fetch(request_fn=_get(f"{stub_url}/500"), cache=cache)
    _fetch(request_fn=_get(f"{stub_url}/200"), cache=cache)  # trifft den Fehlschlag

    hit = _records(journal)[1]
    assert hit["cache_hit"] is True
    assert hit.get("ok") is False, (
        f"Treffer auf einen gecachten Fehlschlag ist kein Erfolg, war {hit!r}")


def test_selbst_auferlegter_rueckzug_markiert_sich_selbst(journal):
    """AC-2: Das erschoepfte EIGENE Tagesbudget (echtes ``_MeteoAlarmBudgetExhausted``,
    kein Netz-Call) muss vom echten Anbieter-Ausfall unterscheidbar sein."""
    from services.official_alerts.meteoalarm import _MeteoAlarmBudgetExhausted

    def _budget_exhausted():
        raise _MeteoAlarmBudgetExhausted("MeteoAlarm-Tagesbudget erschoepft")

    _fetch(request_fn=_budget_exhausted)
    _fetch(request_fn=_get(_dead_url()), key="AT2")

    eigen, fremd = _records(journal)
    assert eigen.get("ok") is False and eigen.get("self_throttled") is True, (
        f"eigener Rueckzug muss als solcher markiert sein, war {eigen!r}")
    assert fremd.get("ok") is False and fremd.get("self_throttled") is False, (
        f"echter Anbieter-Ausfall darf NICHT als eigener Rueckzug gelten, war {fremd!r}")


def test_nicht_zustaendig_treffer_zaehlt_als_erfolg(journal, stub_url):
    """AC-1: Ein 404 ausserhalb des Zustaendigkeitsbereichs (GeoSphere) ist eine
    gueltige Antwort -- kein Ausfall, obwohl derselbe Code sonst Fehlschlag ist."""
    _fetch(request_fn=_get(f"{stub_url}/404"), service="geosphere_warn",
           not_covered_statuses=frozenset({404}))
    _fetch(request_fn=_get(f"{stub_url}/404"), service="geosphere_warn", key="AT2")

    nicht_zustaendig, echter_fehler = _records(journal)
    assert nicht_zustaendig["status"] == 404 and nicht_zustaendig.get("ok") is True, (
        f"'nicht zustaendig' ist ein Erfolg, war {nicht_zustaendig!r}")
    assert echter_fehler["status"] == 404 and echter_fehler.get("ok") is False, (
        f"derselbe Statuscode ohne Zustaendigkeits-Regel bleibt Fehlschlag, "
        f"war {echter_fehler!r}")


def _health(records: list[dict]) -> dict:
    """Auswertung, wie sie ein Betreiber (bzw. S2) faehrt: nur echte Abrufe
    (``cache_hit=false``), gruppiert nach kanonischem Dienstnamen."""
    out: dict = {}
    for rec in records:
        if rec.get("cache_hit") or "ok" not in rec:
            continue
        cur = out.setdefault(rec["service"].split(":", 1)[0],
                             {"last_success_at": None, "last_attempt_at": None})
        cur["last_attempt_at"] = rec["ts"]
        if rec["ok"]:
            cur["last_success_at"] = rec["ts"]
    return out


def test_dauerausfall_ohne_einen_einzigen_erfolg_ist_ablesbar(journal, stub_url):
    """Der Fall aus #1422: MeteoAlarm liefert ueber Stunden nichts, ein anderer
    Dienst ist gesund -- kein Erfolg trotz laufender Versuche muss ablesbar sein."""
    dead = _dead_url()
    for runde in range(6):
        cache: dict = {}
        _fetch(request_fn=_get(dead), cache=cache, key=f"AT{runde}")
        _fetch(request_fn=_get(dead), cache=cache, key=f"AT{runde}")  # Cache-Treffer
    _fetch(request_fn=_get(f"{stub_url}/200"), service="geosphere_warn", key="ZAMG")

    health = _health(_records(journal))
    assert health["meteoalarm"]["last_attempt_at"] is not None, (
        "es gab laufende Versuche -- der Dienst ist in Gebrauch")
    assert health["meteoalarm"]["last_success_at"] is None, (
        f"kein einziger Erfolg muss ablesbar sein, war {health['meteoalarm']!r}")
    assert health["geosphere_warn"]["last_success_at"] is not None, (
        "der gesunde Dienst muss davon unterscheidbar bleiben")
