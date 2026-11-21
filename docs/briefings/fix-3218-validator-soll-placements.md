---
spec_file: docs/specs/modules/fix_3218_validator_soll_placements.md
spec_sha256: 9f2d3ac9234e9959ac59d0838b517cc08b14a572fc91f55fb0f88965a6f9ba35
spec_frozen_sha256: 89fc6b3e7f34157b26e627afb59b3a2660b24f61721685935f23509933727293
---

# PO-Briefing: fix-3218-validator-soll-placements

- **Spec:** docs/specs/modules/fix_3218_validator_soll_placements.md
- **Issue:** #3218
- **Erstellt:** 2026-11-21

## Was gebaut wird

Der Mail-Prüfer erwartet Roh oder Einfach künftig nach der "Was steht wo"-Tabelle und meldet keine falschen Verstösse mehr.

## Definition of Done

Der Fall aus der Staging-Prüfung von #3156 läuft ohne Verstoss-Meldung durch, Bestandsfälle ohne Tabelle prüfen unverändert, die Dokumentation ist nachgezogen.

## Wie geprüft wird

Tests ohne Attrappen belegen jede Anforderung am erwarteten Ergebnis; nicht geprüft werden Auswahl und Reihenfolge der Größen sowie der Orte-Stundenverlauf.

## Kritische Anmerkungen

- Auswahl und Reihenfolge mit Tabelle bleiben ungeprüft (eigenes Ticket #3242); nach Altfeld-Entfernung kann dort derselbe Fehlalarm auftreten.
- Zusätzlich zum Ticket: verständliche Fehlermeldung bei falscher Orte-Hülle und Vererbung der Form bei abgeleiteten Größen.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
