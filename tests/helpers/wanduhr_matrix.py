"""Messwerkzeug: indirekte Wanduhr-Abhaengigkeit eines Testfalls MESSEN,
statt sie am Code zu erraten (#1709).

Ob eine Fixture indirekt von der Wanduhr abhaengt, laesst sich nicht durch
Lesen entscheiden — die Zeitabhaengigkeit entsteht erst im Pruefling
(``src/services/trip_segments.py`` / ``src/services/trip_alert.py``). Sie
laesst sich aber MESSEN: dieselbe Testdatei zu mehreren gestellten Uhrzeiten
laufen lassen und die Ergebnisse vergleichen.

Drei Eigenschaften sind zwingend (Spec ``fix_1709_wallclock_ratsche_indirekt``,
Abschnitt "Gewaehlte Loesung"), alle drei teuer gelernt:

1. **Ein frischer Betriebssystem-Prozess je Datenpunkt.** Mehrere
   ``pytest.main()``-Aufrufe im selben Prozess ergaben eine Matrix (rot
   02-04 UTC), die sich bei frischen Prozessen nicht reproduzieren liess (rot
   04-06 UTC) — Zustand sickert zwischen Laeufen durch.
2. **Nur die Differenz ist auswertbar, nie eine absolute Fehlerzahl.**
   Sitzungsweites ``freezegun`` zerstoert pydantic-v1-Importe
   (``TypeError: metaclass conflict``, ``pydantic/v1/types.py:1180``) und
   erzeugt so Falsch-Positive. ``extend_ignore_list=["pydantic"]`` behebt das
   nicht.
3. **Uhrzeiten in der Ortszone der Fixture waehlen, nicht in UTC.** Wer die
   Grenzen in UTC notiert, sucht bei fremder Zone an der falschen Stelle —
   das ist Sache der Aufrufer:in, dieses Werkzeug rechnet nur mit dem, was
   es bekommt.

Jeder Datenpunkt laeuft deshalb als eigener ``sys.executable -c``-Subprozess
mit ``freeze_time(..., tick=True)`` NUR fuer diesen einen Lauf. Ergebnisse
werden ueber einen ``pytest_runtest_logreport``-Hook eingesammelt und als
JSON in eine Ausgabedatei geschrieben — kein stdout-Parsing.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Sequence

# Wurzel DIESES Checkouts (Pfadregel #1409) — der Kindprozess wird mit dieser
# cwd gestartet, damit fuer Pruefling-Dateien INNERHALB des Repos (z.B. echte
# Fixtures unter tests/tdd/) die uebliche conftest-Kette (tests/conftest.py
# setzt "src" auf sys.path) unveraendert greift. Attrappen ausserhalb des
# Repos (tmp_path) brauchen das nicht -- sie sind bewusst eigenstaendig.
REPO_ROOT = Path(__file__).resolve().parents[2]

# Zeitlimit je Datenpunkt: ein haengender Testfall darf die Messung nicht
# blockieren (Spec, AC-Vorbedingung). Grosszuegig bemessen wie beim Vorbild
# fuer Subprozess-Pytest-Laeufe (tests/tdd/test_worktree_path_resolution_
# effect.py: _SUBPROC_TIMEOUT = 120) -- ein einzelner Datenpunkt entspricht
# demselben Aufwand wie dort ein einzelner Nodeid-Lauf.
_SUBPROC_TIMEOUT_SEC = 120

_KINDPROZESS_SKRIPT = '''\
import json

import pytest
from freezegun import freeze_time


class _Sammler:
    """Sammelt bestanden/fehlgeschlagen je Testfall ueber den pytest-Hook --
    kein stdout-Parsing, keine Zusatzformate."""

    def __init__(self):
        self.ergebnisse = {{}}

    def pytest_runtest_logreport(self, report):
        if report.when == "call":
            self.ergebnisse[report.nodeid] = report.outcome
        elif report.when in ("setup", "teardown") and report.outcome != "passed":
            # Fehler in setup/teardown (z.B. eine fehlschlagende Fixture)
            # zaehlen ebenfalls als abweichendes Ergebnis, ueberschreiben aber
            # ein bereits erfasstes "call"-Ergebnis nicht.
            self.ergebnisse.setdefault(report.nodeid, report.outcome)


sammler = _Sammler()
with freeze_time({uhrzeit_iso}, tick=True):
    pytest.main(
        [{testdatei}, "--allow-hosts=127.0.0.1,::1", "-p", "no:randomly", "-q"],
        plugins=[sammler],
    )

with open({ausgabe}, "w", encoding="utf-8") as f:
    json.dump(sammler.ergebnisse, f)
'''


def lauf_bei_uhrzeit(testdatei: Path, uhrzeit: datetime) -> dict[str, str]:
    """Fuehrt ``testdatei`` EINMAL, in einem FRISCHEN Betriebssystem-Prozess,
    mit gestellter Wanduhr ``uhrzeit`` aus (ein Datenpunkt).

    Gibt ``{nodeid: outcome}`` zurueck (``outcome`` z.B. ``"passed"``,
    ``"failed"``, ``"skipped"``).
    """
    with tempfile.TemporaryDirectory() as tmp:
        ausgabe = Path(tmp) / "ergebnisse.json"
        skript = _KINDPROZESS_SKRIPT.format(
            uhrzeit_iso=repr(uhrzeit.isoformat()),
            testdatei=repr(str(testdatei)),
            ausgabe=repr(str(ausgabe)),
        )
        # PYTEST_*-Env-Variablen des AEUSSEREN Laufs nicht in den Kindprozess
        # durchreichen -- sonst haelt der verschachtelte pytest-Lauf sich
        # faelschlich fuer denselben Testlauf (Muster: test_worktree_path_
        # resolution_effect.py::_run_pytest_in).
        env = {k: v for k, v in os.environ.items() if not k.startswith("PYTEST_")}
        try:
            proc = subprocess.run(
                [sys.executable, "-c", skript],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                timeout=_SUBPROC_TIMEOUT_SEC,
                env=env,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"lauf_bei_uhrzeit({testdatei}, {uhrzeit.isoformat()}) haengt "
                f"nach {_SUBPROC_TIMEOUT_SEC}s -- abgebrochen, um die Messung "
                f"nicht zu blockieren. stdout bisher: {exc.stdout!r}"
            ) from exc

        if not ausgabe.exists():
            raise RuntimeError(
                f"lauf_bei_uhrzeit({testdatei}, {uhrzeit.isoformat()}): der "
                f"Kindprozess hat keine Ergebnisdatei geschrieben (Exit "
                f"{proc.returncode}).\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
            )
        return json.loads(ausgabe.read_text(encoding="utf-8"))


def matrix_differenz(testdatei: Path, uhrzeiten: Sequence[datetime]) -> frozenset[str]:
    """Misst ``testdatei`` zu jeder Uhrzeit (je ein frischer Prozess, s.
    ``lauf_bei_uhrzeit``) und gibt die Menge der Test-Nodeids zurueck, deren
    Ergebnis NICHT bei ALLEN Uhrzeiten identisch ist.

    Bei zwei Uhrzeiten derselben Seite einer Kippkante ist das Ergebnis leer
    -- absolute Fehlerzahlen werden nie ausgewertet (s. Modul-Docstring,
    Punkt 2).
    """
    messungen = [lauf_bei_uhrzeit(testdatei, uhrzeit) for uhrzeit in uhrzeiten]
    alle_nodeids: set[str] = set()
    for messung in messungen:
        alle_nodeids.update(messung)

    abweichend: set[str] = set()
    for nodeid in alle_nodeids:
        ergebnisse_je_uhrzeit = {messung.get(nodeid) for messung in messungen}
        if len(ergebnisse_je_uhrzeit) > 1:
            abweichend.add(nodeid)
    return frozenset(abweichend)
