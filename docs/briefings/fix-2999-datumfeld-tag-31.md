---
spec_file: docs/specs/modules/fix_2999_datumfeld_tag_31.md
spec_sha256: c2af2482c88dac0651dd9adea7fedebc3be9c125671e2407336f4e86e5a6eed5
spec_frozen_sha256: cfb3386babad3a7b910fc8922960e5deba40e8f25461dfdfe6509b1c06b667a7
---

# PO-Briefing: fix-2999-datumfeld-tag-31

- **Spec:** docs/specs/modules/fix_2999_datumfeld_tag_31.md
- **Issue:** #2999
- **Erstellt:** 2026-11-14

## Was gebaut wird

Ein vollständig getipptes Datum wie 31.03.2027 bleibt unverändert; ein nicht existierendes Datum wird gemeldet statt still verschoben.

## Definition of Done

In jedem Monat erscheint und speichert 31.03.2027 korrekt, 31.04.2027 zeigt "Dieses Datum gibt es nicht." und speichert nichts, Uhrzeitfeld unverändert.

## Wie geprüft wird

Automatische Tests und Browser-Tests mit eingefrorener Uhr (November, Februar) belegen alle Anforderungen; Pfeiltasten und Kalenderklick bleiben bewusst unverändert.

## Kritische Anmerkungen

- Pfeiltasten im Feld können Tage weiterhin im heutigen Monat begrenzen; bewusst nicht Teil dieses Fixes.
- Die Bibliothek wird nicht aktualisiert, sondern ein eigener Tipp-Schutz gebaut; Aktualisierung folgt als eigenes Ticket.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
