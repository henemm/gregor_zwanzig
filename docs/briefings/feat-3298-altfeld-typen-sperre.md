---
spec_file: docs/specs/modules/feat_3298_altfeld_typen_sperre.md
spec_sha256: d0e7f654e3bab5446f6e8c42d014b9164baa415b4b3dafd9d545541d85eb248a
spec_frozen_sha256: f62a44e76822dcd9dc3e1c562095d2d46e8980bdd6bd86d8a734895aef1d34e8
---

# PO-Briefing: feat-3298-altfeld-typen-sperre

- **Spec:** docs/specs/modules/feat_3298_altfeld_typen_sperre.md
- **Issue:** #3298
- **Erstellt:** 2026-11-25

## Was gebaut wird

Alte, nicht mehr genutzte Feldnamen verschwinden aus der Oberfläche, und eine dauerhafte Prüfung verhindert, dass sie je zurückkehren.

## Definition of Done

Ortsvergleich und Trip lassen sich in Deutsch und Englisch unverändert bedienen und speichern, und die neue Sperre schlägt bei einem Altnamen an.

## Wie geprüft wird

Automatische Tests prüfen Speichern, Laden und die Sperre samt Selbstnachweis; das Aussehen im Browser prüft nur der Staging-Lauf, nicht die Einzeltests.

## Kritische Anmerkungen

- Zusatz: Zwei weitere Altfelder werden aus den Typen entfernt; sie stehen nicht im Ticket, gehören aber zum Aufräumen.
- Bestandsdaten behalten ihre Altfelder bis zum separaten Datenlauf (#3351); die Sperre erfasst camelCase-Reste nicht.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
