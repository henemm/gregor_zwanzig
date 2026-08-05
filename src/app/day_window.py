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

from typing import Optional

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
