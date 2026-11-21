---
spec_file: docs/specs/modules/feat_3251_abweichungszustand_vorlage.md
spec_sha256: a571864465944a31fee8e91dfd22e9ce79e0becd62209e58ba50dafdd82b8811
spec_frozen_sha256: d167c8d0286d3fc1aee2b02562773d333840b095954cb5f68841a850cdbb600f
---

# PO-Briefing: feat-3251-abweichungszustand-vorlage

- **Spec:** docs/specs/modules/feat_3251_abweichungszustand_vorlage.md
- **Issue:** #3251
- **Erstellt:** 2026-11-21

## Was gebaut wird

Die Prüfliste kennt künftig den Zustand "Vorlage mit Abweichung", sodass die Zurücksetzen-Zeile echt geprüft statt pauschal ausgenommen wird.

## Definition of Done

Der Abgleich meldet die Zurücksetzen-Zeile und "1 Abweichung" in Deutsch und Englisch als gefunden, und die pauschale Ausnahme ist gestrichen.

## Wie geprüft wird

Automatische Tests prüfen Prüfliste und Zuordnung, ein Abgleich auf Staging vorher/nachher das Live-Verhalten; die App selbst bleibt unverändert.

## Kritische Anmerkungen

- Ob die Zurücksetzen-Zeile live beim Prüf-Datensatz wirklich erscheint, ist noch ungemessen; die Spec sieht die Messung vor der Umsetzung vor.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
