"""Issue #2190 — Core-Bind-Guard: der Python-Core lauscht nur auf 127.0.0.1.

Spec: docs/specs/modules/core_bind_guard.md (AC-1 bis AC-6, AC-8).

Verhaltenstests gegen den ECHTEN Startpfad: uvicorn laeuft als Subprozess
auf einem freien Port (nie 8000/8001), der Test beobachtet von aussen, ob der
Port je lauscht (``/proc/net/tcp`` und ``/proc/net/tcp6``, Zustand LISTEN),
welchen Exit-Code der Prozess liefert und was er ins Log schreibt. Kein Mock:
die Zusicherung „kein Socket" wird dort geprueft, wo sie wirkt — im Kernel.

Die Szenarien mit mehreren uvicorn-Configs im selben Prozess (AC-5,
Reihenfolge vor dem Egress-Guard) laufen ebenfalls in einem frischen
Subprozess, damit kein ``uvicorn.Config``-Objekt im pytest-Prozess
zurueckbleibt und spaetere ``with TestClient(app)``-Tests beeinflusst.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import textwrap
import time
import urllib.request
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# Wie lange ein verweigerter Start hoechstens dauern darf, bevor der Test ihn
# als „laeuft trotzdem" wertet. Der App-Import braucht einige Sekunden.
START_TIMEOUT_S = 45.0
POLL_INTERVAL_S = 0.02
TCP_LISTEN_STATE = "0A"


def _free_port() -> int:
    """Freier TCP-Port, nie einer der Betriebs-Ports 8000/8001."""
    while True:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        if port not in (8000, 8001):
            return port


def _port_is_listening(port: int) -> bool:
    """True, wenn irgendein Socket (IPv4 oder IPv6, jede Adresse) auf ``port`` lauscht."""
    for table in ("/proc/net/tcp", "/proc/net/tcp6"):
        try:
            lines = Path(table).read_text().splitlines()[1:]
        except OSError:
            continue
        for line in lines:
            fields = line.split()
            if len(fields) < 4:
                continue
            local_port = int(fields[1].rsplit(":", 1)[1], 16)
            if local_port == port and fields[3] == TCP_LISTEN_STATE:
                return True
    return False


def _subprocess_env(tmp_path: Path, extra: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(REPO_ROOT), str(REPO_ROOT / "src")])
    env["GZ_DATA_DIR"] = str(tmp_path / "data")
    env["GZ_CACHE_DIR"] = str(tmp_path / "cache")
    # Kein echter Telegram-Aufruf beim Start (setMyCommands im Lifespan).
    env["GZ_TELEGRAM_BOT_TOKEN"] = ""
    env["GZ_TELEGRAM_TEST_BOT_TOKEN"] = ""
    env["PYTHONUNBUFFERED"] = "1"
    if extra:
        env.update(extra)
    return env


def _start_core(host: str, port: int, tmp_path: Path, extra_env: dict[str, str] | None = None) -> subprocess.Popen:
    # cwd = tmp_path: keine .env des Repos, kein Zufallszustand aus dem Worktree.
    return subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "api.main:app", "--host", host, "--port", str(port)],
        cwd=str(tmp_path),
        env=_subprocess_env(tmp_path, extra_env),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def _stop(proc: subprocess.Popen) -> str:
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=10)
    out, _ = proc.communicate()
    return out or ""


def _run_refused_start(host: str, tmp_path: Path, extra_env: dict[str, str] | None = None):
    """Startet den Core mit ``host`` und beobachtet bis zum Ende im 20-ms-Takt.

    Rueckgabe: (exit_code oder None, je_gelauscht, port, ausgabe).
    ``exit_code is None`` heisst: der Prozess lief nach START_TIMEOUT_S noch.
    """
    port = _free_port()
    proc = _start_core(host, port, tmp_path, extra_env)
    ever_listened = False
    deadline = time.monotonic() + START_TIMEOUT_S
    try:
        while time.monotonic() < deadline:
            if _port_is_listening(port):
                ever_listened = True
                break
            if proc.poll() is not None:
                break
            time.sleep(POLL_INTERVAL_S)
        exit_code = proc.poll()
    finally:
        output = _stop(proc)
    return exit_code, ever_listened, port, output


# ---------------------------------------------------------------------------
# AC-1 / AC-2 / AC-3: verbotene Bind-Adressen
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("host", ["0.0.0.0", "localhost", "::1"])
def test_core_verweigert_start_auf_nicht_loopback_adresse(host: str, tmp_path: Path) -> None:
    """
    GIVEN: der Core wird mit ``--host <host>`` (nicht 127.0.0.1) gestartet
    WHEN:  uvicorn die App startet
    THEN:  bricht der Start mit Exit 3 ab und der Port lauscht zu keinem Zeitpunkt
    """
    exit_code, ever_listened, port, output = _run_refused_start(host, tmp_path)

    assert not ever_listened, (
        f"Core hat mit --host {host} auf Port {port} gelauscht — Bind-Guard fehlt (#2190).\n{output[-2000:]}"
    )
    assert exit_code is not None, f"Core lief mit --host {host} nach {START_TIMEOUT_S}s noch.\n{output[-2000:]}"
    assert exit_code == 3, f"Erwartet uvicorn-Exit 3 (Lifespan-Abbruch), bekam {exit_code}.\n{output[-2000:]}"


@pytest.mark.parametrize("host", ["0.0.0.0", "::1"])
def test_core_abbruchmeldung_nennt_host_port_und_issue(host: str, tmp_path: Path) -> None:
    """
    GIVEN: ein Betreiber startet den Core mit einer verbotenen Adresse
    WHEN:  der Dienst abbricht
    THEN:  nennt die CRITICAL-Meldung den tatsaechlichen Host, den Port und „#2190"
    """
    exit_code, _ever_listened, port, output = _run_refused_start(host, tmp_path)

    critical_lines = [line for line in output.splitlines() if "CRITICAL" in line and "#2190" in line]
    assert critical_lines, f"Keine CRITICAL-Zeile mit #2190 in der Ausgabe.\n{output[-2000:]}"
    line = critical_lines[0]
    assert host in line, f"Host {host!r} fehlt in der Meldung: {line!r}"
    assert str(port) in line, f"Port {port} fehlt in der Meldung: {line!r}"
    assert exit_code == 3


# ---------------------------------------------------------------------------
# AC-8: kein Override per Umgebungsvariable
# ---------------------------------------------------------------------------


def test_core_verweigert_trotz_gesetzter_umgebungsvariablen(tmp_path: Path) -> None:
    """
    GIVEN: in der Umgebung stehen Variablen, die nach einem Override klingen
    WHEN:  der Core mit ``--host 0.0.0.0`` gestartet wird
    THEN:  verweigert er den Start trotzdem (Exit 3, Port lauscht nie)
    """
    override_env = {
        "GZ_HOST": "0.0.0.0",
        "GZ_ALLOW_ANY_BIND": "1",
        "GZ_BIND_GUARD": "off",
        "GZ_BIND_GUARD_DISABLED": "true",
        "GZ_ENV": "development",
    }
    exit_code, ever_listened, port, output = _run_refused_start("0.0.0.0", tmp_path, override_env)

    assert not ever_listened, f"Override per Umgebung hat Lauschen auf {port} erlaubt.\n{output[-2000:]}"
    assert exit_code == 3, f"Erwartet Exit 3 trotz Override-Variablen, bekam {exit_code}.\n{output[-2000:]}"


# ---------------------------------------------------------------------------
# AC-4: 127.0.0.1 startet normal
# ---------------------------------------------------------------------------


def test_core_startet_auf_127_0_0_1_und_health_antwortet(tmp_path: Path) -> None:
    """
    GIVEN: der Core wird mit ``--host 127.0.0.1`` gestartet
    WHEN:  der Dienst hochgefahren ist
    THEN:  antwortet ``GET /health`` mit 200
    """
    port = _free_port()
    proc = _start_core("127.0.0.1", port, tmp_path)
    status = None
    try:
        deadline = time.monotonic() + START_TIMEOUT_S
        while time.monotonic() < deadline and proc.poll() is None:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as resp:
                    status = resp.status
                    break
            except OSError:
                time.sleep(0.2)
    finally:
        output = _stop(proc)

    assert status == 200, f"/health antwortete nicht (Status {status}).\n{output[-2000:]}"


# ---------------------------------------------------------------------------
# AC-4 (Reihenfolge) / AC-5: Lifespan mit uvicorn-Configs im selben Prozess
# ---------------------------------------------------------------------------

_LIFESPAN_PROBE = textwrap.dedent(
    """
    import asyncio
    import importlib
    import sys

    import uvicorn
    from fastapi import FastAPI

    from api.main import app as core_app

    egress = importlib.import_module("app.egress_guard")

    own_host, foreign_host = sys.argv[1], sys.argv[2]

    foreign = uvicorn.Config(app=FastAPI(), host=foreign_host, port=1)
    foreign.load()
    own = uvicorn.Config(app=core_app, host=own_host, port=54321)
    own.load()

    async def run():
        async with core_app.router.lifespan_context(core_app):
            pass

    try:
        asyncio.run(run())
        print("RESULT=started")
    except Exception as exc:  # noqa: BLE001
        print("RESULT=refused:" + type(exc).__name__)
    print("EGRESS_INSTALLED=" + str(egress._installed))
    """
)


def _run_lifespan_probe(own_host: str, foreign_host: str, tmp_path: Path) -> str:
    # GZ_ENV=staging: install_egress_guard ist nur dann scharf, sodass
    # sichtbar wird, ob der Egress-Guard installiert wurde.
    proc = subprocess.run(
        [sys.executable, "-c", _LIFESPAN_PROBE, own_host, foreign_host],
        cwd=str(tmp_path),
        env=_subprocess_env(tmp_path, {"GZ_ENV": "staging"}),
        capture_output=True,
        text=True,
        timeout=120,
    )
    return proc.stdout + proc.stderr


def test_fremde_config_mit_0_0_0_0_wird_ignoriert(tmp_path: Path) -> None:
    """
    GIVEN: im selben Prozess bedient eine fremde uvicorn-Config mit host=0.0.0.0
           eine andere App, die eigene Config steht auf 127.0.0.1
    WHEN:  der Lifespan von api.main:app laeuft
    THEN:  startet der Core, und der Egress-Guard wird danach installiert
    """
    output = _run_lifespan_probe("127.0.0.1", "0.0.0.0", tmp_path)

    assert "RESULT=started" in output, f"Fremde Config hat den Start verhindert.\n{output[-2000:]}"
    assert "EGRESS_INSTALLED=True" in output, f"Egress-Guard nach erlaubtem Start nicht installiert.\n{output[-2000:]}"


def test_eigene_config_entscheidet_nicht_die_fremde(tmp_path: Path) -> None:
    """
    GIVEN: die eigene Config steht auf 0.0.0.0, eine fremde auf 127.0.0.1
    WHEN:  der Lifespan von api.main:app laeuft
    THEN:  wird der Start verweigert, und der Egress-Guard wurde nie installiert
           (Bind-Guard laeuft als ERSTER Schritt, vor install_egress_guard)
    """
    output = _run_lifespan_probe("0.0.0.0", "127.0.0.1", tmp_path)

    assert "RESULT=refused:RuntimeError" in output, (
        f"Eigene Config mit 0.0.0.0 wurde nicht verweigert.\n{output[-2000:]}"
    )
    assert "EGRESS_INSTALLED=False" in output, (
        f"Egress-Guard wurde VOR dem Bind-Guard installiert (Reihenfolge #2190).\n{output[-2000:]}"
    )


# ---------------------------------------------------------------------------
# AC-6: TestClient ohne uvicorn-Server
# ---------------------------------------------------------------------------


def test_testclient_lifespan_laeuft_ohne_abbruch() -> None:
    """
    GIVEN: Tests nutzen ``with TestClient(app)`` ohne uvicorn-Server
    WHEN:  der Lifespan laeuft
    THEN:  gilt der Guard als nicht anwendbar, /health antwortet 200
    """
    from fastapi.testclient import TestClient

    from api.main import app

    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
