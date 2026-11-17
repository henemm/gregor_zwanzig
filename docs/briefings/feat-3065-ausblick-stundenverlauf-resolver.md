---
spec_file: docs/specs/modules/feat_3065_ausblick_stundenverlauf_resolver.md
spec_sha256: a717c7f096eb23664798543bddc68f99ee69eae312c2d095e7a4e20494600430
spec_frozen_sha256: 0e6922fb9694498ca23446d1cc4fc79c6ea70a2725461dfa6995350f2a96b155
---

# PO-Briefing: feat-3065-ausblick-stundenverlauf-resolver

- **Spec:** docs/specs/modules/feat_3065_ausblick_stundenverlauf_resolver.md
- **Issue:** #3065
- **Erstellt:** 2026-11-16

## Was gebaut wird

Die gemeinsame Einstellungsquelle liefert zusätzlich Reihenfolge und Roh/Einfach des 3-Tages-Ausblicks sowie die Stundenverlauf-Spalten, ohne dass sich Mails ändern.

## Definition of Done

Alle zehn Kriterien sind durch grüne Tests belegt, und die zugestellte Staging-Mail ist in jedem Kanal zeichengleich zum bisherigen Stand.

## Wie geprüft wird

Vergleichstests gegen die bisherigen Regeln und der bestehende Prüfkatalog belegen Gleichheit; ob später Editor oder Mail diese Listen nutzen, wird nicht geprüft.

## Kritische Anmerkungen

- Stundenverlauf ohne Grundauswahl liefert keine Vorgabe-Spalten, sondern "Vorgabe des Renderers"; das Ticket nannte "inkl. Vorgabe-Spalten". Klärung folgt erst in #3058.
- Ein-/Ausschalter von Ausblick und Stundenverlauf sind bewusst nicht abgebildet.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
