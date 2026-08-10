"""ComparePreset-Zeitplan-Reshape — Slot-Aufloesung + Faelligkeitspruefung.

SPEC: docs/specs/modules/compare_preset_zeitplan.md (#1232 Scheibe 2a)

Reine Funktionen (kein IO, kein globaler State):

- `resolve_preset_slots(preset)` liest die 5 neuen Slot-Felder aus einem
  rohen Preset-Dict. Fehlt `morning_time` (Marker "nie migriert"), greift
  die Migrations-Fallback-Tabelle aus der Spec (abhaengig vom Alt-Wert von
  `schedule`).
- `presets_due_for_hour(presets, hour, today)` liefert je faelligem Preset
  ein `DuePreset(preset, target_date, tage_ab_ortstag)` (Morgen-Slot -> today
  bzw. Versatz 0, Abend-Slot -> today+1 bzw. Versatz +1), inkl. Pause-
  (`schedule == "manual"`), Archiv- (`archived_at`) und Laufzeit-Guard
  (`end_date`).
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


# Slot -> Tagesversatz gegen den Sammeltag. Der Morgen-Slot briefed ueber den
# laufenden Tag, der Abend-Slot ueber den Folgetag (#1232 Scheibe 2a).
MORGEN_SLOT_VERSATZ = 0
ABEND_SLOT_VERSATZ = 1


class DuePreset(NamedTuple):
    """Ein faelliges Preset mit seinem Tagesbezug in BEIDEN Formen.

    Issue #1661 (Adversary-Finding F003): der Tagesbezug wird hier — an der
    einzigen Stelle, die den Slot kennt — EINMAL aus `today` gebildet und in
    beiden Formen weitergereicht, statt spaeter aus einer zweiten
    `date.today()`-Auswertung rekonstruiert zu werden:

    * `target_date` — der absolute Zieltag (LESESEITE: Mail-Betreff,
      Vergleichs-Engine).
    * `tage_ab_ortstag` — derselbe Tag als VERSATZ (SCHREIBSEITE: Δ-Anker).
      Er wird erst am Ort gegen die ORTSZEIT aufgeloest
      (`compare_location_weather_source.fetch`), damit der Anker nicht am
      UTC-Tag des Servers haengt (Adversary-Finding F002).

    Beide entstehen aus DERSELBEN Zeitabfrage. Faellt zwischen Sammeln und
    Schreiben eine Mitternacht, bleibt der Versatz dadurch richtig; die
    fruehere Differenzbildung `(target_date - date.today()).days` lag dann
    still um einen Tag daneben (F003).
    """

    preset: dict
    target_date: date
    tage_ab_ortstag: int


def _due(preset: dict, today: date, tage_ab_ortstag: int) -> DuePreset:
    """Baut den Faelligkeits-Eintrag aus dem Versatz — EINE Quelle fuer beide
    Formen, damit `target_date` und `tage_ab_ortstag` nicht auseinanderlaufen
    koennen."""
    return DuePreset(
        preset, today + timedelta(days=tage_ab_ortstag), tage_ab_ortstag,
    )


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
    """Liefert je faelligem Preset ein `DuePreset`-Tripel
    `(preset, target_date, tage_ab_ortstag)`.

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

            # #511: weekly gate't auf den Versandtag (beide Slots) — sonst
            # sendet ein Wochen-Abo taeglich. Fehlt `weekday` (Altbestand),
            # verhaelt sich das Preset wie daily.
            if preset.get("schedule") == "weekly":
                weekday = preset.get("weekday")
                if weekday is not None and int(weekday) != today.weekday():
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
            due.append(_due(preset, today, MORGEN_SLOT_VERSATZ))
        if slots.evening_enabled and slots.evening_time.hour == hour:
            due.append(_due(preset, today, ABEND_SLOT_VERSATZ))
    return due
