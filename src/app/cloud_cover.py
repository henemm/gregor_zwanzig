"""Wirksame Bewoelkung -- die EINE Regel (Issue #3106, ADR-0122).

Dichte tiefe und mittelhohe Wolken zaehlen voll, der darueber hinausgehende
Anteil der Gesamtbewoelkung (duenne hohe Wolken, Cirrus) zaehlt mit
``HOHE_WOLKEN_GEWICHT``. Ab ``HOCHLAGE_SCHWELLE_M`` Standorthoehe liegen tiefe
Wolken unter dem Standort und zaehlen nicht. Fehlen die Schichten, gilt der
Gesamtwert des Modells.

Angewendet wird die Regel genau einmal je Abruf am Ausgang der Normalisierung
(``normalisiere_bewoelkung``); kein Leser rechnet die Bewoelkung erneut um.
Reine Domaenenlogik, ohne I/O.
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.models import NormalizedTimeseries

HOHE_WOLKEN_GEWICHT = 0.5
HOCHLAGE_SCHWELLE_M = 2500


def wirksame_bewoelkung(
    gesamt: Optional[int],
    tief: Optional[int],
    mittel: Optional[int],
    hoch: Optional[int],
    hoehe_m: Optional[float],
) -> Optional[int]:
    """Wirksame Bewoelkung in % (0..100) einer Stunde; ``None`` ohne Daten."""
    if mittel is None or hoch is None:
        return gesamt
    tief_zaehlt = hoehe_m is None or hoehe_m < HOCHLAGE_SCHWELLE_M
    if tief_zaehlt and tief is None:
        return gesamt
    dicht = max(tief, mittel) if tief_zaehlt else mittel
    if tief_zaehlt and gesamt is not None:
        bezug = gesamt
    else:
        bezug = max(mittel, hoch)
    wirksam = dicht + max(0, bezug - dicht) * HOHE_WOLKEN_GEWICHT
    return min(100, max(0, math.floor(wirksam + 0.5)))


def normalisiere_bewoelkung(
    timeseries: "NormalizedTimeseries", hoehe_m: Optional[float],
) -> "NormalizedTimeseries":
    """Setzt je Datenpunkt ``cloud_total_model_pct`` (Modellwert) und
    ueberschreibt ``cloud_total_pct`` mit der wirksamen Bewoelkung (in-place).

    Idempotent: ist ``cloud_total_model_pct`` schon gesetzt, wird von dort
    gerechnet. Punkte ohne Modell-Gesamtwert bleiben unberuehrt -- ein zweiter
    Lauf koennte sie sonst nicht von einem ersten unterscheiden."""
    for dp in timeseries.data:
        modell = (
            dp.cloud_total_model_pct
            if dp.cloud_total_model_pct is not None
            else dp.cloud_total_pct
        )
        if modell is None:
            continue
        dp.cloud_total_model_pct = modell
        dp.cloud_total_pct = wirksame_bewoelkung(
            modell, dp.cloud_low_pct, dp.cloud_mid_pct, dp.cloud_high_pct, hoehe_m,
        )
    return timeseries
