---
spec_file: docs/specs/modules/fix_2794_s3a_teil4b_befunde.md
spec_sha256: 47958b8ff33ea1af45ba44815c8257a8d51ec6d831357746d2e15008a3387bb9
spec_frozen_sha256: 28e9651238c22fea626791c5a0b43c5d9f405c4dac73e37768d335d8d98d0423
---

# PO-Briefing: fix-2794-s3a-teil4b-befunde

- **Spec:** docs/specs/modules/fix_2794_s3a_teil4b_befunde.md
- **Issue:** #2794
- **Erstellt:** 2026-11-12

## Was gebaut wird

Reiter heißt „Etappen“, Handy-Leiste passt vollständig, Übersichtskarten füllen die Breite, Wetter-Karte zählt richtig, Alarm-Titel ist deutsch.

## Definition of Done

Staging zeigt alle fünf Korrekturen, und Soll/Ist-Bilder gegen das Mockup liegen dir für Trip und Orts-Vergleich, Desktop und Handy vor.

## Wie geprüft wird

Automatische Tests und Messung auf Staging belegen Texte, Zahlen und Layout; der Bildvergleich zum Mockup bleibt manuelle Abnahme.

## Kritische Anmerkungen

- Startseiten-Checkliste wertet Wetter ohne gespeicherte Metrikliste als erledigt; bewusste Annäherung, kann eine fehlende Auswahl verdecken.
- Handy-Leiste wird erst nach der Änderung gemessen; passt sie nicht, werden Abstände verkleinert, Wischen bleibt.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
