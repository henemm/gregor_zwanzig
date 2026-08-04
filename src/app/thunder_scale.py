"""Kanonische Zahlen-Skalen fuer ``ThunderLevel`` — Domaenenschicht.

Hierher verschoben aus ``output/metric_format.py`` (#1196-Nacharbeit): der
Zeitplaner braucht beide Skalen (``trip_report_scheduler.py``), darf aber
keine Darstellungsschicht importieren (Waechter #1365,
``tests/unit/test_notification_service.py::test_scheduler_has_no_output_imports``).
Die Abbildung Enum -> Zahl ist reine Domaenenlogik ohne Render-Abhaengigkeit;
``output.metric_format`` re-exportiert beide Funktionen unveraendert, alle
bestehenden Importe bleiben gueltig.
"""
from __future__ import annotations

from typing import Optional

from app.models import ThunderLevel

__all__ = ["thunder_ordinal", "thunder_label_value"]

# Kanonische Ordnungsquelle fuer ThunderLevel (str-Enum ohne eigene Ordnung,
# app/models.py). ThunderLevel(str, Enum) hasht/vergleicht identisch zu
# seinem rohen String-Wert, daher funktioniert dieses Dict transparent auch
# mit rohen "NONE"/"LOW"/"MED"/"HIGH"-Strings als Key (day_comparison.py).
#
# Issue #1474: LOW ist additiv UNTERHALB von MED eingefuegt -- MED wandert von
# Ordinal 1 auf 2, HIGH von 2 auf 3. Jede Stelle, die diese Skala ueber eine
# rohe Zahl anspricht (statt ueber thunder_ordinal(ThunderLevel.X)), meint nach
# dieser Erweiterung etwas anderes als vorher (Spec Abschnitt 1/2).
_THUNDER_ORDER = {
    ThunderLevel.NONE: 0, ThunderLevel.LOW: 1,
    ThunderLevel.MED: 2, ThunderLevel.HIGH: 3,
}


def thunder_ordinal(level: Optional[ThunderLevel]) -> int:
    """Kanonisches Sortier-Ordinal fuer ``ThunderLevel``
    (NONE=0 < LOW=1 < MED=2 < HIGH=3).

    ``None`` sowie unbekannte Werte liefern 0. Nimmt sowohl ``ThunderLevel``-
    Instanzen als auch rohe Strings entgegen (str-Enum-Hash-Aequivalenz).
    """
    if level is None:
        return 0
    return _THUNDER_ORDER.get(level, 0)


# Render-Skala fuer ThunderLevel — zielt exakt auf
# ``src/output/tokens/metrics.LEVELS = {0:'-', 1:'L', 2:'M', 3:'H'}``.
# Issue #1474: LOW belegt endlich den bisher unerreichbaren Render-Platz 1.
# MED/HIGH behalten ihre bisherigen Render-Werte 2/3 (additiv, kein
# Render-Sprung fuer Bestandswerte, Spec AC-1).
_THUNDER_LABEL_VALUE = {
    ThunderLevel.NONE: 0, ThunderLevel.LOW: 1,
    ThunderLevel.MED: 2, ThunderLevel.HIGH: 3,
}


def thunder_label_value(level: Optional[ThunderLevel]) -> int:
    """Kanonischer Render-Wert fuer ``ThunderLevel`` (NONE=0, LOW=1, MED=2, HIGH=3).

    ``None`` sowie unbekannte Werte liefern 0. Nimmt sowohl ``ThunderLevel``-
    Instanzen als auch rohe Strings entgegen (str-Enum-Hash-Aequivalenz).

    Seit Issue #1474 sind Sortier- und Render-Skala fuer alle vier Werte
    zahlenmaessig deckungsgleich ({0,1,2,3} in beiden) — bleiben aber zwei
    separate, benannte Funktionen (ADR-0025, Entscheidung 3). Eine kuenftige
    Aenderung an einer der beiden darf sich nicht auf die andere verlassen:

    * ``thunder_ordinal()``    -> {NONE:0, LOW:1, MED:2, HIGH:3} — **Sortier-/
      Vergleichsordnung**. Nur fuer max()/Vergleiche/Peak-Ermittlung.
    * ``thunder_label_value()`` -> {NONE:0, LOW:1, MED:2, HIGH:3} — **Render-
      Skala** fuer ``tokens/metrics.LEVELS = {0:'-', 1:'L', 2:'M', 3:'H'}``. Nur
      diese Funktion darf Werte fuer ``DailyForecast.thunder_hourly`` bzw.
      ``HourlyValue.value`` auf dem SMS-Token-Pfad erzeugen.
    """
    if level is None:
        return 0
    return _THUNDER_LABEL_VALUE.get(level, 0)
