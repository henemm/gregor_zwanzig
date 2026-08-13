"""Verhaltensnachweis fuer den Playwright-CI-Gate-Auswerter (#1771 Scheibe 2, AC-4).

`.github/scripts/e2e_gate.py` liest den JSON-Report des Playwright-Reporters (Feld
`stats`: `expected`/`unexpected`/`skipped`) und entscheidet ueber DREI Bedingungen statt
nur ueber "keine Roten":

1. `unexpected == 0`      -- keine roten Testfaelle
2. `skipped == 0`         -- kein Skip-Budget aufgebraucht
3. `expected >= E2E_MIN_EXECUTED` -- Mindestzahl TATSAECHLICH AUSGEFUEHRTER Testfaelle

Der Kern-Test dieser Datei (`test_null_ausgefuehrte_tests_geben_exit_ungleich_0`) belegt
AC-4: ein Lauf, in dem der isolierte Stack nicht hochkam und deshalb kein einziger Test
der Positivliste ausgefuehrt wurde, darf NICHT gruen sein, obwohl `unexpected == 0` waere
("0 Tests, 0 rot" ist kein Beweis, sondern ein Bericht ueber gar nichts).

Kern-Schicht, deterministisch: kein Netz, keine echten Playwright-Laeufe, keine Dienste.
Jeder Fall schreibt einen synthetischen JSON-Report nach `tmp_path` und ruft den Pruefling
als echten Unterprozess auf (kein Mock, kein patch()) -- verhaltensgetrieben ueber
Exit-Code und stdout/stderr, nie ueber einen Dateiinhalts-Check des Pruefling-Quelltexts.

Pfadregel #1409: Der Pruefling wird relativ zu DIESER Datei aufgeloest, damit der Test aus
einem Worktree den Worktree-Stand prueft und nicht die Hauptrepo-Kopie.

RED-Phase: `.github/scripts/e2e_gate.py` existiert noch nicht (wird erst in
`/50-implement` angelegt) -- ALLE Faelle hier muessen fehlschlagen, weil `sys.executable`
die fehlende Datei nicht oeffnen kann.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GATE = REPO / ".github" / "scripts" / "e2e_gate.py"


def _report(tmp_path: Path, expected: int, unexpected: int, skipped: int,
            flaky: int = 0, name: str = "report.json") -> Path:
    """Schreibt einen Playwright-JSON-Report mit den gegebenen `stats`-Werten."""
    ziel = tmp_path / name
    inhalt = {
        "stats": {
            "expected": expected,
            "unexpected": unexpected,
            "skipped": skipped,
            "flaky": flaky,
        },
        "suites": [],
    }
    ziel.write_text(json.dumps(inhalt), encoding="utf-8")
    return ziel


def _run_gate(report_path: Path, min_executed: int | str = 50) -> subprocess.CompletedProcess:
    """Ruft den Pruefling als Unterprozess auf, Schwelle ueber die Umgebung."""
    env = {**os.environ, "E2E_MIN_EXECUTED": str(min_executed)}
    return subprocess.run(
        [sys.executable, str(GATE), str(report_path)],
        capture_output=True, text=True, timeout=30, env=env,
    )


def _text(r: subprocess.CompletedProcess) -> str:
    return r.stdout + r.stderr


def _run_gate_ohne_schwelle(report_path: Path, min_executed_raw: str | None = None) -> subprocess.CompletedProcess:
    """Wie `_run_gate`, aber OHNE automatisch eine gueltige `E2E_MIN_EXECUTED`
    zu setzen -- fuer die Faelle, die genau das Fehlen/die Unbrauchbarkeit der
    Schwelle selbst pruefen (Gegenlese-Fund Defekt 2, PR-Review #1771 S2)."""
    env = {k: v for k, v in os.environ.items() if k != "E2E_MIN_EXECUTED"}
    if min_executed_raw is not None:
        env["E2E_MIN_EXECUTED"] = min_executed_raw
    return subprocess.run(
        [sys.executable, str(GATE), str(report_path)],
        capture_output=True, text=True, timeout=30, env=env,
    )


# ------------------------------------------------------------------------- Faelle


def test_alles_gruen_gibt_exit_0(tmp_path):
    """AC-4 Gegenprobe: alle drei Bedingungen erfuellt -> Exit 0.

    GIVEN ein Report mit `expected=55, unexpected=0, skipped=0` und `E2E_MIN_EXECUTED=50`
    WHEN der Gate-Auswerter darauf laeuft
    THEN meldet er Exit 0 -- keine roten Tests, kein Skip-Budget verbraucht, genug
         ausgefuehrte Testfaelle.
    """
    report = _report(tmp_path, expected=55, unexpected=0, skipped=0)
    r = _run_gate(report, min_executed=50)
    ausgabe = _text(r)
    assert r.returncode == 0, f"Erwarteter Exit 0 bei allen drei Bedingungen erfuellt: {ausgabe}"


def test_rote_tests_geben_exit_ungleich_0(tmp_path):
    """Bedingung 1 (`unexpected == 0`): ein roter Testfall macht den Job rot.

    GIVEN ein Report mit `expected=55, unexpected=1, skipped=0`
    WHEN der Gate-Auswerter darauf laeuft
    THEN ist der Exit-Code != 0 und die Meldung nennt die roten Tests
         (Zahl der `unexpected`-Faelle).
    """
    report = _report(tmp_path, expected=55, unexpected=1, skipped=0)
    r = _run_gate(report, min_executed=50)
    ausgabe = _text(r)
    assert r.returncode != 0, f"Ein roter Testfall haette den Job rot machen muessen: {ausgabe}"
    assert "1" in ausgabe and (
        "unexpected" in ausgabe.lower() or "rot" in ausgabe.lower()
    ), f"Meldung nennt nicht die roten Tests: {ausgabe}"


def test_uebersprungene_tests_geben_exit_ungleich_0(tmp_path):
    """Bedingung 2 (`skipped == 0`): ein uebersprungener Testfall verbraucht das
    Skip-Budget und macht den Job rot.

    GIVEN ein Report mit `expected=55, unexpected=0, skipped=1`
    WHEN der Gate-Auswerter darauf laeuft
    THEN ist der Exit-Code != 0 und die Meldung nennt das Skip-Budget
         (bzw. die Zahl uebersprungener Tests).
    """
    report = _report(tmp_path, expected=55, unexpected=0, skipped=1)
    r = _run_gate(report, min_executed=50)
    ausgabe = _text(r)
    assert r.returncode != 0, f"Ein uebersprungener Test haette den Job rot machen muessen: {ausgabe}"
    assert "1" in ausgabe and (
        "skip" in ausgabe.lower() or "übersprung" in ausgabe.lower()
        or "uebersprung" in ausgabe.lower()
    ), f"Meldung nennt nicht das Skip-Budget: {ausgabe}"


def test_null_ausgefuehrte_tests_geben_exit_ungleich_0(tmp_path):
    """AC-4 Kerntest: null ausgefuehrte Tests sind KEIN Erfolg, auch wenn
    `unexpected == 0` gilt.

    GIVEN ein Report mit `expected=0, unexpected=0, skipped=0` (Stack-Start oder
          Seed ist fehlgeschlagen, kein einziger Test der Positivliste lief) und
          `E2E_MIN_EXECUTED=50`
    WHEN der Gate-Auswerter darauf laeuft
    THEN ist der Exit-Code != 0 -- "0 Tests, 0 rot" ist kein Beleg, sondern ein Bericht
         ueber gar nichts. Wuerde der Auswerter hier gruen melden, waere die zentrale
         Zusicherung dieser Scheibe wirkungslos (Prueforten muss dem Wirkort entsprechen).
    """
    report = _report(tmp_path, expected=0, unexpected=0, skipped=0)
    r = _run_gate(report, min_executed=50)
    ausgabe = _text(r)
    assert r.returncode != 0, (
        f"Null ausgefuehrte Tests haetten NIEMALS gruen sein duerfen (AC-4): {ausgabe}"
    )
    assert "0" in ausgabe and "50" in ausgabe, (
        f"Meldung nennt weder die ausgefuehrte Zahl (0) noch die Schwelle (50) -- "
        f"ein blosser Exit-Code != 0 belegt die Ursache noch nicht: {ausgabe}"
    )


def test_zu_wenige_ausgefuehrte_tests_geben_exit_ungleich_0(tmp_path):
    """Bedingung 3 zaehlt ausgefuehrte TESTFAELLE, nicht Listen-DATEIEN.

    GIVEN ein Report mit `expected=11, unexpected=0, skipped=0` und
          `E2E_MIN_EXECUTED=50`
    WHEN der Gate-Auswerter darauf laeuft
    THEN ist der Exit-Code != 0. Belegt: die Pruefung haengt an der Zahl
         AUSGEFUEHRTER Testfaelle (`expected`) -- eine Verwechslung mit der Zahl der
         Listen-Dateien (z.B. `E2E_MIN_SPECS=10`) waere hier faelschlich gruen
         (11 >= 10), obwohl 39 von 50 erwarteten Testfaellen fehlen.
    """
    report = _report(tmp_path, expected=11, unexpected=0, skipped=0)
    r = _run_gate(report, min_executed=50)
    ausgabe = _text(r)
    assert r.returncode != 0, (
        f"11 von 50 erwarteten Testfaellen haetten NICHT gruen sein duerfen "
        f"(Verwechslung mit Datei-Mindestzahl?): {ausgabe}"
    )
    assert "11" in ausgabe and "50" in ausgabe, (
        f"Meldung nennt weder die ausgefuehrte Zahl (11) noch die Schwelle (50) -- "
        f"ein blosser Exit-Code != 0 belegt die Ursache noch nicht: {ausgabe}"
    )


def test_fehlender_report_gibt_exit_ungleich_0(tmp_path):
    """Robustheit: fehlender Report -> Exit != 0 mit klarer Meldung, kein stiller
    Durchlauf.

    GIVEN ein Pfad, unter dem KEINE JSON-Datei existiert
    WHEN der Gate-Auswerter darauf laeuft
    THEN ist der Exit-Code != 0 und die Ausgabe ist nicht leer -- ein fehlender Report
         darf nie als "alles gut" durchgehen.
    """
    fehlender_report = tmp_path / "gibt-es-nicht.json"
    assert not fehlender_report.exists()
    r = _run_gate(fehlender_report, min_executed=50)
    ausgabe = _text(r)
    assert r.returncode != 0, f"Fehlender Report haette NIE Exit 0 ergeben duerfen: {ausgabe}"
    assert fehlender_report.name in ausgabe, (
        f"Meldung nennt nicht den fehlenden Report-Pfad ({fehlender_report.name}) -- "
        f"ein Fehler ueber irgendeine andere fehlende Datei ist kein Beleg, dass GENAU "
        f"der Report als Ursache erkannt wurde: {ausgabe}"
    )


def test_kaputter_report_gibt_exit_ungleich_0(tmp_path):
    """Robustheit: kein gueltiges JSON -> Exit != 0, kein nackter Absturz.

    GIVEN eine Datei, deren Inhalt kein gueltiges JSON ist
    WHEN der Gate-Auswerter darauf laeuft
    THEN ist der Exit-Code != 0 und die Ausgabe ist eine erklaerende Meldung, nicht
         ausschliesslich ein unbehandelter Python-Stacktrace.
    """
    kaputte_datei = tmp_path / "kaputt.json"
    kaputte_datei.write_text("{das ist kein json", encoding="utf-8")
    r = _run_gate(kaputte_datei, min_executed=50)
    ausgabe = _text(r)
    assert r.returncode != 0, f"Kaputtes JSON haette NIE Exit 0 ergeben duerfen: {ausgabe}"
    assert kaputte_datei.name in ausgabe, (
        f"Meldung nennt nicht den kaputten Report-Pfad ({kaputte_datei.name}) -- ein "
        f"unbehandelter Stacktrace an einer ganz anderen Stelle ist kein Beleg, dass "
        f"GENAU das ungueltige JSON als Ursache erkannt wurde: {ausgabe}"
    )


def test_fehlende_schwelle_gibt_exit_ungleich_0(tmp_path):
    """Gegenlese-Fund (Defekt 2): der alte Default `E2E_MIN_EXECUTED=0` machte
    Bedingung 3 wirkungslos, sobald die Variable fehlte -- ein leerer Report
    (Stack nie hochgekommen) waere dann GRUEN gewesen.

    GIVEN ein Report mit `expected=0, unexpected=0, skipped=0` und
          E2E_MIN_EXECUTED NICHT gesetzt
    WHEN der Gate-Auswerter darauf laeuft
    THEN ist der Exit-Code != 0 (fail-closed) und die Meldung nennt
         `E2E_MIN_EXECUTED` als Ursache.
    """
    report = _report(tmp_path, expected=0, unexpected=0, skipped=0)
    r = _run_gate_ohne_schwelle(report)
    ausgabe = _text(r)
    assert r.returncode != 0, (
        f"Fehlende Schwelle haette NIE Exit 0 ergeben duerfen (fail-closed): {ausgabe}"
    )
    assert "E2E_MIN_EXECUTED" in ausgabe, (
        f"Meldung nennt nicht die fehlende Variable E2E_MIN_EXECUTED: {ausgabe}"
    )


def test_unbrauchbare_schwelle_gibt_exit_ungleich_0(tmp_path):
    """Gegenlese-Fund (Defekt 2): eine nicht-parsbare Schwelle darf nicht als
    nackter Python-Stacktrace enden, sondern muss als erklaerte Ablehnung
    scheitern (fail-closed).

    GIVEN ein sonst gueltiger Report und `E2E_MIN_EXECUTED=abc`
    WHEN der Gate-Auswerter darauf laeuft
    THEN ist der Exit-Code != 0, die Ausgabe enthaelt KEINEN unbehandelten
         Traceback und nennt `E2E_MIN_EXECUTED` als Ursache.
    """
    report = _report(tmp_path, expected=55, unexpected=0, skipped=0)
    r = _run_gate_ohne_schwelle(report, min_executed_raw="abc")
    ausgabe = _text(r)
    assert r.returncode != 0, f"Unbrauchbare Schwelle haette NIE Exit 0 ergeben duerfen: {ausgabe}"
    assert "Traceback (most recent call last)" not in ausgabe, (
        f"Ein nackter Python-Stacktrace ist keine erklaerende Meldung: {ausgabe}"
    )
    assert "E2E_MIN_EXECUTED" in ausgabe, (
        f"Meldung nennt nicht die unbrauchbare Variable E2E_MIN_EXECUTED: {ausgabe}"
    )
