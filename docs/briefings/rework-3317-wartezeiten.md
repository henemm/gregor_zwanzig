---
spec_file: docs/specs/modules/rework_3317_wartezeiten_tempo_s1.md
spec_sha256: 864bba100ea43032772518eef4b5bed36e960038bb49b4b9c9ede249849746bf
spec_frozen_sha256: f6b240c492f246eddd68cd1e4bb65ac9462eb3d47365afdc4f376deb68eeee01
---

# PO-Briefing: rework-3317-wartezeiten

- **Spec:** docs/specs/modules/rework_3317_wartezeiten_tempo_s1.md
- **Issue:** #3317
- **Erstellt:** 2026-11-24

## Was gebaut wird

Vier langsame Testdateien laufen schneller, ohne dass eine Prüfung schwächer wird.

## Definition of Done

Je Datei liegt ein Vorher/Nachher-Zeitvergleich vor, alle Tests bleiben grün, und jeder umgebaute Test fällt bei gezielter Verfälschung durch.

## Wie geprüft wird

Gezielte Verfälschungen müssen je umgebautem Test rot werden; der Zeitgewinn wird einmalig gemessen, nicht als Dauertest abgesichert.

## Kritische Anmerkungen

- Das Issue nennt fünf Dateien; die größte (Mail-Prüfungen, 200 s) fehlt und wandert in ein Folge-Issue.
- Ein DWD-Test bleibt lokal rot; ein anderer Test blockiert die Hauptlinie und wird separat geklärt.
- Zeitgewinne sind ungemessen; ohne messbaren Gewinn wird zurückgebaut.

## Freigabe-Frage

Darf die Mail-Prüfungs-Datei, größter Zeitfresser des Tickets, in ein Folge-Issue verschoben werden?

## Ampel

Ampel: rot
