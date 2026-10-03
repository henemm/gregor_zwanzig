---
spec_file: docs/specs/modules/fix_2215_unsaved_input_marker.md
spec_sha256: 7abcf0cd036f721dfcab84307d6d0f461ad048870e34580b218c23adf82e13b0
---

# PO-Briefing: fix-2215-debounce-setdirty

- **Spec:** docs/specs/modules/fix_2215_unsaved_input_marker.md
- **Issue:** #2215
- **Erstellt:** 2026-10-03

## Was gebaut wird

Der Speicher-Chip zeigt nie fälschlich „Gespeichert", solange im Trip oder Ortsvergleich ein ungültiger Zwischenstand auf dem Bildschirm steht.

## Definition of Done

In Trip und Ortsvergleich bleibt der Chip bei ungültiger Folgeeingabe auf „Nicht gespeichert", der letzte gültige Stand ist gesichert, danach zeigt er wieder „Gespeichert".

## Wie geprüft wird

Tests spielen den Ablauf mit Zeitablauf durch und prüfen die Anzeige je Editor; ein echter Browser wird nicht gemessen.

## Kritische Anmerkungen

- Neu: Ortsvergleich-Zweig (Desktop, Mobil) wurde nachgetragen; im Testplan steht dafür kein eigener benannter Test, nur allgemein AC-9.
- Abweichung vom Ticket: Vorgemerkter Save wird nicht abgebrochen, sondern läuft weiter, damit nichts verloren geht.

## Freigabe-Frage

Ist es richtig, dass der letzte gültige Stand weiter gespeichert wird und nur die Anzeige „Nicht gespeichert" bleibt?
