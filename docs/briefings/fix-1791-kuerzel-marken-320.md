---
spec_file: docs/specs/modules/fix_1791_kuerzel_marken_320px.md
spec_sha256: 5d93450cb1182ecdd4cbcc333e77fa9eb38efea6a3e9ff323481bd4fdcd4297d
spec_frozen_sha256: 41e096cafac2031745a280c028fe3355d3f5f82bb76d7489174c1b7d0d950f8d
---

# PO-Briefing: fix-1791-kuerzel-marken-320

- **Spec:** docs/specs/modules/fix_1791_kuerzel_marken_320px.md
- **Issue:** #1791
- **Erstellt:** 2026-10-18

## Was gebaut wird

Auf schmalen Handys (320 Pixel) zeigt die Reihenfolge-Liste Kürzel-Marken wieder vollständig, weil die Bedienknöpfe unter den Namen rutschen.

## Definition of Done

Bei 320 Pixel Breite sind in Trip und Ortsvergleich alle Marken ganz lesbar, nichts überlagert sie, ab 900 Pixel sieht alles aus wie bisher.

## Wie geprüft wird

Ein Browsertest gegen Staging misst die Marken bei vierzehn Fenstergrößen; er läuft nicht in der automatischen Ampel, nur von Hand.

## Kritische Anmerkungen

- "Von der Bottom-Nav verdeckt" wird nicht im Produkt behoben: laut Messung war es ein Testfehler, kein echter Fehler.
- Rückfallschutz fehlt: Der Browsertest läuft nicht in der CI-Ampel, ein späterer Rückfall fiele nicht automatisch auf.
- Zeilen werden unter 900 Pixel höher; ob das gut aussieht, ist ungeprüft (nur Screenshot-Sichtung geplant).

## Freigabe-Frage

Ist es für dich in Ordnung, dass Bedienknöpfe auf kleinen Handys unter den Namen rutschen und die Zeilen dadurch höher werden?
