---
spec_file: docs/specs/modules/fix_2598_ortsvergleich_alarm_kopfzeile.md
spec_sha256: 1aec3e2220c562655e0ba67ca99fd142390e98890762781c1cf79c7e6e9bb753
spec_frozen_sha256: 586d7b7ec9e2c0161bdbbbc6938091740481df822ccb429d437b94b9158ea1ef
---

# PO-Briefing: fix-2598-ortsvergleich-alarm-kopfzeile

- **Spec:** docs/specs/modules/fix_2598_ortsvergleich_alarm_kopfzeile.md
- **Issue:** #2598
- **Erstellt:** 2026-11-09

## Was gebaut wird

Ortsvergleich-Alarme nennen den Ortsnamen nur noch einmal und zeigen statt „km 0–0“ den Ortsnamen.

## Definition of Done

Auf Staging zeigt ein echter Ortsvergleich-Alarm per Mail und Telegram keinen doppelten Ortsnamen und kein „km 0–0“; Trip-Alarme bleiben unverändert.

## Wie geprüft wird

Automatische Tests rendern alle Alarmarten in allen Kanälen, auf Deutsch und Englisch, und vergleichen Trip-Alarme Zeichen für Zeichen; echter Empfang bleibt Staging-Abnahme.

## Kritische Anmerkungen

- Umfang größer als im Ticket-Text: Radar-Alarm und Beginn-Verschiebung mit einem Ort sind dabei, laut Tech-Lead-Kommentar im Ticket.
- Der Alarmtext „Änderung unter“ bei Regel „über“ bleibt bewusst unverändert (eigenes Ticket #1895).

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
