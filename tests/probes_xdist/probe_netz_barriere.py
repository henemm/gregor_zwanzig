"""Sonde #3278 (AC-4): alle drei Netz-Pruefungen in BEIDEN Workern.

Unter ``--dist loadgroup`` laeuft jeder Test nur EINMAL. Deshalb wartet jeder
der zwei parametrisierten Aufrufe zuerst in einer Barriere, bis sich zwei
verschiedene Worker eingetragen haben: solange ein Worker wartet, muss der
zweite Aufruf auf dem anderen Worker laufen. Kommt er nicht, endet die Sonde
nach dem Zeitlimit rot (kein Haengen)."""
from __future__ import annotations

import time

import probe_ac6_netz as netz
import pytest
from _probe_util import probe_dir, protokolliere, worker_id

BARRIERE_SEKUNDEN = 12  # unter dem globalen timeout = 30


def _warte_auf_zwei_worker() -> None:
    (probe_dir() / f"barriere-{worker_id()}").touch()
    ende = time.monotonic() + BARRIERE_SEKUNDEN
    while True:
        da = sorted(p.name for p in probe_dir().glob("barriere-*"))
        if len(da) >= 2:
            return
        if time.monotonic() >= ende:
            protokolliere("barriere_abgelaufen", da=da)
            pytest.fail(f"Barriere abgelaufen: nur {da} statt zwei Worker")
        time.sleep(0.05)


@pytest.mark.parametrize("aufruf", [0, 1])
def test_probe_netz_in_beiden_workern(aufruf):
    _warte_auf_zwei_worker()
    netz.test_probe_ac6_egress_ist_blockiert()
    netz.test_probe_ac6_fremder_loopback_port_ist_blockiert()
    netz.test_probe_ac6_eigener_port_bleibt_erlaubt()
