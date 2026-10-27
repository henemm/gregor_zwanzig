---
spec_file: docs/specs/modules/fix_2554_dwd_gewitterabruf_budget.md
spec_sha256: 28e48c371e2b0e50456133bcaa1c0b2370e5cac81cf30905fcf98d7ed760dcd3
---

# PO-Briefing: fix-2554-dwd-gewitterabruf-budget

- **Spec:** docs/specs/modules/fix_2554_dwd_gewitterabruf_budget.md
- **Issue:** #2554
- **Erstellt:** 2026-10-13

## Was gebaut wird

Gewitterdaten des DWD werden parallel geladen, damit Berichte auch bei langsamem DWD schnell kommen und mehr Gewitterstunden enthalten.

## Definition of Done

Bei künstlich verlangsamtem DWD enthält der Abruf mindestens doppelt so viele Gewitterstunden wie vorher, und das Gesundheitsjournal meldet erschöpftes Zeitbudget.

## Wie geprüft wird

Tests mit simuliertem langsamem DWD-Server belegen Tempo, Reihenfolge und Journal; die echte Störung vom 12.10. lässt sich nicht nachstellen.

## Kritische Anmerkungen

- Ursache vom 12.10. unbelegt und verschwunden; ob die Änderung die echte Störung entschärft, zeigt erst die nächste.
- Das 150-Sekunden-Limit bleibt; bei erneuter Störung dauern Berichte weiterhin bis zu 150 Sekunden länger.
- Abbruch nach 10 statt 30 Sekunden ohne Wiederholung: bei kurzen DWD-Aussetzern bleiben einzelne Gewitterwerte leer.

## Freigabe-Frage

Gibst du die parallele Ladung mit 10-Sekunden-Limit frei?
