"""Vorgewaermter Fork-Server fuer Mail-Validatoren (Issue #3331).

SPEC: docs/specs/modules/rework_3331_validatoren_tempo.md. Als Skript ist dies der
Server (je JSON-Zeile ein ``os.fork``-Kind), ``Klient`` die Gegenseite im Test.
"""
import atexit
import contextlib
import json
import os
import runpy
import select
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

SERVER_SKRIPT = Path(__file__).resolve()
START_FRIST = 60.0  # bis zur Startzeile, beim ersten Lauf samt Serverstart
#: Nur schwere Module; Hook-Module kommen je Lauf frisch aus der Hook-Kopie.
VORAB = ("argparse email imaplib re html dataclasses math app.metric_catalog app.loader app.ampel_templates "
         "i18n.catalog output.renderers.compare_hourly_metric_ids output.renderers.channel_layout "
         "output.renderers.compare_metric_catalog output.renderers.email.helpers playwright.sync_api").split()


class ServerFehler(RuntimeError):
    """Server tot, ungeeignet oder mit fremder Antwort."""


def _beende_gruppe(pid: int) -> None:
    with contextlib.suppress(ProcessLookupError, PermissionError):  # macOS: EPERM bei Zombies
        os.killpg(pid, signal.SIGKILL)


def _fuehre_aus(skript: str) -> int:
    code = None  # Regeln wie bei ``python skript``
    try:
        runpy.run_path(skript, run_name="__main__")
    except SystemExit as ende:
        code = ende.code
    except BaseException as fehler:
        tb = fehler.__traceback__  # ohne Rahmen von Server und runpy
        while tb and tb.tb_frame.f_code.co_filename != skript:
            tb = tb.tb_next
        sys.excepthook(type(fehler), fehler.with_traceback(tb), tb)
        code = 1
    if code is not None and not isinstance(code, int):
        print(code, file=sys.stderr)
        code = 1
    sys.stdout.flush()
    sys.stderr.flush()
    return (code or 0) & 0xFF


def _kind(anfrage: dict, sync: socket.socket, fremde_fds: list[int], basis: list[str], ausgaben) -> None:
    """Kehrt nie zurueck; stirbt der Server vor der Startzeile, endet das Kind ohne Lauf."""
    code = 1
    try:
        for fd in fremde_fds:  # sonst bliebe beim Klienten/Server das EOF aus
            os.close(fd)
        os.setsid()
        os.environ.clear()
        os.environ.update(anfrage["env"])
        time.tzset()
        tempfile.tempdir = None
        os.chdir(anfrage["cwd"])
        sys.argv = [anfrage["skript"], *anfrage["args"]]
        sys.path[:] = [os.path.dirname(anfrage["skript"]), *basis]
        for ziel, datei in enumerate(ausgaben, start=1):
            os.dup2(datei.fileno(), ziel)
        sync.sendall(b"1")
        if sync.recv(1):
            code = _fuehre_aus(anfrage["skript"])
    except BaseException:
        sys.excepthook(*sys.exc_info())
    finally:
        os._exit(code)


def _warte(pid: int, ende: float) -> int:
    try:
        while not (fertig := os.waitpid(pid, os.WNOHANG))[0]:
            if time.monotonic() > ende:
                raise TimeoutError("Frist im Server ueberschritten")
            time.sleep(0.005)
        return os.waitstatus_to_exitcode(fertig[1])
    except BaseException:
        _beende_gruppe(pid)
        raise


def _bediene(anfrage: dict, ein_fd: int, aus, basis: list[str]) -> None:
    def antworte(**felder):
        print(json.dumps({"kennung": anfrage["kennung"], **felder}), file=aus, flush=True)
    hier, dort = socket.socketpair()
    with tempfile.TemporaryFile("w+") as out, tempfile.TemporaryFile("w+") as err, hier, dort:
        pid = os.fork()
        if pid == 0:
            _kind(anfrage, dort, [ein_fd, aus.fileno(), hier.fileno()], basis, (out, err))
        dort.close()
        assert hier.recv(1), "Kind konnte nicht eingerichtet werden"
        antworte(pid=pid)
        hier.sendall(b"1")
        code = _warte(pid, time.monotonic() + anfrage["timeout"] + 1)  # nach dem Klienten
        out.seek(0)
        err.seek(0)
        antworte(returncode=code, stdout=out.read(), stderr=err.read())


