"""Tagesfenster-Grundlagen: Konstanten, Aufloesung, Stunden-Zugehoerigkeit.

Hierher verschoben aus ``output/renderers/day_window.py`` (#1498, Fall 2):
der Zeitplaner (``trip_report_scheduler``) braucht dieselben Fenster-Grenzen
fuer die Gewitter-Vorschau, darf aber per Architektur-Wache
(``tests/unit/test_notification_service.py``) nichts aus ``output``
importieren. Die Fenster-SEMANTIK ist keine Render-Frage, sondern eine
Domaenen-Konvention (ADR-0025) — sie wohnt deshalb in ``app``, wie schon
``app/thunder_scale.py``. ``output/renderers/day_window.py`` re-exportiert
alle drei Namen unveraendert (bestehende Importe bleiben gueltig).
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone, tzinfo
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:  # pragma: no cover - nur fuer Typpruefer
    from app.models import TripSegment

DAY_WINDOW_START_HOUR = 4
DAY_WINDOW_END_HOUR = 19


def resolve_configured_window(
    day_window_start_hour: Optional[int],
    day_window_end_hour: Optional[int],
) -> tuple[int, int]:
    """Epic #1319 Scheibe B (erweitert Issue #1361/#1372 S1b, AC-3): eine
    Quelle fuer die effektiven Fenster-Grenzen.

    ``None``/fehlend (Alt-Trip, Rueckwaertskompatibilitaet) oder ein
    ungueltiges Paar (ausserhalb 0-23, ``start == end``) faellt still auf
    den Default 4/19 zurueck -- Defense-in-Depth, falls eine ungueltige
    Kombination den Go-Store-Klemmpfad umgeht und dennoch bis zum Renderer
    durchreicht (AC-4).

    ``start > end`` ist seit #1361/#1372 S1b (PO-Entscheidung 2026-07-25)
    ein GUELTIGES Fenster ueber Mitternacht (z. B. 22-2 Uhr) -- NICHT mehr
    invalide. Nur ``start == end`` (Nullstunden- bzw. Ganztags-Mehrdeutigkeit)
    bleibt abgelehnt. Konsumenten (``build_day_window_points()``,
    ``comparison_engine._filter_by_target_date_and_window()``) muessen den
    Mitternachts-Fall selbst wrap-aware behandeln.
    """
    if day_window_start_hour is None or day_window_end_hour is None:
        return DAY_WINDOW_START_HOUR, DAY_WINDOW_END_HOUR
    # F004: bool ist eine int-Subklasse in Python -- ohne den expliziten
    # Ausschluss wuerde JSON true/false als Stunde 1/0 durchgehen.
    if not (type(day_window_start_hour) is int and type(day_window_end_hour) is int):
        return DAY_WINDOW_START_HOUR, DAY_WINDOW_END_HOUR
    if not (0 <= day_window_start_hour <= 23 and 0 <= day_window_end_hour <= 23):
        return DAY_WINDOW_START_HOUR, DAY_WINDOW_END_HOUR
    if day_window_start_hour == day_window_end_hour:
        return DAY_WINDOW_START_HOUR, DAY_WINDOW_END_HOUR
    return day_window_start_hour, day_window_end_hour


def window_end_utc_exclusive(
    local_date: date, end_hour: int, tz: tzinfo,
) -> datetime:
    """Endstunde des Tagesfensters -> EXKLUSIVE UTC-Obergrenze (Issue #1599).

    Die Obergrenze ist INKLUSIV gemeint (PO-Entscheidung 2026-08-17, ADR-0035):
    ``end_hour = 19`` heisst „die Stunde 19 zaehlt vollstaendig mit", das
    Fenster endet zeitlich also um 20:00 Ortszeit. Das inklusive Stundenband
    ``[start_h .. end_h]`` entspricht dem halboffenen Intervall
    ``[start_h:00, (end_h+1):00)``.

    EINE Umrechnung fuer alle drei Alarm-Stellen (``trip_segments``,
    ``compare_location_weather_source``, ``compare_official_alert``) — vorher
    rechnete jede fuer sich, und genau deshalb lief die Kante auseinander
    (#1599). Die konfigurierten Stundenzahlen selbst bleiben unberuehrt, dafuer
    bleibt ``resolve_configured_window()`` zustaendig.

    Reihenfolge ist BINDEND: erst ``.astimezone(timezone.utc)``, dann
    ``+ 1 h``. ``time(end_hour + 1)`` gibt es bei ``end_hour = 23`` nicht, und
    eine Addition VOR der Umrechnung verschoebe die Grenze in einer
    Zeitumstellungsnacht um eine Stunde.
    """
    return (
        datetime.combine(local_date, time(end_hour))
        .replace(tzinfo=tz)
        .astimezone(timezone.utc)
        + timedelta(hours=1)
    )


def display_end_time(segment: "TripSegment") -> datetime:
    """Das ANZEIGE-Ende eines Segments — die letzte zum Segment gehoerende
    Stunde statt der exklusiven Alarm-Obergrenze (Issue #1599).

    Seit #1599 endet das ZIEL-Segment eine Stunde spaeter, damit die Randstunde
    des Tagesfensters bewertet wird (``window_end_utc_exclusive()``). Die
    sichtbare Ausgabe darf diese Stunde NICHT gewinnen: Stundentabelle,
    Kopfzeile „Wetter am Ziel", Nacht-Block, Ankunft-Zeilen und die
    Kurzform-Kanaele zeigen unveraendert dasselbe wie vorher. Jeder
    Anzeige-Konsument liest deshalb hier statt direkt ``segment.end_time``.

    Wirkt AUSSCHLIESSLICH auf das Ziel-Segment (``segment_id == "Ziel"``, der
    etablierte Diskriminator). Regulaere Etappen enden zu krummen Zeiten aus
    Naismith/``arrival_override``; dort gehoert die Ankunftsstunde bewusst dem
    FOLGE-Segment (Bug #806/#1146), eine pauschale Verschiebung wuerde eine
    Stunde doppelt zaehlen oder verlieren.

    Die Stunde wird nur zurueckgenommen, wenn danach noch ein echtes Fenster
    bleibt (``> start_time``). Das trennt exakt die beiden Faelle in
    ``trip_segments``: Fenstergrenze (Ende = Fensterende + 1 h, Anzeige nimmt
    die Stunde zurueck) und Spaetankunfts-Mindestfenster (Ende = Ankunft + 1 h,
    Anzeige laesst es unveraendert — genau der Wert, den sie vor #1599 zeigte).
    """
    end = segment.end_time
    if str(getattr(segment, "segment_id", "")) != "Ziel":
        return end
    zurueckgenommen = end - timedelta(hours=1)
    return zurueckgenommen if zurueckgenommen > segment.start_time else end


def night_addendum(
    own_hourly,
    night_hourly,
    win_start: int,
    win_end: int,
):
    """Level + fruehste Stunde des schlimmsten Gewitters AUSSERHALB des
    Fensters (#1651).

    ``own_hourly``/``night_hourly`` sind Folgen von
    ``(Ortszeit-Stunde, ThunderLevel)`` aus den jeweils bereits vorliegenden,
    UNGEFILTERTEN Zeitreihen -- kein neuer Netzabruf.

    ``night_hourly`` (falls gegeben) ueberschreibt ``own_hourly`` fuer die
    Stunden, die es abdeckt (00:00-06:00 des Folgetags): es ist dieselbe
    Quelle, welche die „Nacht am Ziel"-Tabelle direkt neben der Vorschau
    zeigt. Genau daran scheiterte #1498 -- zwei Quellen sagten fuer DIESELBE
    Stunde derselben Mail Widerspruechliches.

    Mehrere Stunden ausserhalb bilden EINEN Pool (z. B. 00-03 und 20-23
    zusammen): es gewinnt das hoechste Level, davon die frueheste Stunde --
    spiegelbildlich zur Innerhalb-Fenster-Regel in
    ``_thunder_entry_from_trend_row``.

    Rueckgabe ``None``, wenn ausserhalb des Fensters kein Gewitter liegt
    (dann entsteht kein Zusatz).
    """
    from app.models import ThunderLevel
    from app.thunder_scale import thunder_ordinal

    def _peak_per_hour(pairs) -> dict:
        peaks: dict = {}
        for hour, level in pairs or ():
            if level is None:
                continue
            h = int(hour)
            prev = peaks.get(h)
            if prev is None or thunder_ordinal(level) > thunder_ordinal(prev):
                peaks[h] = level
        return peaks

    merged = _peak_per_hour(own_hourly)
    merged.update(_peak_per_hour(night_hourly))

    outside = [
        (hour, level)
        for hour, level in merged.items()
        if level != ThunderLevel.NONE
        and not hour_in_window(hour, win_start, win_end)
    ]
    if not outside:
        return None
    level = max((lv for _h, lv in outside), key=thunder_ordinal)
    hour = min(h for h, lv in outside if lv == level)
    return level, hour


# Wortschatz des Nacht-Zusatzes (#1651). Bewusste Abweichung vom Tagestext,
# wo MED kein Adjektiv traegt („Gewitter moeglich ab HH:MM"): der Halbsatz
# muss fuer sich lesbar sein -- ein „nachts Gewitter" ohne Stufe waere von
# „Stufe unbekannt" nicht unterscheidbar.
_NIGHT_ADDENDUM_WORD = {
    "LOW": "leichtes",
    "MED": "mittleres",
    "HIGH": "starkes",
}


def format_night_addendum(level, hour: int) -> str:
    """Der angehaengte Halbsatz zu einem ``night_addendum()``-Treffer.

    EINE Stelle fuer den Wortlaut: beide Bauwege des Vorschau-Satzes
    (Trend-Weg und Fetch-Weg) sind wortgleich, aber unabhaengiger Code --
    eine zweite Kopie wuerde driften.
    """
    word = _NIGHT_ADDENDUM_WORD.get(getattr(level, "name", str(level)))
    if word is None:
        return ""
    return f", nachts {word} Gewitter ab {int(hour):02d}:00"


def hour_in_window(hour: int, start_hour: int, end_hour: int) -> bool:
    """Liegt die Ortszeit-Stunde im Fenster? Beide Grenzen einschliesslich.

    Wrap-aware (#1361/#1372 S1b): bei ``start > end`` (z. B. 22-2) zaehlen
    die Stunden >= start ODER <= end. Innerhalb EINES Kalendertags bleibt
    die chronologische Ordnung dabei die gewoehnliche Stundenordnung —
    ein ``min()`` ueber Fenster-Treffer desselben Datums ist korrekt.
    """
    if start_hour <= end_hour:
        return start_hour <= hour <= end_hour
    return hour >= start_hour or hour <= end_hour
