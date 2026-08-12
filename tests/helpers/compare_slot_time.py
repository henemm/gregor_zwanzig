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


def utc_slot_for_manual_hour(hour: int) -> str:
    """Slot-Uhrzeit (``"HH:MM:SS"``) fuer ein Preset OHNE aufloesbaren Ort, das
    ueber den manuellen Ausloeser ``run_compare_presets_daily(hour=...)``
    faellig werden soll.

    Der Ausloeser verankert seinen Zeitpunkt in der Referenz-Zone
    (``CompareDispatchStrategy.MANUAL_TRIGGER_REFERENCE_ZONE``) — ein reines
    Ops-Werkzeug ohne Preset-Bezug, den der Produktiv-Cron nicht benutzt. Ein
    Preset ohne aufloesbaren Ort rechnet seit #1726 dagegen in UTC und sieht
    zu DEMSELBEN Zeitpunkt eine ANDERE Stunde; mit dem 06:00-Migrations-
    Rueckfall waere es bei ``hour=6`` gar nicht mehr faellig und der Test
    pruefte einen Lauf, der nie stattfindet.

    Die Stunde wird aus derselben Umrechnung gewonnen, die der Ausloeser
    benutzt, statt getippt: als feste "04:00:00" haenge sie am Sommerzeit-
    Versatz der Referenz-Zone und waere im Winter falsch.
    """
    from zoneinfo import ZoneInfo

    from services.dispatch_orchestrator import CompareDispatchStrategy

    zone = ZoneInfo(CompareDispatchStrategy.MANUAL_TRIGGER_REFERENCE_ZONE)
    utc_hour = (
        datetime.now(zone)
        .replace(hour=hour, minute=0, second=0, microsecond=0)
        .astimezone(timezone.utc)
        .hour
    )
    return f"{utc_hour:02d}:00:00"
