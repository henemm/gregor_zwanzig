---
spec_file: docs/specs/modules/feat_2261_sz8_messpunkt_position.md
spec_sha256: bddb5c8edbbb1581cf46c0ce840fe990d3664201782ba6c6cc0fe8d6f1249363
---

# PO-Briefing: Radar-Alarm misst dort, wo der Nutzer sein wird (feat-2261-sz8-messpunkt-position)

## Was gebaut wird

Ein Prüf-Test, kein neues Verhalten. Er beweist, dass der Radar-Alarm dort misst, wo der Nutzer laut Plan zum Regenzeitpunkt sein wird, und dass ein verschobener Wegpunkt den Messpunkt mitverschiebt. Produktivcode wird voraussichtlich nicht angefasst.

## Definition of Done

Der Test ist grün, und vier gezielte Verfälschungen des Codes machen jeweils den passenden Test rot. Zwei Doku-Nachträge zu #2017 stehen; das Restrisiko hat das eigene Issue #2480.

## Wie geprüft wird

Der echte Radar-Alarm läuft zweimal, mit normaler und verschobener Etappe. Verglichen werden die abgefragten Koordinaten und die Höhe.

## Was sich für dich sichtbar ändert

Nichts. Du bekommst nur Absicherung gegen ein stilles Zurückfallen auf den Etappenstart.

## Kritische Anmerkungen

1. Der Test ist voraussichtlich sofort grün; seinen Wert beweisen erst die Verfälschungen.
2. Ein Hilfsbaustein wird aus der #822-Testdatei verschoben; unveränderter Lauf belegt gleiches Verhalten.
