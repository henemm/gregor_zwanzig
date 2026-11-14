---
spec_file: docs/specs/fast/fix-2953-aufnahme-breite.md
spec_sha256: d6357a151a5c7e1a2f9c5e4d5deeb6aa344b1107c7ed3591e66728b5c11779f4
spec_frozen_sha256: c1591181e648a8bf99c6be20cb5e0d7a5e792decfa2a1e12bc24c0f35c2300bd
---

# PO-Briefing: fix-2953-aufnahme-breite

- **Spec:** docs/specs/fast/fix-2953-aufnahme-breite.md
- **Issue:** #2953
- **Erstellt:** 2026-11-14

## Was gebaut wird

Die Testbilder der Handy-Ansicht werden wieder korrekt 390 Pixel breit; für Nutzer ändert sich nichts.

## Definition of Done

Alle Handy-Testaufnahmen sind genau so breit wie der Bildschirm, und eine zu breite Aufnahme lässt den Testlauf sichtbar fehlschlagen.

## Wie geprüft wird

Eine neue Breitenprüfung vergleicht Bildbreite und Bildschirmbreite; sie belegt nur die Testbilder, nicht das Verhalten auf echten Handys.

## Kritische Anmerkungen

- Abweichung vom Ticket: Der lange Titel ist nicht die Ursache, und es gibt keinen Nutzerfehler. Es wird kein Produktcode geändert.
- Die Messung (kein seitliches Scrollen) liegt nur als Aussage in der Spec vor, nicht als dauerhafter Test.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
