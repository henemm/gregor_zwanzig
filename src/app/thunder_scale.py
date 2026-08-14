"""Kanonische Zahlen-Skalen fuer ``ThunderLevel`` — Domaenenschicht.

Hierher verschoben aus ``output/metric_format.py`` (#1196-Nacharbeit): der
Zeitplaner braucht beide Skalen (``trip_report_scheduler.py``), darf aber
keine Darstellungsschicht importieren (Waechter #1365,
``tests/unit/test_notification_service.py::test_scheduler_has_no_output_imports``).
Die Abbildung Enum -> Zahl ist reine Domaenenlogik ohne Render-Abhaengigkeit;
``output.metric_format`` re-exportiert beide Funktionen unveraendert, alle
bestehenden Importe bleiben gueltig.

Issue #1680 S5b: aus DEMSELBEN Grund und nach DEMSELBEN Muster sind
``union_of_max_carriers()`` (S2) sowie ``thunder_signal_label()``/
``THUNDER_SIGNAL_LABEL_DE`` (S1) nachgezogen -- die Gewitter-Vorschau baut
ihren Herkunfts-Zusatz im Zeitplaner (Spec E1), und ein direkter
``from output.metric_format import ...`` dort macht denselben Waechter rot.
Beide sind reine Domaenenlogik: eine Aggregationsregel ueber Stufen und ein
Beschriftungs-Dict, keine Render-Abhaengigkeit.
"""
from __future__ import annotations

from typing import Iterable, Optional

from app.models import ThunderLevel

__all__ = [
    "thunder_ordinal",
    "thunder_label_value",
    "thunder_signal_label",
    "THUNDER_SIGNAL_LABEL_DE",
    "union_of_max_carriers",
]

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


# Die vier Zutaten der Fusion, deutsch beschriftet (Issue #1680 S1). Die
# Einfuegereihenfolge in `_signal_levels()` ist zugleich die Nenn-Reihenfolge
# der Herkunft -- deterministisch, ohne zweites Sortier-Vokabular.
# NICHT zu verwechseln mit `thunder_enrichment._SIGNAL_ZU_FELD`: das ist das
# Rohwert-Routing der Quellen (`"lpi"`, `"cin_ml"`, ...), eine andere Ebene.
THUNDER_SIGNAL_LABEL_DE: dict[str, str] = {
    "wettercode": "Wettercode",
    "blitzdichte": "Blitzdichte",
    "cape": "CAPE",
    "blitzpotenzial": "Blitzpotenzial",
}


def thunder_signal_label(name: str) -> str:
    """Deutsche Beschriftung EINER Fusions-Zutat (Issue #1680 S1).

    Exakt-Treffer zuerst, sonst der rohe Name selbst -- nie ein erfundener
    Ersatztext (Muster ``official_alert_source_label``, ADR-0007). Ohne
    Heuristik-Stufe, weil die Signalmenge geschlossen ist (vier feste
    Schluessel, kein Namensraum mit Praefix-Varianten).
    """
    return THUNDER_SIGNAL_LABEL_DE.get(name, name)


def union_of_max_carriers(
    pairs: Iterable[tuple[Optional[ThunderLevel], Optional[list[str]]]],
) -> Optional[list[str]]:
    """Vereinigt die Traeger DERJENIGEN Paare, die die Hoechststufe erreichen
    (Issue #1680 S2).

    Die EINE Stelle, an der die Aggregationsregel
    ``"thunder_level_max_signals": "union_of_max_carriers"`` (deklariert in
    ``WeatherMetricsService.compute_basis_metrics()``) tatsaechlich gerechnet
    wird. Herausgeloest aus ``_compute_thunder_level_signals()``, damit die
    unabhaengigen Aggregationswege (Stunden, Wegpunkte, spaeter Segmente) sie
    IMPORTIEREN statt sie zu kopieren — dieselbe Fehlerklasse, gegen die #1480
    laeuft. Muster: ``hail_priority()``.

    Genannt wird JEDE Zutat, die die Hoechststufe traegt (PO-Auslegung (ii),
    Scheibe 1) — es wird kein Gewinner gekuert, ein Paar unterhalb des Maximums
    steuert NICHTS bei. Dedupliziert unter Erhalt der ERSTauftrittsreihenfolge;
    da jede einzelne Traegerliste aus ``thunder_signal_carriers()`` bereits in
    der Katalogreihenfolge von ``THUNDER_SIGNAL_LABEL_DE`` steht, bleibt die
    Nennreihenfolge deterministisch — ohne zweites Sortier-Vokabular.

    ``None`` (nicht ``[]``) heisst "keine Aussage": kein Paar nennt eine Stufe
    (z.B. leere Auswahl) ODER kein Paar am Maximum nennt einen Traeger (z.B.
    ein Alt-Schnappschuss ohne das Feld). Eine Stufe ``NONE`` ist dabei eine
    ECHTE Stufe und kein Ausstiegsgrund — liegt das Maximum aber BEI ``NONE``,
    ist das Ergebnis ``None``, weil "kein Gewitter" keine Herkunft hat. Das
    garantiert die Funktion SELBST und verlaesst sich nicht darauf, dass ihre
    Aufrufer zu einem ``NONE``-Punkt ohnehin keine Traeger liefern — sie ist
    fuer die Wiederverwendung gebaut, und eine Zusicherung, die nur aus dem
    Verhalten der heutigen Aufrufer folgt, braeche beim naechsten.

    Rueckgabe ist bewusst eine ``list``, NIE ein ``set``: das Ergebnis landet
    ueber ``SegmentWeatherSummary.thunder_level_max_signals`` im Wetter-
    Schnappschuss, und ein ``set`` braeche dort ``json.dumps`` — der Fehler
    wird still geschluckt, der GESAMTE Schnappschuss waere weg (#1405).

    Issue #1680 S5b: hierher verschoben aus ``output/metric_format.py``. Der
    frueher benutzte Helfer ``max_thunder()`` ist durch sein eigenes Innenleben
    (``max(..., key=thunder_ordinal)``) ersetzt — dieselbe kanonische Ordnung,
    aber ohne Abhaengigkeit auf die Darstellungsschicht (s. Modul-Docstring).
    """
    paare = list(pairs)
    stufen = [s for s, _ in paare if s is not None]
    if not stufen:
        return None
    top = max(stufen, key=thunder_ordinal)
    if top == ThunderLevel.NONE:
        return None
    traeger: list[str] = []
    for stufe, liste in paare:
        if stufe != top:
            continue
        for name in liste or []:
            if name not in traeger:
                traeger.append(name)
    return traeger or None
