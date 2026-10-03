---
spec_file: docs/specs/modules/fix_2215_unsaved_input_marker.md
spec_sha256: 003a629ac39dd6bd1542901b4993a8af9dc2c537abec98a1b9acd962f2870be4
---

# PO-Briefing: fix-2215-debounce-setdirty

- **Spec:** docs/specs/modules/fix_2215_unsaved_input_marker.md
- **Issue:** #2215
- **Erstellt:** 2026-10-03

## Was gebaut wird

Folgt auf eine gültige Eingabe ein ungültiger Zwischenstand, zeigt der Speicher-Chip nie fälschlich „Gespeichert", sondern bleibt auf „Nicht gespeichert".

## Definition of Done

In Trip und Ortsvergleich bleibt der Chip bei ungültiger Folgeeingabe auf „Nicht gespeichert", der letzte gültige Stand ist gesichert, danach zeigt er wieder „Gespeichert".

## Wie geprüft wird

Tests spielen den Ablauf mit Zeitablauf durch und prüfen die Anzeige je Editor; echter Browser und Mobildarstellung werden nicht gemessen.

## Kritische Anmerkungen

- Abweichung vom Ticket-Titel: Der vorgemerkte Save wird nicht abgebrochen, sondern läuft weiter, damit nichts verloren geht.
- Ein schon laufender Speichervorgang lässt sich nicht zurücknehmen; nur die Anzeige bleibt ehrlich.

## Freigabe-Frage

Ist es richtig, dass der letzte gültige Stand weiter gespeichert wird und nur die Anzeige „Nicht gespeichert" bleibt?
