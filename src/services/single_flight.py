"""Single-flight: je Schluessel fuehrt genau ein Aufrufer (Leader) den Abruf aus.

Issue #1539 (S1b/S2). Wer waehrend eines laufenden Flugs mit demselben Schluessel
kommt, wartet hoechstens ``wait_timeout_s`` auf das Ergebnis des Leaders und holt
danach selbst ab (fail-open, der Aufrufer entscheidet).

Zusicherungen:
- ``self._lock`` schuetzt nur das Anlegen/Entfernen des Flugs, NIE ``leader_fn``.
- ``run()`` wirft nie: eine Ausnahme des Leaders steht in ``FlightResult.error``
  (bei Leader und allen Wartenden dasselbe Objekt).
- Reentranz: derselbe Thread mit demselben Schluessel laeuft ohne Warten durch.
- Die Hilfe kennt keine Nutzerdaten; sie transportiert nur, was der Leader liefert.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any, Callable, Hashable


@dataclass
class FlightResult:
    value: Any = None
    error: BaseException | None = None
    is_leader: bool = False
    timed_out: bool = False


class _Flight:
    def __init__(self) -> None:
        self.done = threading.Event()
        self.owner = threading.get_ident()
        self.value: Any = None
        self.error: BaseException | None = None


class SingleFlight:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._flights: dict[Hashable, _Flight] = {}

    def run(
        self, key: Hashable, leader_fn: Callable[[], Any], *, wait_timeout_s: float
    ) -> FlightResult:
        with self._lock:
            flight = self._flights.get(key)
            is_leader = flight is None
            if is_leader:
                flight = self._flights[key] = _Flight()
        if is_leader:
            return self._lead(key, flight, leader_fn)
        if flight.owner == threading.get_ident():
            return self._run_reentrant(leader_fn)
        if not flight.done.wait(timeout=max(wait_timeout_s, 0.0)):
            return FlightResult(timed_out=True)
        return FlightResult(value=flight.value, error=flight.error)

    def _lead(self, key: Hashable, flight: _Flight, leader_fn) -> FlightResult:
        try:
            flight.value = leader_fn()
        except BaseException as exc:  # noqa: BLE001 -- wandert ins Ergebnis
            flight.error = exc
        finally:
            with self._lock:
                self._flights.pop(key, None)
            flight.done.set()
        return FlightResult(value=flight.value, error=flight.error, is_leader=True)

    @staticmethod
    def _run_reentrant(leader_fn) -> FlightResult:
        try:
            return FlightResult(value=leader_fn(), is_leader=True)
        except BaseException as exc:  # noqa: BLE001
            return FlightResult(error=exc, is_leader=True)
