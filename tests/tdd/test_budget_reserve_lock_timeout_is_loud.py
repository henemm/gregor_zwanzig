"""TDD RED fuer Issue #1539 (Workflow feat-1539-s1b-s2-abruf-baustein), Teil B.

SPEC: docs/specs/modules/feat_1539_s1b_s2_abruf_baustein.md (Abschnitte C, D)
AC-9: Lock-Timeout ist laut: ``reserve()`` liefert True (fail-open) ohne
Ausnahme, der Verlustzaehler steigt um genau 1, WARNING im Log.

Verlustzaehler: ``services.forecast_budget.forecast_budget_lost_bookings`` und
``services.official_alerts.meteoalarm_budget.meteoalarm_budget_lost_bookings``.
Sperrfrist: ``LOCK_TIMEOUT_SECONDS`` im jeweiligen Modul (monkeypatch).

RED-Erwartung: ``reserve`` bzw. Zaehler existieren nicht -> AttributeError.

Ausfuehrung:
    uv run pytest tests/tdd/test_budget_reserve_lock_timeout_is_loud.py -v -rA --disable-socket

Kein Mock: ein echter Sperrhalter haelt die ``.lock``-Datei per ``fcntl.flock``.
"""
from __future__ import annotations

import fcntl
import logging
import os
from contextlib import contextmanager

import services.forecast_budget as fb
import services.official_alerts.meteoalarm_budget as mb


@contextmanager
def _fremder_sperrhalter(lock_pfad):
    lock_pfad.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lock_pfad), os.O_CREAT | os.O_RDWR, 0o644)
    fcntl.flock(fd, fcntl.LOCK_EX)
    try:
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def test_forecast_reserve_bei_globalem_lock_timeout_ist_laut(tmp_path, monkeypatch, caplog):
    """AC-9 (Forecast, globale Datei)."""
    monkeypatch.setattr(fb, "LOCK_TIMEOUT_SECONDS", 0.2)
    gate = fb.ForecastBudgetGate(None, data_root=tmp_path)
    lock = tmp_path / "diagnostics" / "forecast_budget.json.lock"
    vorher = fb.forecast_budget_lost_bookings

    with _fremder_sperrhalter(lock), caplog.at_level(logging.WARNING):
        ergebnis = gate.reserve("polling")

    assert ergebnis is True
    assert fb.forecast_budget_lost_bookings - vorher == 1
    assert any(r.levelno >= logging.WARNING for r in caplog.records)


def test_forecast_reserve_bei_nutzer_lock_timeout_ist_laut(tmp_path, monkeypatch, caplog):
    """AC-9 (Forecast, Nutzer-Topf; globale Buchung gelingt, nur der Nutzer-Topf geht verloren)."""
    monkeypatch.setattr(fb, "LOCK_TIMEOUT_SECONDS", 0.2)
    gate = fb.ForecastBudgetGate("nutzer_a", data_root=tmp_path)
    lock = tmp_path / "users" / "nutzer_a" / "diagnostics" / "forecast_budget.json.lock"
    vorher = fb.forecast_budget_lost_bookings

    with _fremder_sperrhalter(lock), caplog.at_level(logging.WARNING):
        ergebnis = gate.reserve("polling")

    assert ergebnis is True
    assert fb.forecast_budget_lost_bookings - vorher == 1
    assert any(r.levelno >= logging.WARNING for r in caplog.records)


def test_meteoalarm_reserve_bei_lock_timeout_ist_laut(tmp_path, monkeypatch, caplog):
    """AC-9 (MeteoAlarm)."""
    monkeypatch.setattr(mb, "LOCK_TIMEOUT_SECONDS", 0.2)
    gate = mb.MeteoAlarmBudgetGate(data_root=tmp_path)
    lock = tmp_path / "diagnostics" / "meteoalarm_budget.json.lock"
    vorher = mb.meteoalarm_budget_lost_bookings

    with _fremder_sperrhalter(lock), caplog.at_level(logging.WARNING):
        ergebnis = gate.reserve()

    assert ergebnis is True
    assert mb.meteoalarm_budget_lost_bookings - vorher == 1
    assert any(r.levelno >= logging.WARNING for r in caplog.records)
