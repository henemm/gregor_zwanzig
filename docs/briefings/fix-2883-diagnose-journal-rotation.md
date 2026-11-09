---
spec_file: docs/specs/modules/fix_2883_diagnose_journal_rotation.md
spec_sha256: 53bd33889b5cc9e7f55ad7054109b7600dd0bdf78c6b4278acd47c771b1c204d
spec_frozen_sha256: 5831d169421850a8d56825bdf5bea5b3b5a8331a3ce0ab731dec44f3c0010bcb
---

# PO-Briefing: fix-2883-diagnose-journal-rotation

- **Spec:** docs/specs/modules/fix_2883_diagnose_journal_rotation.md
- **Issue:** #2883
- **Erstellt:** 2026-11-09

## Was gebaut wird

Zwei interne Diagnose-Protokolle wachsen nicht mehr unbegrenzt, sondern behalten nur die letzten Monate, ohne dass die Überwachung etwas verliert.

## Definition of Done

Auf Produktion ist die 22,5-MB-Altdatei archiviert, das Protokoll beginnt klein, und der Systemstatus meldet unveränderte Werte ohne Lesefehler oder Fehlalarm.

## Wie geprüft wird

Automatische Tests mit echten Dateien belegen Rotation, Parallelität und Statusberechnung; der Echtbetrieb auf Produktion wird nur manuell nach dem Deploy beobachtet.

## Kritische Anmerkungen

- Bewusste Zusatzänderung: Ein unlesbares Anreicherungs-Protokoll löst jetzt eine Fehlermeldung aus, bisher blieb es stumm.
- Rückblick schrumpft auf etwa vier Monate; die zweite Rotation verwirft die heutigen Altdaten endgültig.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
