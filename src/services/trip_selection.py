"""Geteilter Baustein: "welche Tour meint eine Nachricht ohne Trip-Namen?"

Verschoben aus ``services.inbound_telegram_reader._find_active_trip``
(Issue #2184, Epic #2133 Scheibe S4) — bit-identisches Verhalten, nur ohne
``self.`` und ohne das Laden der Touren. Vorbild und Praezedenz:
``services.trip_day`` (#1470).

Der Schnitt liegt bewusst NACH dem Laden: ``load_all_trips(user_id)`` bleibt im
jeweiligen Reader, weil vier bestehende Testdateien
``services.inbound_telegram_reader.load_all_trips`` auf dem Modulpfad patchen —
wanderte der Aufruf mit hierher, griffen alle vier Patches ins Leere und liefen
still gegen echte Daten statt gegen Fixtures.

SPEC: docs/specs/modules/feat_2184_s4_premium_sms_kommandoverarbeiter.md
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from services.trip_day import trip_local_today

if TYPE_CHECKING:
    from app.trip import Trip


def pick_active_trip(trips: list["Trip"], now_utc: datetime) -> "Trip | None":
    """Aktive Tour = erste Tour mit Datum-Overlap, sonst frueheste zukuenftige.

    Issue #1727 S5a: "heute" ist der ORTStag DIESER Tour (ADR-0044), nicht das
    Datum der Serveruhr. Der Vergleichstag wird deshalb IN der Schleife je Tour
    bestimmt — ein einziger, aus nur einer Tour abgeleiteter Tag waehlt an der
    Tourgrenze die bereits abgelaufene Tour. Auch der Zukunfts-Rueckfall
    rechnet je Tour.

    Args:
        trips: Touren des Mandanten, bereits geladen.
        now_utc: Zeitpunkt der eingehenden Nachricht. Pflichtparameter — ein
            Default auf die Systemuhr wuerde genau die Umgebungsuhr wieder
            einfuehren, die ADR-0051 Regel 3 verbietet.
    """
    if not trips:
        return None

    # 1. Overlap: stage[0].date <= Ortstag DIESER Tour <= stage[-1].date
    for trip in trips:
        if not trip.stages:
            continue
        today = trip_local_today(trip, now_utc)
        if trip.stages[0].date <= today <= trip.stages[-1].date:
            return trip

    # 2. Fallback: fruehester zukuenftiger Trip — "zukuenftig" ebenfalls am
    #    Ortstag DIESER Tour gemessen, nicht an einem gemeinsamen Wert.
    future = [
        t for t in trips
        if t.stages and t.stages[0].date > trip_local_today(t, now_utc)
    ]
    if future:
        return min(future, key=lambda t: t.stages[0].date)

    return None
