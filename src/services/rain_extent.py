"""Nass/Trocken-Zonenbildung entlang der Reststrecke (Issue #2051 S2a).

Reine Auswertung: aus den Abfragepunkten (`points_along_remaining_route`,
`trip_segments.py`) und ihren Nowcast-Ergebnissen entstehen getrennte
Nass-Zonen mit eigener km-Lage und eigener Zeitspanne.

Zwei Entscheidungen der Spec wohnen hier (E2/E4):

* Ein TROCKENER Punkt trennt zwei Zonen, er ueberbrueckt sie nie. Der
  Punktabstand liegt an der Aufloesungsgrenze der Quelle — ein trockener
  Messpunkt ist echtes Signal. Eine Huelle ueber ihn hinweg wuerde trockene
  Strecke als nass ausweisen, also eine Aussage ueber das Wetter erfinden.
* Ein Punkt OHNE Daten (`results[i] is None`) faellt heraus: er trennt keine
  Zone und erweitert keine. Er ist eine Luecke, kein Messwert.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Sequence

from services.radar_service import (
    INTENSITY_CONVECTIVE,
    INTENSITY_HEAVY,
    INTENSITY_LIGHT,
    INTENSITY_MODERATE,
)

if TYPE_CHECKING:  # pragma: no cover — nur fuer Typpruefung
    from app.models import GPXPoint
    from services.radar_service import NowcastResult

# Issue #2051 S4 (E2): Rangfolge fuer den staerksten Intensitaetswert einer
# Zone. `INTENSITY_DRY` kommt in einer Zone strukturell nicht vor -- nur
# nasse Punkte (`onset_minutes is not None`) gehen ueberhaupt in die
# Zonenbildung ein.
_INTENSITY_RANK = {
    INTENSITY_LIGHT: 0,
    INTENSITY_MODERATE: 1,
    INTENSITY_HEAVY: 2,
    INTENSITY_CONVECTIVE: 3,
}


@dataclass(frozen=True)
class RainZone:
    """Ein zusammenhaengend nasser Abschnitt der Reststrecke.

    `km_from`/`km_to` sind die Kilometrierung der beteiligten Punkte
    (`GPXPoint.distance_from_start_km`) — NICHT die Segment-Grenzen. Die
    beiden Bedeutungen haben bewusst zwei Namen (`OnsetEvent.km_from` bleibt
    die Segment-Lage, Spec AC-7).

    `onset_minutes`/`event_end_minutes` gelten fuer DIESE Zone: fruehester
    Beginn und spaetestes Ende unter ihren eigenen Punkten, nie eine globale
    Spanne ueber mehrere Zonen (AC-6). `event_end_minutes` ist `None`, wenn
    kein Punkt der Zone ein Ende kennt.

    `intensity_label`/`source` sind additiv (Issue #2051 S4, E2): der
    staerkste Intensitaetswert bzw. die rohe Quelle des km-kleinsten Punkts
    der Zone. Beide tragen den Default `""`, bestehende S2a/S2b-Konstruktionen
    (alle mit Keyword-Argumenten) bleiben unveraendert lauffaehig.
    """
    km_from: float
    km_to: float
    onset_minutes: int
    event_end_minutes: int | None
    intensity_label: str = ""
    source: str = ""


def derive_rain_zones(
    points: "Sequence[GPXPoint]",
    results: "Sequence[NowcastResult | None]",
) -> list[RainZone]:
    """Benachbarte NASSE Punkte zu Zonen verschmelzen (E2/E4, s. Modulkopf).

    Nass heisst: das Ergebnis dieses Punktes traegt einen Beginn
    (`onset_minutes is not None`). Punkte ohne Ergebnis (`None`) werden
    uebersprungen, jeder uebrige trockene Punkt schliesst die laufende Zone.
    """
    zonen: list[RainZone] = []
    laufend: list[tuple[float, int, int | None, str, str]] = []

    def _abschliessen() -> None:
        if not laufend:
            return
        zonen.append(
            RainZone(
                km_from=min(k for k, _o, _e, _i, _s in laufend),
                km_to=max(k for k, _o, _e, _i, _s in laufend),
                onset_minutes=min(o for _k, o, _e, _i, _s in laufend),
                event_end_minutes=(
                    max(e for _k, _o, e, _i, _s in laufend if e is not None)
                    if any(e is not None for _k, _o, e, _i, _s in laufend)
                    else None
                ),
                # Issue #2051 S4 (E2): staerkster Wert unter den Punkten der
                # Zone, unabhaengig von seiner Position.
                intensity_label=max(
                    (i for _k, _o, _e, i, _s in laufend),
                    key=lambda label: _INTENSITY_RANK.get(label, -1),
                ),
                # Issue #2051 S4 (E2): rohe Quelle des ERSTEN (km-kleinsten)
                # Punkts -- `laufend` wird in Punkt-Reihenfolge (aufsteigende
                # km) befuellt, kein Mehrheitsentscheid.
                source=laufend[0][4],
            )
        )
        laufend.clear()

    for punkt, ergebnis in zip(points, results):
        if ergebnis is None:
            continue  # E4: echte Luecke — weder nass noch trocken
        onset = getattr(ergebnis, "onset_minutes", None)
        if onset is None:
            _abschliessen()  # E2: der trockene Punkt TRENNT
            continue
        laufend.append(
            (
                punkt.distance_from_start_km,
                onset,
                getattr(ergebnis, "event_end_minutes", None),
                getattr(ergebnis, "intensity_label", ""),
                getattr(ergebnis, "source", ""),
            )
        )
    _abschliessen()
    return zonen
