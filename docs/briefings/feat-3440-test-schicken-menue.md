---
spec_file: docs/specs/modules/feat_3440_test_schicken_menue.md
spec_sha256: f898e07be76a34a5a4c58780599a7f765322a48a0fafddc1c2ea9c6f02b31aab
spec_frozen_sha256: 6b8308c03bb4675ec94e541139e5d4024e98f2751b9f2d3798bf929aedc794f0
---

# PO-Briefing: feat-3440-test-schicken-menue

- **Spec:** docs/specs/modules/feat_3440_test_schicken_menue.md
- **Issue:** #3440
- **Erstellt:** 2026-11-27

## Was gebaut wird

„Test schicken“ öffnet in Trip und Orte ein Menü, mit dem man jeden Kanal einzeln oder alle testen kann.

## Definition of Done

Im Trip- und Orte-Hub zeigt das Menü vier Kanäle mit Ziel oder Sperrgrund, ein Klick schickt nur an den gewählten Kanal.

## Wie geprüft wird

Automatische Tests und Staging-Durchläufe, echter Versand nur per E-Mail und Telegram; SMS und Premium-SMS nur als Anzeige und Schnittstellentest.

## Kritische Anmerkungen

- Abweichung vom Mockup: E-Mail zeigt gekürzte Adresse statt „an 2 Empfänger“, Telegram „verbunden“ statt „@henning“; beruft sich auf Ihre Entscheidungen in #3202, deren Wortlaut ich nicht prüfen konnte.
- Zusatz: unbestätigte E-Mail-Adresse sperrt den E-Mail-Test; das gilt schon heute im Dialog.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
