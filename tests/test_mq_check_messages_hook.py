"""Issue #3294 (Spec docs/specs/modules/imac_portabilitaet.md, AC-4 bis AC-6).

Der SessionStart-Hook fuer die Claude-MQ-Nachrichtenpruefung laeuft auf jedem
Rechner: liegt das Server-Skript vor, wird es direkt aufgerufen; sonst per SSH
auf dem Server; ist der nicht erreichbar, endet der Hook still mit Exit 0.
Die Tests fuehren das Skript und das Kommando aus settings.json real aus.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HOOK = REPO / ".claude" / "hooks" / "mq_check_messages.sh"


def _fake_script(tmp_path: Path, text: str = "=== 1 OFFENE NACHRICHT(EN) FÜR gregor ===") -> Path:
    fake = tmp_path / "check-messages.sh"
    fake.write_text(f'#!/bin/bash\necho "{text}"\n', encoding="utf-8")
    return fake


def _env(**extra: str) -> dict[str, str]:
    env = dict(os.environ)
    env.update(extra)
    return env


def test_ac4_vorhandenes_server_skript_wird_durchgereicht(tmp_path: Path) -> None:
    fake = _fake_script(tmp_path)
    res = subprocess.run(
        ["bash", str(HOOK)],
        env=_env(GZ_MQ_CHECK_SCRIPT=str(fake), GZ_MQ_SSH_HOST="gz-nicht-vorhanden.invalid"),
        capture_output=True, text=True, timeout=30,
    )
    assert res.returncode == 0, res.stderr
    assert "OFFENE NACHRICHT(EN) FÜR gregor" in res.stdout


def test_ac5_ohne_skript_und_ohne_server_still_und_schnell(tmp_path: Path) -> None:
    start = time.monotonic()
    res = subprocess.run(
        ["bash", str(HOOK)],
        env=_env(
            GZ_MQ_CHECK_SCRIPT=str(tmp_path / "gibt-es-nicht.sh"),
            GZ_MQ_SSH_HOST="gz-nicht-vorhanden.invalid",
        ),
        capture_output=True, text=True, timeout=30,
    )
    dauer = time.monotonic() - start
    assert res.returncode == 0
    assert res.stdout == ""
    assert res.stderr == ""
    assert dauer < 10, f"Hook brauchte {dauer:.1f} s"


def test_ac6_sessionstart_kommando_nutzt_repo_skript(tmp_path: Path) -> None:
    settings = json.loads((REPO / ".claude" / "settings.json").read_text(encoding="utf-8"))
    kommandos = [
        h["command"]
        for eintrag in settings["hooks"]["SessionStart"]
        for h in eintrag["hooks"]
        if h.get("type") == "command"
    ]
    mq = [k for k in kommandos if "mq_check_messages" in k or "check-messages" in k]
    assert len(mq) == 1, kommandos
    fake = _fake_script(tmp_path, "Nachricht aus dem Fake-Skript")
    res = subprocess.run(
        ["bash", "-c", mq[0]],
        env=_env(
            CLAUDE_PROJECT_DIR=str(REPO),
            GZ_MQ_CHECK_SCRIPT=str(fake),
            GZ_MQ_SSH_HOST="gz-nicht-vorhanden.invalid",
        ),
        cwd=str(tmp_path),
        capture_output=True, text=True, timeout=30,
    )
    assert res.returncode == 0, res.stderr
    assert "Nachricht aus dem Fake-Skript" in res.stdout
