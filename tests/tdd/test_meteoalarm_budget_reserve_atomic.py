"""TDD RED fuer Issue #1539 (Workflow feat-1539-s1b-s2-abruf-baustein), Teil B.

SPEC: docs/specs/modules/feat_1539_s1b_s2_abruf_baustein.md (Abschnitt D)
AC-7: atomares ``MeteoAlarmBudgetGate.reserve(now=None) -> bool``.

RED-Erwartung: ``reserve`` existiert noch nicht -> AttributeError.

Ausfuehrung:
    uv run pytest tests/tdd/test_meteoalarm_budget_reserve_atomic.py -v -rA --disable-socket

Kein Mock: echte Datei in ``tmp_path``, echte Threads; Budget ueber die echte
Env-Variable ``GZ_METEOALARM_DAILY_BUDGET``.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone

import pytest

from services.official_alerts.meteoalarm_budget import MeteoAlarmBudgetGate

JOIN_TIMEOUT_S = 30.0


def _calls(root) -> int:
    return json.loads((root / "diagnostics" / "meteoalarm_budget.json").read_text())["calls"]


@pytest.mark.timeout(60)
def test_parallel_reserve_genau_restbudget_mal_true(tmp_path, monkeypatch):
    """AC-7: Budget 10, Vorlauf 6 (ueber record_call) -> M=4; N=16 parallel ->
    genau 4 True, ``calls`` steht bei genau 10."""
    monkeypatch.setenv("GZ_METEOALARM_DAILY_BUDGET", "10")
    seed = MeteoAlarmBudgetGate(data_root=tmp_path)
    for _ in range(6):
        seed.record_call()
    n = 16
    barrier = threading.Barrier(n)
    results: list = []
    errors: list = []
    lock = threading.Lock()

    def _worker() -> None:
        try:
            barrier.wait(timeout=JOIN_TIMEOUT_S)
            value = MeteoAlarmBudgetGate(data_root=tmp_path).reserve()
            with lock:
                results.append(value)
        except BaseException as exc:  # noqa: BLE001
            with lock:
                errors.append(exc)

    threads = [threading.Thread(target=_worker, daemon=True) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=JOIN_TIMEOUT_S)
    assert not any(t.is_alive() for t in threads)
    assert errors == [], f"Ausnahmen in Threads: {errors!r}"

    assert len(results) == n
    assert sum(1 for r in results if r is True) == 4, f"erlaubt: {results}"
    assert _calls(tmp_path) == 10


def test_nach_utc_tageswechsel_beginnt_zaehler_bei_null(tmp_path, monkeypatch):
    """AC-7: Budget 3 am Tag 1 ausgeschoepft; ``now=`` auf Tag 2 -> wieder True,
    ``calls`` steht bei 1 (Zaehler begann bei 0)."""
    monkeypatch.setenv("GZ_METEOALARM_DAILY_BUDGET", "3")
    tag1 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    tag2 = datetime(2026, 1, 2, 0, 5, tzinfo=timezone.utc)
    gate = MeteoAlarmBudgetGate(data_root=tmp_path)

    assert [gate.reserve(now=tag1) for _ in range(3)] == [True, True, True]
    assert gate.reserve(now=tag1) is False
    assert _calls(tmp_path) == 3

    assert gate.reserve(now=tag2) is True
    assert _calls(tmp_path) == 1
