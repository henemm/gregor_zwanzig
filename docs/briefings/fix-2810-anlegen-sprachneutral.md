---
spec_file: docs/specs/modules/fix_2810_anlegen_helfer_sprachneutral.md
spec_sha256: eb2b7ef6c9576cca5eb67fb786b2cd3072811d0b550947367f80b2ff499c64b6
spec_frozen_sha256: f4bf2087508db0d8a29cde0da3f9736c7357d71c117d1114da3c2d2255fcdbeb
---

# PO-Briefing: fix-2810-anlegen-sprachneutral

- **Spec:** docs/specs/modules/fix_2810_anlegen_helfer_sprachneutral.md
- **Issue:** #2810
- **Erstellt:** 2026-11-13

## Was gebaut wird

Das automatische Anlegen von Trip und Ortsvergleich lässt sich künftig auch mit englischer Oberfläche prüfen.

## Definition of Done

Trip und Vergleich lassen sich am Handy mit englischem und deutschem Konto anlegen, das Orte-Fenster schließt sich, Beschriftungen bleiben übersetzt.

## Wie geprüft wird

Echte Browser-Tests legen Vergleich und Trip in Englisch und Deutsch an; andere Tests mit deutscher Beschriftung bleiben unberührt.

## Kritische Anmerkungen

- Weitere Tests mit deutscher Schliessen-Beschriftung bleiben nur deutsch lauffähig; als Nebenbefund gemeldet, nicht Teil dieses Tickets.
- Desktop-Trip in Englisch ist nicht eigens getestet.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
