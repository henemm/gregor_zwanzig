"""Nachweisform fuer den Ad-hoc-Verlauf (Issue #2185, Epic #2133 / S2).

Warum es diesen Helfer gibt: mit der Wechselpunkt-Verdichtung fasst
``TripCommandProcessor._format_drilldown`` aufeinanderfolgende Stunden mit
identischem formatiertem Wert zu EINEM Zeitbereich zusammen. Die alte
Nachweisform "mindestens sechs Zeilen, je Uhrzeit eine"
(``telegram_tier3_drilldown.md`` AC-1) ist damit unbrauchbar geworden — und
sie war ohnehin schwach: sechs beliebige, auch lueckenhafte oder doppelte
Zeilen haetten sie bestanden.

Ersatz ist die ABDECKUNGS-Zusicherung (``feat_2185_verlauf_wechselpunkte.md``
AC-7): jeder Zeitpunkt, fuer den ein Datenpunkt vorliegt, ist von genau einer
Zeile abgedeckt — und keine Zeile deckt einen Zeitpunkt ab, fuer den keiner
vorliegt. Sie faengt damit sowohl einen verschluckten Punkt als auch einen
Bereich, der eine Datenluecke ueberbrueckt.
"""
from __future__ import annotations

import re

#: Zeitfeld einer Verlaufszeile: Einzeluhrzeit ``HH:MM`` oder Bereich
#: ``HH:MM–HH:MM``. Formtolerant beim Trennstrich — die Spec legt den INHALT
#: fest ("EIN Zeitbereich"), nicht das Strichzeichen.
ZEILE = re.compile(
    r"^(?P<von>\d{2}:\d{2})"
    r"(?:\s*[–—-]\s*(?P<bis>\d{2}:\d{2}))?"
    r"\s\s+(?P<text>\S.*)$"
)


def zeilen(body: str) -> list[re.Match]:
    """Alle Verlaufszeilen (ohne Kopfzeile) als geparste Treffer."""
    treffer = [ZEILE.match(z) for z in body.splitlines()]
    return [t for t in treffer if t]


def grenzen(body: str) -> list[tuple[str, str | None]]:
    """Zeitgrenzen je Zeile — ``(von, bis)``, ``bis=None`` bei Einzelstunde."""
    return [(t.group("von"), t.group("bis")) for t in zeilen(body)]


def _minuten(hhmm: str) -> int:
    stunde, minute = hhmm.split(":")
    return int(stunde) * 60 + int(minute)


def abgedeckte_stunden(body: str) -> list[str]:
    """Alle von den Verlaufszeilen abgedeckten Uhrzeiten, in Reihenfolge.

    Ein Bereich ``HH:MM–HH:MM`` wird auf die volle Stundenfolge aufgespannt —
    genau das behauptet er ja. Doppelungen bleiben stehen, damit eine
    Ueberschneidung zweier Zeilen auffaellt statt in einer Menge zu
    verschwinden. Ein Bereich ueber Ortsmitternacht wird korrekt fortgesetzt.
    """
    ergebnis: list[str] = []
    for von, bis in grenzen(body):
        start = _minuten(von)
        if bis is None:
            ergebnis.append(von)
            continue
        ende = _minuten(bis)
        if ende < start:
            ende += 24 * 60
        for m in range(start, ende + 1, 60):
            ergebnis.append(f"{(m // 60) % 24:02d}:{m % 60:02d}")
    return ergebnis
