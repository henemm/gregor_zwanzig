---
spec_file: docs/specs/modules/feat_3202_kanalzeile_mockup.md
spec_sha256: 750e926ede954035d3035821c40d027c804c3f009876e9f00382b77bda19b5fa
spec_frozen_sha256: 44656852f5f8858b80c46bde66de175ff899feebf35ba26d7996421c7c41dc97
---

# PO-Briefing: feat-3202-kanalzeile-mockup

- **Spec:** docs/specs/modules/feat_3202_kanalzeile_mockup.md
- **Issue:** #3202
- **Erstellt:** 2026-11-21

## Was gebaut wird

Die Kanalzeile im Reiter Zustellung zeigt gekürzte Adresse und Nummer, Telegram nur als „verbunden“, im Orts-Vergleich die Empfängerzahl.

## Definition of Done

Im Reiter Zustellung stehen auf Staging Kürzungen wie im Mockup, in Deutsch und Englisch, und der Ganzseitenvergleich meldet keine neue Abweichung.

## Wie geprüft wird

Unit-Tests für die Kürzung, Browser-Tests für Trip und Orts-Vergleich, Deutsch und Englisch, zwei Nutzer; die Bildprüfung gegen das Mockup bleibt manuell.

## Kritische Anmerkungen

- Premium-Zeile ohne Rückadresse im Normalzustand steht nicht in den Ticket-Entscheidungen; die Spec nennt es als PO-Entscheidung.
- Telegram-Name fehlt bewusst (deine Entscheidung); bleibt als dokumentierte Mockup-Abweichung.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
