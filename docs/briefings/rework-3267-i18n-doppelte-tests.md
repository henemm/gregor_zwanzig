---
spec_file: docs/specs/modules/rework_3267_i18n_dubletten.md
spec_sha256: 6cafa8e5e4ebf07fd8e590fee6a6cd7ecde8224ffe2c7cb08ffb9f2c79f9bdf6
spec_frozen_sha256: 1cd4f4fbd17205f472c14cbeeb2c104cabf3349c2781c7b4dadedb94075f65d4
---

# PO-Briefing: rework-3267-i18n-doppelte-tests

- **Spec:** docs/specs/modules/rework_3267_i18n_dubletten.md
- **Issue:** #3267
- **Erstellt:** 2026-11-23

## Was gebaut wird

Zehn doppelte Prüfungen der Zweisprachigkeit werden aus der Testsammlung entfernt; für Nutzer ändert sich nichts.

## Definition of Done

Die zehn Dopplungen sind entfernt, kein Produktcode ist verändert, alle Prüfungen und alle sechs Automatik-Checks sind grün.

## Wie geprüft wird

Je Dopplung wird gezielt ein Fehler eingebaut und gezeigt, dass die bleibende Prüfung ihn weiterhin findet; Produktverhalten wird nicht neu getestet.

## Kritische Anmerkungen

- Eine zehnte Dopplung liegt in einer Datei außerhalb der im Ticket genannten Gruppe; sie ist identisch, also im Sinn des Tickets.
- Das Ticket schätzte rund 30 Dateien, tatsächlich sind es 23.
- Gelingt der Nachweis beim SMS-Längenfall nicht, bleibt dieser Test bestehen; das ist dokumentiert.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
