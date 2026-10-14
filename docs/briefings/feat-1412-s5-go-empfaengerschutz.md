---
spec_file: docs/specs/modules/fix_1412_s5_go_empfaengerschutz.md
spec_sha256: 9cd1f880a24490d43d750201731368ab2d2a247d8233c8b5ace3fe84af09b2a3
---

# PO-Briefing: feat-1412-s5-go-empfaengerschutz

- **Spec:** docs/specs/modules/fix_1412_s5_go_empfaengerschutz.md
- **Issue:** #1412
- **Erstellt:** 2026-10-14

## Was gebaut wird

Mails über das lokale Relay gehen nur noch an henemm.com-Adressen, Fremdadressen nur über Resend.

## Definition of Done

Beide Prüfläufe ohne Ausnahme grün; Staging-Passwort-Reset an Fremdadresse bleibt aus, an Wegwerf-Konto kommt an.

## Wie geprüft wird

Tests belegen Blocken und Durchlassen je Adressform; echter Versand wird nur auf Staging geprüft, nicht in Produktion.

## Kritische Anmerkungen

- Fall „Adresse plus Textrest ohne Komma“ wird geblockt statt erlaubt wie analysiert; ungequotete Namen fallen ebenfalls raus.
- Python-Guard wird strenger: kaputte Empfängerfelder blocken künftig auch Briefings und Alarme.
- Reset an Fremdadressen scheitert auf Staging still; nur das Log zeigt es.

## Freigabe-Frage

Darf der Empfängerschutz so verschärft werden, inklusive Blockade kaputter Empfängerfelder bei Briefings und Alarmen?
