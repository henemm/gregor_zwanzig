"""Geteilte Zeitbudget-Bausteine fuer Provider-HTTP-Aufrufe (#2302 Scheibe A).

SPEC: docs/specs/modules/fix_2302_s1_provider_zeitbudget_baustein.md

Fasst die drei Bestandteile des unter #1448 S3 in `openmeteo.py` gebauten
Musters zusammen — `before`-Hook (Frist fixieren), zeitbasierte
Stop-Bedingung, Timeout-Deckelung am Kopf des Versuchs — damit mehrere
Provider dieselbe Mechanik nutzen, ohne sie zu kopieren.

Warum hier und nicht in `base.py`: `base.py` ist bewusst frei von
`httpx`/`tenacity` (Registry + Fehlerklassen, `base.py:7-16`).

Warum Fabriken/Funktionen und KEIN Modul-Level-`Retrying`-Objekt: jeder
Provider baut seinen `@retry(...)` weiter selbst. Teilten sich zwei Provider
ein `Retrying`, wirkte eine Aenderung an der Retry-Konfiguration des einen
still auf den anderen (Spec AC-6).

Warum der Hook ueber den METHODENNAMEN aufloest und nie ueber den Wert: die
Fristdauer steht als Modul-Global im jeweiligen Provider-Modul
(`FETCH_DEADLINE_SECONDS`) und wird von Tests zur Laufzeit gepatcht. Eine
Closure, die den Wert beim Dekorieren einfriert, saehe den Patch nie
(Spec AC-5).
"""
from __future__ import annotations

import time
from typing import Callable, Optional

from providers.base import ProviderRequestError


def make_deadline_before_hook(deadline_attr: str) -> Callable[[object], None]:
    """Fabrik fuer einen tenacity-``before``-Hook, der ``deadline_at`` fixiert.

    Args:
        deadline_attr: Name der providereigenen Accessor-METHODE, die die
            Fristdauer in Sekunden liefert (z. B. ``_fetch_deadline_seconds``).
            Aufgeloest wird sie erst beim Feuern des Hooks, also zur
            Aufrufzeit — nur so wirkt ein Laufzeit-Patch des Modul-Globals.

    Der ``if ... is None``-Waechter ist der Kern: ``before`` feuert vor JEDEM
    Versuch und ``retry_state.kwargs`` ist dieselbe dict-Instanz ueber die
    ganze Kette. Wuerde die Ersatzfrist bei jedem Versuch neu gebildet, waere
    sie eine rollende Frist statt einer festen Obergrenze — also wirkungslos.

    Kein ``getattr``-Default: fehlt der Accessor am Provider, soll es knallen,
    nicht still ``None`` liefern und die Absicherung stumm abschalten.
    """

    def _resolve_deadline(retry_state) -> None:
        if retry_state.kwargs.get("deadline_at") is None:
            provider = retry_state.args[0]  # dekorierte Methode: args[0] ist self
            dauer = getattr(provider, deadline_attr)()
            retry_state.kwargs["deadline_at"] = time.monotonic() + dauer

    return _resolve_deadline


def stop_at_deadline(retry_state) -> bool:
    """Zeitbasierte tenacity-Stop-Bedingung, per ``|`` mit
    ``stop_after_attempt(...)`` zu ``stop_any`` kombinierbar.

    Generisch, keine Fabrik noetig: liest nur die von
    ``make_deadline_before_hook`` fixierte ``deadline_at`` gegen
    ``time.monotonic()``. Versuchszahl UND verstrichene Zeit begrenzen die
    Kette damit gemeinsam — inklusive der Wartepausen, denn tenacity wertet
    ``stop`` VOR dem Schlafen aus.
    """
    deadline_at = retry_state.kwargs.get("deadline_at")
    return deadline_at is not None and time.monotonic() >= deadline_at


def capped_timeout_or_raise(
    *,
    provider_name: str,
    base_timeout: float,
    deadline_at: Optional[float],
    budget_label: str,
    budget_seconds: float,
) -> float:
    """Kopf-Check EINES Versuchs: Restzeit pruefen und den HTTP-Timeout deckeln.

    Args:
        provider_name: Provider-Kennung fuer die ``ProviderRequestError``.
        base_timeout: Der regulaere Timeout des Providers (Modul-Global
            ``TIMEOUT``) — bleibt die Obergrenze.
        deadline_at: Absolute monotone Frist. ``None`` heisst "keine Frist"
            und liefert ``base_timeout`` unveraendert zurueck.
        budget_label/budget_seconds: Bausteine des Fehlertexts, vom Aufrufer
            gestellt, damit jede Datei ihren eigenen Wortlaut behaelt.

    Returns:
        Der fuer diesen Versuch zu verwendende Timeout:
        ``min(base_timeout, Restzeit)``.

    Raises:
        ProviderRequestError: Wenn die Frist bereits abgelaufen ist.
    """
    if deadline_at is None:
        return base_timeout
    restzeit = deadline_at - time.monotonic()
    if restzeit <= 0:
        raise ProviderRequestError(
            provider_name,
            f"Zeitbudget ({budget_label}={budget_seconds:.0f}s) "
            "vor diesem Versuch bereits aufgebraucht",
        )
    return min(base_timeout, restzeit)
