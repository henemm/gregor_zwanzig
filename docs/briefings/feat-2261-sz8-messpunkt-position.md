---
spec_file: docs/specs/modules/feat_2261_sz8_messpunkt_position.md
spec_sha256: 23db8c269225de085b99fd4965577b675eab416a886ca1cec7bfab38b7d45f53
---

# PO-Briefing: Radar-Alarm misst dort, wo der Nutzer sein wird (feat-2261-sz8-messpunkt-position)

- **Spec:** docs/specs/modules/feat_2261_sz8_messpunkt_position.md
- **Issue:** #2261
- **Erstellt:** 2026-10-02

## Was gebaut wird

Ein Prüf-Test beweist, dass der Radar-Alarm dort misst, wo der Nutzer laut Plan zum Regenzeitpunkt sein wird.

## Definition of Done

Der Test ist grün, und fünf gezielte Verfälschungen des Codes machen jeweils den passenden Test rot; das Restrisiko hat Issue #2480.

## Wie geprüft wird

Der echte Radar-Alarm läuft mit normaler und verschobener Etappe; verglichen werden abgefragte Koordinaten und Höhe, nicht die Wirkung auf echte Nutzer.

## Kritische Anmerkungen

- Test ist voraussichtlich sofort grün; seinen Wert beweisen erst die fünf Verfälschungen, einschliesslich der Obergrenze der Messpunkte.
- Ein Hilfsbaustein wird aus einer anderen Testdatei verschoben; unveränderter Lauf soll gleiches Verhalten belegen.

## Freigabe-Frage

Gibst du diese reine Nachweis-Scheibe ohne Änderung am Produktivverhalten frei?
