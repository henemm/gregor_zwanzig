"""Gemeinsamer, begrenzter Abruf-Baustein (Issue #1539 S2).

``fetch_ordered(items, fn, provider=..., deadline_at=...)`` fuehrt ``fn(item)``
fuer alle Eintraege parallel aus und liefert die Ergebnisse in EINGABE-
Reihenfolge. Noch kein Produktivpfad nutzt den Baustein (das sind S3/S4).

Zusicherungen (Spec feat_1539_s1b_s2_abruf_baustein, Abschnitt E):
- modulweiter, lazy Executor (``GZ_PARALLEL_FETCH_WORKERS``, Default 8) -- nicht
  der anyio-Pool, dessen Threads durch ``def``-Handler belegt sind;
- ``BoundedSemaphore`` je Provider; der Slot umspannt die GANZE Aufgabe inklusive
  ihrer Wiederholungsversuche. Erwerb mit Frist (``acquire(timeout=Restzeit)``,
  ADR-0038): verwaiste Worker eines frueheren Aufrufs duerfen Folgeaufrufe nie
  unbegrenzt blockieren -- Ablauf => ``skipped="deadline"``;
- ``skipped="deadline"``: nicht gestartet; ``skipped="timeout"``: lief noch bei
  Fristablauf, Ergebnis verworfen (der Thread selbst laeuft weiter);
- ``copy_context()`` je Aufgabe (call_source, Senken reisen in den Worker);
- ein Aufruf aus einem Worker laeuft INLINE seriell (kein Deadlock im vollen Pool).
"""
from __future__ import annotations

import contextvars
import os
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from typing import Any, Callable, Optional

DEFAULT_WORKERS = 8
_DEFAULT_SLOTS = {"open_meteo": 3, "meteoalarm": 1, "meteo_france": 4}
_UNKNOWN_PROVIDER_SLOTS = 3

_state_lock = threading.Lock()
_executor: Optional[ThreadPoolExecutor] = None
_semaphores: dict[str, threading.BoundedSemaphore] = {}
_in_worker = threading.local()


@dataclass
class FetchOutcome:
    index: int
    item: Any
    value: Any = None
    error: BaseException | None = None
    skipped: str | None = None  # None | "deadline" | "timeout"


def _env_int(name: str, default: int) -> int:
    try:
        value = int(os.environ.get(name, ""))
    except ValueError:
        return default
    return value if value > 0 else default


def _get_executor() -> ThreadPoolExecutor:
    global _executor
    with _state_lock:
        if _executor is None:
            _executor = ThreadPoolExecutor(
                max_workers=_env_int("GZ_PARALLEL_FETCH_WORKERS", DEFAULT_WORKERS),
                thread_name_prefix="parallel-fetch",
            )
        return _executor


def _get_semaphore(provider: str) -> threading.BoundedSemaphore:
    with _state_lock:
        sem = _semaphores.get(provider)
        if sem is None:
            default = _DEFAULT_SLOTS.get(provider, _UNKNOWN_PROVIDER_SLOTS)
            slots = _env_int(f"GZ_PARALLEL_FETCH_SLOTS_{provider.upper()}", default)
            sem = _semaphores[provider] = threading.BoundedSemaphore(slots)
        return sem


def _reset_for_tests() -> None:
    """Verwirft Executor und Semaphoren, damit Tests neue Env-Werte setzen koennen."""
    global _executor
    with _state_lock:
        executor, _executor = _executor, None
        _semaphores.clear()
    if executor is not None:
        executor.shutdown(wait=False, cancel_futures=True)


def _run_task(fn: Callable[[Any], Any], item: Any, releases: list) -> tuple:
    """Laeuft im Worker (innerhalb ``ctx.run``). Gibt die Slots im ``finally`` frei."""
    _in_worker.active = True
    try:
        return ("ok", fn(item))
    except BaseException as exc:  # noqa: BLE001 -- Teilausfall steht im Outcome
        return ("err", exc)
    finally:
        _in_worker.active = False
        for sem in releases:
            sem.release()


def _acquire_slots(sems: list, deadline_at: float) -> Optional[list]:
    """Erwirbt alle Semaphoren mit Frist; ``None`` bei Fristablauf (nichts gehalten)."""
    held: list = []
    for sem in sems:
        remaining = deadline_at - time.monotonic()
        if remaining <= 0 or not sem.acquire(timeout=remaining):
            for h in held:
                h.release()
            return None
        held.append(sem)
    return held


def _fetch_inline(items: list, fn, deadline_at: float) -> list[FetchOutcome]:
    outcomes = [FetchOutcome(index=i, item=item) for i, item in enumerate(items)]
    for out in outcomes:
        if time.monotonic() >= deadline_at:
            out.skipped = "deadline"
            continue
        try:
            out.value = fn(out.item)
        except BaseException as exc:  # noqa: BLE001
            out.error = exc
            continue
        if time.monotonic() > deadline_at:
            out.value, out.skipped = None, "timeout"
    return outcomes


def fetch_ordered(
    items,
    fn: Callable[[Any], Any],
    *,
    provider: str,
    deadline_at: float,
    max_parallel: Optional[int] = None,
) -> list[FetchOutcome]:
    """Siehe Moduldoc. ``deadline_at`` ist ein absoluter ``time.monotonic()``-Wert."""
    items = list(items)
    if getattr(_in_worker, "active", False):
        return _fetch_inline(items, fn, deadline_at)

    outcomes = [FetchOutcome(index=i, item=item) for i, item in enumerate(items)]
    sems = [_get_semaphore(provider)]
    if max_parallel is not None and max_parallel > 0:
        sems.insert(0, threading.BoundedSemaphore(max_parallel))
    executor = _get_executor()
    pending: list[tuple[FetchOutcome, Future, list]] = []
    for out in outcomes:
        held = _acquire_slots(sems, deadline_at)
        if held is None:
            out.skipped = "deadline"
            continue
        ctx = contextvars.copy_context()
        fut = executor.submit(ctx.run, _run_task, fn, out.item, held)
        pending.append((out, fut, held))

    wait([f for _, f, _ in pending], timeout=max(deadline_at - time.monotonic(), 0.0))
    for out, fut, held in pending:
        _collect(out, fut, held)
    return outcomes


def _collect(out: FetchOutcome, fut: Future, held: list) -> None:
    if fut.done() and not fut.cancelled():
        kind, payload = fut.result()
        if kind == "ok":
            out.value = payload
        else:
            out.error = payload
    elif fut.cancel():
        # Nie gestartet (Executor ausgelastet): Slots gibt der Aufrufer frei.
        for sem in held:
            sem.release()
        out.skipped = "deadline"
    else:
        out.skipped = "timeout"  # laeuft noch; Ergebnis wird verworfen
