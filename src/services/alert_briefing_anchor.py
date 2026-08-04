"""Vergleichs-Bezugspunkt (Δ-Anker) und Melde-Gedächtnis — EIN geteilter
Baustein für Trip UND Ortsvergleich (Issue #1467 Scheibe S2, AG5).

PO wörtlich: „Beide Dienste sollen sich natürlich gleich verhalten. Verwende
zwingend den gleichen Code."

Warum ein gemeinsamer Baustein und nicht zwei `if`-Zweige: Δ-Anker und
Melde-Gedächtnis MÜSSEN immer zusammen und unter DERSELBEN Bedingung behandelt
werden. Ein frischer Anker ohne Gedächtnis-Reset ist die gefährlichste
Kombination — `DeviationAlertEngine._filter_against_alert_state`
(`app/deviation_alert_engine.py`) vergleicht gegen den ABSOLUTEN
`last_reported_value` des Gedächtnisses; steht dort noch der alte Wert, während
der Anker schon der neue ist, verschwinden Änderungen gegenüber dem — jetzt
überschriebenen — Vergleichspunkt für immer (stiller ausbleibender Alarm).

Reihenfolge: erst Anker schreiben, dann Gedächtnis leeren.

`AlertStateService.reset()` schont `official_alert:`-Schlüssel bereits selbst
(#1460 P2) — hier wird nichts nachgebaut.

SPEC: docs/specs/modules/rework_1467_s2_aenderungsalarm.md, Abschnitt „AG5",
AC-14..AC-19 und AC-27.
"""
from __future__ import annotations

import logging
from typing import Callable, Iterable, Optional

logger = logging.getLogger("alert_briefing_anchor")


def write_anchor_and_reset_memory(
    *,
    user_id: str,
    entity_ids: Iterable[str],
    write_anchor: Callable[[], None],
    on_demand: bool = False,
    reset_memory: Optional[Callable[[str], None]] = None,
) -> None:
    """Schreibt den Δ-Anker und leert danach das Melde-Gedächtnis.

    Args:
        user_id: echte Nutzer-Kennung (Mandantentrennung, nie `"default"`).
        entity_ids: ALLE betroffenen Kennungen — Trip: `[trip.id]`;
            Ortsvergleich: `[f"{preset_id}:{loc.id}" for loc in locations]`
            über alle Orte des Presets, nicht nur die getriggerten (Risiko R3:
            ein still übersprungener Ort behielte sein altes Gedächtnis und
            würde nach dem nächsten Briefing nie wieder melden).
        write_anchor: schreibt den Δ-Anker. Die Fehlerbehandlung liegt beim
            Aufrufer — beide Bestandspfade sind dort bereits fail-soft.
        on_demand: True ⇒ es passiert NICHTS, weder Anker noch Reset
            (Ad-hoc-Abruf/Handversand ist gegenüber beiden Zuständen
            read-only, Issue #1007).
        reset_memory: optionaler Haken für Aufrufer, die den Reset über eine
            eigene, überschreibbare Naht führen — genau ein Fall: der Trip mit
            `TripReportSchedulerService._reset_alert_state_after_briefing`
            (seit #816 (B) Bestandsverhalten, das AC-27 unverändert lassen
            muss). Diese Naht delegiert ihrerseits an `reset_alert_memory()`,
            es gibt also nur EINE Reset-Fassung. Ohne Angabe wird
            `reset_alert_memory()` direkt gerufen.
    """
    if on_demand:
        return

    write_anchor()

    for entity_id in entity_ids:
        if reset_memory is not None:
            reset_memory(entity_id)
        else:
            reset_alert_memory(user_id=user_id, entity_id=entity_id)


def reset_alert_memory(*, user_id: str, entity_id: str) -> None:
    """DER Reset-Weg für das Melde-Gedächtnis — Trip UND Ortsvergleich.

    Einzige Fassung im Repo (Issue #1467 S2 AG5, PO: „Verwende zwingend den
    gleichen Code"). `TripReportSchedulerService._reset_alert_state_after_briefing`
    ist nur noch eine überschreibbare Naht, die hierher delegiert.

    Fail-soft je Kennung: ein Fehler bei EINER Kennung darf die übrigen nicht
    verhindern (Risiko R3 — ein still übersprungener Ort behielte sein altes
    Gedächtnis und würde nach dem nächsten Briefing nie wieder melden). Die
    Warnung nennt Kennung UND Ausnahmetyp, damit ein echter Programmfehler
    auffindbar bleibt, statt still als „nichts zu tun" durchzugehen.
    """
    from services.alert_state import AlertStateService

    try:
        AlertStateService(user_id=user_id).reset(entity_id)
    except Exception as e:
        logger.warning(
            "Failed to reset alert_state for %s: %s: %s", entity_id, type(e).__name__, e
        )
