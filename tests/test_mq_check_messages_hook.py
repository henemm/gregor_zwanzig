"""Issue #3294 (Spec docs/specs/modules/imac_portabilitaet.md, AC-4 bis AC-6).

Der SessionStart-Hook fuer die Claude-MQ-Nachrichtenpruefung laeuft auf jedem
Rechner: liegt das Server-Skript vor, wird es direkt aufgerufen; sonst per SSH
auf dem Server; ist der nicht erreichbar, endet der Hook still mit Exit 0.
Die Tests fuehren das Skript und das Kommando aus settings.json real aus.
"""

from __future__ import annotations

import json
import os
import socket
import stat
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


# --- Fix-Runde Adversary F001/F002 (#3294) ---------------------------------

def _fake_ssh(tmp_path: Path, ausgabe: str, exitcode: int) -> tuple[Path, Path]:
    """Legt ein `ssh` in ein eigenes PATH-Verzeichnis, das seine Argumente
    protokolliert und eine feste Ausgabe mit festem Exit-Code liefert."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    log = tmp_path / "ssh-aufrufe.log"
    fake = bindir / "ssh"
    fake.write_text(
        "#!/bin/bash\n"
        f'printf "%s\\n" "$*" >> "{log}"\n'
        f"printf '%s' '{ausgabe}'\n"
        f"exit {exitcode}\n",
        encoding="utf-8",
    )
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    return bindir, log


def _run_hook(tmp_path: Path, bindir: Path | None = None, **extra: str) -> subprocess.CompletedProcess:
    env = _env(**extra)
    if bindir is not None:
        env["PATH"] = f"{bindir}{os.pathsep}{env['PATH']}"
    return subprocess.run(["bash", str(HOOK)], env=env, cwd=str(tmp_path),
                          capture_output=True, text=True, timeout=60)


def test_f002_server_skript_vorhanden_kein_zusaetzlicher_ssh_aufruf(tmp_path: Path) -> None:
    fake = _fake_script(tmp_path, "nur einmal")
    bindir, log = _fake_ssh(tmp_path, "zweites Mal per ssh", 0)
    res = _run_hook(tmp_path, bindir, GZ_MQ_CHECK_SCRIPT=str(fake))
    assert res.returncode == 0
    assert res.stdout.count("nur einmal") == 1
    assert "zweites Mal" not in res.stdout
    assert not log.exists(), "ssh wurde trotz vorhandenem Server-Skript aufgerufen"


def test_f002_server_skript_mit_fehler_liefert_trotzdem_exit_0(tmp_path: Path) -> None:
    fake = tmp_path / "check-messages.sh"
    fake.write_text('#!/bin/bash\necho "Teilausgabe"\nexit 3\n', encoding="utf-8")
    res = _run_hook(tmp_path, GZ_MQ_CHECK_SCRIPT=str(fake))
    assert res.returncode == 0
    assert "Teilausgabe" in res.stdout


def test_f001_ssh_weg_mit_zeitgrenzen_und_ohne_passwortabfrage(tmp_path: Path) -> None:
    bindir, log = _fake_ssh(tmp_path, "=== 1 OFFENE NACHRICHT(EN) FÜR gregor ===", 0)
    res = _run_hook(tmp_path, bindir, GZ_MQ_CHECK_SCRIPT=str(tmp_path / "fehlt.sh"),
                    GZ_MQ_SSH_HOST="testserver")
    assert res.returncode == 0
    assert "OFFENE NACHRICHT(EN) FÜR gregor" in res.stdout
    aufruf = log.read_text(encoding="utf-8")
    for option in ("ConnectTimeout=3", "BatchMode=yes", "ServerAliveInterval=2", "ServerAliveCountMax=2"):
        assert option in aufruf, f"ssh-Option {option} fehlt: {aufruf}"
    assert "testserver" in aufruf
    assert "cd ~/gregor_zwanzig && bash ~/claude-mq/check-messages.sh" in aufruf


def test_f002_ssh_fehler_mit_teilausgabe_bleibt_still(tmp_path: Path) -> None:
    bindir, _ = _fake_ssh(tmp_path, "halbe Ausgabe", 255)
    res = _run_hook(tmp_path, bindir, GZ_MQ_CHECK_SCRIPT=str(tmp_path / "fehlt.sh"))
    assert res.returncode == 0
    assert res.stdout == ""
    assert res.stderr == ""


def test_f001_haengender_server_blockiert_den_start_nicht(tmp_path: Path) -> None:
    """Echter ssh gegen einen Port, der Verbindungen annimmt und nie antwortet
    (Server hängt, iMac unterwegs). ConnectTimeout muss greifen."""
    with socket.socket() as srv:
        srv.bind(("127.0.0.1", 0))
        srv.listen(5)
        port = srv.getsockname()[1]
        start = time.monotonic()
        res = _run_hook(tmp_path, GZ_MQ_CHECK_SCRIPT=str(tmp_path / "fehlt.sh"),
                        GZ_MQ_SSH_HOST=f"ssh://gz-test@127.0.0.1:{port}")
        dauer = time.monotonic() - start
    assert res.returncode == 0
    assert res.stdout == ""
    assert dauer < 10, f"Hook hing {dauer:.1f} s am hängenden Server"
