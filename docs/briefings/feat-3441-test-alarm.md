---
spec_file: docs/specs/modules/feat_3441_test_alarm.md
spec_sha256: c1595696f155cc62be27fcb6bd14af04fd200aaad522d286825135ee3f6bc854
spec_frozen_sha256: 08d49865e15338291412ca0fcd11601e003f990828279480eb1eec8fa25c3161
---

# PO-Briefing: feat-3441-test-alarm

- **Spec:** docs/specs/modules/feat_3441_test_alarm.md
- **Issue:** #3441
- **Erstellt:** 2026-11-27

## Was gebaut wird

Im Menü „Test schicken“ gibt es einen Test-Alarm, der einen Beispiel-Alarm mit echten Werten an alle Alarm-Kanäle schickt.

## Definition of Done

Test-Alarm erreicht in Trip und Orten jeden eingerichteten Alarm-Kanal mit [TEST]-Kennzeichnung, nennt das Ergebnis je Kanal und verändert keinen echten Alarm-Zustand.

## Wie geprüft wird

Automatische Tests und echter Versand per E-Mail und Telegram auf Staging; SMS nur simuliert, weil echte Kosten entstehen.

## Kritische Anmerkungen

- Anfrage: Test-Alarm ersetzt die Alarm-Vorschau. Spec lässt Vorschau vorerst stehen (Folge-Issue #3458); beide laufen parallel.
- Test-SMS verbrauchen echtes Tageskontingent und kosten Geld; echter SMS-Versand wird nie geprüft.

## Freigabe-Frage

Darf die Alarm-Vorschau bis zum Folge-Issue #3458 parallel zum neuen Test-Alarm bestehen bleiben?

## Ampel

Ampel: rot
