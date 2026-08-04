"""ComparePreset-Zeitplan-Reshape — Slot-Aufloesung + Faelligkeitspruefung.

SPEC: docs/specs/modules/compare_preset_zeitplan.md (#1232 Scheibe 2a)

Reine Funktionen (kein IO, kein globaler State):

- `resolve_preset_slots(preset)` liest die 5 neuen Slot-Felder aus einem
  rohen Preset-Dict. Fehlt `morning_time` (Marker "nie migriert"), greift
  die Migrations-Fallback-Tabelle aus der Spec (abhaengig vom Alt-Wert von
  `schedule`).
- `presets_due_for_hour(presets, hour, today)` liefert je faelligem Preset
  ein `(preset, target_date)`-Tupel (Morgen-Slot -> today, Abend-Slot ->
  today+1), inkl. Pause- (`schedule == "manual"`), Archiv- (`archived_at`)
  und Laufzeit-Guard (`end_date`).
"""
from __future__ import annotations

import logging
from datetime import date, time as dt_time, timedelta
from typing import NamedTuple

from services.compare_alert_guard import is_silenced

logger = logging.getLogger("scheduler.compare_slot")


class PresetSlots(NamedTuple):
    morning_enabled: bool
    morning_time: dt_time
    evening_enabled: bool
    evening_time: dt_time


def _parse_time(value: str) -> dt_time:
    return dt_time.fromisoformat(value)


def resolve_preset_slots(preset: dict) -> PresetSlots:
    """Liest die Slot-Felder eines Presets, mit Migrations-Fallback.

    Marker fuer "nie migriert": `morning_time` fehlt komplett (Alt-Preset-
    JSON, wie es der Python-Dispatch roh von der Platte liest). In dem Fall
    entscheidet der Alt-Wert von `schedule` ueber Morgen- vs. Abend-Intention
    (KL-6): `daily_evening` -> Abend-Slot aktiv, alles andere (`daily`,
    `weekly`, `manual`, leer/unbekannt, `daily_morning`) -> Morgen-Slot aktiv
    (verhaltensidentisch zum bisherigen 06:00-Cron).
    """
    if preset.get("morning_time") is None:
        if preset.get("schedule") == "daily_evening":
            return PresetSlots(False, dt_time(6, 0), True, dt_time(18, 0))
        return PresetSlots(True, dt_time(6, 0), False, dt_time(18, 0))

    morning_enabled = bool(preset.get("morning_enabled", True))
    morning_time = _parse_time(preset["morning_time"])
    evening_enabled = bool(preset.get("evening_enabled", False))
    evening_time = _parse_time(preset.get("evening_time") or "18:00:00")
    return PresetSlots(morning_enabled, morning_time, evening_enabled, evening_time)


def presets_due_for_hour(presets: list, hour: int, today: date) -> list:
    """Liefert je faelligem Preset ein `(preset, target_date)`-Tupel.

    Guards (in dieser Reihenfolge): stillgelegt laut
    `compare_alert_guard.is_silenced` — `paused_at` gesetzt ODER
    `schedule == "manual"` ODER `archived_at` gesetzt (unabhaengig von
    etwaigen explizit gesetzten Slots), danach `end_date` in der
    Vergangenheit stoppt ab dem Folgetag. Morgen- und Abend-Slot werden unabhaengig voneinander
    geprueft (KL-5: beide koennen in derselben Stunde faellig sein).

    Adversary-Fund F002 (#1232 Scheibe 2a): ein einzelnes Preset mit
    korruptem `end_date` (oder korrupten Slot-Uhrzeiten) darf den Dispatch
    fuer die uebrigen Presets desselben Users nicht abbrechen — es wird
    uebersprungen (Log-Warnung), der Rest der Liste laeuft unbeeinflusst
    weiter.
    """
    due: list = []
    for preset in presets:
        # Issue #1467 S2 AG6: dieselbe Frage wie in den drei Alarm-Pfaden —
        # deshalb dieselbe, einzige Fassung (AC-28). `paused_at` kommt damit
        # neu hinzu; ein pausiertes Preset war hier ohnehin nie faellig
        # gemeint.
        if is_silenced(preset):
            continue

        try:
            end_date_str = preset.get("end_date")
            if end_date_str:
                if date.fromisoformat(end_date_str) < today:
                    continue

            slots = resolve_preset_slots(preset)
        except (ValueError, TypeError) as e:
            logger.warning(
                "Preset %s: korrupte Zeitplan-Daten (end_date/morning_time/"
                "evening_time), wird uebersprungen: %s",
                preset.get("id", "?"),
                e,
            )
            continue

        if slots.morning_enabled and slots.morning_time.hour == hour:
            due.append((preset, today))
        if slots.evening_enabled and slots.evening_time.hour == hour:
            due.append((preset, today + timedelta(days=1)))
    return due
