---
spec_file: docs/specs/modules/feat_3423_pruefkonto_zugang_e2e.md
spec_sha256: a9c5e4382ebdb87c19df5efa5836338abe44f50b81db5b36c90cfe9b9f2b6978
spec_frozen_sha256: 40e1270938fddc1003639ec17d168f1e01241ee1f368824af736522d0db395a1
---

# PO-Briefing: feat-3423-imac-seed-ids

- **Spec:** docs/specs/modules/feat_3423_pruefkonto_zugang_e2e.md
- **Issue:** #3423
- **Erstellt:** 2026-11-27

## Was gebaut wird

Browser-Prüfungen auf den Beispieldaten laufen vom iMac über den festen Prüfzugang ohne Handarbeit und ohne Rückfrage.

## Definition of Done

Vom iMac läuft die Test-Alarm-Prüfung grün durch, das Ergebnis wird gespeichert, und #3423 sowie #3402 sind mit Nachweis geschlossen.

## Wie geprüft wird

Kleine automatische Tests belegen Konto- und ID-Wahl samt Fehlermeldungen; ob der echte iMac-Lauf klappt, zeigt erst der Nachweislauf nach dem Deploy.

## Kritische Anmerkungen

- Keine — Spec deckt die Anfrage ab, jede Anforderung hat einen Test.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
