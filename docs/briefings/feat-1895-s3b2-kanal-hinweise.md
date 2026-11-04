---
spec_file: docs/specs/modules/alert_metric_channels.md
spec_sha256: 5f91a09a26b93510d7ad685dd58acd79e3cad3576cc61d59455f817d49ed75ae
spec_frozen_sha256: 07b6feabdc77ebe2e8a104bc614d9b12fcf4f205996ddac731301b0d40f44772
---

# PO-Briefing: feat-1895-s3b2-kanal-hinweise

- **Spec:** docs/specs/modules/alert_metric_channels.md (Scheibe S3b2)
- **Issue:** #1895
- **Erstellt:** 2026-11-04

## Was gebaut wird

Bei eigener Kanalwahl zeigt der Alarm-Block Hinweise, wenn ein gewählter Kanal keinen Empfänger hat oder seine Schwelle zu hoch ist.

## Definition of Done

Auf Staging erscheinen die Hinweise in Handy- und Desktop-Ansicht lesbar, ohne dass Auswahl oder Speichern blockiert werden.

## Wie geprüft wird

Automatische Tests prüfen Bedingungen, zwei Nutzer, Sprachen und Speicherweg; die Mandantentrennung nur im Kern, weil Staging nur einen Login kennt.

## Kritische Anmerkungen

- Abweichung vom Ticket: Schwellen-Hinweis erscheint bei jeder Schwelle über „niedrig", nicht nur wenn sie die Dringlichkeit der Metrik-Stufe übersteigt; Hinweis kann also unnötig warnen.

## Freigabe-Frage

Genügt dir ein stufenunabhängiger Schwellen-Hinweis, oder soll er genau die Dringlichkeit der gewählten Metrik-Stufe berücksichtigen?

## Ampel

Ampel: rot
