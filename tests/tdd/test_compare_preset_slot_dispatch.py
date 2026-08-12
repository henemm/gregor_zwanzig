"""
Tests fuer #1232 Scheibe 2a — ComparePreset-Zeitplan-Reshape (Backend).

SPEC: docs/specs/modules/compare_preset_zeitplan.md

Getestet wird ein noch nicht existierendes, rein deterministisches Modul
`src.services.compare_slot_scheduler` mit zwei reinen Funktionen:

- `resolve_preset_slots(preset: dict) -> Slots`
  Liest die 5 neuen Slot-Felder aus einem rohen Preset-Dict, wendet bei
  fehlendem `morning_time` (Nil-Check-Marker "Altdaten, nie migriert") die
  Migrations-Fallback-Tabelle aus der Spec an.
- `presets_due_for_hour(presets, all_locations, now_utc) -> list[DuePreset]`
  Liefert je faelligem Preset den Tagesbezug in BEIDEN Formen — Zieldatum
  (Morgen-Slot -> heute, Abend-Slot -> morgen) UND Versatz gegen den Ortstag
  (0 bzw. +1) —, inkl. Pause-/Archiv-/Laufzeit-Guards.
  Der Versatz kam mit #1661 (Adversary-Finding F003) hinzu: er wird von hier
  bis zum Δ-Anker durchgereicht, statt spaeter aus einer zweiten
  `date.today()`-Auswertung rekonstruiert zu werden. Jeder Faelligkeits-Assert
  unten pinnt ihn deshalb mit — ein vertauschter oder fest verdrahteter
  Versatz faellt hier auf.

RED-Zustand (jetzt): `services.compare_slot_scheduler` existiert nicht
  -> ModuleNotFoundError bei Collection, alle Tests unten sind rot.

KEINE Mocks/patch/MagicMock — reine Funktionen mit dict-Fixtures.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from services.compare_slot_scheduler import presets_due_for_hour, resolve_preset_slots
from tests.helpers.compare_slot_time import utc_moment
from services.scheduler_dispatch_service import build_compare_preset_subject

TODAY = date(2026, 7, 12)


def _preset(**overrides) -> dict:
    """Baut ein Compare-Preset-Dict mit den echten Feldnamen aus
    data/users/<user>/compare_presets.json (Bestandsschema)."""
    preset = {
        "id": "preset-1",
        "name": "Alpen vs Voralpen",
        "schedule": "daily",
        "weekday": None,
        "hour_from": 9,
        "hour_to": 16,
        "location_ids": ["ort-a", "ort-b"],
        "empfaenger": ["nutzer@example.com"],
        "archived_at": None,
        "letzter_versand": None,
    }
    preset.update(overrides)
    return preset


def _without_slot_fields(preset: dict) -> dict:
    """Entfernt alle 5 Slot-Felder komplett (simuliert Alt-Preset-JSON, wie
    es der Python-Dispatch roh von der Platte liest — kein Key vorhanden,
    nicht nur None)."""
    for key in ("morning_enabled", "morning_time", "evening_enabled", "evening_time", "end_date"):
        preset.pop(key, None)
    return preset


# --- AC-4: Morgen-Slot faellig genau zur konfigurierten Stunde ------------

def test_ac4_morning_slot_due_at_configured_hour_not_outside():
    """GIVEN ein Preset mit aktivem Morgen-Versand um 07:00
    WHEN presets_due_for_hour bei hour=7 laeuft
    THEN ist das Preset faellig mit target=heute; bei hour=8 nicht faellig."""
    preset = _preset(
        morning_enabled=True, morning_time="07:00:00",
        evening_enabled=False, evening_time="18:00:00",
    )

    due_at_7 = presets_due_for_hour([preset], {}, utc_moment(TODAY, 7))
    due_at_8 = presets_due_for_hour([preset], {}, utc_moment(TODAY, 8))

    assert due_at_7 == [(preset, TODAY, 0)]
    assert due_at_8 == []


# --- AC-5: Abend-Slot faellig, Ziel ist der Folgetag -----------------------

def test_ac5_evening_slot_due_targets_next_day():
    """GIVEN ein Preset mit aktivem Abend-Versand um 18:00
    WHEN presets_due_for_hour bei hour=18 laeuft
    THEN ist das Preset faellig mit target=heute+1; bei hour=17 nicht faellig."""
    preset = _preset(
        morning_enabled=False, morning_time="06:00:00",
        evening_enabled=True, evening_time="18:00:00",
    )

    due_at_18 = presets_due_for_hour([preset], {}, utc_moment(TODAY, 18))
    due_at_17 = presets_due_for_hour([preset], {}, utc_moment(TODAY, 17))

    assert due_at_18 == [(preset, TODAY + timedelta(days=1), 1)]
    assert due_at_17 == []


# --- AC-3 / KL-6: Migrations-Fallback fuer alle 6 Alt-Werte ---------------

@pytest.mark.parametrize(
    "schedule_value",
    ["daily", "weekly", "manual", "", "daily_morning"],
)
def test_migration_fallback_defaults_to_active_morning_slot(schedule_value):
    """GIVEN ein Alt-Preset ohne Slot-Felder mit schedule in
    {daily, weekly, manual, leer, daily_morning}
    WHEN resolve_preset_slots laeuft
    THEN ist der Morgen-Slot aktiv @06:00 und der Abend-Slot inaktiv @18:00
    (verhaltensidentisch zum bisherigen 06:00-Cron / Nutzer-Intention Morgen)."""
    preset = _without_slot_fields(_preset(schedule=schedule_value))

    morning_enabled, morning_time, evening_enabled, evening_time = resolve_preset_slots(preset)

    assert morning_enabled is True
    assert morning_time.hour == 6
    assert morning_time.minute == 0
    assert evening_enabled is False
    assert evening_time.hour == 18
    assert evening_time.minute == 0


def test_migration_fallback_daily_evening_defaults_to_active_evening_slot():
    """GIVEN ein Alt-Preset ohne Slot-Felder mit schedule='daily_evening'
    WHEN resolve_preset_slots laeuft
    THEN ist der Morgen-Slot inaktiv @06:00 und der Abend-Slot aktiv @18:00
    (Nutzer-Intention Abend, KL-6-Migration behebt den Wertemengen-Mismatch)."""
    preset = _without_slot_fields(_preset(schedule="daily_evening"))

    morning_enabled, morning_time, evening_enabled, evening_time = resolve_preset_slots(preset)

    assert morning_enabled is False
    assert morning_time.hour == 6
    assert evening_enabled is True
    assert evening_time.hour == 18


def test_migration_fallback_manual_still_paused_despite_active_slot():
    """GIVEN ein Alt-Preset ohne Slot-Felder mit schedule='manual'
    WHEN presets_due_for_hour zur (via Fallback aktiven) Morgen-Stunde laeuft
    THEN wird trotzdem nichts versendet — Pause bleibt Pause,
    unabhaengig vom migrierten Slot."""
    preset = _without_slot_fields(_preset(schedule="manual"))

    due = presets_due_for_hour([preset], {}, utc_moment(TODAY, 6))

    assert due == []


# --- AC-6: schedule='manual' MIT explizit gesetzten Slots -----------------

def test_ac6_manual_schedule_with_explicit_slots_never_due():
    """GIVEN ein Preset mit schedule='manual' und explizit gesetzten,
    an sich faelligen Slot-Feldern (Morgen und Abend)
    WHEN presets_due_for_hour zu beiden Stunden laeuft
    THEN wird zu keiner der beiden Stunden versendet (Pause haelt)."""
    preset = _preset(
        schedule="manual",
        morning_enabled=True, morning_time="07:00:00",
        evening_enabled=True, evening_time="18:00:00",
    )

    due_morning = presets_due_for_hour([preset], {}, utc_moment(TODAY, 7))
    due_evening = presets_due_for_hour([preset], {}, utc_moment(TODAY, 18))

    assert due_morning == []
    assert due_evening == []


# --- AC-7: Laufzeit-Ende (end_date) ---------------------------------------

def test_ac7_end_date_in_past_never_due():
    """GIVEN ein Preset mit end_date gestern und faelliger Morgen-Stunde
    WHEN presets_due_for_hour laeuft
    THEN wird nichts versendet."""
    preset = _preset(
        morning_enabled=True, morning_time="07:00:00",
        evening_enabled=False, evening_time="18:00:00",
        end_date=(TODAY - timedelta(days=1)).isoformat(),
    )

    due = presets_due_for_hour([preset], {}, utc_moment(TODAY, 7))

    assert due == []


def test_ac7_end_date_today_still_due():
    """GIVEN ein Preset mit end_date == heute und faelliger Morgen-Stunde
    WHEN presets_due_for_hour laeuft
    THEN wird heute noch versendet (Guard greift erst ab morgen)."""
    preset = _preset(
        morning_enabled=True, morning_time="07:00:00",
        evening_enabled=False, evening_time="18:00:00",
        end_date=TODAY.isoformat(),
    )

    due = presets_due_for_hour([preset], {}, utc_moment(TODAY, 7))

    assert due == [(preset, TODAY, 0)]


def test_ac7_end_date_none_unbounded_still_due():
    """GIVEN ein Preset mit end_date=None (unbegrenzte Laufzeit)
    WHEN presets_due_for_hour zur faelligen Stunde laeuft
    THEN wird versendet."""
    preset = _preset(
        morning_enabled=True, morning_time="07:00:00",
        evening_enabled=False, evening_time="18:00:00",
        end_date=None,
    )

    due = presets_due_for_hour([preset], {}, utc_moment(TODAY, 7))

    assert due == [(preset, TODAY, 0)]


# --- AC-8: archived_at ------------------------------------------------------

def test_ac8_archived_preset_never_due():
    """GIVEN ein Preset mit archived_at gesetzt und faelliger Morgen-Stunde
    WHEN presets_due_for_hour laeuft
    THEN wird nichts versendet — Archivierung stoppt unabhaengig vom Zeitplan."""
    preset = _preset(
        morning_enabled=True, morning_time="07:00:00",
        evening_enabled=False, evening_time="18:00:00",
        archived_at="2026-07-01T00:00:00Z",
    )

    due = presets_due_for_hour([preset], {}, utc_moment(TODAY, 7))

    assert due == []


# --- KL-5: gleiche Stunde fuer Morgen und Abend ----------------------------

def test_kl5_same_hour_for_morning_and_evening_yields_two_entries():
    """GIVEN ein Preset mit morning_time.hour == evening_time.hour == 9
    WHEN presets_due_for_hour bei hour=9 laeuft
    THEN enthaelt das Ergebnis ZWEI Eintraege: (preset, heute) und
    (preset, heute+1) — beide Mails gehen raus, keine Deduplizierung."""
    preset = _preset(
        morning_enabled=True, morning_time="09:00:00",
        evening_enabled=True, evening_time="09:45:00",
    )

    due = presets_due_for_hour([preset], {}, utc_moment(TODAY, 9))

    assert due == [(preset, TODAY, 0), (preset, TODAY + timedelta(days=1), 1)]


# --- KL-2: Minuten-Granularitaet wird ignoriert ---------------------------

def test_kl2_morning_time_minutes_are_ignored_for_due_check():
    """GIVEN ein Preset mit morning_time="07:45:00"
    WHEN presets_due_for_hour bei hour=7 laeuft
    THEN ist es trotz der 45-Minuten-Differenz faellig (nur volle Stunde
    zaehlt); resolve_preset_slots liefert dennoch die echte Minute (45)."""
    preset = _preset(
        morning_enabled=True, morning_time="07:45:00",
        evening_enabled=False, evening_time="18:00:00",
    )

    due = presets_due_for_hour([preset], {}, utc_moment(TODAY, 7))
    _, morning_time, _, _ = resolve_preset_slots(preset)

    assert due == [(preset, TODAY, 0)]
    assert morning_time.hour == 7
    assert morning_time.minute == 45


# --- Explizite Slot-Felder haben Vorrang vor dem Migrations-Fallback ------

def test_explicit_slot_fields_override_schedule_fallback():
    """GIVEN ein Preset mit schedule='daily' aber explizit gesetzten
    Slot-Feldern (Morgen aus, Abend an @20:00)
    WHEN presets_due_for_hour laeuft
    THEN gewinnt die explizite Konfiguration ueber den Fallback: nur der
    Abend-Slot ist faellig, der Morgen-Slot bleibt trotz schedule='daily'
    inaktiv."""
    preset = _preset(
        schedule="daily",
        morning_enabled=False, morning_time="06:00:00",
        evening_enabled=True, evening_time="20:00:00",
    )

    due_morning_hour = presets_due_for_hour([preset], {}, utc_moment(TODAY, 6))
    due_evening_hour = presets_due_for_hour([preset], {}, utc_moment(TODAY, 20))

    assert due_morning_hour == []
    assert due_evening_hour == [(preset, TODAY + timedelta(days=1), 1)]


# --- AC-11: Reine Funktion, keine Vermischung zwischen Nutzer-Listen ------

def test_ac11_two_user_preset_lists_evaluated_independently():
    """GIVEN zwei getrennte Preset-Listen zweier Nutzer mit unterschiedlichem
    Zeitplan zur selben Stunde
    WHEN presets_due_for_hour je Liste separat UND als kombinierte Liste
    aufgerufen wird
    THEN liefert die kombinierte Auswertung exakt die Summe der Einzel-
    Auswertungen — die Funktion ist pur je Aufruf, kein globaler State
    beeinflusst ein anderes Nutzer-Preset."""
    preset_user_a = _preset(
        id="preset-user-a",
        morning_enabled=True, morning_time="07:00:00",
        evening_enabled=False, evening_time="18:00:00",
    )
    preset_user_b = _preset(
        id="preset-user-b",
        morning_enabled=False, morning_time="07:00:00",
        evening_enabled=True, evening_time="07:00:00",
    )

    result_a = presets_due_for_hour([preset_user_a], {}, utc_moment(TODAY, 7))
    result_b = presets_due_for_hour([preset_user_b], {}, utc_moment(TODAY, 7))
    combined = presets_due_for_hour([preset_user_a, preset_user_b], {}, utc_moment(TODAY, 7))

    assert result_a == [(preset_user_a, TODAY, 0)]
    assert result_b == [(preset_user_b, TODAY + timedelta(days=1), 1)]
    assert combined == result_a + result_b


# --- Adversary-Fund F001: Betreff-Datum muss target_date widerspiegeln -----

def test_f001_subject_date_matches_evening_target_date_not_send_time():
    """GIVEN ein Abend-Versand mit target_date = morgen
    WHEN build_compare_preset_subject(name, target_date) aufgerufen wird
    THEN enthaelt der Betreff das Datum von target_date (morgen), NICHT das
    des Sende-Zeitpunkts (heute) — sonst widerspricht der Betreff dem
    Mail-Body ("Datum: morgen"). Deterministisch, ohne echten Mail-Versand."""
    tomorrow = TODAY + timedelta(days=1)

    subject = build_compare_preset_subject("Alpen vs Voralpen", tomorrow)

    assert tomorrow.strftime("%d.%m.%Y") in subject
    assert TODAY.strftime("%d.%m.%Y") not in subject


def test_f001_subject_date_matches_morning_target_date():
    """GIVEN ein Morgen-Versand mit target_date = heute
    WHEN build_compare_preset_subject(name, target_date) aufgerufen wird
    THEN enthaelt der Betreff das Datum von heute."""
    subject = build_compare_preset_subject("Alpen vs Voralpen", TODAY)

    assert TODAY.strftime("%d.%m.%Y") in subject


# --- Adversary-Fund F002: korruptes end_date bricht nicht den ganzen Lauf --

def test_f002_corrupt_end_date_skips_only_that_preset():
    """GIVEN eine Liste mit einem Preset mit korruptem end_date UND einem
    validen, an sich faelligen Preset
    WHEN presets_due_for_hour laeuft
    THEN wird das korrupte Preset uebersprungen (keine Exception nach aussen),
    das valide Preset bleibt trotzdem faellig."""
    corrupt_preset = _preset(
        id="preset-corrupt",
        morning_enabled=True, morning_time="07:00:00",
        evening_enabled=False, evening_time="18:00:00",
        end_date="not-a-date",
    )
    valid_preset = _preset(
        id="preset-valid",
        morning_enabled=True, morning_time="07:00:00",
        evening_enabled=False, evening_time="18:00:00",
    )

    due = presets_due_for_hour([corrupt_preset, valid_preset], {}, utc_moment(TODAY, 7))

    assert due == [(valid_preset, TODAY, 0)]


# --- Adversary-Fund F003 (#1661): Versatz kommt von hier, nicht von spaeter --

def test_f003_slot_versatz_und_zieldatum_stammen_aus_derselben_zeitabfrage():
    """GIVEN ein Preset mit aktivem Morgen- UND Abend-Slot zur selben Stunde
    WHEN `presets_due_for_hour` laeuft
    THEN traegt jeder Eintrag den Versatz gegen den Sammeltag (Morgen 0,
    Abend +1) UND es gilt `target_date == today + tage_ab_ortstag` — beide
    Formen stammen aus derselben, EINEN Zeitabfrage.

    Warum das hier gepinnt gehoert: `presets_due_for_hour` ist die einzige
    Stelle im ganzen Weg, die den Slot KENNT. Bis #1661 Runde 2 wurde der
    Versatz stattdessen spaeter im Schreibpfad als
    `(target_date - date.today()).days` rekonstruiert — aus einer zweiten
    Zeitabfrage zu einem anderen Realzeitpunkt. Fiel dazwischen Mitternacht,
    lag der Δ-Anker still einen Tag daneben (Adversary-Finding F003).

    Der Test faengt beide naheliegenden Verfaelschungen: Morgen-/Abend-Versatz
    vertauscht, und Versatz fest auf einen Wert verdrahtet.
    """
    preset = _preset(
        morning_enabled=True, morning_time="09:00:00",
        evening_enabled=True, evening_time="09:45:00",
    )

    due = presets_due_for_hour([preset], {}, utc_moment(TODAY, 9))

    versaetze = [eintrag.tage_ab_ortstag for eintrag in due]
    assert versaetze == [0, 1], (
        "Der Morgen-Slot briefed ueber den laufenden Tag (Versatz 0), der "
        f"Abend-Slot ueber den Folgetag (Versatz +1). Gefunden: {versaetze!r}"
    )
    for eintrag in due:
        assert eintrag.target_date == TODAY + timedelta(days=eintrag.tage_ab_ortstag), (
            "Zieldatum und Versatz muessen denselben Tag meinen — sonst "
            "beschreiben Mail-Betreff und Δ-Anker verschiedene Kalendertage. "
            f"Gefunden: target_date={eintrag.target_date}, "
            f"tage_ab_ortstag={eintrag.tage_ab_ortstag}, today={TODAY}"
        )
