---
spec_file: docs/specs/modules/feat_3440_test_schicken_menue.md
spec_sha256: be648ef98ea5f556e5618e075aa00b9d9efcc13cc28713536f65d92a690b643e
spec_frozen_sha256: db03bda64cbf7f079b9a1a2cf7090dbc2109c457cec5b24f21b861f42ec59cdc
---

# PO-Briefing: feat-3440-test-schicken-menue

- **Spec:** docs/specs/modules/feat_3440_test_schicken_menue.md
- **Issue:** #3440
- **Erstellt:** 2026-11-27

## Was gebaut wird

Der Knopf „Test schicken“ öffnet ein Menü, mit dem man ein Test-Briefing gezielt an einen Kanal oder alle schickt.

## Definition of Done

Trip- und Orte-Ansicht öffnen das Menü; ein Klick auf einen Kanal schickt dort genau ein Test-Briefing mit Rückmeldung.

## Wie geprüft wird

Tests prüfen alle Anforderungen; echt versendet wird nur E-Mail und Telegram, SMS und Premium-SMS nur ohne Sendung.

## Kritische Anmerkungen

- Ziele weichen vom Ticket ab (Adresse statt Empfängerzahl, „verbunden“ statt Telegram-Name); durch PO-Entscheidung #3202 gedeckt.
- Zusatz: unbestätigte E-Mail ist gesperrt, wie bisher im Dialog.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
