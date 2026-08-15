"""Briefing-Zeiten fuer Test-Aufbauten, die NICHT in den Vorlauf der
Alarm-Sperre (#1594) fallen.

Hintergrund: seit #1594 schweigt der Aenderungs- und der amtliche Alarm, wenn
fuer dieselbe Entitaet innerhalb der naechsten 60 Minuten ein geplantes
Briefing ansteht, das noch nicht versucht wurde. Ein Bestandstest, der einen
Alarm erwartet, misst dann nicht mehr seine eigene Zusicherung, sondern die
Sperre — er wird taeglich in einem Zeitfenster rot und ausserhalb gruen.

Die Bestandstests konfigurieren gar keine Briefing-Zeiten; sie erben die
Modell-Vorgaben (``TripReportConfig``: 07:00/18:00 Ortszeit) bzw. den
Migrations-Rueckfall der Vergleichs-Slots (06:00 Ortszeit). Damit ist jede
solche Entitaet zweimal taeglich 60 Minuten lang „Briefing steht bevor".

Dieses Modul liefert stattdessen Zeiten, die zu JEDER Wanduhrzeit ausserhalb
des Vorlaufs liegen. Es haengt bewusst von keinem anderen Test-Helfer ab —
sonst entstuende ein Import-Ring mit ``compare_briefings``.
"""
from __future__ import annotations

from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

# Abstand zur JETZIGEN Ortsstunde. Warum drei und nicht eine Stunde:
# `check_briefing_imminent()` tastet das Fenster [now, now + 60 min] ab, die
# Faelligkeit selbst gilt fuer die volle Stunde (`slot.hour == hour`). Ein
# Lauf um 14:59 Ortszeit sieht damit noch die Stunde 15 — ein Abstand von
# einer Stunde waere je nach Minute mal drin und mal nicht. Zwei Stunden
# genuegten rechnerisch; drei laesst Luft fuer Tests, die selbst eine Stunde
# vorspulen.
MORGEN_ABSTAND_STUNDEN = 3
ABEND_ABSTAND_STUNDEN = 6


def briefing_stunden_ausserhalb_des_vorlaufs(zone: ZoneInfo) -> tuple[int, int]:
    """Morgen- und Abend-Briefingstunde in ``zone``, beide ausserhalb des
    60-Minuten-Vorlaufs (#1594).

    ``zone`` MUSS die Zone sein, in der der Pruefling die Faelligkeit
    auswertet — fuer Trips ``anchor_tz(trip, now)``, fuer Vergleiche
    ``first_resolvable_tz(...)``. Eine andere Zone waere eine Zusicherung am
    falschen Ort: die Stunde saehe sicher aus und laege trotzdem im Fenster.
    """
    jetzt = datetime.now(timezone.utc).astimezone(zone).hour
    return (
        (jetzt + MORGEN_ABSTAND_STUNDEN) % 24,
        (jetzt + ABEND_ABSTAND_STUNDEN) % 24,
    )


def briefing_zeiten_ausserhalb_des_vorlaufs(zone: ZoneInfo) -> tuple[time, time]:
    """Dasselbe als ``time``-Paar — fuer ``TripReportConfig``."""
    morgen, abend = briefing_stunden_ausserhalb_des_vorlaufs(zone)
    return time(morgen, 0), time(abend, 0)


def briefing_zeiten_fuer_trip(trip) -> tuple[time, time]:
    """Zeiten ausserhalb des Vorlaufs in genau der Zone, in der die Sperre die
    Faelligkeit DIESES Trips auswertet.

    ``anchor_tz`` ist dieselbe Aufloesung, die ``trip_alert._is_briefing_
    imminent()`` benutzt. Wer hier stattdessen eine feste Zone (oder die
    Serverzone) einsetzt, rechnet am Wirkort vorbei: die Stunde saehe sicher
    aus und laege bei einer Tour in einer anderen Zone trotzdem im Fenster.
    """
    from services.trip_day import anchor_tz

    return briefing_zeiten_ausserhalb_des_vorlaufs(
        anchor_tz(trip, datetime.now(timezone.utc))
    )


def briefing_zeiten_iso(zone: ZoneInfo) -> tuple[str, str]:
    """Dasselbe als ``"HH:00:00"``-Paar — fuer Preset- und Trip-JSON.

    Go kappt Versandzeiten ohnehin auf die volle Stunde
    (``internal/store/slot_hour_normalization.go``), und die Faelligkeit
    vergleicht nur die Stunde.
    """
    morgen, abend = briefing_stunden_ausserhalb_des_vorlaufs(zone)
    return f"{morgen:02d}:00:00", f"{abend:02d}:00:00"
