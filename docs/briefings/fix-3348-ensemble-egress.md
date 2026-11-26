---
spec_file: docs/specs/modules/fix_3348_ensemble_egress.md
spec_sha256: adc654839754ccf6a0f5fdfcd2fc1f133551eec5bc56a2564f593b49234f02f5
spec_frozen_sha256: 9dc60fb1cdc347d13afa13d0c76f73c0ee9b95985bb29629f2b9966f9f9adb31
---

# PO-Briefing: fix-3348-ensemble-egress

- **Spec:** docs/specs/modules/fix_3348_ensemble_egress.md
- **Issue:** #3348
- **Erstellt:** 2026-11-26

## Was gebaut wird

Auf Staging erscheint die Großwetterlage in der Trip-Mail wieder, weil der bisher gesperrte Wetter-Datendienst freigegeben wird.

## Definition of Done

Staging-Mail zeigt die Großwetterlage bei eingeschaltetem Schalter und nicht bei ausgeschaltetem, und das Produktions-Log bleibt ohne Sperrmeldung.

## Wie geprüft wird

Automatische Tests belegen Freigabe und weiterhin gesperrte andere Dienste; die echte Mail auf Staging wird einmalig geprüft, nicht dauerhaft automatisch.

## Kritische Anmerkungen

- Die Mail-Prüfung auf Staging (An- und Aus-Fall) ist reine Abnahme, kein dauerhafter automatischer Test.
- Produktion war laut Spec nie betroffen; dort ändert sich nichts.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
