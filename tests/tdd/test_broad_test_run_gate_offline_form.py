"""TDD RED -- Issue #1755 AC-5: Breitlauf-Gate gibt nur die sichere
Offline-Form frei.

SPEC: docs/specs/modules/fix_1755_offline_volllauf.md (AC-5)

Bisher galt ``--disable-socket`` allein als Freigabe fuer einen Volllauf.
Die einzige praktisch benutzbare Erweiterung (``--allow-hosts=127.0.0.1``)
liesse jeden Test Prod/Staging auf Loopback erreichen. Freigegeben wird
kuenftig nur:

    --disable-socket [--allow-unix-socket] --allow-hosts=<nur Loopback> --loopback-own-ports

Kein Mock-Theater: der echte Hook laeuft als Subprozess mit JSON-Payload auf
stdin (Muster wie test_broad_test_run_gate_pytest_word_position.py). Geprueft
werden Exit-Code und Meldungstext.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
HOOK = ROOT / ".claude" / "hooks" / "broad_test_run_gate.py"

sys.path.insert(0, str(ROOT / ".claude" / "hooks"))
pytest.importorskip("broad_test_run_gate")

NEW_FORM = (
    "--disable-socket --allow-unix-socket "
    "--allow-hosts=127.0.0.1,::1,localhost --loopback-own-ports"
)
DOCUMENTED_CALL = f"uv run pytest {NEW_FORM} --ignore=tests/red/"


_NO_OVERRIDE_ROOT = Path(tempfile.mkdtemp(prefix="gate1755-"))


def _run_gate(command: str) -> subprocess.CompletedProcess:
    """Echter Hook als Subprozess. ``CLAUDE_PROJECT_DIR`` zeigt auf ein leeres
    Temp-Verzeichnis ohne Override-Token-Datei -- ein Override des PO kann die
    Blockfaelle so nicht verfaelschen (``hook_utils.find_project_root`` liest
    diese Variable zuerst)."""
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = str(_NO_OVERRIDE_ROOT)
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=payload, capture_output=True, text=True, cwd=str(ROOT), env=env, timeout=30,
    )


# ---------------------------------------------------------------------------
# Freigegeben
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "command",
    [
        DOCUMENTED_CALL,
        f"uv run pytest {NEW_FORM}",
        "uv run pytest --disable-socket --allow-hosts=127.0.0.1,::1,localhost --loopback-own-ports",
        "uv run pytest --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1 --loopback-own-ports",
        f"sh -c \"uv run pytest {NEW_FORM}\"",
    ],
    ids=["doku-aufruf", "neue-form", "ohne-unix-socket", "nur-127", "roh-fallback-sicher"],
)
def test_ac5_neue_offline_form_ist_freigegeben(command):
    proc = _run_gate(command)
    assert proc.returncode == 0, proc.stderr


@pytest.mark.parametrize(
    "command",
    [
        "uv run pytest tests/tdd/test_x.py",
        "uv run pytest --collect-only",
        "uv run pytest tests/tdd/test_x.py --disable-socket",
    ],
    ids=["datei-benannt", "collect-only", "datei-plus-disable-socket"],
)
def test_ac5_bisherige_freigaben_bleiben(command):
    proc = _run_gate(command)
    assert proc.returncode == 0, proc.stderr


# ---------------------------------------------------------------------------
# Blockiert
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "command",
    [
        "uv run pytest --disable-socket",
        "uv run pytest --disable-socket --ignore=tests/red/",
        "uv run pytest --disable-socket --allow-unix-socket",
        "uv run pytest --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,::1,localhost",
        "uv run pytest --disable-socket --allow-hosts=0.0.0.0/0 --loopback-own-ports",
        "uv run pytest --disable-socket --allow-hosts=8.8.8.8 --loopback-own-ports",
        "uv run pytest --disable-socket --allow-hosts=127.0.0.1,8.8.8.8 --loopback-own-ports",
        "uv run pytest --disable-socket --allow-hosts=127.0.0.0/8 --loopback-own-ports",
        "uv run pytest --loopback-own-ports --allow-hosts=127.0.0.1",
        f"uv run pytest {NEW_FORM} --force-enable-socket",
        f"uv run pytest {NEW_FORM} -p no:socket",
        f"uv run pytest {NEW_FORM} -p no:_loopback_port_guard",
        f"uv run pytest {NEW_FORM} -o addopts=",
        f"uv run pytest {NEW_FORM} -c /tmp/leer.ini",
        f"uv run pytest {NEW_FORM} --override-ini=addopts=",
        "sh -c \"uv run pytest --disable-socket\"",
        "sh -c \"uv run pytest --disable-socket --allow-hosts=8.8.8.8 --loopback-own-ports\"",
        f"sh -c \"uv run pytest {NEW_FORM} -p no:socket\"",
        "uv run pytest --disable-socket --allow-hosts 8.8.8.8 --loopback-own-ports",
        "uv run pytest --disable-socket --allow-hosts=127.0.0.1 --allow-hosts=8.8.8.8 --loopback-own-ports",
        f"uv run pytest {NEW_FORM} -pno:socket",
        f"PYTEST_ADDOPTS=--force-enable-socket uv run pytest {NEW_FORM}",
        f"env PYTEST_ADDOPTS=--force-enable-socket uv run pytest {NEW_FORM}",
        f"export PYTEST_ADDOPTS=-pno:socket && uv run pytest {NEW_FORM}",
        # Fix-Loop 1 (F001): Shell-Metazeichen ohne Leerraum im Wert bzw.
        # Positionsargument -- shlex liefert EIN Token, die Shell startet
        # danach nacktes pytest.
        "python3 -m pytest --disable-socket --allow-hosts=127.0.0.1 --loopback-own-ports --ignore=x;pytest",
        f"uv run pytest {NEW_FORM} tests/;pytest",
        f"uv run pytest {NEW_FORM} --tb=short&&pytest",
        f"uv run pytest {NEW_FORM} --maxfail=1|pytest",
        f"uv run pytest {NEW_FORM} --ignore=$(pytest)",
        f"uv run pytest {NEW_FORM} --ignore=`pytest`",
        "sh -c \"python3 -m pytest --disable-socket --allow-hosts=127.0.0.1 --loopback-own-ports --ignore=x;pytest\"",
        f"sh -c \"uv run pytest {NEW_FORM} tests/;pytest\"",
        # F004: Substitution im Umleitungsziel -- die Argumente vor '>' sind
        # sauber, nur die Pruefung des Gesamtkommandos faengt das.
        f"uv run pytest {NEW_FORM} > $(pytest -q)",
        f"uv run pytest {NEW_FORM} > `pytest -q`",
        f"sh -c \"uv run pytest {NEW_FORM} > $(pytest -q)\"",
    ],
    ids=[
        "disable-socket-allein",
        "disable-socket-ignore-red",
        "disable-plus-unix",
        "ci-form-ohne-port-waechter",
        "cidr-alles",
        "fremder-host",
        "gemischt-fremder-host",
        "loopback-cidr",
        "ohne-disable-socket",
        "force-enable-socket",
        "p-no-socket",
        "p-no-guard",
        "o-addopts",
        "c-ini",
        "override-ini",
        "roh-disable-socket-allein",
        "roh-fremder-host",
        "roh-p-no-socket",
        "allow-hosts-leerzeichen-fremd",
        "allow-hosts-doppelt-letzter-fremd",
        "pno-zusammengeschrieben",
        "pytest-addopts-praefix",
        "env-pytest-addopts",
        "export-pytest-addopts",
        "semikolon-im-ignore-wert",
        "semikolon-im-positionsargument",
        "und-und-im-tb-wert",
        "pipe-im-maxfail-wert",
        "kommandosubstitution-im-wert",
        "backtick-im-wert",
        "roh-semikolon-im-ignore-wert",
        "roh-semikolon-im-positionsargument",
        "umleitungsziel-kommandosubstitution",
        "umleitungsziel-backtick",
        "roh-umleitungsziel-kommandosubstitution",
    ],
)
def test_ac5_unsichere_form_ist_blockiert(command):
    proc = _run_gate(command)
    assert proc.returncode == 2, (
        f"Erwartet Block (Exit 2), bekam {proc.returncode} fuer: {command}\n{proc.stderr}"
    )


def test_ac5_blockmeldung_nennt_den_neuen_aufruf():
    proc = _run_gate("uv run pytest --disable-socket")
    assert proc.returncode == 2, proc.stderr
    assert "--loopback-own-ports" in proc.stderr, proc.stderr
    assert "--allow-hosts=127.0.0.1,::1,localhost" in proc.stderr, proc.stderr
