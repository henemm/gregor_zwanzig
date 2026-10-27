---
spec_file: docs/specs/modules/rework_2276_s6d_wertebereiche.md
spec_sha256: f244a18a702d7f9e813428499d6b755d971432b02f106de1db692ffd946f281e
---

# PO-Briefing: refactor-2276-s6d-corridor-wertprops

- **Spec:** docs/specs/modules/rework_2276_s6d_wertebereiche.md
- **Issue:** #2276
- **Erstellt:** 2026-09-22

## Was gebaut wird

Die Wertebereiche-Fläche des Ortsvergleichs wird intern auf denselben Speicherweg wie bei der Tour umgestellt, ohne sichtbare Änderung.

## Definition of Done

Die Wertebereiche-Einstellungen im Ortsvergleich verhalten sich am Bildschirm und am Handy genau wie vorher, inklusive der Fehleranzeige bei ungültigen Eingaben.

## Wie geprüft wird

Automatisierte Prüfungen sichern die Umstellung strukturell ab; das sichtbare Verhalten im Browser wird nur bei der Auslieferung getestet, nicht bei jeder Änderung.

## Kritische Anmerkungen

- Die Prüfung gegen einen früher gefundenen schweren Fehler läuft nur beim Ausliefern, nicht bei jeder Code-Änderung — Regressionsrisiko.
- Freigabe schließt nur diese Teilscheibe ab — Versand-Tab und die endgültige Alt-Code-Entfernung folgen noch in späteren Schritten.

## Freigabe-Frage

Sollen wir diese Umstellung freigeben, obwohl die Fehler-Sicherung für ungültige Grenzen erst beim Ausliefern getestet wird?
