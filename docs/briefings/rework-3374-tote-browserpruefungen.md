---
spec_file: docs/specs/modules/rework_3374_tote_browserpruefungen.md
spec_sha256: e2237f8e51c1bb1cb2f39b4d78bd4b91bce97d076b4e3fc9da802716d36fd9ee
spec_frozen_sha256: ffbf72416309b06fac1203c3d2feca07bf898e66e55cb6389792e78eff38cbc9
---

# PO-Briefing: rework-3374-tote-browserpruefungen

- **Spec:** docs/specs/modules/rework_3374_tote_browserpruefungen.md
- **Issue:** #3374
- **Erstellt:** 2026-11-26

## Was gebaut wird

Veraltete Browser-Prüfungen des alten Editors werden gelöscht; noch gültige Zusicherungen laufen künftig als Prüfungen der heutigen Oberfläche.

## Definition of Done

Acht tote Prüfdateien sind weg, zehn noch gültige Zusicherungen laufen grün in der Automatik, und die Produktion bleibt unverändert.

## Wie geprüft wird

Ein Löschnachweis-Test und drei Wiederholungsläufe der erweiterten Browser-Prüfungen gegen den echten Stack; Produktverhalten wird nicht neu getestet.

## Kritische Anmerkungen

- „21 statt 9 Zeilen“ ist kein Fehler, sondern gewollt (Erbe der Grundauswahl); keine Code-Änderung.
- Der Katalog-Fehlerfall wird im Test simuliert, nicht am echten System erzeugt.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
