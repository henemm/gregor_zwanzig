---
spec_file: docs/specs/modules/fix_2231_slot_reparatur.md
spec_sha256: 8576dcaed53d3f6ac24da7914285fd7f9f6f8b61d5d5244a6719aea3b18591b6
---

# PO-Briefing: fix-2231-slot-reparatur

- **Spec:** docs/specs/modules/fix_2231_slot_reparatur.md
- **Issue:** #2231
- **Erstellt:** 2026-10-06

## Was gebaut wird

Eine beschädigte Briefing-Buchführungsdatei wird automatisch beiseitegelegt und neu aufgebaut, statt alle Briefings des Nutzers stillzulegen.

## Definition of Done

Bei beschädigter Datei laufen Briefings weiter, schon versendete kommen nicht doppelt, und die kaputte Datei bleibt unverändert erhalten.

## Wie geprüft wird

Tests mit echten Dateien belegen Reparatur, Doppelversand-Schutz und Nutzertrennung; echte Zustellung über Staging prüfen sie nicht.

## Kritische Anmerkungen

- Sind beide Dateien beschädigt, kann ein Briefing einmal doppelt rausgehen.
- Bei kaputtem Versandprotokoll entfällt ein hängengebliebenes Briefing für diesen Tag.
- Beiseitegelegte Dateien bleiben liegen; Hinweis nur als Log-Zeile.

## Freigabe-Frage

Darf eine beschädigte Buchführungsdatei automatisch ersetzt werden, obwohl in seltenen Fällen ein Briefing doppelt oder gar nicht ankommt?
