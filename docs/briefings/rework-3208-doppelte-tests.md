---
spec_file: docs/specs/modules/rework_3208_doppelte_zusicherungen.md
spec_sha256: 20b4c1f7fd858aa595c192ce6abc8c4909afcb636e934e84731cb3f3938c4990
spec_frozen_sha256: 941df1d222431f15dc6cdade726efcdc5b2eceee2ba43cff02489549502ef949
---

# PO-Briefing: rework-3208-doppelte-tests

- **Spec:** docs/specs/modules/rework_3208_doppelte_zusicherungen.md
- **Issue:** #3208
- **Erstellt:** 2026-11-21

## Was gebaut wird

Doppelt vorhandene Prüfungen der Gehzeit-Berechnung und der SMS-Auswahl werden zusammengelegt, ohne dass ein Schutz verloren geht.

## Definition of Done

Fünf überflüssige Tests sind entfernt, jeder gezielt eingebaute Fehler wird weiterhin von einem Test erkannt, und alle Prüfungen laufen grün.

## Wie geprüft wird

Gezielt eingebaute Fehler werden vor und nach dem Umbau von Tests erkannt; am Produktverhalten ändert sich nichts, es wird nicht neu getestet.

## Kritische Anmerkungen

- Sprachkatalog, Kanal-Rendering und weitere Gruppen fehlen bewusst; Folge-Tickets 3263 bis 3267 existieren, die Ausbeute dieses Tickets ist klein.
- Erhalt der Issue-Bezüge wird nur per Sichtprüfung im Review kontrolliert, nicht automatisch.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
