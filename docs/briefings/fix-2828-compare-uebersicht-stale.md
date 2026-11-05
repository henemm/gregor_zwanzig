---
spec_file: docs/specs/bugfix/bug_2828_compare_uebersicht_stale.md
spec_sha256: 8711b1ec6628d0ef3aebbe2bc20502c1c2077b9d15f355a6a3db8b47c299ffb1
spec_frozen_sha256: c3410d916acc7cbe98249beda5e9753839b86c7093c0a4813ccb6294297f71ee
---

# PO-Briefing: fix-2828-compare-uebersicht-stale

- **Spec:** docs/specs/bugfix/bug_2828_compare_uebersicht_stale.md
- **Issue:** #2828
- **Erstellt:** 2026-11-05

## Was gebaut wird

Die Übersicht des Ortsvergleichs zeigt nach dem Speichern in einem anderen Reiter sofort den neuen Stand, ohne Neuladen.

## Definition of Done

Nach Ändern und Speichern von Orten, Wertebereichen oder Versand zeigt die Übersicht den neuen Wert ohne Seitenneuladen; Trip-Übersicht verhält sich unverändert.

## Wie geprüft wird

Ein Browser-Test ändert und speichert Werte und prüft die Übersicht; der Konfliktfall (412) ist womöglich nur per Quelltext-Prüfung belegt.

## Kritische Anmerkungen

- Das Ticket nennt einen „Vorschau"-Reiter; den gibt es nicht mehr, geprüft wird stattdessen die Übersicht.
- Bei Speicherkonflikt zeigt die Übersicht den eingegebenen, ungespeicherten Stand; die Spec nennt das bewusst entschieden.
- Alarm-Änderungen sind in der Vergleichs-Übersicht nicht sichtbar; die Prüfung dort ist schwach.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
