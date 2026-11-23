---
spec_file: docs/specs/modules/feat_3304_was_steht_wo_vorschau.md
spec_sha256: 5865c6430323e4599d22a3c95aa9efc3c7dd83b3cbc46612b2b87cd94b010655
spec_frozen_sha256: a8612a7fc1c47156ca34b77416a755908c3c575e1e534b60358ac12b022ef82b
---

# PO-Briefing: feat-3041-tabelle-beim-anlegen

- **Spec:** docs/specs/modules/feat_3304_was_steht_wo_vorschau.md
- **Issue:** #3304 (Teil A von #3041)
- **Erstellt:** 2026-11-23

## Was gebaut wird

Die Tabelle „Was steht wo“ kann künftig auch für noch nicht gespeicherte Trips und Orte berechnet werden, sichtbar ändert sich nichts.

## Definition of Done

Vorschau liefert für Trip- und Orte-Entwurf dieselbe Tabelle wie ein gespeichertes Abo, speichert nichts, trennt Nutzer sauber und läuft nach Staging-Prüfung produktiv.

## Wie geprüft wird

Automatische Tests vergleichen Vorschau und gespeicherte Ansicht, prüfen zwei Nutzer, Fehlerfälle und unveränderte Daten; die Bildschirmanzeige selbst ist nicht Teil davon.

## Kritische Anmerkungen

- Kein Bildschirm ruft die Vorschau auf; sichtbar wird sie erst mit den Folgeteilen B bis D.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
