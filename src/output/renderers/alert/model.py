"""Kanonisches Alert-Datenmodell + reine Helfer (Issue #917, ADR-0011).

`AlertMessage` ist kanonisch: das reservierte `source`-Feld erlaubt dem
Radar-Pfad (#919) ohne Modell-Bruch zu konvergieren.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AlertEvent:
    """Ein einzelnes Abweichungs-Ereignis (Deviation-Art in #917)."""
    metric_id: str           # catalog metric_id (NICHT summary_field)
    value_from: float
    value_to: float
    threshold: float
    cmp: str                 # "über" | "unter" — aus Katalog je metric_id
    occurred_at: str | None  # "HH:MM"
    km_from: float
    km_to: float


@dataclass(frozen=True)
class OnsetEvent:
    """Ein Radar-Onset-Ereignis (Niederschlag oder Gewitter im Anmarsch)."""
    onset_minutes: int
    onset_time: str           # "HH:MM"
    km_from: float
    km_to: float
    is_convective: bool
    intensity_label: str
    source_label: str
    briefing_context: str | None = None  # Issue #952: 4. Datenblock-Zeile (E-Mail only)


@dataclass(frozen=True)
class AlertMessage:
    """Kanonische Alert-Nachricht über alle vier Kanäle."""
    trip_short: str
    stand_at: str                              # "HH:MM"
    events: tuple[AlertEvent | OnsetEvent, ...]  # ≥1
    source: str | None = None                  # Radar (#919): source != None → Onset-Zweig; Deviation → None
    cooldown_display: str | None = None        # Radar (#919): Pflichttext Cooldown-Hinweis


def direction(e: AlertEvent) -> str:
    return "up" if e.value_to >= e.value_from else "down"


def arrow(e: AlertEvent) -> str:
    return "↑" if direction(e) == "up" else "↓"


def delta_pct(e: AlertEvent) -> int | None:
    """Prozentuale Änderung. value_from==0 → definierter Sonderfall (None)."""
    if e.value_from == 0:
        return None
    return round((e.value_to - e.value_from) / e.value_from * 100)


def over_thr(e: AlertEvent) -> bool:
    # Issue #958: `threshold` ist IMMER die Δ-Auslöseschwelle (nie ein
    # Absolutwert-Referenzwert). Ein Event liegt „über Schwelle", wenn der
    # BETRAG der Änderung die Schwelle erreicht — unabhängig von `cmp` und
    # von der Richtung (siehe WeatherChange.threshold-Docstring, ADR-0013).
    return abs(e.value_to - e.value_from) >= e.threshold


def side_label(e: AlertEvent) -> str:
    return "über" if over_thr(e) else "unter"


def severity(e: AlertEvent) -> float:
    """Relative Schwellüberschreitung. threshold==0 → Sonderfall (kein Crash).

    Bei threshold==0 fehlt ein sinnvoller Schwell-Nenner; die Distanz wird daher
    durch die Werte-Magnitude normiert, damit ein 0-Schwellen-Ereignis ein echtes
    Über-Schwelle-Ereignis nicht künstlich überholt.
    """
    if e.threshold == 0:
        scale = max(abs(e.value_to), abs(e.value_from), 1.0)
        dist = (e.threshold - e.value_to) if e.cmp == "unter" else (e.value_to - e.threshold)
        return dist / scale
    if e.cmp == "über":
        return (e.value_to - e.threshold) / e.threshold
    return (e.threshold - e.value_to) / e.threshold


def km_span(events: tuple) -> tuple[float, float]:
    return (min(e.km_from for e in events), max(e.km_to for e in events))
