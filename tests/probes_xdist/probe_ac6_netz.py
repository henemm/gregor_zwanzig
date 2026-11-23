"""Sonde AC-6 (#3209): Egress-Sperre (pytest-socket) und Loopback-Port-Guard
(#1755) muessen in JEDEM xdist-Worker greifen. Jede Beobachtung wird mit der
Worker-Kennung protokolliert; die Zusicherung macht der aeussere Test."""
from __future__ import annotations

import socket

from _probe_util import protokolliere


def _ist_blockiert(exc: BaseException) -> bool:
    return "Blocked" in type(exc).__name__


def test_probe_ac6_egress_ist_blockiert():
    try:
        socket.create_connection(("1.1.1.1", 80), timeout=2).close()
        ergebnis = "offen"
    except BaseException as exc:  # noqa: BLE001 -- Typ wird protokolliert
        ergebnis = "blockiert" if _ist_blockiert(exc) else f"anders:{type(exc).__name__}"
    protokolliere("ac6_egress", ergebnis=ergebnis)


def test_probe_ac6_fremder_loopback_port_ist_blockiert():
    # Port 9 (discard) bindet kein Test selbst -> fremder Loopback-Port.
    try:
        socket.create_connection(("127.0.0.1", 9), timeout=2).close()
        ergebnis = "offen"
    except BaseException as exc:  # noqa: BLE001
        ergebnis = "blockiert" if _ist_blockiert(exc) else f"anders:{type(exc).__name__}"
    protokolliere("ac6_fremd", ergebnis=ergebnis)


def test_probe_ac6_eigener_port_bleibt_erlaubt():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]
    try:
        client = socket.create_connection(("127.0.0.1", port), timeout=2)
        client.close()
        ergebnis = "erlaubt"
    except BaseException as exc:  # noqa: BLE001
        ergebnis = f"anders:{type(exc).__name__}"
    finally:
        server.close()
    protokolliere("ac6_eigen", ergebnis=ergebnis)
