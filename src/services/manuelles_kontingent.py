"""Obergrenze der Abruf-Einheiten eines Handversands bzw. Antwort-Befehls.

Issue #2961, ADR-0117 Nachtrag (Prioritaet ``user_manual``): ein Versand, der
mehr Einheiten braeuchte als der Rest des Nutzerkontingents, wird VOR dem
ersten Abruf abgelehnt. Dafuer braucht ``forecast_budget.manueller_abruf``
eine sichere Obergrenze; zu viel Gebuchtes wird nach dem Versand erstattet
(Cache-Treffer zaehlen nicht).

Herleitung (gemessen, Spec): je Wegpunkt einer Etappe ein Abschnitt, je
Abschnitt ohne Cache-Treffer ein Abruf. Ein Trip-Versand ruft die Zieletappe,
die Nachtreihe und bis zu drei Folgeetappen (Trend) bzw. heute+morgen
(Abfragen) bzw. die Gewitter-Vorschau ab -- hoechstens die vier
abschnittsreichsten Etappen plus eins. Dazu kommt hoechstens eine
Gewitter-/Radar-Anreicherung je Reihe, die "jetzt" beruehrt (Zieletappe und
Nacht), und fuer ``now``/``strecke`` bis zu ``RADAR_ZONE_MAX_POINTS + 1``
Radarpunkte.

SPEC: docs/specs/modules/security_haertung_2026_11_abruf_kontingent_interaktiv.md
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from services.trip_segments import RADAR_ZONE_MAX_POINTS

if TYPE_CHECKING:
    from app.trip import Trip

#: Mindestschaetzung (Radar-Befehle ohne Etappenabruf).
MINDESTSCHAETZUNG = RADAR_ZONE_MAX_POINTS + 1


def schaetzung_trip(trip: "Trip") -> int:
    """Obergrenze fuer Handversand und Befehle eines Trips."""
    abschnitte = sorted((len(s.waypoints or []) for s in trip.stages or []), reverse=True)
    if not abschnitte:
        return MINDESTSCHAETZUNG
    vorhersage = sum(abschnitte[:4]) + 1  # vier groesste Etappen + Nacht
    anreicherung = abschnitte[0] + 1      # Reihen, die "jetzt" beruehren
    return max(vorhersage + anreicherung, MINDESTSCHAETZUNG)


def schaetzung_vergleich(anzahl_orte: int) -> int:
    """Obergrenze fuer einen Ortsvergleich: je Ort eine Reihe plus hoechstens
    eine Anreicherung."""
    return max(2 * max(int(anzahl_orte), 0), MINDESTSCHAETZUNG)
