"""TDD RED fuer Issue #1539 (Workflow feat-1539-s1b-s2-abruf-baustein), Teil B.

SPEC: docs/specs/modules/feat_1539_s1b_s2_abruf_baustein.md (Abschnitt C)
ACs:  AC-6 (atomares reserve bei Parallelzugriff, Kontoschutz exakt),
      AC-8 (zwei Nutzer parallel, kein Uebersprechen, kein Deadlock),
      AC-10 (Schluesselmenge der Budget-Dateien unveraendert).

Schnittstelle (verbindlich): ``ForecastBudgetGate.reserve(priority, units=1,
now=None) -> bool``. Verlustzaehler lebt in ``services.forecast_budget``.

RED-Erwartung: ``reserve`` existiert noch nicht -> AttributeError in jedem
Test (Aufruf steht bewusst INNERHALB der Testfunktionen).

Ausfuehrung:
    uv run pytest tests/tdd/test_forecast_budget_reserve_atomic.py -v -rA --disable-socket

Kein Mock: echte Dateien in ``tmp_path``, echte Threads, echte fcntl-Sperren.
``DAILY_BUDGET`` ist eine Klassenkonstante, die ``allow()`` zur Aufrufzeit liest;
sie wird per ``monkeypatch.setattr`` verkleinert, der Ausgangsstand entsteht
ueber das Produkt (``record_call``).
"""
from __future__ import annotations

import json
import threading

import pytest

from services.forecast_budget import PROVIDER, ForecastBudgetGate

BUDGET = 20
JOIN_TIMEOUT_S = 30.0


def _run_parallel(n: int, fn):
    """Startet n Threads hinter einer Barrier. Sammelt Ergebnisse UND Ausnahmen."""
    barrier = threading.Barrier(n)
    results: list = []
    errors: list = []
    res_lock = threading.Lock()

    def _worker(i: int) -> None:
        try:
            barrier.wait(timeout=JOIN_TIMEOUT_S)
            value = fn(i)
            with res_lock:
                results.append(value)
        except BaseException as exc:  # noqa: BLE001 - Thread-Ausnahmen selbst einsammeln
            with res_lock:
                errors.append(exc)

    threads = [threading.Thread(target=_worker, args=(i,), daemon=True) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=JOIN_TIMEOUT_S)
    assert not any(t.is_alive() for t in threads), "Thread haengt (Deadlock?)"
    assert errors == [], f"Ausnahmen in Threads: {errors!r}"
    return results


def _global_file(root):
    return root / "diagnostics" / "forecast_budget.json"


def _user_file(root, user_id):
    return root / "users" / user_id / "diagnostics" / "forecast_budget.json"


def _calls(pfad) -> int:
    return json.loads(pfad.read_text())["calls"].get(PROVIDER, 0)


@pytest.mark.timeout(60)
def test_parallel_reserve_kontoschutz_ab_100_prozent_exakt(tmp_path, monkeypatch):
    """AC-6: Restbudget M=5 (bis exakt 100 %), N=16 parallel -> genau 5 True,
    ``calls`` steht bei genau 20, nie darueber."""
    monkeypatch.setattr(ForecastBudgetGate, "DAILY_BUDGET", BUDGET)
    vorlauf = 15
    seed = ForecastBudgetGate("nutzer_a", data_root=tmp_path)
    for _ in range(vorlauf):
        seed.record_call()
    rest = BUDGET - vorlauf
    n = 16
    assert rest < n

    results = _run_parallel(
        n, lambda i: ForecastBudgetGate("nutzer_a", data_root=tmp_path).reserve("polling")
    )

    assert len(results) == n
    assert sum(1 for r in results if r is True) == rest, f"erlaubt: {results}"
    assert _calls(_global_file(tmp_path)) == BUDGET
    assert _calls(_user_file(tmp_path, "nutzer_a")) == BUDGET


@pytest.mark.timeout(60)
def test_parallel_reserve_schwelle_ohne_nutzer_exakt(tmp_path, monkeypatch):
    """AC-6: unattributiert (user_id=None), polling-Schwelle 80 %: Vorlauf 75 von
    100 -> genau 5 True, ``calls`` genau 80."""
    monkeypatch.setattr(ForecastBudgetGate, "DAILY_BUDGET", 100)
    seed = ForecastBudgetGate(None, data_root=tmp_path)
    for _ in range(75):
        seed.record_call()
    n = 16

    results = _run_parallel(
        n, lambda i: ForecastBudgetGate(None, data_root=tmp_path).reserve("polling")
    )

    assert sum(1 for r in results if r is True) == 5, f"erlaubt: {results}"
    assert _calls(_global_file(tmp_path)) == 80


@pytest.mark.timeout(60)
def test_user_briefing_wird_auch_bei_100_prozent_nie_gedrosselt(tmp_path, monkeypatch):
    """AC-6 (fix_1329-Invariante): user_briefing bleibt auch parallel ungedrosselt."""
    monkeypatch.setattr(ForecastBudgetGate, "DAILY_BUDGET", BUDGET)
    seed = ForecastBudgetGate("nutzer_a", data_root=tmp_path)
    for _ in range(BUDGET):
        seed.record_call()

    results = _run_parallel(
        8,
        lambda i: ForecastBudgetGate("nutzer_a", data_root=tmp_path).reserve("user_briefing"),
    )

    assert results == [True] * 8


@pytest.mark.timeout(60)
def test_zwei_nutzer_parallel_buchen_nur_eigenen_topf_ohne_deadlock(tmp_path, monkeypatch):
    """AC-8: A bucht 10x, B 7x parallel -> Topf A == 10, Topf B == 7, global 17."""
    monkeypatch.setattr(ForecastBudgetGate, "DAILY_BUDGET", 9000)
    plan = ["nutzer_a"] * 10 + ["nutzer_b"] * 7

    results = _run_parallel(
        len(plan),
        lambda i: ForecastBudgetGate(plan[i], data_root=tmp_path).reserve("polling"),
    )

    assert results == [True] * len(plan)
    assert _calls(_user_file(tmp_path, "nutzer_a")) == 10
    assert _calls(_user_file(tmp_path, "nutzer_b")) == 7
    assert _calls(_global_file(tmp_path)) == 17


def _schluessel(pfad) -> dict:
    data = json.loads(pfad.read_text())
    return {"top": set(data), "calls": set(data["calls"])}


def test_reserve_schreibt_dieselbe_schluesselmenge_wie_record_call(tmp_path):
    """AC-10: Baseline entsteht im Test aus ``allow()`` + ``record_call()``;
    ``reserve()`` darf kein Feld hinzufuegen oder weglassen (global + Nutzer)."""
    basis = tmp_path / "basis"
    neu = tmp_path / "neu"

    g_alt = ForecastBudgetGate("nutzer_a", data_root=basis)
    assert g_alt.allow("polling") is True
    g_alt.record_call()

    g_neu = ForecastBudgetGate("nutzer_a", data_root=neu)
    assert g_neu.reserve("polling") is True

    assert _schluessel(_global_file(neu)) == _schluessel(_global_file(basis))
    assert _schluessel(_user_file(neu, "nutzer_a")) == _schluessel(
        _user_file(basis, "nutzer_a")
    )
    # Zusatz: reserve bucht genau eine Einheit wie record_call.
    assert _calls(_global_file(neu)) == _calls(_global_file(basis)) == 1
