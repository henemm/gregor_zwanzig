"""Issue #1539 (Fix-Loop 1, Adversary F007): Waechter fuer drei Randzonen von
``ForecastBudgetGate.reserve()``.

SPEC: docs/specs/modules/feat_1539_s1b_s2_abruf_baustein.md (AC-7 Tageswechsel,
      AC-8 feste Reihenfolge global -> Nutzer, AC-9 laute Verluste)

  (a) IO-/Schreibfehler (nicht nur Sperr-Timeout) zaehlt als verlorene Buchung.
  (b) UTC-Tageswechsel gilt auch fuer ``reserve()`` (``now`` wird durchgereicht).
  (c) Der Nutzer-Topf wird NICHT unter der globalen Sperre gebucht.

Kein Mock: echte Dateien in ``tmp_path``, echte Sperrhalter (``fcntl.flock``).

Ausfuehrung:
    uv run pytest tests/tdd/test_forecast_budget_reserve_waechter.py -v -rA --disable-socket
"""
from __future__ import annotations

import fcntl
import json
import logging
import os
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest

import services.forecast_budget as fb


def _lies(pfad) -> dict:
    return json.loads(pfad.read_text())


def test_a_schreibfehler_statt_sperr_timeout_zaehlt_als_verlorene_buchung(tmp_path, caplog):
    """AC-9 (IO-Zweig): ``forecast_budget.json`` ist ein VERZEICHNIS -- das
    atomare Ersetzen scheitert mit einem IO-Fehler. ``reserve`` bleibt
    fail-open (True), der Verlustzaehler steigt um genau 1, WARNING im Log."""
    (tmp_path / "diagnostics" / "forecast_budget.json").mkdir(parents=True)
    gate = fb.ForecastBudgetGate(None, data_root=tmp_path)
    vorher = fb.forecast_budget_lost_bookings

    with caplog.at_level(logging.WARNING):
        ergebnis = gate.reserve("polling")

    assert ergebnis is True
    assert fb.forecast_budget_lost_bookings - vorher == 1
    assert any(r.levelno >= logging.WARNING for r in caplog.records)


def test_b_utc_tageswechsel_gilt_auch_fuer_reserve(tmp_path):
    """AC-7 (Forecast): die Budgetdatei von HEUTE ist voll (9000 Calls). Fuer
    einen Zeitpunkt am Folgetag beginnt der Zaehler bei 0: ``reserve`` erlaubt
    ``polling`` und schreibt Datum und Zaehler des neuen Tages."""
    gate = fb.ForecastBudgetGate(None, data_root=tmp_path)
    heute = datetime.now(timezone.utc)
    morgen = heute + timedelta(days=1)
    pfad = tmp_path / "diagnostics" / "forecast_budget.json"
    pfad.parent.mkdir(parents=True)
    pfad.write_text(json.dumps({
        "date": heute.date().isoformat(), "calls": {fb.PROVIDER: fb.ForecastBudgetGate.DAILY_BUDGET},
        "cache_hits": 0, "cache_misses": 0, "active_users": [],
    }))

    assert gate.reserve("polling", now=morgen) is True

    daten = _lies(pfad)
    assert daten["date"] == morgen.date().isoformat()
    assert daten["calls"][fb.PROVIDER] == 1


def test_c_nutzer_topf_wird_nicht_unter_der_globalen_sperre_gebucht(tmp_path, monkeypatch):
    """AC-8: Ein fremder Halter blockiert die Sperre des NUTZER-Topfs. Die
    Nutzer-Buchung wartet darauf -- die GLOBALE Sperre muss dabei frei sein
    (feste Reihenfolge, nie beide gehalten), und die globale Buchung steht
    bereits in der Datei."""
    monkeypatch.setattr(fb, "LOCK_TIMEOUT_SECONDS", 8.0)
    gate = fb.ForecastBudgetGate("nutzer_a", data_root=tmp_path)
    globale = tmp_path / "diagnostics" / "forecast_budget.json"
    nutzer_lock = tmp_path / "users" / "nutzer_a" / "diagnostics" / "forecast_budget.json.lock"
    nutzer_lock.parent.mkdir(parents=True)
    halter = os.open(str(nutzer_lock), os.O_CREAT | os.O_RDWR, 0o644)
    fcntl.flock(halter, fcntl.LOCK_EX)
    ergebnis: list = []
    fehler: list = []

    def _lauf() -> None:
        try:
            ergebnis.append(gate.reserve("user_briefing"))
        except BaseException as exc:  # noqa: BLE001 - C4-62
            fehler.append(exc)

    t = threading.Thread(target=_lauf, daemon=True)
    t.start()
    try:
        ende = time.monotonic() + 5.0
        while time.monotonic() < ende and not (
            globale.exists() and _lies(globale)["calls"].get(fb.PROVIDER) == 1
        ):
            time.sleep(0.05)
        assert globale.exists() and _lies(globale)["calls"].get(fb.PROVIDER) == 1, (
            "globale Buchung steht nicht, solange der Nutzer-Topf wartet"
        )
        assert t.is_alive(), "reserve endete, obwohl der Nutzer-Topf gesperrt ist"
        # Die globale Sperre muss JETZT frei sein.
        fd = os.open(str(globale) + ".lock", os.O_CREAT | os.O_RDWR, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)
    finally:
        fcntl.flock(halter, fcntl.LOCK_UN)
        os.close(halter)
        t.join(timeout=15)

    assert not t.is_alive() and not fehler, fehler
    assert ergebnis == [True]
    assert _lies(tmp_path / "users" / "nutzer_a" / "diagnostics" / "forecast_budget.json")[
        "calls"][fb.PROVIDER] == 1
