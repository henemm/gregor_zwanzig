"""Single-flight: Wartezeit ist begrenzt, danach holt der Wartende selbst ab.

SPEC: docs/specs/modules/feat_1539_s1b_s2_abruf_baustein.md
AC:   AC-5 (haengender Leader -> Wartender erreicht die Frist, holt selbst ab
      und kehrt fristgerecht zurueck, fail-open).

RED-Erwartung: ``services.single_flight`` und
``warn_egress.WARN_FLIGHT_WAIT_TIMEOUT_S`` existieren noch nicht
(ImportError / AttributeError).

Ausfuehren:
    uv run pytest tests/tdd/test_single_flight_wait_is_bounded.py -v -rA --disable-socket
"""
from __future__ import annotations

import threading
import time

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
def test_ac5_wartender_bekommt_timed_out_nach_frist():
    from services.single_flight import SingleFlight

    sf = SingleFlight()
    leader_in, release = threading.Event(), threading.Event()
    errors: list = []
    out: dict = {}

    def leader_fn():
        leader_in.set()
        assert release.wait(timeout=20)
        return "L"

    tl = _start(lambda: out.__setitem__("leader", sf.run("k", leader_fn, wait_timeout_s=20)), errors)
    assert leader_in.wait(timeout=10)

    def waiter_leader_fn():
        raise AssertionError("Wartender darf leader_fn nicht ausfuehren")

    t0 = time.monotonic()
    res = sf.run("k", waiter_leader_fn, wait_timeout_s=0.4)
    elapsed = time.monotonic() - t0

    assert res.timed_out is True and res.value is None and res.is_leader is False
    assert res.error is None
    assert 0.3 <= elapsed < 3.0, f"Wartezeit {elapsed:.2f}s ausserhalb der Frist"
    assert tl.is_alive(), "Leader haengt noch -- Wartender hat nicht auf ihn gewartet"

    release.set()
    tl.join(timeout=10)
    assert not tl.is_alive()
    assert errors == [], errors
    assert out["leader"].value == "L" and out["leader"].is_leader is True


@pytest.mark.timeout(30)
def test_ac5_cached_fetch_wartender_holt_selbst_ab(tmp_path, monkeypatch):
    from services.official_alerts import warn_egress

    monkeypatch.setattr(warn_egress, "WARN_CALLS_PATH_OVERRIDE", tmp_path / "j.jsonl")
    monkeypatch.setattr(warn_egress, "WARN_FLIGHT_WAIT_TIMEOUT_S", 0.4)

    class Resp:
        status_code = 200
        headers: dict = {}

        def __init__(self, v):
            self._v = v

        def json(self):
            return {"v": self._v}

    leader_in, release = threading.Event(), threading.Event()
    lock = threading.Lock()
    calls = {"n": 0}
    errors: list = []
    out: dict = {}
    cache: dict = {}

    def request_fn():
        with lock:
            calls["n"] += 1
            mine = calls["n"]
        if mine == 1:  # der Leader haengt
            leader_in.set()
            assert release.wait(timeout=20)
            return Resp("leader")
        return Resp("waiter")

    def call():
        return warn_egress.cached_fetch(
            cache=cache, cache_key="AT", service="s", host="h",
            request_fn=request_fn, parse_fn=lambda r: r.json())

    tl = _start(lambda: out.__setitem__("leader", call()), errors)
    assert leader_in.wait(timeout=10)

    t0 = time.monotonic()
    tw = _start(lambda: out.__setitem__("waiter", call()), errors)
    tw.join(timeout=5)
    elapsed = time.monotonic() - t0

    waiter_done = not tw.is_alive()
    leader_still_blocked = tl.is_alive()
    release.set()
    tl.join(timeout=10)
    tw.join(timeout=10)

    assert not tl.is_alive() and not tw.is_alive()
    assert errors == [], errors
    assert waiter_done and leader_still_blocked, "Wartender haette fristgerecht zurueckkehren muessen"
    assert elapsed < 3.0, f"Wartender brauchte {elapsed:.2f}s"
    assert out["waiter"] == {"v": "waiter"}, out
    assert calls["n"] == 2, "Wartender musste selbst abholen (fail-open)"
