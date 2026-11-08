---
spec_file: docs/specs/modules/fix_2815_delete_fremd_404.md
spec_sha256: c3b2212cbbd53c51a13181c0638a54b73d2c9b84f7d6e4f4106004285b79f545
spec_frozen_sha256: 6e9e042f4bdc50e2562222a2212335e912e4c2f2218850fe80a1973e9b23352f
---

# PO-Briefing: fix-2815-delete-fremd-404

- **Spec:** docs/specs/modules/fix_2815_delete_fremd_404.md
- **Issue:** #2815
- **Erstellt:** 2026-11-07

## Was gebaut wird

Wer eine fremde oder nicht vorhandene Trip-, Orts- oder Gruppen-ID löscht, bekommt „nicht gefunden“ statt stillem Erfolg.

## Definition of Done

Auf Staging liefert das Löschen eines fremden Trips durch einen zweiten Nutzer „nicht gefunden“, der Trip des ersten Nutzers bleibt unverändert erhalten.

## Wie geprüft wird

Automatische Tests mit zwei Nutzern je Löschweg belegen alle Anforderungen; die Oberfläche selbst wird nicht angepasst oder getestet.

## Kritische Anmerkungen

- Zusatz: Das Ticket nennt nur Trips; die Spec ändert auch Orte und Gruppen. Das hat bisher niemand entschieden.
- Zweiter Browser-Tab: Löschen eines schon gelöschten Trips zeigt künftig einen Fehler statt stillem Erfolg; bewusst nicht behoben.

## Freigabe-Frage

Soll die Änderung wie in der Spec auch für Orte und Gruppen gelten, obwohl das Ticket nur Trips nennt?

## Ampel

Ampel: rot
