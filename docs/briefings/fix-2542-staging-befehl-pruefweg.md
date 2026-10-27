---
spec_file: docs/specs/modules/fix_2542_staging_befehl_pruefweg.md
spec_sha256: e53cd24103958a8edf12aca9e7abb70f423f5a3fff53bd8ce41128a153be76a1
---

# PO-Briefing: fix-2542-staging-befehl-pruefweg

- **Spec:** docs/specs/modules/fix_2542_staging_befehl_pruefweg.md
- **Issue:** #2542
- **Erstellt:** 2026-10-09

## Was gebaut wird

Ein Prüfwerkzeug schickt Befehle wie status über den echten Mail-Eingang an Staging und wertet die Antwort aus.

## Definition of Done

Alle vier Prüfszenarien bestehen auf Staging, #2441 ist danach in Produktion ausgeliefert und der Selftest besteht.

## Wie geprüft wird

Deterministische Tests prüfen Adressbau, Relay-Sperre, Antwortauswertung und Aufräumen; der eigentliche Staging-Lauf geschieht nur in der Verifikation, nicht im Dauertest.

## Kritische Anmerkungen

- SMS, Premium-SMS, Telegram bleiben auf Staging ungeprüft; das Prod-Gate könnte weiter "unklar" statt "verifiziert" zeigen.
- Statt eines gesicherten Test-Eingangs wird der echte Zustellweg genutzt; Produktcode bleibt unverändert.
- Live-Prüfungen werden ohne Zugangsdaten übersprungen; Überspringen darf nicht als bestanden gelten.

## Freigabe-Frage

Genügt es dir, dass SMS, Premium-SMS und Telegram nur per Kern-Test und Handy-Nachtest geprüft werden, und gibst du frei?