def _server() -> None:
    assert hasattr(os, "fork"), "validator_server: os.fork fehlt auf dieser Plattform"
    ein, aus = os.fdopen(os.dup(0), "rb"), os.fdopen(os.dup(1), "w")
    os.dup2(os.open(os.devnull, os.O_RDONLY), 0)
    os.dup2(2, 1)  # nichts ausser dem Protokoll geht an den Klienten
    basis = sys.path[1:]
    sys.path[:] = [str(SERVER_SKRIPT.parents[2] / "src"), *basis]
    for name in VORAB:
        __import__(name)
    if threading.active_count() != 1:
        raise SystemExit(f"validator_server: mehr als ein Thread vor dem fork: {threading.enumerate()}")
    for zeile in ein:  # bis EOF, auch bei hart beendetem Klienten
        _bediene(json.loads(zeile), ein.fileno(), aus, basis)


class Klient:
    """Server ab dem ersten Lauf, nach JEDER Ausnahme verworfen (kein Rueckfall)."""
    def __init__(self, server_skript: Path = SERVER_SKRIPT):
        self.server_skript, self._proc, self.pid = server_skript, None, None
        atexit.register(self.verwerfen)

    def lauf(self, skript, args, *, env, cwd, timeout: float = 180) -> subprocess.CompletedProcess:
        befehl = [sys.executable, str(skript), *args]
        self._kennung, self._kind, self._puffer = os.urandom(8).hex(), None, b""
        try:
            if self._proc is None:
                self._starte()
            self._sende({"kennung": self._kennung, "skript": str(skript), "args": list(args),
                         "env": dict(env), "cwd": str(cwd), "timeout": timeout})
            self._kind = self._lies(0, time.monotonic() + START_FRIST)["pid"]
            antwort = self._lies(1, time.monotonic() + timeout)
            self._kennung = self._kind = None
            return subprocess.CompletedProcess(befehl, *(antwort[k] for k in ("returncode", "stdout", "stderr")))
        except BaseException as fehler:
            self.verwerfen()
            if isinstance(fehler, TimeoutError):
                raise subprocess.TimeoutExpired(befehl, timeout) from fehler
            raise

    def _starte(self) -> None:
        self._stderr = tempfile.TemporaryFile("w+")  # eine volle Pipe blockierte den Server
        self._proc = subprocess.Popen([sys.executable, str(self.server_skript)], stdin=subprocess.PIPE,
                                      stdout=subprocess.PIPE, stderr=self._stderr, bufsize=0)
        self.pid = self._proc.pid

    def _sende(self, anfrage: dict) -> None:
        daten, fd = json.dumps(anfrage).encode() + b"\n", self._proc.stdin.fileno()
        with contextlib.suppress(BrokenPipeError):  # Server tot: _lies meldet es
            while daten:
                if not select.select([], [fd], [], START_FRIST)[1]:
                    raise TimeoutError
                daten = daten[os.write(fd, daten[:select.PIPE_BUF]):]

    def _lies(self, nr: int, ende: float) -> dict:
        """Antwortzeile ``nr``; bleibt im Puffer, damit ``verwerfen`` sie findet."""
        while self._puffer.count(b"\n") <= nr:
            if not select.select([self._proc.stdout], [], [], max(0.0, ende - time.monotonic()))[0]:
                raise TimeoutError
            stueck = self._proc.stdout.read(1 << 16)
            if not stueck:
                if time.monotonic() >= ende:
                    raise TimeoutError
                with contextlib.suppress(subprocess.TimeoutExpired):
                    self._proc.wait(5)  # das EOF kommt teils vor der Meldung auf stderr
                self._stderr.seek(0)
                raise ServerFehler(f"Server tot: {self._stderr.read()}")
            self._puffer += stueck
        antwort = json.loads(self._puffer.split(b"\n")[nr])
        if antwort.get("kennung") != self._kennung:
            raise ServerFehler(f"Antwort mit fremder Kennung: {antwort}")
        return antwort

    def verwerfen(self) -> None:
        """Server samt Kindgruppe eines offenen Laufs beenden. Ist der Server tot,
        steht die Startzeile in der Pipe, oder das Kind endet selbst (``_kind``)."""
        if self._proc is None:
            return
        try:
            with self._proc as proc, self._stderr:
                proc.kill()
                proc.wait()
                if self._kennung and self._kind is None:
                    with contextlib.suppress(Exception):
                        self._kind = self._lies(0, time.monotonic() + 2)["pid"]
                if self._kind is not None:
                    _beende_gruppe(self._kind)
        finally:
            self._proc = self.pid = None


GEMEINSAM = Klient()  # ein Server je Testprozess (je xdist-Worker)

if __name__ == "__main__":
    _server()
