"""Geteilte Ableitung der Alarm-Dringlichkeit (Issue #1461 Scheibe S3a).

Vier reine Funktionen, kein Zustand: eine Ableitung je Meldungsart (amtliche
Warnung, Radar/Nowcast, Vorhersage-Änderung) plus ein Kombinator für den
Mehrquellen-Fall. Rückgabewert ausschließlich das bestehende Vokabular
`"LOW"`/`"MODERATE"`/`"HIGH"` (Issue #1459).

SPEC: docs/specs/modules/feat_1461_s3a_alarm_dringlichkeit.md (E1-E5)

`hazard_symbols` und `radar_service` werden als Module importiert, nicht als
kopierte Namen -- die Funktionen lesen bei jedem Aufruf den aktuellen Zustand
der referenzierten Konstanten (AC-4, AC-10).
"""
from __future__ import annotations

import output.tokens.hazard_symbols as hazard_symbols
import services.radar_service as radar_service
from services.deviation_alert_engine import DeviationAlertEngine

_LETTER_TO_URGENCY = {"L": "LOW", "M": "MODERATE", "H": "HIGH"}
_RANK = {"LOW": 0, "MODERATE": 1, "HIGH": 2}


def urgency_from_official_level(level: int) -> str:
    """Amtliche Warnstufe (1-4) -> Dringlichkeit, über die bestehende
    Abbildung `hazard_symbols.LEVEL_LETTERS` (E2). Fallback bei einer Stufe
    außerhalb des Katalogs ist konservativ `"HIGH"` (AC-3)."""
    letter = hazard_symbols.LEVEL_LETTERS.get(level, "H")
    return _LETTER_TO_URGENCY[letter]


def urgency_from_radar(*, is_convective: bool, intensity_label: str) -> str:
    """Radar/Nowcast-Kennzahlen -> Dringlichkeit (E3). Konvektive Gefahr
    (Gewitter/Hagel) ist immer `"HIGH"`, sonst entscheidet das Intensitäts-
    Label gegen die benannten Konstanten in `radar_service` -- case-
    insensitiv (AC-9), da der Trip-Pfad den ersten Buchstaben kleinschreibt."""
    if is_convective:
        return "HIGH"
    label = (intensity_label or "").strip().lower()
    if label == radar_service.INTENSITY_HEAVY.lower():
        return "HIGH"
    if label == radar_service.INTENSITY_MODERATE.lower():
        return "MODERATE"
    return "LOW"  # leicht, kein Niederschlag, unbekannt


def urgency_from_changes(changes) -> str:
    """Δ-Wetter-Änderungsliste -> Dringlichkeit (E4). Delegiert unverändert
    an `DeviationAlertEngine._highest_severity()` -- keine zweite Rangfolge-
    Logik (Wiederholungs-Klasse #1481)."""
    return DeviationAlertEngine._highest_severity(changes)


def highest_urgency(*urgencies: str) -> str:
    """Kombinator für den Mehrquellen-Fall (E5): die höchste beteiligte
    Dringlichkeit gewinnt. Leere Eingabe (kein beteiligtes Signal) liefert
    `"LOW"`."""
    if not urgencies:
        return "LOW"
    return max(urgencies, key=lambda u: _RANK.get(u, 0))


def exceeds(a: str, b: str) -> bool:
    """Echtes Groesser-als auf der bestehenden LOW/MODERATE/HIGH-Skala
    (Issue #1467 S4b-1, V2-Eskalation). Nutzt dieselbe `_RANK`-Tabelle wie
    `highest_urgency()`/`meets_or_exceeds()` -- keine zweite Rangfolge
    (Wiederholungs-Klasse #1481). Unbekannte Werte gelten konservativ als
    niedrigste Stufe."""
    return _RANK.get(a, 0) > _RANK.get(b, 0)


def meets_or_exceeds(urgency: str, threshold: str) -> bool:
    """Rangvergleich fuer die Kanal-Schwelle (#1461 S3b-2a): erreicht/uebertrifft
    `urgency` den `threshold`? Nutzt dieselbe `_RANK`-Tabelle wie
    `highest_urgency()` -- keine zweite Rangordnung (Wiederholungs-Klasse
    #1481). Unbekannte Werte gelten konservativ als niedrigste Stufe."""
    return _RANK.get(urgency, 0) >= _RANK.get(threshold, 0)


def min_official_level_for_threshold(threshold: str) -> int:
    """Kanal-Schwelle ('LOW'/'MODERATE'/'HIGH') -> niedrigste amtliche
    Warnstufe, ab der eine Warnung diesen Kanal im SMS-/Telegram-Bericht
    erreichen darf (#1461 S3b-2a, "MIN_SMS_LEVEL geht auf"). Ueber
    `hazard_symbols.LEVEL_LETTERS` -- dieselbe Tabelle wie
    `urgency_from_official_level()`, keine zweite Zahlenreihe. Unbekannter
    Wert faellt konservativ auf `hazard_symbols.MIN_SMS_LEVEL` zurueck."""
    letter = {v: k for k, v in _LETTER_TO_URGENCY.items()}.get(threshold)
    inverse_levels = {v: k for k, v in hazard_symbols.LEVEL_LETTERS.items()}
    return inverse_levels.get(letter, hazard_symbols.MIN_SMS_LEVEL)
