"""Ausdruecklich leeres `--e2e-path=` bricht Deploy-Gate und Selbsttest ab.

Fehlerbild (Sammel #1197, Adversary #1382 F003): `staging_gate.py` und
`prod_selftest.py` pruefen `--e2e-path` per Wahrheitswert. Ein ausdruecklich
LEERER Wert (`--e2e-path=`) wurde dadurch wie „nicht angegeben" behandelt —
die Regel „ausdruecklich uebergebener Pfad ist massgeblich" (#1382 AC-15)
griff nicht, die Vorfahren-Suche lief unbemerkt weiter.

Erwartung: leerer Wert -> fail-closed, Exit != 0, Meldung nennt `--e2e-path`.
Nachweis ueber das ECHTE Argument-Parsing (Unterprozess), nicht ueber einen
Funktionsaufruf. Der Abbruch passiert vor jeder Git-/Netz-Aktion.

Pfadregel #1409: Prueflinge relativ zu DIESER Datei aufgeloest.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_HOOKS = Path(__file__).resolve().parents[2] / ".claude" / "hooks"


@pytest.mark.parametrize("skript, modus", [
    ("staging_gate.py", ["--check", "--scope", "backend"]),
    ("staging_gate.py", ["--write-verdict", "VERIFIED", "--scope", "backend"]),
    ("prod_selftest.py", ["--workflow", "test-leerer-pfad"]),
])
def test_leerer_e2e_pfad_bricht_fail_closed_ab(tmp_path, skript, modus):
    """Given `--e2e-path=` (ausdruecklich leer) / When das Werkzeug ueber die
    Kommandozeile laeuft / Then Exit != 0 und die Meldung nennt den leeren
    `--e2e-path` als Grund."""
    r = subprocess.run(
        [sys.executable, str(_HOOKS / skript), *modus, "--e2e-path="],
        cwd=str(tmp_path), capture_output=True, text=True, timeout=60,
    )
    ausgabe = r.stdout + r.stderr
    assert r.returncode != 0, f"leerer --e2e-path haette abbrechen muessen: {ausgabe}"
    assert "--e2e-path" in ausgabe and "leer" in ausgabe, ausgabe
