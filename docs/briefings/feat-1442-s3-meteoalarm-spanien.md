---
spec_file: docs/specs/modules/feat_1442_s3_meteoalarm_spanien.md
spec_sha256: 2529f88b27758d0d4a9598f92accda3e889fe8dd3470cba9834b3f4ab407f9dd
spec_frozen_sha256: bfbead76099f27e969d7ab6f33354a075a411a295e4dc07c7bd71108685c1297
---

# PO-Briefing: feat-1442-s3-meteoalarm-spanien

- **Spec:** docs/specs/modules/feat_1442_s3_meteoalarm_spanien.md
- **Issue:** #1442
- **Erstellt:** 2026-10-30

## Was gebaut wird

Wanderpunkte auf Mallorca und in Spanien erhalten amtliche Unwetterwarnungen des spanischen Wetterdienstes, auf allen vier Kanälen.

## Definition of Done

Eine aktive Warnung für Punkte am GR221 und an der Küste erscheint mit Stufe, Art und Zeitraum; Feed-Ausfall wird als „nicht abrufbar“ gemeldet.

## Wie geprüft wird

Netzfreie Tests gegen eine echte Feed-Aufzeichnung plus ein lokaler Live-Test; geprüft wird die Datenquelle, nicht der echte Mailversand.

## Kritische Anmerkungen

- Lizenz der Zonendatei ungeklärt; Spanien wird im bestehenden Antrag mit Finnland gebündelt.
- Warntexte erscheinen auf Englisch, nicht Deutsch, auch in Mallorca-Briefings.
- Drei Kriterien prüfen nur Datei- bzw. Quelltextinhalt, kein Verhalten.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
