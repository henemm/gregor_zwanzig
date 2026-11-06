---
spec_file: docs/specs/bugfix/fix_2223_nachtfenster_ortszeit.md
spec_sha256: 296e2dd98a4c3d7967bf3b950ad69a9bfed6f875b623be8e8db0ca029957800f
spec_frozen_sha256: 294c37d1c819f0bf12bd545edad58b13f0748b9f3e72551bc80be51c0edfbebe
---

# PO-Briefing: fix-2223-nachtfenster-ortszeit

- **Spec:** docs/specs/bugfix/fix_2223_nachtfenster_ortszeit.md
- **Issue:** #2223
- **Erstellt:** 2026-11-06

## Was gebaut wird

Die Nachtprognose am Ziel endet um 06:00 Uhr Ortszeit statt nach UTC-Rechnung, was unnötige Wetterabfragen spart.

## Definition of Done

Bei Ankunft am Ortsabend umfasst die Nachtprognose etwa 10 statt 29 Stunden, in Europa endet sie um 06:00 Ortszeit, in Versand und Vorschau gleich.

## Wie geprüft wird

Automatische Tests zählen die angefragten Stunden für westliche Zone, Mallorca/Korsika, Sommerzeit-Umstellung und unbekannte Zone; echte Provider-Kontingente werden nicht gemessen.

## Kritische Anmerkungen

- Ankunft nachts vor 06:00 Ortszeit behält bewusst das lange Fenster (ca. 30 Stunden); dokumentierte Einschränkung, nicht behoben.
- Im Hauptfall Europa ändert sich das Ende nur um 1–2 Stunden; die große Ersparnis betrifft nur westliche Zonen.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
