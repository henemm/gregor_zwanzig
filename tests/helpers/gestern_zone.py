"""Gemeinsame Gestern-Zone fuer die Prozesszonen-Tests (#2744, #2314).

Die Zonenwahl steht an EINER Stelle: ``tests/tdd/test_prozesszonen_schalter.py``
und ``tests/tdd/test_ortstag_helfer.py`` benutzen beide diese Hilfe statt
eigener Stundengrenzen.

``<-24>+24`` (POSIX-Zone, Offset -24 h) liefert zu JEDER UTC-Zeit den UTC-Tag
minus 1 (gemessen um 00:00:00, 23:45:00 und 23:59:59 UTC) -- sie traegt also
den ganzen UTC-Tag. Die frueheren Zonen ``Pacific/Marquesas`` (bis 09:30 UTC)
und ``<-2330>+23:30`` (bis 23:30 UTC) trugen nur Teile davon.
"""
from __future__ import annotations

import subprocess
from datetime import datetime, timezone

GESTERN_ZONE = "<-24>+24"


def echte_utc_jetzt() -> datetime:
    """Real-Zeit-UTC-`jetzt`, UNBEEINFLUSST von einer gestellten Wanduhr
    (``GZ_TEST_WALL_CLOCK_UTC``/``freeze_time``, #2096) -- gelesen per
    Subprozess ``date -u``, weil freezegun ``datetime.now()`` und
    ``time.time()`` im LAUFENDEN Prozess patcht. Die Sonden-Subprozesse sind
    nie eingefroren, ihre Zonenwahl muss deshalb die ECHTE Zeit sehen."""
    proc = subprocess.run(
        ["date", "-u", "+%s"], capture_output=True, text=True,
        timeout=10, check=True,
    )
    return datetime.fromtimestamp(int(proc.stdout.strip()), tz=timezone.utc)


def gestern_zone_fuer(jetzt_utc: datetime) -> str:
    """Zone, unter der ein Prozess zu ``jetzt_utc`` den UTC-Tag minus 1 sieht.

    Durchgehend ``<-24>+24``: sie traegt zu jeder Tageszeit, eine
    Stundengrenze gibt es nicht mehr. Der Parameter bleibt, damit die
    Aufrufer die ECHTE Startzeit (``echte_utc_jetzt()``) dokumentiert
    uebergeben und in ihren Meldungen nennen koennen."""
    return GESTERN_ZONE
