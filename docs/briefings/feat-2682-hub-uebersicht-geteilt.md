---
spec_file: docs/specs/modules/feat_2682_hub_uebersicht_geteilt.md
spec_sha256: 1ae76bd3c5441de4e086f86c6d88d2ea5330d61ce89d168c2ac1b0b8ddc0c07c
spec_frozen_sha256: 7c642e7cf984f1558891488905bd73e3c1cf9701dae55a91339294e7ad1d0187
---

# PO-Briefing: feat-2682-hub-uebersicht-geteilt

- **Spec:** docs/specs/modules/feat_2682_hub_uebersicht_geteilt.md
- **Issue:** #2682
- **Erstellt:** 2026-11-01

## Was gebaut wird

Trip und Ortsvergleich bekommen dieselbe Übersicht mit Kennzahlen-Leiste, Versand-Karte und Versand-Historie, statt zweimal getrennt gebaut zu sein.

## Definition of Done

In der Trip-Übersicht erscheinen Kennzahlen und Versand-Karte mit echten Werten, die Vergleichs-Übersicht sieht unverändert aus, und beide nutzen denselben Baustein.

## Wie geprüft wird

Vergleich vorher und nachher Bild für Bild verglichen, Trip per Staging-Test mit zwei Nutzern; Optik und Wortlaut am Handy bleiben Augenprüfung.

## Kritische Anmerkungen

- Die Karte „Alerts (letzte 7 Tage)“ im Trip entfällt ersatzlos, weil sie nur Festtext zeigt; das verlangte das Ticket nicht.
- „Zuletzt raus“ beim Trip zählt Test-Versand nicht mit; Fehlversuche fehlen, weil der Log sie nicht führt.
- Im Vergleich ändert sich die Orte-Zahl bei gelöschten Orten bewusst auf die auffindbaren Orte.

## Freigabe-Frage

Darf die Alerts-Karte der Trip-Übersicht ersatzlos entfallen, da sie nur einen Festtext ohne Datenquelle zeigt?

## Ampel

Ampel: rot
