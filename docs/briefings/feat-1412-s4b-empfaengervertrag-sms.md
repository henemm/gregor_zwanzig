---
spec_file: docs/specs/modules/fix_1412_s4b_empfaengervertrag_sms.md
spec_sha256: b5ada6f05e9c185a856c027b56b62a85bb4dc4ac5913557a6a0cec22f4684e21
spec_frozen_sha256: b7aa9737f826b55e02c95425033b2455761d576b438cb8cd7fc55eea99a79669
---

# PO-Briefing: feat-1412-s4b-empfaengervertrag-sms

- **Spec:** docs/specs/modules/fix_1412_s4b_empfaengervertrag_sms.md
- **Issue:** #1412
- **Erstellt:** 2026-10-25

## Was gebaut wird

Textnachrichten (SMS und Premium-SMS) gehen nur noch an die jeweils bestätigte Nummer des Nutzers, sonst wird der Versand blockiert.

## Definition of Done

Mit bestätigter Nummer kommen Briefings, Alarme und Bestätigungscodes weiter an; ohne bestätigte Nummer oder bei fremder Nummer wird nichts versendet.

## Wie geprüft wird

Automatische Tests mit zwei Nutzern beweisen Blockade und Zustellung; echter Versand auf Staging bleibt offen.

## Kritische Anmerkungen

- Echter SMS-Versand auf Staging ungeklärt: Testsystem sendet nie echt. Blockade belegen nur automatische Tests.
- Format bestehender Nummern ungemessen; SMS-Nummern werden deshalb locker statt streng geprüft.
- Zusatz ungefragt: schließt Lücke, durch die ohne Nutzerprofil die Betreibernummer SMS erhalten konnte.

## Freigabe-Frage

Soll der SMS-Versand auf bestätigte Nummern beschränkt werden, obwohl ein übersehener Versandweg künftig verstummen könnte?
