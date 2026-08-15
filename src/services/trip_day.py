"""Geteilter Baustein: "welcher Kalendertag ist gerade, an der Ortszeit der
Tour?" (ADR-0044, Issue #1697).

Verschoben aus ``services.trip_command_processor`` (#1470,
``_trip_tz``/``_display_tz``/``_anchor_tz``) — bit-identisches Verhalten,
nur ``self.`` entfernt. Neu ist ausschliesslich :func:`trip_local_today`.

SPEC: docs/specs/modules/fix_1697_ortstag_statt_servertag.md

Warum ein eigenes Modul statt ``utils/timezone.py``: letzteres ist eine
generische Koordinaten-/Zeitzonen-Bibliothek ohne Domaenenwissen
(``tz_for_coords``, ``local_dt``, ``UTC``) — kennt weder ``Trip`` noch
``Stage``. Diese Funktionen kennen ``Trip.stages``/``Trip.get_stage_for_date``
und gehoeren deshalb in die Domaenen-Schicht (``src/services/``).
"""
from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from utils.timezone import UTC, local_dt, tz_for_coords

if TYPE_CHECKING:
    from zoneinfo import ZoneInfo

    from app.trip import Trip


def trip_tz(trip: "Trip") -> "ZoneInfo":
    """Ortszone der Tour OHNE Tagesbezug — erste Etappe, die Wegpunkte hat.

    Beantwortet allein die Frage "welcher Kalendertag ist gerade?" (#1470).
    Es ist derselbe Weg, den :func:`display_tz` schon als Rueckfall geht, nur
    ohne das Tagesargument — keine zweite Aufloesung. Ohne Wegpunkt bleibt
    die importierte UTC-Konstante (Hausnorm #1345), nie ein hartverdrahtetes
    ``ZoneInfo("UTC")``.
    """
    stage = next((s for s in trip.stages if s.waypoints), None)
    if stage is None:
        return UTC
    wp = stage.waypoints[0]
    return tz_for_coords(wp.lat, wp.lon)


def display_tz(trip: "Trip", day_date: date) -> "ZoneInfo":
    """Anzeige-Zeitzone = ORTSzeit des Wegpunkts an ``day_date`` — Rueckfall
    auf :func:`trip_tz`, wenn diese Etappe keine Wegpunkte traegt."""
    stage = trip.get_stage_for_date(day_date)
    if stage is None or not stage.waypoints:
        return trip_tz(trip)
    wp = stage.waypoints[0]
    return tz_for_coords(wp.lat, wp.lon)


def anchor_tz(trip: "Trip", now_utc: datetime) -> "ZoneInfo":
    """Zone, die entscheidet WELCHER Kalendertag gerade ist (#1470 F003).

    Genommen wird die Etappe des WELTZEIT-Tages. Der liegt hoechstens einen
    Tag neben dem Ortstag, trifft also praktisch immer die Etappe, auf der
    der Nutzer gerade steht. Der frueher benutzte Anker "erste Etappe der
    Tour" war bei einer Tour ueber mehrere Zonen grob daneben: gemessen an
    einer Tour Neuseeland -> Korsika lag der Tageswechsel ZEHN Stunden
    falsch. Mit diesem Anker bleibt als Restfehler nur die Zonendifferenz
    zweier BENACHBARTER Etappen — null, ausser der Wanderer wechselt an
    genau diesem Tag die Zone (Known Limitation, PO 2026-08-10).

    ``local_dt(..., UTC)`` statt ``now_utc.date()``: der Weltzeit-Tag soll
    aus der Weltzeit kommen, auch wenn ein Aufrufer den Zeitstempel einmal
    in einer anderen Zone hereinreicht.
    """
    return display_tz(trip, local_dt(now_utc, UTC).date())


def trip_local_now(trip: "Trip", now_utc: datetime) -> datetime:
    """Die Ortszeit der Tour zum Zeitpunkt ``now_utc`` — Datum UND Uhrzeit aus
    EINER Zonen-Aufloesung (#1724).

    Henne-Ei-Aufloesung in zwei Schritten (#1470): :func:`anchor_tz` bestimmt
    zuerst WELCHER Kalendertag gerade ist (ueber die Etappe des Weltzeit-Tages),
    dann liefert dieselbe Zone die Ortszeit.

    Wer Tag und Stunde braucht, ruft DIESE Funktion einmal — nicht
    :func:`trip_local_today` und daneben eine zweite Aufloesung fuer die
    Stunde. Zwei Aufloesungen koennen an der Tagesgrenze auseinanderfallen und
    sind genau die Fehlerklasse, die #1697 dreimal gefunden hat.
    """
    return local_dt(now_utc, anchor_tz(trip, now_utc))


def trip_local_today(trip: "Trip", now_utc: datetime) -> date:
    """Der Kalendertag "heute", gemessen an der Ortszeit der Tour (ADR-0044).

    Duenne Sicht auf :func:`trip_local_now` — verhaltensgleich zur Fassung aus
    #1697, nur ohne eigene Aufloesung.
    """
    return trip_local_now(trip, now_utc).date()
