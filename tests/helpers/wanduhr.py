"""Issue #2096: die Ankerbestimmung des Uhr-Schalters — EINE Stelle.

Der Schalter selbst ist die Session-Fixture ``_gestellte_wanduhr`` in
``tests/conftest.py``; sein Selbsttest steht in
``tests/tdd/test_gestellte_wanduhr_schalter.py``. Beide brauchen dieselbe
Umrechnung ``Roh-Wert -> Ankerzeitpunkt``. Sie liegt deshalb hier und nicht
zweimal dort: ein Selbsttest, der den Anker NACHRECHNET statt ihn aus
derselben Quelle zu beziehen, prueft am Ende seine eigene Kopie und wuerde
eine abweichende Fixture nicht bemerken.
"""
from __future__ import annotations

import os
from datetime import datetime, time, timezone

ENV_NAME = "GZ_TEST_WALL_CLOCK_UTC"


def roh_wert() -> str:
    """Der gesetzte Roh-Wert oder ``""`` (nicht gesetzt)."""
    return os.environ.get(ENV_NAME, "").strip()


def anker_aus(roh: str) -> datetime:
    """Der Zeitpunkt, auf den der Schalter die Uhr stellt.

    Zwei Formen: ``HH:MM`` meint diese Uhrzeit UTC am heutigen Kalendertag,
    ein vollstaendiger ISO-Zeitstempel wird unveraendert uebernommen.
    """
    if "-" in roh:
        return datetime.fromisoformat(roh)
    stunde, _, minute = roh.partition(":")
    return datetime.combine(
        datetime.now(timezone.utc).date(),
        time(int(stunde), int(minute or 0)),
        tzinfo=timezone.utc,
    )
