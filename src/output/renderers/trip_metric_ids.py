"""Kanonischer Resolver: Trip-Metrik-Konfiguration -> aktive Metrik-IDs.

Trip-Gegenstueck zu ``compare_hourly_metric_ids.py::resolve_hourly_metrics()``
(#1366) -- eine Funktion, mehrere Aufrufer (html.py, plain.py, compact.py),
keine pro-Renderer-Zweitentscheidung (Trip/Compare-Teilungsinvariante,
CLAUDE.md).

Spec: docs/specs/modules/trip_empty_metric_selection.md

Anders als beim Ortsvergleich speichert der Trip die Auswahl nicht als Liste
aktiver Schluessel, sondern als vollstaendige Metrik-Liste mit
``enabled``-Flags. "Leer" entsteht auf zwei Wegen, die ohne das
``altbestand``-Flag ununterscheidbar zusammenfallen:

- Fall A (Altbestand): ``metrics`` fehlt ganz / ist leer -> bisheriges
  Verhalten (Standard-Siebener-Satz).
- Fall B (bewusste Leerauswahl): ``metrics`` hat Eintraege, alle mit
  ``enabled=False`` -> ``[]`` bleibt ``[]``.
"""
from __future__ import annotations

from typing import Sequence

from app.metric_catalog import get_all_metrics

# Issue #1552: aus dem Register abgeleitet (trip_default_rank), statt als
# Literal gefuehrt -- eine Quelle fuer "was ist Trip-Anlege-Standard"
# (Register + Frontend-Vorbelegung lesen denselben Marker).
DEFAULT_TRIP_METRIC_IDS: tuple[str, ...] = tuple(
    m.id for m in sorted(
        (m for m in get_all_metrics() if m.trip_default_rank is not None),
        key=lambda m: m.trip_default_rank,
    )
)


def resolve_trip_active_metrics(
    metrics: Sequence, *, altbestand: bool = True,
) -> list[str]:
    """Liefert die aktiven Metrik-IDs fuer den Trip-Metriken-Ueberblick.

    ``metrics``: Liste von ``MetricConfig``-aehnlichen Objekten mit
    ``metric_id``/``enabled``-Attributen (die kollabierte oder rohe
    ``dc.metrics``-Liste).

    ``altbestand=True`` (Default, rueckwaertskompatibel fuer Direktaufrufer,
    Invariante 5): ist das Ergebnis leer, wird auf ``DEFAULT_TRIP_METRIC_IDS``
    zurueckgefallen (Fall A). ``altbestand=False`` liefert eine bewusst leere
    Auswahl unveraendert als ``[]`` (Fall B).

    Reihenfolge = Erstvorkommen in ``metrics`` (Invariante 4, kein
    Sortier-Eingriff).
    """
    active = [mc.metric_id for mc in metrics if mc.enabled]
    if not active and altbestand:
        return list(DEFAULT_TRIP_METRIC_IDS)
    return active


__all__ = ["resolve_trip_active_metrics", "DEFAULT_TRIP_METRIC_IDS"]
