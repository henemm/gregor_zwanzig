---
spec_file: docs/specs/modules/fix_2422_s5_ortsvergleich_kette.md
spec_sha256: 56695cef2c0f0e4e3ae418a127853eb7f036b4fc2a9cb187ffca112ac69eca99
---

# PO-Briefing: fix-2422-s5-ortsvergleich-kette

- **Spec:** docs/specs/modules/fix_2422_s5_ortsvergleich_kette.md
- **Issue:** #2422
- **Erstellt:** 2026-09-30

## Was gebaut wird

Im Ortsvergleich kommt jede Einstellung je Kanal im gesendeten Text an; Telegram-Kurzstil wirkt im Briefing, abgelaufene Vergleiche schweigen.

## Definition of Done

Telegram-Briefing im Kurzstil gleicht dem SMS-Text, abgelaufene Ortsvergleiche senden weder Briefing noch Alarm, alle neuen Tests sind grün.

## Wie geprüft wird

Automatische Tests folgen jeder Einstellung von der Datei bis zum aufgezeichneten Text je Kanal; echter Versand läuft nur auf Staging.

## Kritische Anmerkungen

- Speichern mit nur einem Kanal ersetzt die ganze Kanal-Metrik-Auswahl; wird nur festgehalten, nicht geändert.
- Bisherige Zusicherung, abgelaufene Vergleiche alarmierten weiter, entfällt; ein Bestandstest wird auf „stumm" umgestellt.
- Umfang: rund 1000 Zeilen Testcode, Größenlimit muss angehoben werden.

## Freigabe-Frage

Soll die Spec so umgesetzt werden, inklusive Telegram-Kurzstil-Fix und stummer abgelaufener Ortsvergleiche?
