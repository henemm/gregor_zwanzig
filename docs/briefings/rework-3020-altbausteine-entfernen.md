---
spec_file: docs/specs/modules/rework_3020_altbausteine_entfernen.md
spec_sha256: 94165fc15c3bfe54bd0beb39321f94e05d707aacfd7f6f67bd5328eb920d83f7
spec_frozen_sha256: 52e049ee1e902946efbd739459593aeb3a69db429b126581debddfe75e9e3412
---

# PO-Briefing: rework-3020-altbausteine-entfernen

- **Spec:** docs/specs/modules/rework_3020_altbausteine_entfernen.md
- **Issue:** #3020
- **Erstellt:** 2026-11-25

## Was gebaut wird

Verlorene Schutz-Prüfungen werden wiederhergestellt, dann 42 tote Alt-Dateien gelöscht; Nutzer bemerken keine Änderung.

## Definition of Done

Beide Schritte sind auf Produktion, alle 42 Dateien gelöscht, Trip- und Orte-Seiten in Deutsch und Englisch unverändert, Tests grün.

## Wie geprüft wird

Elementlisten-Vergleich vor und nach jedem Schritt, Gegenproben an wiederhergestellten Tests und Strukturwächter; Löschungen selbst beweisen kein Verhalten.

## Kritische Anmerkungen

- Limit von 250 Zeilen und fünf Dateien wird bewusst weit überschritten; die Freigabe deckt das ab.
- Testfolgen der Löschung sind nicht gemessen; wie viele Tests entfallen, zeigt erst die Probe-Löschung.
- Echte Fehler, die Schritt 1 findet, werden nur als eigene Tickets erfasst, nicht behoben.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
