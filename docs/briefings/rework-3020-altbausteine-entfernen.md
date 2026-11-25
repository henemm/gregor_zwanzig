---
spec_file: docs/specs/modules/rework_3020_altbausteine_entfernen.md
spec_sha256: 830e7896eaef305ed38de99034fda62be702ebdf211e71e081c659f6eeea6555
spec_frozen_sha256: 8949fc20d5b5e18489ec5e841faa0d25b4168693536cccb30c421f950eda0d93
---

# PO-Briefing: rework-3020-altbausteine-entfernen

- **Spec:** docs/specs/modules/rework_3020_altbausteine_entfernen.md
- **Issue:** #3020
- **Erstellt:** 2026-11-25

## Was gebaut wird

Die alte, nirgends mehr sichtbare Wetter- und Versand-Oberfläche wird in vier einzeln auslieferbaren Schritten gelöscht, ohne dass Nutzer etwas bemerken.

## Definition of Done

Alle 54 alten Bausteine sind gelöscht, Trip- und Orte-Seiten sehen in Deutsch und Englisch auf Staging und Produktion unverändert aus.

## Wie geprüft wird

Elementlisten-Vergleich, bestehende Browser-Tests und Strukturwächter belegen Unverändertheit; umgestellte Tests bekommen eine Gegenprobe, Inhalt der vier Kanäle wird nicht berührt.

## Kritische Anmerkungen

- Das Limit von 250 Zeilen und fünf Dateien wird bewusst weit überschritten (fast nur Löschungen); Freigabe deckt das ab.
- Eine Änderung an einer geschützten Hook-Datei braucht in Schritt 3 voraussichtlich eine einmalige menschliche Freigabe.
- Rund 160 Tests werden gelöscht oder umgestellt; die Entscheidung je Test steht erst in einer Tabelle, die in Schritt 1 entsteht.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
