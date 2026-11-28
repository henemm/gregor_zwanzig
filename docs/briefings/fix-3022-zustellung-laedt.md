---
spec_file: docs/specs/modules/fix_3022_zustellung_laedt.md
spec_sha256: 56833db037c1bb20daa65c5d225a4fe83aca98d1cb3881a81ce8da97c52ebc17
spec_frozen_sha256: 0dfba4c74981cd74c84290224caff01dd728a710af26d8e1f4613f0693ec40dc
---

# PO-Briefing: fix-3022-zustellung-laedt

- **Spec:** docs/specs/modules/fix_3022_zustellung_laedt.md
- **Issue:** #3022
- **Erstellt:** 2026-11-28

## Was gebaut wird

Im Orts-Vergleich zeigt der Reiter Zustellung sofort alle Bereiche, auch wenn die Metrik-Liste noch lädt, wie beim Trip.

## Definition of Done

Bei hängender Metrik-Liste zeigen Zustellung und Wetter ihre Inhalte, und der Abgleich auf Staging meldet für beide Zustände keine Abweichung.

## Wie geprüft wird

Tests mit absichtlich nie ladender Metrik-Liste belegen Anzeige und Speicherverhalten; Staging-Abgleich prüft zwei Konten, getestet wird nur Anzeige, nicht Datenstände.

## Kritische Anmerkungen

- Zusatz zum Ticket: Auch der Reiter Wetter wird behoben; drei zusätzliche Einträge der Besitzerliste entfallen (62 statt 59).
- Aufräumen des nun ungenutzten Hintergrundcodes ist ausdrücklich ausgelagert (Folge-Issue #3495).

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
