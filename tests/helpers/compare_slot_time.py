"""Zeitpunkt-Helfer fuer `compare_slot_scheduler.presets_due_for_hour` (#1726).

Die Funktion nahm bis #1726 eine fertige Stunde und einen fertigen Kalendertag
entgegen. Seit #1726 loest sie beides SELBST auf — je Preset in der Ortszone
seines ersten aufloesbaren Orts. Aufrufer geben deshalb einen ZEITPUNKT und
die Ortsliste.

Bestandstests, die nur „Slot 7 Uhr am Tag D" ausdruecken wollten und gar keine
Orte kennen, uebergeben eine LEERE Ortsliste: dann greift der dokumentierte
UTC-Rueckfall (`utils.timezone.first_resolvable_tz`), und `utc_moment(D, 7)`
ist genau der Zeitpunkt, an dem die Ortsstunde 7 und der Ortstag D ist.

Bewusst KEIN Standardwert fuer die Zone: wer eine Zonen-Aussage pruefen will,
baut seine Orte selbst und rechnet den Zeitpunkt dagegen — sonst prueft der
Test die Zonenwahl nicht, sondern nur, dass sie irgendwas liefert.
"""
from __future__ import annotations

from datetime import date, datetime, timezone


def utc_moment(today: date, hour: int) -> datetime:
    """Weltzeit-Zeitpunkt mit Ortsstunde ``hour`` am Ortstag ``today`` — fuer
    Presets ohne aufloesbare Orte (Zone = UTC)."""
    return datetime(today.year, today.month, today.day, hour, tzinfo=timezone.utc)
