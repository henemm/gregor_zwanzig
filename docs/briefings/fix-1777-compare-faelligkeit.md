---
spec_file: docs/specs/modules/fix_1777_compare_faelligkeit_und_idempotenz.md
spec_sha256: fa9ed20135bb717978c2d30111cec3b07153666e8e0d24ef8b7c5a08ecf5b321
spec_frozen_sha256: 0c4dbe763db35f901fe7ad303f7f8c398b6993c12ce5bf1cfc5492c2f361ce75
---

# PO-Briefing: fix-1777-compare-faelligkeit

- **Spec:** docs/specs/modules/fix_1777_compare_faelligkeit_und_idempotenz.md
- **Issue:** #1777
- **Erstellt:** 2026-11-01

## Was gebaut wird

Ortsvergleich-Briefings kommen auch nach Zeitumstellung oder ausgefallenem Stundenlauf genau einmal pro Tag bei den Empfängern an.

## Definition of Done

Vergleich auf 02:00 kommt am Frühjahrstag einmal an, am Herbsttag nicht doppelt, verpasste Läufe werden binnen drei Stunden nachgeholt.

## Wie geprüft wird

Automatische Tests mit simulierter Uhr decken jede Anforderung ab; echte Umstellungstage und Live-Versand werden nicht geprüft.

## Kritische Anmerkungen

- Zusätzlich: Bei Wetterausfall wird der Vergleich nun nachgeliefert statt auszufallen; im Ticket nicht entschieden.
- Anzeige „Nächstes Briefing“ und Alarm-Sperre ändern sich sichtbar; frühere Festlegung „kein Nachholfenster“ wird abgelöst.

## Freigabe-Frage

Soll ein Vergleich bei kurzem Wetterausfall automatisch nachgeliefert werden?

## Ampel

Ampel: rot
