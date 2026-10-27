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
    """Der Zeitpunkt, auf den der Schalter die Uhr stellt — IMMER UTC-behaftet.

    Zwei Formen:

    * ``HH:MM`` (auch ``HH``) meint diese Uhrzeit UTC am heutigen
      Kalendertag — die Form der vier Nachweis-Laeufe.
    * ein ISO-Zeitstempel meint genau diesen Zeitpunkt. Traegt er einen
      Versatz, wird er auf UTC umgerechnet (derselbe Augenblick, andere
      Schreibweise); traegt er keinen, gilt er als UTC.

    Warum die Vereinheitlichung: ein naiver Rueckgabewert waere von
    freezegun als ORTSZEIT verstanden worden. Auf einem Server in einer
    anderen Zone haette der Schalter die Uhr dann still um den Zonenversatz
    daneben gestellt — und alle vier Nachweis-Laeufe haetten weiterhin gruen
    ausgesehen. Der Name der Variablen (``..._UTC``) ist damit auch das
    tatsaechliche Verhalten.

    Unbrauchbare Eingaben (leer, Unsinn, ``"25:00"``, kaputter ISO-Stempel)
    loesen ``ValueError`` aus. Bewusst laut: ein Schalter, der bei Unsinn
    stillschweigend irgendeinen Zeitpunkt nimmt, stellt die Uhr falsch und
    laesst den Lauf trotzdem gruen aussehen.
    """
    if "-" in roh:
        zeitpunkt = datetime.fromisoformat(roh)
        if zeitpunkt.tzinfo is None:
            return zeitpunkt.replace(tzinfo=timezone.utc)
        return zeitpunkt.astimezone(timezone.utc)
    stunde, _, minute = roh.partition(":")
    return datetime.combine(
        datetime.now(timezone.utc).date(),
        time(int(stunde), int(minute or 0)),
        tzinfo=timezone.utc,
    )
