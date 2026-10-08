---
spec_file: docs/specs/modules/fix_2124_versand_nginx_timeout.md
spec_sha256: 3a7a0f0e3cd6e0e77fd731886d4a718b1c19e78641600c6a89dd87cfe66766cf
---

# PO-Briefing: fix-2124-versand-nginx-timeout

- **Spec:** docs/specs/modules/fix_2124_versand_nginx_timeout.md
- **Issue:** #2124
- **Erstellt:** 2026-10-07

## Was gebaut wird

Trip-Versand zeigt bei Laufzeit über 60 Sekunden kein falsches „fehlgeschlagen" mehr und löst keinen versehentlichen zweiten Versand aus.

## Definition of Done

Ein Versand über 60 Sekunden auf Staging endet mit Erfolgsmeldung, und genau eine Mail kommt an.

## Wie geprüft wird

Tests prüfen Zeitgrenzen, Sperre und Meldungstexte; ob nginx wirklich wartet, beweist nur ein Staging-Versand.

## Kritische Anmerkungen

- Asynchroner Versand mit Statusanzeige (Issue-Vorschlag) abgelehnt; bei „Ergebnis unklar" erfährt der Nutzer den Ausgang nicht.
- Doppelversand vom 30.08. ist nicht belegt; Fix schützt nur vor Nachdrücken während des Laufs.
- Staging-Nachweis ist „nicht messbar", wenn der Versand unter 60 Sekunden bleibt.

## Freigabe-Frage

Genügt Ihnen synchroner Versand mit Meldung „Ergebnis unklar" statt asynchronem Versand mit Statusanzeige?
