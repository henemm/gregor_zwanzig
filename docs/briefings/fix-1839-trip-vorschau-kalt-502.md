---
spec_file: docs/specs/modules/fix_1839_trip_vorschau_kalt.md
spec_sha256: c62822e33662a82eea02ce66da62691e88fbbecf677baa3d4351790a46128741
spec_frozen_sha256: 6d13440a9fceac4cc48827ed87906df10afa6e33e7095bc66dd333b6dec6a6a4
---

# PO-Briefing: fix-1839-trip-vorschau-kalt-502

- **Spec:** docs/specs/modules/fix_1839_trip_vorschau_kalt.md
- **Issue:** #1839
- **Erstellt:** 2026-11-07

## Was gebaut wird

Alarm-Vorschau und SMS-Vorschau liefern auch bei kaltem Wetter-Cache ihr Ergebnis, mit Hinweis „wird berechnet“, statt Fehler.

## Definition of Done

Eine kalte Vorschau, die länger als 30 Sekunden rechnet, zeigt bis 120 Sekunden ihr Ergebnis statt Fehler 502.

## Wie geprüft wird

Automatische Tests belegen Zeitgrenzen, Gleichzeitigkeit und Nutzertrennung; die tatsächliche Kaltzeit wird nur auf Staging gemessen, nicht zugesagt.

## Kritische Anmerkungen

- Abweichung: Den Vorschau-Reiter gibt es nicht mehr; wirksam ist die Alarm-Vorschau, Aufwärmlauf-Rückbau entfällt, da nichts vorhanden.
- Alarm-Vorschau wartet künftig bis 120 Sekunden (Browser 130 statt 40); Vorwärmen wurde bewusst nicht gebaut.
- Kaltzeit ungemessen, Schätzung 45–75 Sekunden; Beschleunigung durch Gleichzeitigkeit wirkt nur im SMS-Messweg.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
