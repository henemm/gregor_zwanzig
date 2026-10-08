"""Warn-Feed-Cache: parallele Aufrufer teilen sich EINEN Upstream-Abruf (C4-64).

SPEC: docs/specs/modules/feat_1539_s1b_s2_abruf_baustein.md
ACs:  AC-1 (ein request_fn-Aufruf, N-1 cache_hit-Zeilen), AC-3 (Fehlschlag und
      capture-id erreichen die Senken JEDES Wartenden), AC-4 (Wartende bekommen
      das Entry aus dem Flug, nicht per erneutem cache.get nach TTL-Ablauf).

RED-Erwartung: ``cached_fetch`` hat heute weder Sperre noch Flug -- jeder der
N Threads ruft ``request_fn`` selbst auf (Zaehler > 1, Journal ohne Hits).
Kein Mock-Theater: ``request_fn`` ist eine echte zaehlende Funktion am
Netz-Rand (thread-sicherer Zaehler), das Journal wird real zurueckgelesen.

Ausfuehren:
    uv run pytest tests/tdd/test_warn_feed_single_flight.py -v -rA --disable-socket
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import pytest

N = 12


class _Resp:
    """Antwort-Daten am Netz-Rand (keine Logik, nur Werte)."""

    def __init__(self, status_code=200, body=None):
        self.status_code = status_code
        self.headers: dict = {}
        self._body = {"features": []} if body is None else body

    def json(self):
        return self._body


class _CountingRequest:
    """Echte zaehlende ``request_fn``; optional verzoegert/blockiert."""

    def __init__(self, *, delay=0.0, gate=None, status=200, on_done=None):
        self._lock = threading.Lock()
        self.calls = 0
        self._delay, self._gate, self._status, self._on_done = delay, gate, status, on_done

    def __call__(self):
        with self._lock:
            self.calls += 1
        if self._gate is not None:
            assert self._gate.wait(timeout=20), "Gate nie geoeffnet"
        if self._delay:
            time.sleep(self._delay)
        if self._on_done is not None:
            self._on_done()
        return _Resp(self._status, {"features": [{"id": "x"}]})


@pytest.fixture
def journal(tmp_path, monkeypatch):
    from services.official_alerts import warn_egress

    path = tmp_path / "warn_service_calls.jsonl"
    monkeypatch.setattr(warn_egress, "WARN_CALLS_PATH_OVERRIDE", path)
    return path


@pytest.fixture
def capture_id(monkeypatch):
    """Deterministische Kennung des Eingangs-Mitschnitts (kein Plattenzugriff)."""
    from services import alert_input_capture

    monkeypatch.setattr(alert_input_capture, "capture_system", lambda **kw: "cap-1")


def _records(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def _run_parallel(n, work, *, join_s=25):
    """n Threads starten gleichzeitig (Barrier); Ausnahmen werden eingesammelt."""
    barrier = threading.Barrier(n)
    errors: list[BaseException] = []
    results: list = [None] * n

    def runner(i):
        try:
            barrier.wait(timeout=10)
            results[i] = work(i)
        except BaseException as exc:  # noqa: BLE001 -- C4-62: selbst einsammeln
            errors.append(exc)

    threads = [threading.Thread(target=runner, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    return threads, errors, results, join_s


def _finish(threads, errors, join_s):
    for t in threads:
        t.join(timeout=join_s)
    assert not any(t.is_alive() for t in threads), "Thread haengt"
    assert errors == [], f"Thread-Ausnahmen: {errors!r}"


def _fetch(cache, request_fn, **kw):
    from services.official_alerts import warn_egress

    return warn_egress.cached_fetch(
        cache=cache, cache_key="AT", service="meteoalarm:AT:p1", host="h",
        request_fn=request_fn, parse_fn=lambda r: r.json(), **kw)


def test_pruefling_liegt_im_worktree():
    from services.official_alerts import warn_egress

    expected = Path(__file__).resolve().parents[2] / "src"
    assert expected in Path(warn_egress.__file__).resolve().parents


@pytest.mark.timeout(30)
def test_ac1_n_parallele_aufrufer_ein_upstream_abruf(journal, capture_id):
    """AC-1: request_fn genau 1x, alle gleiches Ergebnis, N-1 cache_hit-Zeilen."""
    cache: dict = {}
    req = _CountingRequest(delay=0.5)
    threads, errors, results, j = _run_parallel(N, lambda i: _fetch(cache, req))
    _finish(threads, errors, j)

    assert req.calls == 1, f"request_fn {req.calls}x aufgerufen, erwartet 1x"
    assert all(r == results[0] and r is not None for r in results), results
    recs = _records(journal)
    hits = [r for r in recs if r["cache_hit"] is True]
    misses = [r for r in recs if r["cache_hit"] is False]
    assert len(misses) == 1 and len(hits) == N - 1, (len(misses), len(hits))
    assert all(r["ok"] is True for r in recs)


@pytest.mark.timeout(30)
def test_ac1_wartende_bedienen_eigene_capture_id_senke(journal, capture_id):
    """AC-3 (Erfolgsfall): jeder Thread sieht die capture-id in SEINER Senke."""
    from services.official_alerts import warn_egress

    cache: dict = {}
    req = _CountingRequest(delay=0.5)
    sinks: list = [None] * N

    def work(i):
        with warn_egress.observe_capture_id() as sink:
            sinks[i] = sink
            return _fetch(cache, req)

    threads, errors, _, j = _run_parallel(N, work)
    _finish(threads, errors, j)

    assert req.calls == 1
    assert [s["capture_ids"] for s in sinks] == [["cap-1"]] * N, [s["capture_ids"] for s in sinks]


@pytest.mark.timeout(30)
def test_ac3_fehlschlag_erreicht_fehler_senke_jedes_wartenden(journal, capture_id):
    """AC-3: Leader scheitert (HTTP 500) -> JEDE Fehler-Senke meldet failed,
    JEDE capture-id-Senke traegt die Kennung; nur ein Upstream-Abruf."""
    from services.official_alerts import warn_egress

    cache: dict = {}
    req = _CountingRequest(delay=0.5, status=500)
    fail_sinks: list = [None] * N
    cap_sinks: list = [None] * N

    def work(i):
        with warn_egress.observe_fetch_failure() as fs, warn_egress.observe_capture_id() as cs:
            fail_sinks[i], cap_sinks[i] = fs, cs
            return _fetch(cache, req)

    threads, errors, results, j = _run_parallel(N, work)
    _finish(threads, errors, j)

    assert req.calls == 1, f"request_fn {req.calls}x aufgerufen, erwartet 1x"
    assert results == [None] * N
    assert [s["failed"] for s in fail_sinks] == [True] * N, [s["failed"] for s in fail_sinks]
    assert [s["capture_ids"] for s in cap_sinks] == [["cap-1"]] * N


@pytest.mark.timeout(30)
def test_ac4_wartende_bekommen_entry_aus_dem_flug_nicht_per_cache_get(journal, capture_id):
    """AC-4: Der Leader 'schlaeft' laenger als die TTL (Uhr springt waehrend des
    Abrufs ueber die TTL). Ein erneutes cache.get waere ein falscher Miss ->
    zweiter Upstream-Abruf. Erwartet: Entry kommt aus dem Flug."""
    clock = {"t": 1000.0}
    cache: dict = {}
    gate = threading.Event()
    req = _CountingRequest(gate=gate, on_done=lambda: clock.__setitem__("t", 5000.0))
    threads, errors, results, j = _run_parallel(
        N, lambda i: _fetch(cache, req, clock=lambda: clock["t"], success_ttl=10.0))
    time.sleep(1.0)  # alle Threads sind im Aufruf, Leader haengt im Abruf
    gate.set()
    _finish(threads, errors, j)

    assert req.calls == 1, f"request_fn {req.calls}x aufgerufen (falscher Miss), erwartet 1x"
    assert all(r is not None and r == results[0] for r in results), results
    hits = [r for r in _records(journal) if r["cache_hit"] is True]
    assert len(hits) == N - 1


# --- Waechter (Fix-Loop 1, Adversary F003/F004) ------------------------------

class _VorgaengerSchreibtDict(dict):
    """Echtes ``dict``: der ERSTE ``get`` liefert Miss, danach landet ein frischer
    Eintrag im Cache -- wie ein Vorgaenger-Flug, der zwischen Erstpruefung und
    Flugstart endet."""

    def __init__(self, entry):
        super().__init__()
        self._entry = entry
        self._schon = False

    def get(self, key, default=None):
        ergebnis = super().get(key, default)
        if not self._schon:
            self._schon = True
            self[key] = self._entry
        return ergebnis


@pytest.mark.timeout(30)
def test_f003_vorgaenger_flug_schreibt_zwischen_erstpruefung_und_flugstart_kein_zweiter_abruf(
    journal, capture_id,
):
    """Erstpruefung = Miss, dann ist der Cache frisch befuellt, dann wird der
    Aufrufer Leader: die Doppelpruefung im Leader muss den Treffer bedienen,
    ``request_fn`` darf NICHT laufen."""
    entry = {"data": {"features": [{"id": "vorgaenger"}]}, "fetched_at": 1000.0,
             "ttl": 100.0, "capture_id": None}
    cache = _VorgaengerSchreibtDict(entry)
    req = _CountingRequest()

    ergebnis = _fetch(cache, req, clock=lambda: 1000.0)

    assert req.calls == 0, "Doppelpruefung fehlt: zweiter Upstream-Abruf"
    assert ergebnis == {"features": [{"id": "vorgaenger"}]}
    hits = [r for r in _records(journal) if r["cache_hit"] is True]
    assert len(hits) == 1


@pytest.mark.timeout(30)
def test_f004_zwei_cache_dicts_gleicher_schluessel_parallel_je_ein_abruf(journal, capture_id):
    """Zwei verschiedene Cache-Dicts mit identischem Schluessel teilen KEINEN
    Flug (``id(cache)`` im Flug-Schluessel): je Cache ein Upstream-Abruf."""
    cache_1: dict = {}
    cache_2: dict = {}
    req = _CountingRequest(delay=0.5)
    threads, errors, results, j = _run_parallel(
        2, lambda i: _fetch(cache_1 if i == 0 else cache_2, req))
    _finish(threads, errors, j)

    assert req.calls == 2, f"request_fn {req.calls}x aufgerufen, erwartet 2x (je Cache 1x)"
    assert all(r is not None for r in results)
