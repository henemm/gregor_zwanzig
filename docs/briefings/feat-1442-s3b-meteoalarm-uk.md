---
spec_file: docs/specs/modules/feat_1442_s3b_meteoalarm_uk.md
spec_sha256: 335e8e13ee8e5e5c52c7f5edef5984bfdac458d1ba5a834d8426c7e040baf64b
spec_frozen_sha256: 631b460d16a017e90fbae74f72a76f3726b67faeaad9189394bd4d0a69a10332
---

# PO-Briefing: feat-1442-s3b-meteoalarm-uk

- **Spec:** docs/specs/modules/feat_1442_s3b_meteoalarm_uk.md
- **Issue:** #1442 (Teil S3b)
- **Erstellt:** 2026-10-31

## Was gebaut wird

Wanderer im Vereinigten Königreich (England, Schottland, Wales, Nordirland) erhalten amtliche Unwetterwarnungen auf allen vier Kanälen, in Trip und Ortsvergleich.

## Definition of Done

Orte im Vereinigten Königreich zeigen aktuelle Warnungen, bei Ausfall steht „nicht abrufbar"; auf Staging bestätigt.

## Wie geprüft wird

Tests mit echter Feed-Probe; Live-Test nur bei bestehender Warnung, sonst übersprungen.

## Abweichungen vom Ticket

- Abrufbudget entfällt (Feed kontingentfrei).
- Überlappungs-Teilziel nicht eigens geprüft.
- Belgien folgt separat.

## Kritische Anmerkungen

- Warntexte nur auf Englisch.
- Dünner Live-Beweis (3 Warnungen, Nebel-Fehler #2696).
- Irland, Kanalinseln, Isle of Man nicht abgedeckt.

## Freigabe-Frage

Vereinigtes Königreich mit englischen Texten und diesen Lücken anbinden?

## Ampel

Ampel: gelb
