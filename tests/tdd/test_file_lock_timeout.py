"""RED — Fix #1448 Scheibe S2: Dateisperren bekommen eine Zeitgrenze.

Spec: docs/specs/modules/fix_1448_s2_dateisperren.md (AC-1..AC-5)

Die entscheidende Falle (`fcntl.flock` ist prozessweit): eine Sperre, die im
selben Prozess/Deskriptor gehalten wird, ist fuer einen zweiten Erwerb
sofort frei -- ein Test darauf waere immer gruen und wuerde nichts beweisen
(vgl. `reference_regex_guard_matches_nothing_always_green`). Deshalb haelt
ein echter zweiter Prozess (`multiprocessing.Process`) die Sperre, signalisiert
per `multiprocessing.Event`, dass er sie WIRKLICH haelt, und der
Test-Helfer `_locked_by_other_process()` verifiziert das zusaetzlich aktiv
mit einem eigenen `LOCK_EX | LOCK_NB`-Versuch, der mit `BlockingIOError`
scheitern MUSS -- sonst ist der ganze Testaufbau wertlos.

Die drei Pruefling-Klassen (`ForecastBudgetGate`, `ThrottleStore`,
`MeteoAlarmBudgetGate`) existieren bereits heute; `services.file_lock`
(AC-1) existiert noch NICHT -- der resultierende `ImportError` ist fuer
AC-1 die erwartete, unvermeidliche Rotfaerbung. Fuer AC-2/AC-3 haengen die
drei bestehenden Aufrufer heute unbegrenzt an einer gehaltenen Fremdsperre
(nacktes `fcntl.flock(fd, fcntl.LOCK_EX)` ohne `LOCK_NB`) -- die
`@pytest.mark.timeout(...)`-Marken fangen dieses Haengen als Rotfaerbung ab,
statt in den globalen 30s-Timeout aus `pyproject.toml` zu laufen.

AC-4/AC-5 sind bewusst KEINE Bug-Reproduktionen, sondern Regressions-Waechter
fuer Verhalten, das VOR dieser Scheibe schon gilt und danach unveraendert
gelten soll (kein neues blanket Fail-open bei `ThrottleStore` / normaler
Schreibvorgang ohne Konkurrenz) -- sie sind daher schon heute gruen, was
laut Spec ("bleibt unveraendert" / "wird weiterhin durchgereicht") auch so
erwartet ist.
"""
from __future__ import annotations

import fcntl
import importlib
import json
import logging
import multiprocessing
import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import pytest

# Pfadregel #1409: kein fester Hauptrepo-Pfad -- alle Importe laufen ueber
# das normale Paket-System (pythonpath=["src", "."] aus pyproject.toml), der
# Kindprozess (multiprocessing, Start-Methode "fork" unter Linux) erbt den
# bereits geladenen sys.path des Elternprozesses, ohne dass hier irgendein
# Pfad manuell zusammengesetzt werden muss.

_CASES = ["forecast_budget", "throttle_store", "meteoalarm_budget"]


# ---------------------------------------------------------------------------
# Gemeinsamer Zweitprozess-Helfer
# ---------------------------------------------------------------------------


def _hold_lock_worker(
    lock_path: str,
    ready: "multiprocessing.synchronize.Event",
    release: "multiprocessing.synchronize.Event",
) -> None:
    """Laeuft in einem ECHTEN zweiten Prozess: oeffnet dieselbe Sperrdatei,
    erwirbt eine exklusive `fcntl`-Sperre, signalisiert dem Elternprozess
    ueber `ready`, dass sie wirklich gehalten wird, und haelt sie, bis der
    Elternprozess ueber `release` freigibt (Sicherheitsnetz: spaetestens
    nach 10s, falls der Elternprozess z.B. durch einen Timeout abbricht,
    bevor er `release` setzen konnte)."""
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        ready.set()
        release.wait(timeout=10.0)
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _verify_lock_actually_blocks(lock_path: Path) -> None:
    """Selbstkontrolle (Team-Lead-Vorgabe): ein unabhaengiger
    `LOCK_EX | LOCK_NB`-Versuch im Elternprozess MUSS mit `BlockingIOError`
    scheitern, solange der Kindprozess die Sperre haelt -- sonst haelt der
    Kindprozess sie nicht wirklich und der gesamte Testaufbau ist wertlos."""
    fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o644)
    try:
        with pytest.raises(BlockingIOError):
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    finally:
        os.close(fd)


