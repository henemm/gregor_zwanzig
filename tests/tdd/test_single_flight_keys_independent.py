"""Single-flight: ein haengender Flug blockiert andere Schluessel nicht.

SPEC: docs/specs/modules/feat_1539_s1b_s2_abruf_baustein.md
AC:   AC-2 (Schluessel B kehrt zurueck, waehrend Leader A haengt; der interne
      Registrier-Lock wird nie ueber den Netzabruf gehalten).

RED-Erwartung: ``services.single_flight`` existiert noch nicht (ImportError).
Der ``cached_fetch``-Test mit zwei Schluesseln ist ein Waechtertest und heute
schon gruen (kein Flug, also keine Blockade); er bewacht ab GREEN, dass der
Flug Schluessel nicht verkettet.

Ausfuehren:
    uv run pytest tests/tdd/test_single_flight_keys_independent.py -v -rA --disable-socket
"""
from __future__ import annotations

import threading

import pytest


def _start(target, errors):
    def runner():
        try:
            target()
        except BaseException as exc:  # noqa: BLE001 -- C4-62
            errors.append(exc)

    t = threading.Thread(target=runner)
    t.start()
    return t


@pytest.mark.timeout(30)
def test_ac2_anderer_schluessel_wartet_nicht_auf_haengenden_leader():
    from services.single_flight import SingleFlight

    sf = SingleFlight()
    a_in, release_a = threading.Event(), threading.Event()
    errors: list = []
    out: dict = {}

    def leader_a():
        assert sf._lock.locked() is False
        a_in.set()
        assert release_a.wait(timeout=20)
        return "A"

    def run_a():
        out["a"] = sf.run("A", leader_a, wait_timeout_s=20)

    def run_b():
        def leader_b():
            # Registrier-Lock darf waehrend des Abrufs nicht gehalten werden
            assert sf._lock.locked() is False
            return "B"

        out["b"] = sf.run("B", leader_b, wait_timeout_s=20)

    ta = _start(run_a, errors)
    assert a_in.wait(timeout=10)
    tb = _start(run_b, errors)
    tb.join(timeout=5)
    b_done_while_a_blocked = not tb.is_alive() and ta.is_alive()
    release_a.set()
    ta.join(timeout=10)
    tb.join(timeout=10)

    assert not ta.is_alive() and not tb.is_alive()
    assert errors == [], errors
    assert b_done_while_a_blocked, "B musste fertig sein, waehrend A noch haengt"
    assert out["b"].value == "B" and out["b"].is_leader is True
    assert out["a"].value == "A" and out["a"].is_leader is True


@pytest.mark.timeout(30)
def test_ac2_registrier_lock_frei_nach_lauf_und_nach_fehler():
    from services.single_flight import SingleFlight

    sf = SingleFlight()
    res = sf.run("k", lambda: 1, wait_timeout_s=5)
    assert res.value == 1 and res.error is None and res.timed_out is False
    assert sf._lock.locked() is False

    boom = RuntimeError("boom")

    def failing():
        raise boom

    res = sf.run("k", failing, wait_timeout_s=5)  # run() wirft nie
    assert res.error is boom and res.is_leader is True
    assert sf._lock.locked() is False
    # Flug wurde entfernt: naechster Lauf ist wieder Leader
    assert sf.run("k", lambda: 2, wait_timeout_s=5).is_leader is True


@pytest.mark.timeout(30)
def test_ac2_cached_fetch_zwei_schluessel_unabhaengig(tmp_path, monkeypatch):
    """Waechtertest (heute gruen): cached_fetch fuer Schluessel B kehrt zurueck,
    waehrend Schluessel A im Abruf haengt."""
    from services.official_alerts import warn_egress

    monkeypatch.setattr(warn_egress, "WARN_CALLS_PATH_OVERRIDE", tmp_path / "j.jsonl")

    class Resp:
        status_code = 200
        headers: dict = {}

        def __init__(self, v):
            self._v = v

        def json(self):
            return {"v": self._v}

    a_in, release_a = threading.Event(), threading.Event()
    cache: dict = {}
    errors: list = []
    out: dict = {}

    def req_a():
        a_in.set()
        assert release_a.wait(timeout=20)
        return Resp("A")

    def call(key, req):
        return warn_egress.cached_fetch(
            cache=cache, cache_key=key, service="s", host="h",
            request_fn=req, parse_fn=lambda r: r.json())

    ta = _start(lambda: out.__setitem__("a", call("A", req_a)), errors)
    assert a_in.wait(timeout=10)
    tb = _start(lambda: out.__setitem__("b", call("B", lambda: Resp("B"))), errors)
    tb.join(timeout=5)
    b_ok = not tb.is_alive() and ta.is_alive()
    release_a.set()
    ta.join(timeout=10)
    tb.join(timeout=10)

    assert not ta.is_alive() and not tb.is_alive()
    assert errors == [], errors
    assert b_ok, "Schluessel B hat auf haengenden Schluessel A gewartet"
    assert out["b"] == {"v": "B"} and out["a"] == {"v": "A"}
