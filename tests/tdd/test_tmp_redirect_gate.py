"""Waechter fuer #1688: Ausgabe-Umleitung nach /tmp wird vor dem Entstehen der Datei blockiert.

Kein Mock-Theater: der echte Hook laeuft als Subprozess mit echtem stdin-JSON
(PreToolUse:Bash). Der Hook ist eigenstaendig (kein Plugin noetig). Fehlalarm-Faelle
(Lesen, Projekt, Scratchpad, /dev/null, fd-Duplizierung) sind ebenso Pflicht wie die
Blockfaelle.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
# Ueberschreibbar fuer die Mutations-Gegenprobe (externe Kopie statt Originaldatei).
HOOK = Path(os.environ["GZ_TMP_REDIRECT_GATE_PATH"]) if os.environ.get(
    "GZ_TMP_REDIRECT_GATE_PATH") else ROOT / ".claude" / "hooks" / "tmp_redirect_gate.py"
SCRATCH = "/tmp/claude-1000/-home-user-proj/abc-123/scratchpad"


def _run(command: str, raw_stdin: str | None = None) -> subprocess.CompletedProcess:
    payload = raw_stdin if raw_stdin is not None else json.dumps(
        {"tool_name": "Bash", "tool_input": {"command": command}})
    return subprocess.run([sys.executable, str(HOOK)], input=payload, capture_output=True,
                          text=True, timeout=30)


BLOCK = [
    "uv run pytest tests/x.py > /tmp/pytest_full.log",
    "uv run pytest tests/x.py > /tmp/pytest_full.log 2>&1",
    "uv run pytest tests/x.py >> /tmp/out.txt",
    "uv run pytest tests/x.py 2>/tmp/err.txt",
    "uv run pytest tests/x.py &> /tmp/all.log",
    "uv run pytest tests/x.py 2>&1 | tee /tmp/pytest-output.txt",
    "uv run pytest tests/x.py | tee -a /var/tmp/o.log",
    "uv run pytest tests/x.py --junitxml=/tmp/junit.xml",
    "uv run pytest tests/x.py --junitxml /tmp/junit.xml",
    "some_tool --output /dev/shm/res.json",
    "echo hi >/tmp/x",
    "echo hi > '/tmp/with space.log'",
    "echo hi > /tmp/../tmp/x",
    "echo hi > /tmp/claude-1000/../x.log",
    "cd /tmp && make > /tmp/make.log",
    'sh -c "uv run pytest tests/x.py > /tmp/n.log"',
]

ALLOW = [
    f"uv run pytest tests/x.py > {SCRATCH}/pytest.log 2>&1",
    f"uv run pytest tests/x.py 2>&1 | tee {SCRATCH}/o.log",
    "uv run pytest tests/x.py > out.log 2>&1",
    "uv run pytest tests/x.py > ./logs/out.log",
    "uv run pytest tests/x.py > /home/user/gregor_zwanzig/out.log",
    "uv run pytest tests/x.py > /dev/null 2>&1",
    "uv run pytest tests/x.py 2>&1",
    "cat /tmp/pytest_full.log",
    "ls -l /tmp",
    "grep foo < /tmp/in.txt",
    "diff /tmp/a /tmp/b > result.diff",
    "echo '> /tmp/x' is just text",
    "echo hi",
    f"uv run pytest tests/x.py --junitxml={SCRATCH}/j.xml",
    f'sh -c "uv run pytest tests/x.py > {SCRATCH}/n.log"',
]


@pytest.mark.parametrize("command", BLOCK)
def test_umleitung_nach_tmp_wird_blockiert(command):
    res = _run(command)
    assert res.returncode == 2, (command, res.stderr)
    assert "scratchpad" in res.stderr.lower()


@pytest.mark.parametrize("command", ALLOW)
def test_harmlose_kommandos_bleiben_frei_und_stumm(command):
    res = _run(command)
    assert res.returncode == 0, (command, res.stderr)
    assert res.stdout == "" and res.stderr == ""


@pytest.mark.parametrize("raw", ["", "kein json", "[]", json.dumps({"tool_input": []}),
                                 json.dumps({"tool_input": {"command": 5}})])
def test_kaputte_eingabe_ist_fail_open(raw):
    assert _run("", raw_stdin=raw).returncode == 0


def test_hook_ist_in_settings_verdrahtet():  # doc-compliance-test
    settings = json.loads((ROOT / ".claude" / "settings.json").read_text())
    kommandos = [h["command"] for e in settings["hooks"]["PreToolUse"]
                 if e.get("matcher") == "Bash" for h in e["hooks"]]
    assert any("tmp_redirect_gate.py" in k for k in kommandos)
