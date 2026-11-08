"""pytest-Plugin: Loopback nur zu selbst gebundenen Ports (Issue #1755).

SPEC: docs/specs/modules/fix_1755_offline_volllauf.md

Aktiv nur mit ``--loopback-own-ports``. Gedacht fuer den sicheren
Offline-Volllauf (einzeilig, woertlich; optional dahinter `` > datei 2>&1``,
jede andere Abweichung blockt das Breitlauf-Gate)::

    uv run pytest --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,::1,localhost --loopback-own-ports --ignore=tests/red/

pytest-socket filtert nur nach Host. Auf diesem Rechner lauschen Prod und
Staging auf Loopback -- ``--allow-hosts=127.0.0.1`` allein liesse jeden Test
sie erreichen. Dieses Plugin erlaubt Loopback-Verbindungen nur zu Ports, die
der Testprozess selbst gebunden hat.

Mechanik (bewusst NICHT per ``trylast``-Hook je Test: pytest baut Fixtures
innerhalb seines eigenen ``pytest_runtest_setup`` auf, ein spaeter Hook saehe
Fixture-Setup-Verbindungen nicht):

* ``bind`` wird ab ``pytest_configure`` umhuellt; nach erfolgreichem Bind
  landet der tatsaechliche Port (auch bei Port 0) im Bind-Set. Das erfasst
  Session-/Modul-Fixtures und Server in Threads.
* ``connect``: pytest-socket ruft nach seiner Host-Pruefung die Modul-Variable
  ``pytest_socket._true_connect`` auf (und setzt sie beim Aufraeumen zurueck
  auf ``socket.socket.connect``). Diese wird durch die Port-Pruefung ersetzt
  -- die Pruefung liegt damit HINTER pytest-socket, dauerhaft, auch im
  Fixture-Setup und zwischen den Tests.
* ``connect_ex`` laesst pytest-socket offen; die Huelle prueft selbst: Unix-
  Sockets durch, nachweisbares Loopback nur zu eigenen Ports, alles andere
  gesperrt (die Startpruefung erzwingt ``--allow-hosts`` nur Loopback, also
  waere jedes andere Ziel auch fuer pytest-socket gesperrt).

Bekannte Grenzen:

* Ausgang aus Kindprozessen (curl, Go, Playwright) ist nicht erfasst.
* Verbindungslose Sendungen (UDP ``sendto``/``sendmsg``) sind nicht
  abgedichtet -- wie bei pytest-socket selbst, das ebenfalls nur ``connect``
  sperrt (Adversary-Befund F002, bewusst nicht Teil dieses Fixes).
"""
from __future__ import annotations

import ipaddress
import socket
import threading

import pytest

_ALLOWED_LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}

_bound_ports: set[int] = set()
_lock = threading.Lock()
_allowed_list: list[str] = []


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("socket")
    group.addoption(
        "--loopback-own-ports",
        action="store_true",
        dest="loopback_own_ports",
        help=(
            "Loopback-Verbindungen nur zu Ports erlauben, die der Testprozess "
            "selbst gebunden hat (Issue #1755). Verlangt --disable-socket und "
            "--allow-hosts nur aus 127.0.0.1,::1,localhost."
        ),
    )


def _validate_options(config: pytest.Config) -> list[str]:
    """Startpruefung; liefert die freigegebenen Hosts oder bricht ab."""
    if not config.getoption("disable_socket", default=False):
        raise pytest.UsageError(
            "--loopback-own-ports verlangt --disable-socket (pytest-socket)."
        )
    raw = config.getoption("allow_hosts", default=None) or ""
    entries = [e.strip() for e in raw.split(",")] if raw else []
    bad = [e for e in entries if e not in _ALLOWED_LOOPBACK_HOSTS]
    if bad:
        raise pytest.UsageError(
            "--loopback-own-ports erlaubt in --allow-hosts nur "
            "127.0.0.1,::1,localhost; unzulaessig: " + ",".join(bad)
        )
    return entries


def _is_loopback_host(host: object) -> bool:
    """Nur nachweisbares Loopback: ``localhost`` oder eine Loopback-IP."""
    if not isinstance(host, str):
        return False
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _blocked(host: object) -> Exception:
    from pytest_socket import SocketConnectBlockedError

    return SocketConnectBlockedError(_allowed_list, host if isinstance(host, str) else None)


def _check_loopback_port(address: object) -> None:
    """Loopback-Ziel mit fremdem Port -> SocketConnectBlockedError."""
    if not isinstance(address, tuple) or len(address) < 2:
        return
    host, port = address[0], address[1]
    if not _is_loopback_host(host):
        return
    with _lock:
        owned = port in _bound_ports
    if not owned:
        raise _blocked(f"{host}:{port}")


def _is_inet(sock: socket.socket) -> bool:
    return sock.family in (socket.AF_INET, socket.AF_INET6)


def _install(real_socket: type, pytest_socket_mod: object) -> None:
    real_bind = real_socket.bind
    real_connect = pytest_socket_mod._true_connect  # type: ignore[attr-defined]
    real_connect_ex = real_socket.connect_ex

    def tracking_bind(self, address):
        real_bind(self, address)
        if _is_inet(self):
            port = self.getsockname()[1]
            with _lock:
                _bound_ports.add(port)

    def guarded_connect(self, *args):
        if args and _is_inet(self):
            _check_loopback_port(args[0])
        return real_connect(self, *args)

    def guarded_connect_ex(self, address):
        if not _is_inet(self):
            return real_connect_ex(self, address)
        host = address[0] if isinstance(address, tuple) and address else None
        if not _is_loopback_host(host):
            raise _blocked(host)
        _check_loopback_port(address)
        return real_connect_ex(self, address)

    real_socket.bind = tracking_bind
    real_socket.connect_ex = guarded_connect_ex
    pytest_socket_mod._true_connect = guarded_connect  # type: ignore[attr-defined]
    real_socket.connect = guarded_connect


def pytest_configure(config: pytest.Config) -> None:
    if not config.getoption("loopback_own_ports", default=False):
        return
    hosts = _validate_options(config)
    try:
        import pytest_socket
    except ImportError as exc:  # pragma: no cover - pytest-socket ist Pflicht
        raise pytest.UsageError("--loopback-own-ports verlangt pytest-socket.") from exc
    if not hasattr(pytest_socket, "_true_connect") or not hasattr(pytest_socket, "_true_socket"):
        raise pytest.UsageError(
            "--loopback-own-ports: pytest-socket ohne _true_connect/_true_socket "
            "(Version geaendert) -- Waechter kann nicht eingehaengt werden."
        )
    _allowed_list[:] = hosts
    _install(pytest_socket._true_socket, pytest_socket)
