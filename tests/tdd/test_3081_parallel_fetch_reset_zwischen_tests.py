"""TDD RED -- Bugfix #3081 (Teil von #1196): Kern-Tests stabilisieren.

SPEC: docs/specs/modules/fix_3081_flaky_kerntests.md (AC-5)

AC-5: Der prozessweite Parallelabruf (``parallel_fetch``: Executor mit 8
Workern, Semaphor je Provider) wird zwischen Tests nicht zurueckgesetzt.
Ein nachlaufender Worker eines frueheren Tests haelt so einen Slot des
Semaphors ``official_alerts`` ueber das Testende hinaus und kann den
Warn-Abruf eines Folgetests verdraengen. Erwartet: eine autouse-Fixture in
``tests/conftest.py`` setzt nach JEDEM Test ``_reset_for_tests()`` ab.

Aufbau (Kern-Schicht, echt, kein Mock): Der erste Test startet ueber den
echten ``fetch_ordered`` eine Aufgabe, die bis nach dem Testende blockiert
(Frist sehr kurz => ``skipped="timeout"``, der Worker laeuft weiter und haelt
seinen Slot). Der zweite Test laeuft unmittelbar danach (Definitionsreihen-
folge in derselben Datei) und erwartet einen frischen Parallelabruf: kein
Executor, alle Slots von ``official_alerts`` frei.

Ohne Reset-Fixture: der zweite Test sieht den alten Executor und einen
belegten Slot => ROT.
"""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from services import parallel_fetch  # noqa: E402

_PROVIDER = "official_alerts"
_SLOTS = 3  # Default fuer unbekannte Provider (_UNKNOWN_PROVIDER_SLOTS)

# Gibt den nachlaufenden Worker frei; der zweite Test setzt es am Ende.
_FREIGABE = threading.Event()


def _blockiert_bis_freigabe(_item):
    _FREIGABE.wait(timeout=20.0)
    return "spaet"


def test_ac5_a_nachlaufender_worker_haelt_slot_ueber_das_testende():
    """Vorbedingung herstellen: ein Worker belegt nach Testende noch einen Slot."""
    _FREIGABE.clear()
    ergebnisse = parallel_fetch.fetch_ordered(
        ["warnabruf"],
        _blockiert_bis_freigabe,
        provider=_PROVIDER,
        deadline_at=time.monotonic() + 0.2,
    )
    assert ergebnisse[0].skipped == "timeout", (
        "Testaufbau: die Aufgabe muss noch laufen, wenn die Frist ablaeuft "
        f"(war skipped={ergebnisse[0].skipped!r})"
    )
    assert parallel_fetch._executor is not None, "Testaufbau: Executor angelegt"


def test_ac5_b_folgetest_sieht_frischen_parallelabruf():
    """AC-5: Nach dem vorigen Test sind Executor und Semaphoren zurueckgesetzt."""
    try:
        executor_alt = parallel_fetch._executor
        sem = parallel_fetch._get_semaphore(_PROVIDER)
        frei = 0
        for _ in range(_SLOTS):
            if sem.acquire(blocking=False):
                frei += 1
        for _ in range(frei):
            sem.release()

        assert executor_alt is None, (
            "Der Executor des vorigen Tests lebt noch: der Parallelabruf wird "
            "zwischen Tests nicht zurueckgesetzt (autouse-Fixture fehlt)"
        )
        assert frei == _SLOTS, (
            f"Nur {frei} von {_SLOTS} Slots von '{_PROVIDER}' frei: ein Worker des "
            "vorigen Tests haelt noch einen Slot (autouse-Fixture fehlt)"
        )
    finally:
        _FREIGABE.set()  # nachlaufenden Worker beenden
