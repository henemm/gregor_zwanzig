"""Issue #3047 E4: EINE Lese-Regel fuer den Schalter „Amtliche Warnungen".

PO-Entscheidung 2026-11-16 (Spec feat_3047 „Nachtrag Runde 7"): Ist der
Briefing-Schalter (``official_alerts_enabled``, #1087) ODER der Alarm-Schalter
(``official_warnings.enabled``, Altbestand ``official_alert_triggers_enabled``,
#1088/#1258) an, gilt „beides an": das Briefing holt die Warnungen UND der
amtliche Alarm ist scharf. Nur wenn beide aus sind, ist beides aus.

Gleiche Regel wie der Editor (``frontend/.../wetter-tab/amtlicheWarnungen.ts``).
Trip (Objekt) und Orts-Briefing (dict) lesen dieselbe Funktion; vorher stand die
Logik viermal einzeln im Briefing- und Alarmpfad und lief im Mischzustand
auseinander.
"""
from __future__ import annotations

from typing import Any, Mapping


def amtliche_warnungen_an(
    official_alerts_enabled: Any,
    official_warnings: Any,
    official_alert_triggers_enabled: Any,
) -> bool:
    """Wirksamer Schalter aus den drei gespeicherten Feldern.

    - Briefing: fehlend/``None``/``True`` = an, nur ``False`` = aus.
    - Alarm: ``official_warnings`` gilt nur mit Schluessel ``enabled`` als
      gesetzt (leeres ``{}`` = nicht migriert, #1258 F003); sonst Altfeld
      ``official_alert_triggers_enabled`` (nur ``False`` = aus).
    """
    briefing = official_alerts_enabled is not False
    if isinstance(official_warnings, dict) and "enabled" in official_warnings:
        alarm = bool(official_warnings.get("enabled"))
    else:
        alarm = official_alert_triggers_enabled is not False
    return briefing or alarm


def amtliche_warnungen_an_trip(trip: Any) -> bool:
    """Lese-Regel fuer ein geladenes ``Trip``-Objekt."""
    return amtliche_warnungen_an(
        getattr(trip, "official_alerts_enabled", None),
        getattr(trip, "official_warnings", None),
        getattr(trip, "official_alert_triggers_enabled", None),
    )


def amtliche_warnungen_an_preset(preset: Mapping[str, Any]) -> bool:
    """Lese-Regel fuer ein Orts-Briefing (Preset-dict)."""
    return amtliche_warnungen_an(
        preset.get("official_alerts_enabled"),
        preset.get("official_warnings"),
        preset.get("official_alert_triggers_enabled"),
    )