@contextmanager
def _locked_by_other_process(lock_path: Path):
    """Haelt `lock_path` waehrend des `with`-Blocks in einem echten zweiten
    Prozess exklusiv gesperrt (siehe Moduldocstring). Raeumt den Kindprozess
    in jedem Fall auf (auch wenn der `with`-Block durch einen
    `pytest.mark.timeout`-Abbruch verlassen wird -- `fcntl.flock` ist ein
    unterbrechbarer Syscall, PEP 475 laesst die Timeout-Exception durch)."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    ready = multiprocessing.Event()
    release = multiprocessing.Event()
    proc = multiprocessing.Process(
        target=_hold_lock_worker, args=(str(lock_path), ready, release)
    )
    proc.start()
    try:
        bekam_signal = ready.wait(timeout=5.0)
        assert bekam_signal, (
            "Kindprozess hat innerhalb von 5s nicht signalisiert, dass er "
            "die Sperre haelt -- Testaufbau kaputt."
        )
        _verify_lock_actually_blocks(lock_path)
        yield
    finally:
        release.set()
        proc.join(timeout=5.0)
        if proc.is_alive():
            proc.terminate()
            proc.join(timeout=2.0)


# ---------------------------------------------------------------------------
# AC-1 -- acquire_exclusive() selbst
# ---------------------------------------------------------------------------


@pytest.mark.timeout(8)
def test_acquire_exclusive_returns_false_when_locked_by_other_process(tmp_path):
    """AC-1: Given eine zweite Prozess-Instanz haelt bereits eine exklusive
    Sperre auf derselben Sperrdatei / When `acquire_exclusive(fd, timeout_s)`
    mit einer (per Test auf Millisekunden geschrumpften) Zeitgrenze
    aufgerufen wird / Then kehrt der Aufruf spaetestens nach `timeout_s` mit
    `False` zurueck, statt unbegrenzt zu blockieren.

    RED heute: `services.file_lock` existiert noch nicht -- der Import
    schlaegt mit `ImportError`/`ModuleNotFoundError` fehl. Bewusst innerhalb
    der Testfunktion importiert (nicht auf Modulebene), damit dieser
    unvermeidliche Fehlschlag nur DIESEN Test rot faerbt, statt per
    Collect-Error die gesamte Datei zum Absturz zu bringen
    (`reference_pytest_collect_error_kills_whole_suite`).
    """
    from services.file_lock import acquire_exclusive

    lock_path = tmp_path / "irgendein_zaehler.json.lock"
    with _locked_by_other_process(lock_path):
        fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o644)
        try:
            start = time.monotonic()
            ergebnis = acquire_exclusive(fd, timeout_s=0.3)
            elapsed = time.monotonic() - start
        finally:
            os.close(fd)

    assert ergebnis is False, (
        "acquire_exclusive() hat True zurueckgegeben, obwohl die Sperre "
        "nachweislich von einem anderen Prozess gehalten wurde."
    )
    assert elapsed < 2.0, (
        f"acquire_exclusive() brauchte {elapsed:.2f}s statt spaetestens nach "
        "timeout_s=0.3 zurueckzukehren."
    )


# ---------------------------------------------------------------------------
# Gemeinsame Aufbau-Helfer fuer AC-2/AC-3/AC-5 (parametrisiert ueber die drei
# bestehenden Zaehler-Klassen)
# ---------------------------------------------------------------------------


def _build_case(case_name: str, tmp_path: Path):
    """Baut die jeweilige Zaehler-Klasse auf einem isolierten `tmp_path`
    auf und liefert (Objekt, Modul-des-Aufrufers, Sperrdatei-Pfad) zurueck.
    Das Modul wird gebraucht, um `LOCK_TIMEOUT_SECONDS` dort per
    `monkeypatch` zu schrumpfen, sobald der jeweilige Aufrufer sie (nach dem
    Fix) tatsaechlich aus seinem eigenen Namensraum liest."""
    if case_name == "forecast_budget":
        from services.forecast_budget import ForecastBudgetGate

        obj = ForecastBudgetGate(data_root=tmp_path)
        module = importlib.import_module("services.forecast_budget")
    elif case_name == "throttle_store":
        from services.throttle_store import ThrottleStore

        obj = ThrottleStore("nutzer-s2-dateisperren", data_dir=tmp_path)
        module = importlib.import_module("services.throttle_store")
    elif case_name == "meteoalarm_budget":
        from services.official_alerts.meteoalarm_budget import MeteoAlarmBudgetGate

        obj = MeteoAlarmBudgetGate(data_root=tmp_path)
        module = importlib.import_module("services.official_alerts.meteoalarm_budget")
    else:  # pragma: no cover - Programmierfehler im Test selbst
        raise ValueError(case_name)
    lock_path = Path(str(obj._path) + ".lock")
    return obj, module, lock_path


def _trigger_update(case_name: str, obj) -> None:
    if case_name == "throttle_store":
        obj.record("trip", "etappe-1", datetime.now(timezone.utc))
    else:
        obj.record_call()


def _assert_written(case_name: str, obj) -> None:
    state = json.loads(obj._path.read_text())
    if case_name == "forecast_budget":
        assert state["calls"].get("openmeteo", 0) == 1, state
    elif case_name == "meteoalarm_budget":
        assert state["calls"] == 1, state
    else:
        assert state["trip"]["etappe-1"], state


# ---------------------------------------------------------------------------
# AC-2 -- WARNING bei Timeout
# ---------------------------------------------------------------------------


@pytest.mark.timeout(8)
@pytest.mark.parametrize("case_name", _CASES)
def test_update_logs_warning_with_lock_path_when_timed_out(
    case_name, tmp_path, monkeypatch, caplog
):
    """AC-2: Given `acquire_exclusive()` liefert `False`, weil die Sperre
    einer der drei Zaehler-Klassen nicht innerhalb der Frist erworben werden
    kann / When der jeweilige `_safe_update()`/`_update()`-Aufruf diesen Fall
    durchlaeuft / Then wird eine WARNING-Zeile mit Sperrpfad und gewarteter
    Zeit geloggt.

    RED heute: alle drei Aufrufer nutzen noch nacktes
    `fcntl.flock(fd, fcntl.LOCK_EX)` ohne `LOCK_NB` und ohne Zeitgrenze --
    der Aufruf haengt unbegrenzt an der extern gehaltenen Sperre (kein
    Zurueckkehren, keine WARNING), bis `@pytest.mark.timeout(8)` den Test
    abbricht und rot faerbt.
    """
    obj, module, lock_path = _build_case(case_name, tmp_path)
    monkeypatch.setattr(module, "LOCK_TIMEOUT_SECONDS", 0.05, raising=False)

    with caplog.at_level(logging.WARNING):
        with _locked_by_other_process(lock_path):
            _trigger_update(case_name, obj)

    warnungen = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert warnungen, (
        f"[{case_name}] keine WARNING geloggt, obwohl die Sperre {lock_path} "
        "nachweislich extern gehalten wurde (RED erwartet: der Aufrufer "
        "haengt heute unbegrenzt statt aufzugeben und zu loggen)."
    )
    assert any(str(lock_path) in r.getMessage() for r in warnungen), (
        f"[{case_name}] Sperrpfad {lock_path} taucht in keiner WARNING-Zeile "
        f"auf: {[r.getMessage() for r in warnungen]}"
    )


# ---------------------------------------------------------------------------
# AC-3 -- kein Werfen bei Timeout
# ---------------------------------------------------------------------------


@pytest.mark.timeout(8)
@pytest.mark.parametrize("case_name", _CASES)
def test_update_does_not_raise_when_lock_times_out(case_name, tmp_path, monkeypatch):
    """AC-3: Given die Sperre einer der drei Zaehler-Klassen kann nicht
    innerhalb der Frist erworben werden / When der jeweilige Aufruf
    zurueckkehrt / Then laeuft der Aufrufer normal weiter, ohne eine
    Exception zu werfen -- insbesondere `ThrottleStore._update()`, das vor
    dieser Scheibe KEIN umschliessendes `try/except` hatte.

    RED heute: alle drei Aufrufer haengen unbegrenzt an der gehaltenen
    Fremdsperre statt zurueckzukehren -- `@pytest.mark.timeout(8)` faerbt
    diesen Hang als Fehlschlag, kein `pytest.raises` noetig, ein
    unbehandelter Timeout-Abbruch IST hier die Rotfaerbung.

    F001 (Adversary-Mutationsprobe #1448 S2): reines "wirft nicht" reicht
    nicht -- ein `return` OHNE vorherigen Abbruch des Schreibvorgangs wuerde
    diesen Test unveraendert gruen lassen, obwohl dann OHNE gehaltene Sperre
    geschrieben wuerde (genau das Datenrisiko, vor dem diese Scheibe
    schuetzen soll). Deshalb zusaetzlich: Zustandsdatei VOR der Fremdsperre
    mit bekanntem Inhalt vorbereiten und danach beweisen, dass der
    uebersprungene Aufruf die Datei byteidentisch unangetastet laesst.
    """
    obj, module, lock_path = _build_case(case_name, tmp_path)
    monkeypatch.setattr(module, "LOCK_TIMEOUT_SECONDS", 0.05, raising=False)

    _trigger_update(case_name, obj)  # bekannter Inhalt VOR der Fremdsperre
    vorher = obj._path.read_bytes()

    with _locked_by_other_process(lock_path):
        _trigger_update(case_name, obj)  # darf NICHT werfen UND NICHT schreiben

    nachher = obj._path.read_bytes()
    assert nachher == vorher, (
        f"[{case_name}] Zustandsdatei wurde trotz Sperren-Timeout veraendert "
        f"-- der uebersprungene Schreibvorgang haette NICHTS anfassen duerfen "
        f"(vorher={vorher!r}, nachher={nachher!r})."
    )


# ---------------------------------------------------------------------------
# AC-4 -- Nicht-Sperre-Fehler propagiert weiterhin (nur ThrottleStore)
# ---------------------------------------------------------------------------


@pytest.mark.timeout(6)
def test_update_still_raises_on_non_lock_error(tmp_path, monkeypatch):
    """AC-4: Given ein IO-Fehler tritt in `ThrottleStore._update()` auf, der
    NICHT die Sperre betrifft / When `_update()` laeuft / Then wird dieser
    Fehler weiterhin durchgereicht wie vor dieser Scheibe -- kein neues
    blanket Fail-open, nur der Sperre-Timeout-Fall wird neu abgefangen.

    F002 (Adversary-Mutationsprobe #1448 S2, staerkerer Fall): ein Fehler VOR
    dem Sperrblock (z.B. `mkdir` auf einem blockierten Pfad) sagt nichts
    darueber aus, ob ein Fehler WAEHREND die Sperre gehalten wird noch
    korrekt durchgereicht wird -- `throttle_store.py:132-137` hat um den
    geschuetzten Block (`_load`/`mutate`/`_write`) nur ein `finally`
    (Sperre freigeben), KEIN `except`. Deshalb hier gezielt `self._write()`
    selbst zum Werfen bringen, waehrend die Sperre gehalten wird (per
    `monkeypatch`, nicht `unittest.mock` -- erzwingt einen deterministischen
    Fehlerpfad, verifiziert kein Verhalten durch Vorspiegelung).

    Kein RED im Bug-Sinn: `ThrottleStore._update()` hat schon HEUTE kein
    umschliessendes `try/except` um den geschuetzten Block, dieser Fehler
    propagiert also bereits vor dieser Scheibe. Der Test ist ein
    Regressions-Waechter dafuer, dass die S2-Aenderung daran nichts aendert
    (Spec: "wird weiterhin durchgereicht wie vor dieser Scheibe").
    """
    from services.throttle_store import ThrottleStore

    store = ThrottleStore("nutzer-ac4", data_dir=tmp_path)

    def _write_boom(data: dict) -> None:
        raise OSError("simulierter IO-Fehler waehrend gehaltener Sperre")

    monkeypatch.setattr(store, "_write", _write_boom)

    with pytest.raises(OSError):
        store.record("trip", "etappe-1", datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# AC-5 -- Normalfall ohne Konkurrenz bleibt unveraendert
# ---------------------------------------------------------------------------


@pytest.mark.timeout(8)
@pytest.mark.parametrize("case_name", _CASES)
def test_update_writes_immediately_without_contention(
    case_name, tmp_path, monkeypatch, caplog
):
    """AC-5: Given keine Konkurrenz auf der Sperrdatei (Normalfall) / When
    eine der drei Zaehler-Klassen `_safe_update()`/`_update()` aufruft /
    Then bleibt das Verhalten unveraendert: die Sperre wird sofort erworben,
    die Daten werden korrekt geschrieben, keine WARNING erscheint.

    Kein RED im Bug-Sinn: ohne externe Konkurrenz erwirbt das heutige,
    nackte `fcntl.flock(fd, fcntl.LOCK_EX)` die Sperre sofort -- dieser Test
    ist ein Regressions-Waechter, der garantiert, dass die neue
    Zeitgrenzen-Logik den Normalfall nicht anfasst.
    """
    obj, module, lock_path = _build_case(case_name, tmp_path)
    monkeypatch.setattr(module, "LOCK_TIMEOUT_SECONDS", 0.05, raising=False)

    with caplog.at_level(logging.WARNING):
        _trigger_update(case_name, obj)

    _assert_written(case_name, obj)
    warnungen = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert not warnungen, (
        f"[{case_name}] unerwartete WARNING ohne jede Sperren-Konkurrenz: "
        f"{[r.getMessage() for r in warnungen]}"
    )
