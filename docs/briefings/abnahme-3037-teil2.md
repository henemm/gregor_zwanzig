---
spec_file: docs/specs/modules/feat_3037_abnahme_teil2.md
spec_sha256: aedacdb063d25232b4a5470fc6a3e745133a7d5620d1bf8a4f23838401fa731b
spec_frozen_sha256: 71c91a486dedd0ac0603ba23b8151d233b6ca260f220c55bca70e5f65484ae5f
---

# PO-Briefing: abnahme-3037-teil2

- **Spec:** docs/specs/modules/feat_3037_abnahme_teil2.md
- **Issue:** #3037
- **Erstellt:** 2026-11-26

## Was gebaut wird

Die Abnahme der Tabelle „Was steht wo“ wird abgeschlossen: Trip und Orte werden gegen echte Testmails und Bilder geprüft.

## Definition of Done

Alle Messläufe sind auf Staging grün oder jeder Befund hat ein Issue, Henning hat die Soll/Ist-Bilder erhalten, und #3037 ist geschlossen.

## Wie geprüft wird

Automatische Tests sichern das Prüfwerkzeug ab; Bilder, Mails und Elementliste werden live auf Staging gemessen, nicht in der Testautomatik.

## Kritische Anmerkungen

- Handy wird nur im 390-Pixel-Fenster geprüft; das echte Gerät beurteilt Henning anhand der Bilder.
- Mail-Nachweis nur für E-Mail; Englisch nur für den Trip, Orte nur Deutsch.
- Zusätzlich gebaut: Erweiterung des Mail-Prüfwerkzeugs, nötig für Konfigurationsabgleich und Ein-Ort-Fall.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
