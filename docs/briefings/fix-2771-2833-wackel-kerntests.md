---
spec_file: docs/specs/modules/fix_2771_2833_wackel_kerntests.md
spec_sha256: b88e7a8af81177516276f569270b03a111bf4df00d1b8dff9f42d3d928e48238
spec_frozen_sha256: f5d2102da49fef7bfb0f061cfe7d9b2845d2e7b167eaa755866370da4f9e6c4e
---

# PO-Briefing: fix-2771-2833-wackel-kerntests

- **Spec:** docs/specs/modules/fix_2771_2833_wackel_kerntests.md
- **Issue:** #2771 und #2833
- **Erstellt:** 2026-11-06

## Was gebaut wird

Drei zufällig rot werdende Automatiktests werden stabilisiert, damit Änderungen nicht mehr grundlos an der Prüfung scheitern.

## Definition of Done

Die drei Tests laufen wiederholt grün, jeweils deutlich unter 30 Sekunden, ohne Änderung am Produktivcode, an der globalen Zeitgrenze oder Überspringen.

## Wie geprüft wird

Zwei neue Tests erzwingen die Fehlerauslöser; die Lockerung der Zeitgrenze wird nur durch eine gezielte Gegenprobe belegt, nicht durch einen eigenen Test.

## Kritische Anmerkungen

- Ursache bei #2833 weicht von der Vermutung im Ticket ab (Sende-Drossel statt Netzzugriff); Ergebnis erfüllt trotzdem die Erwartung.
- Ein zusätzlicher, ähnlicher Fristtest wird mitgelockert; elf weitere Zeitgrenzen bleiben bewusst unangetastet (Sammel-Ticket).

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
