---
spec_file: docs/specs/modules/fix_2218_scheibe_c_observability.md
spec_sha256: f6467ae9ed7c55a77e8f0f7386feea3373de180c00a2b7214ca38c15f9b39d63
---

# PO-Briefing: fix-2218-scheibe-c-observability

- **Spec:** docs/specs/modules/fix_2218_scheibe_c_observability.md (v1.1)
- **Issue:** #2218
- **Erstellt:** 2026-10-08

## Was gebaut wird

Ausfälle und Mailversand werden nachweisbar: Mail-Kennung im Log, echter Scheduler-Status, ehrliche Journaleinträge, mehr Alarm-Sichtbarkeit.

## Definition of Done

Jede Mail trägt eine im Log wiederfindbare Kennung, der Scheduler meldet seinen echten Zustand, und alle sechs Lücken sind per Test belegt geschlossen.

## Wie geprüft wird

Automatische Tests prüfen alle Punkte; ob Resend die Mail-Kennung durchreicht, wird nur einmal auf Staging gemessen.

## Kritische Anmerkungen

- Mailtests nutzen eine Attrappe statt echtem Testserver: schwächerer Nachweis als freigegeben; echte Zustellung zeigt nur Staging.
- Umfang wuchs von etwa 75 auf 235 Zeilen; erhöhtes Zeilenlimit nötig, begründet.
- Fünf der Punkte sind auf Staging nicht messbar; dort zählt nur der Test.

## Freigabe-Frage

Geben Sie Version 1.1 frei, einschließlich des schwächeren Mailtests mit Attrappe statt echtem Testserver?
