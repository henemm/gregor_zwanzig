---
spec_file: docs/specs/modules/feat_3202_kanalzeile_mockup.md
spec_sha256: b443f825f35424a146555e9d0d3ba4a557e10ed4ca53f5dbe35c4bf9f3a304d5
spec_frozen_sha256: 62aa2ca5c2f8747d0cfb859c028a57b6ac0e777052177b177d9d18a2cd780b48
---

# PO-Briefing: feat-3202-kanalzeile-mockup

- **Spec:** docs/specs/modules/feat_3202_kanalzeile_mockup.md
- **Issue:** #3202
- **Erstellt:** 2026-11-21

## Was gebaut wird

Die Kanalzeile im Reiter Zustellung zeigt gekürzte Adresse und Nummer, Telegram nur als „verbunden“, nirgends eine Empfängerzahl.

## Definition of Done

Im Reiter Zustellung stehen auf Staging die gekürzten Werte, in Deutsch und Englisch, und der Ganzseitenvergleich meldet keine neue Abweichung.

## Wie geprüft wird

Unit-Tests für die Kürzung, Browser-Tests für Trip und Orts-Vergleich, Deutsch und Englisch, zwei Nutzer; die Bildprüfung gegen das Mockup bleibt manuell.

## Kritische Anmerkungen

- Ticket verlangt „+N Empfänger“ im Orts-Vergleich; die Spec streicht es überall (PO-Entscheidung 21.11., nur dort belegt).
- Das Mockup wird zusätzlich geändert (Telegram ohne Namen, E-Mail ohne Empfängerzusatz); Premium ohne Rückadresse steht nicht im Ticket.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
