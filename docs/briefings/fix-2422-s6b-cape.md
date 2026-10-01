---
spec_file: docs/specs/modules/fix_2422_s6b_cape_aus_roh_einfach.md
spec_sha256: 1caa103e7fa67fb9dd9f52ea3f99b87396838e1a68e96fb006089af13940ce57
---

# PO-Briefing: fix-2422-s6b-cape

- **Spec:** docs/specs/modules/fix_2422_s6b_cape_aus_roh_einfach.md
- **Issue:** #2422
- **Erstellt:** 2026-10-01

## Was gebaut wird

Die Gewitterenergie (CAPE) verschwindet aus der Roh/Einfach-Auswahl der SMS; nur die vier Wolken-Größen bleiben.

## Definition of Done

Der Roh/Einfach-Umschalter erscheint nur bei den vier Wolken-Größen, und SMS-Texte bestehender Trips bleiben unverändert.

## Wie geprüft wird

Tests belegen die Auswahlliste an der Schnittstelle und im Editor sowie unveränderte SMS-Texte; CAPE in Alarmen wird nicht angefasst.

## Kritische Anmerkungen

- Zusatz: Die Spec löscht auch die CAPE-Stufenlogik im Code; verlangt war nur das Streichen aus der Liste.
- Unschärfe: „Übrige Token byte-gleich zum Stand vor S6b" nutzt als Vergleich nur ein Staging-Beispiel.

## Freigabe-Frage

Soll CAPE aus der Roh/Einfach-Auswahl gestrichen werden, ohne dass sich für Nutzer sichtbar etwas ändert?
