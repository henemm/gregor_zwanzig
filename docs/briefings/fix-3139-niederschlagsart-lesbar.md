---
spec_file: docs/specs/modules/fix_3139_niederschlagsart_lesbar.md
spec_sha256: 86d2b282219005a75023d2f8c726a4a6fe475b3122a072a42bb93fc50a499501
spec_frozen_sha256: 577e2d7df4d0d288cdfd6d40ca2964cf69699c3da0b7d6a86602ecaac567b6da
---

# PO-Briefing: fix-3139-niederschlagsart-lesbar

- **Spec:** docs/specs/modules/fix_3139_niederschlagsart_lesbar.md
- **Issue:** #3139
- **Erstellt:** 2026-11-21

## Was gebaut wird

Trip-Briefings zeigen die Niederschlagsart als lesbares Wort in deiner Sprache statt als Programmtext.

## Definition of Done

Telegram und Trip-Mail zeigen auf Staging in Deutsch und Englisch Regen, Schnee, Mischniederschlag oder Eisregen statt „PrecipType.RAIN“; Orts-Vergleich und SMS bleiben unverändert.

## Wie geprüft wird

Automatische Tests rendern echte Briefings in beiden Sprachen, auch mit fehlenden oder unbekannten Werten; echte Zustellung wird per Staging-Mail geprüft.

## Kritische Anmerkungen

- Zusatz gegenüber dem Ticket: Der Fix gilt auch für Trip-Mails (HTML und Text), nicht nur Telegram; das entspricht der Kanal-Parität.
- Drei getrennte Wortquellen für Niederschlagsart bleiben bestehen; Aufräumen ist ausdrücklich ausgeklammert und wird separat geführt.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
