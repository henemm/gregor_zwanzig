"""TDD RED -- Issue #1755: sicherer Offline-Volllauf.

SPEC: docs/specs/modules/fix_1755_offline_volllauf.md (AC-1 bis AC-4, AC-6)

Das neue pytest-Plugin ``tests/_loopback_port_guard.py`` (Option
``--loopback-own-ports``) soll Loopback-Verbindungen nur zu Ports erlauben,
die der Testprozess selbst gebunden hat. Prod und Staging lauschen auf diesem
Rechner auf Loopback (8090, 8000, 3000 ...), pytest-socket filtert nur nach
Host -- ohne das Plugin erreicht ``--allow-hosts=127.0.0.1`` jeden Dienst.

Nachweis dort, wo die Zusicherung WIRKT: jeder Fall ist ein echter
pytest-Unterprozess mit pytest-socket UND Plugin in derselben Sitzung
(pytest-socket setzt ``socket.connect`` je Test neu, ein Unit-Test der
Waechterfunktion allein beweist nichts). Kein Mock: echte HTTP-Stub-Server,
ein echter fremder Listener zaehlt eingehende Verbindungen.

Der fremde Listener laeuft im AEUSSEREN Testprozess -- fuer den inneren
pytest-Lauf ist er genau das, was Prod auf 8090 waere: ein Port, den der
innere Prozess nicht selbst gebunden hat.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
TESTS_DIR = ROOT / "tests"

OFFLINE_FORM = [
    "--disable-socket",
    "--allow-unix-socket",
    "--allow-hosts=127.0.0.1,::1,localhost",
    "--loopback-own-ports",
]


def _run_inner(tmp_path: Path, test_source: str, args: list[str],
               extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    """Startet einen echten pytest-Unterprozess in ``tmp_path`` mit
    pytest-socket (automatisch als Entry-Point geladen) und dem neuen Plugin
    (``-p _loopback_port_guard``, ``tests/`` auf dem PYTHONPATH)."""
    (tmp_path / "pytest.ini").write_text("[pytest]\naddopts =\n")
    (tmp_path / "test_inner.py").write_text(textwrap.dedent(test_source))
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(TESTS_DIR), str(ROOT / "src"), str(ROOT), env.get("PYTHONPATH", "")]
    )
    env.pop("PYTEST_ADDOPTS", None)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "_loopback_port_guard",
         "-p", "no:cacheprovider", "-rA", "test_inner.py", *args],
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


def _out(proc: subprocess.CompletedProcess) -> str:
    return proc.stdout + "\n" + proc.stderr


def _assert_plugin_loaded(proc: subprocess.CompletedProcess) -> None:
    text = _out(proc)
    assert "No module named" not in text, f"Plugin fehlt:\n{text}"
    assert "unrecognized arguments" not in text, f"Option unbekannt:\n{text}"


class _ForeignListener:
    """Fremder Listener (simuliert Prod auf Loopback): bindet einen Port auf
    127.0.0.1 und -- falls verfuegbar -- denselben Port auf ::1.

    Kein Accept-Thread: der Kernel schliesst den TCP-Handshake auch ohne
    ``accept()`` ab und legt die Verbindung in den Rueckstau. ``drain()``
    leert ihn NACH dem inneren Lauf synchron (non-blocking bis
    ``BlockingIOError``) -- so faellt auch ein echtes ``connect``, dem der
    Waechter erst hinterher eine Exception nachwirft, sicher auf."""

    def __init__(self) -> None:
        self.sockets: list[socket.socket] = []
        v4 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        v4.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        v4.bind(("127.0.0.1", 0))
        v4.listen(16)
        self.port = v4.getsockname()[1]
        self.sockets.append(v4)
        self.has_v6 = False
        try:
            v6 = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
            v6.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
            v6.bind(("::1", self.port))
            v6.listen(16)
            self.sockets.append(v6)
            self.has_v6 = True
        except OSError:
            pass

    def drain(self) -> int:
        """Zahl der Verbindungen, die seit Start im Rueckstau gelandet sind."""
        count = 0
        for srv in self.sockets:
            srv.setblocking(False)
            while True:
                try:
                    conn, _ = srv.accept()
                except (BlockingIOError, InterruptedError):
                    break
                count += 1
                conn.close()
        return count

    def close(self) -> None:
        for s in self.sockets:
            s.close()


@pytest.fixture
def foreign_listener():
    listener = _ForeignListener()
    yield listener
    listener.close()


# ---------------------------------------------------------------------------
# AC-1: selbst gebundene Stub-Server sind erreichbar
# ---------------------------------------------------------------------------

_AC1_SOURCE = '''
import http.client
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"stub-antwort-1755"
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def _serve(server):
    server.serve_forever(poll_interval=0.05)


@pytest.fixture(scope="session")
def session_stub():
    """Server wird IN EINEM THREAD gebunden (Port 0) -- Session-Fixture."""
    holder = {}
    ready = threading.Event()

    def _start():
        srv = HTTPServer(("127.0.0.1", 0), _Handler)
        holder["srv"] = srv
        ready.set()
        srv.serve_forever(poll_interval=0.05)

    t = threading.Thread(target=_start, daemon=True)
    t.start()
    assert ready.wait(5)
    yield holder["srv"].server_address[1]
    holder["srv"].shutdown()


def _get(port):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("GET", "/")
    resp = conn.getresponse()
    data = resp.read()
    conn.close()
    return resp.status, data


def test_stub_im_test_gebunden():
    srv = HTTPServer(("127.0.0.1", 0), _Handler)
    t = threading.Thread(target=_serve, args=(srv,), daemon=True)
    t.start()
    try:
        assert _get(srv.server_address[1]) == (200, b"stub-antwort-1755")
    finally:
        srv.shutdown()


def test_session_stub_erster_zugriff(session_stub):
    assert _get(session_stub) == (200, b"stub-antwort-1755")


def test_session_stub_folgetest(session_stub):
    assert _get(session_stub) == (200, b"stub-antwort-1755")


def test_session_stub_per_localhost(session_stub):
    conn = http.client.HTTPConnection("localhost", session_stub, timeout=5)
    conn.request("GET", "/")
    assert conn.getresponse().read() == b"stub-antwort-1755"
    conn.close()
'''


def test_ac1_selbst_gebundene_stub_server_sind_erreichbar(tmp_path):
    """AC-1: Stub im Test, Stub in Session-Fixture (in Thread gebunden),
    Folgetest und ``localhost`` -- echter HTTP-Roundtrip, kein
    SocketBlockedError."""
    proc = _run_inner(tmp_path, _AC1_SOURCE, OFFLINE_FORM)
    _assert_plugin_loaded(proc)
    text = _out(proc)
    assert proc.returncode == 0, text
    assert "4 passed" in text, text
    assert "SocketBlockedError" not in text
    assert "SocketConnectBlockedError" not in text


# ---------------------------------------------------------------------------
# AC-2: fremder Loopback-Port bleibt gesperrt (connect + connect_ex,
#       127.0.0.1 / ::1 / localhost)
# ---------------------------------------------------------------------------

_AC2_SOURCE = '''
import os
import socket

import pytest
from pytest_socket import SocketConnectBlockedError

PORT = int(os.environ["GZ_FOREIGN_PORT"])
HAS_V6 = os.environ["GZ_FOREIGN_V6"] == "1"


def _sock(family):
    s = socket.socket(family, socket.SOCK_STREAM)
    s.settimeout(2)
    return s


@pytest.mark.parametrize("call", ["connect", "connect_ex"])
def test_fremder_port_v4(call):
    s = _sock(socket.AF_INET)
    try:
        with pytest.raises(SocketConnectBlockedError):
            getattr(s, call)(("127.0.0.1", PORT))
    finally:
        s.close()


@pytest.mark.parametrize("call", ["connect", "connect_ex"])
def test_fremder_port_anderes_loopback_127_x(call):
    # connect: blockt schon pytest-socket (Host nicht freigegeben);
    # nur connect_ex belegt hier den neuen Waechter.
    s = _sock(socket.AF_INET)
    try:
        with pytest.raises(SocketConnectBlockedError):
            getattr(s, call)(("127.0.0.2", PORT))
    finally:
        s.close()


@pytest.mark.parametrize("call", ["connect", "connect_ex"])
def test_fremder_port_v6(call):
    if not HAS_V6:
        pytest.skip("kein ::1 auf diesem Rechner")
    s = _sock(socket.AF_INET6)
    try:
        with pytest.raises(SocketConnectBlockedError):
            getattr(s, call)(("::1", PORT))
    finally:
        s.close()


@pytest.mark.parametrize("call", ["connect", "connect_ex"])
def test_fremder_port_localhost(call):
    s = _sock(socket.AF_INET)
    try:
        with pytest.raises(SocketConnectBlockedError):
            getattr(s, call)(("localhost", PORT))
    finally:
        s.close()


def test_fremder_port_create_connection():
    with pytest.raises(SocketConnectBlockedError):
        socket.create_connection(("127.0.0.1", PORT), timeout=2)


# Verbindungen aus dem FIXTURE-SETUP: pytest-socket setzt seine Sperre in
# pytest_runtest_setup; ein Waechter, der sich erst danach (trylast) einhaengt,
# saehe Fixture-Setup-Verbindungen nur durch den Host-Filter -- Port offen.
@pytest.fixture(scope="session")
def session_fixture_versucht_fremden_port():
    s = _sock(socket.AF_INET)
    try:
        with pytest.raises(SocketConnectBlockedError):
            s.connect_ex(("127.0.0.1", PORT))
    finally:
        s.close()
    return True


@pytest.fixture
def function_fixture_versucht_fremden_port():
    s = _sock(socket.AF_INET)
    try:
        with pytest.raises(SocketConnectBlockedError):
            s.connect(("127.0.0.1", PORT))
    finally:
        s.close()
    return True


def test_fremder_port_aus_fixture_setup(
    session_fixture_versucht_fremden_port, function_fixture_versucht_fremden_port
):
    assert session_fixture_versucht_fremden_port is True
    assert function_fixture_versucht_fremden_port is True
'''


def test_ac2_fremder_loopback_port_bleibt_gesperrt(tmp_path, foreign_listener):
    """AC-2: Ein Listener, den der innere Testprozess NICHT gebunden hat
    (Prod-Simulation), ist ueber keine Zielform und keine Aufrufart
    erreichbar -- und sieht tatsaechlich 0 Verbindungen."""
    proc = _run_inner(
        tmp_path, _AC2_SOURCE, OFFLINE_FORM,
        extra_env={
            "GZ_FOREIGN_PORT": str(foreign_listener.port),
            "GZ_FOREIGN_V6": "1" if foreign_listener.has_v6 else "0",
        },
    )
    _assert_plugin_loaded(proc)
    text = _out(proc)
    assert proc.returncode == 0, text
    expected = "10 passed" if foreign_listener.has_v6 else "8 passed"
    assert expected in text, text
    seen = foreign_listener.drain()
    assert seen == 0, f"Fremder Listener hat {seen} Verbindung(en) gesehen"


def test_ac2_gegenprobe_ohne_plugin_option_ist_der_port_offen(tmp_path, foreign_listener):
    """Gegenprobe zum Messaufbau: dieselbe Sitzung OHNE ``--loopback-own-ports``
    (nackte CI-Form) erreicht den fremden Listener -- genau das Loch, das AC-2
    schliesst. Belegt, dass AC-2 nicht nur deshalb gruen ist, weil der Listener
    unerreichbar waere."""
    source = '''
    import os, socket
    def test_offen():
        s = socket.create_connection(("127.0.0.1", int(os.environ["GZ_FOREIGN_PORT"])), timeout=2)
        s.close()
    '''
    proc = _run_inner(
        tmp_path, source,
        ["--disable-socket", "--allow-unix-socket", "--allow-hosts=127.0.0.1,::1,localhost"],
        extra_env={"GZ_FOREIGN_PORT": str(foreign_listener.port)},
    )
    _assert_plugin_loaded(proc)
    assert proc.returncode == 0, _out(proc)
    assert foreign_listener.drain() >= 1


# ---------------------------------------------------------------------------
# AC-3: echter Ausgang bleibt gesperrt
# ---------------------------------------------------------------------------

_AC3_SOURCE = '''
import socket

import pytest
from pytest_socket import SocketConnectBlockedError


@pytest.mark.parametrize("call", ["connect", "connect_ex"])
def test_externe_adresse(call):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1)
    try:
        with pytest.raises(SocketConnectBlockedError):
            getattr(s, call)(("203.0.113.5", 80))
    finally:
        s.close()
'''


def test_ac3_externe_adresse_bleibt_gesperrt(tmp_path):
    """AC-3: TEST-NET-1 ``203.0.113.5`` ist per ``connect`` UND ``connect_ex``
    gesperrt (pytest-socket allein laesst ``connect_ex`` offen)."""
    proc = _run_inner(tmp_path, _AC3_SOURCE, OFFLINE_FORM)
    _assert_plugin_loaded(proc)
    text = _out(proc)
    assert proc.returncode == 0, text
    assert "2 passed" in text, text


# ---------------------------------------------------------------------------
# AC-4: ungueltige Optionskombinationen brechen beim Start ab
# ---------------------------------------------------------------------------

_TRIVIAL_SOURCE = '''
def test_laeuft():
    assert True
'''


@pytest.mark.parametrize(
    "args, reason_fragment",
    [
        (["--loopback-own-ports"], "--disable-socket"),
        (["--allow-hosts=127.0.0.1", "--loopback-own-ports"], "--disable-socket"),
        (["--disable-socket", "--allow-hosts=8.8.8.8", "--loopback-own-ports"], "8.8.8.8"),
        (["--disable-socket", "--allow-hosts=0.0.0.0/0", "--loopback-own-ports"], "0.0.0.0/0"),
        (["--disable-socket", "--allow-hosts=127.0.0.1,8.8.8.8", "--loopback-own-ports"], "8.8.8.8"),
    ],
    ids=["nur-option", "ohne-disable-socket", "fremder-host", "cidr-alles", "gemischt"],
)
def test_ac4_ungueltige_kombination_bricht_ab(tmp_path, args, reason_fragment):
    proc = _run_inner(tmp_path, _TRIVIAL_SOURCE, args)
    _assert_plugin_loaded(proc)
    text = _out(proc)
    assert proc.returncode not in (0, 1, 5), text
    assert "1 passed" not in text, text
    assert "--loopback-own-ports" in text, text
    assert reason_fragment in text, text


def test_ac4_gueltige_kombination_startet(tmp_path):
    proc = _run_inner(tmp_path, _TRIVIAL_SOURCE, OFFLINE_FORM)
    _assert_plugin_loaded(proc)
    text = _out(proc)
    assert proc.returncode == 0, text
    assert "1 passed" in text, text


def test_ac4_option_ueber_projekt_conftest_geladen():
    """Das Plugin muss ueber ``tests/conftest.py`` geladen werden -- sonst ist
    ``--loopback-own-ports`` im echten Projektlauf unbekannt."""
    env = dict(os.environ)
    env.pop("PYTEST_ADDOPTS", None)
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider",
         *OFFLINE_FORM, "tests/tdd/test_loopback_port_guard_offline_lauf.py"],
        cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=180,
    )
    text = _out(proc)
    assert "unrecognized arguments" not in text, text
    assert proc.returncode == 0, text


# ---------------------------------------------------------------------------
# AC-6: Prod-ansprechende Kern-Tests sind deselektiert
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "rel",
    [
        "tests/tdd/test_bug707_trip_datum_overwrite.py",
        "tests/tdd/test_bug717_waypointspanel_spread_fix.py",
        "tests/tdd/test_design_optimierungen.py",
    ],
)
def test_ac6_prod_ansprechende_datei_ist_im_kern_deselektiert(rel):
    env = dict(os.environ)
    env.pop("PYTEST_ADDOPTS", None)
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", rel],
        cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=180,
    )
    text = _out(proc)
    # Exit 5 = keine Tests ausgewaehlt; alle durch addopts-Marker deselektiert.
    assert proc.returncode == 5, text
    assert "deselected" in text, text
