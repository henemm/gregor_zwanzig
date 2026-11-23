---
spec_file: docs/specs/modules/fix_3283_was_steht_wo_optik.md
spec_sha256: 3ef745663061e72c48ca106df6feb1c7461c666485e088f4c5e46a24a9952faf
spec_frozen_sha256: 735dfad5177c6e3a98838680281c9f9af54f9eef194712048278b849f77b97e0
---

# PO-Briefing: fix-3283-wsw-optik

- **Spec:** docs/specs/modules/fix_3283_was_steht_wo_optik.md
- **Issue:** #3283
- **Erstellt:** 2026-11-23

## Was gebaut wird

Die Karte „Was steht wo“ wird an das freigegebene Soll-Bild angeglichen: nichts abgeschnitten, lesbare Symbole, saubere Legende.

## Definition of Done

Die Bildprüfung für Trip, drei Orte und einen Ort in Deutsch und Englisch meldet keinen offenen Befund, der Text-Abgleich bleibt grün.

## Wie geprüft wird

Automatische Tests prüfen Berechnung, Telegram-Ausgabe und gerenderte Karte; die Bildprüfung auf Staging belegt die Optik, nicht jede Pixelkleinigkeit.

## Kritische Anmerkungen

- Telegram-Nachrichten ändern sich real: Gewitter und Gefühlte Temperatur erscheinen künftig, gemäß bereits entschiedener Zählregel (achte Metrik).
- Bei Befund 2 wurde die Karte angeglichen, nicht das Soll-Bild; vom Ticket als Alternative zugelassen.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
