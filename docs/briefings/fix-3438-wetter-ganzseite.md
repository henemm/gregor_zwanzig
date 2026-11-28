---
spec_file: docs/specs/modules/fix_3438_wetter_ganzseite.md
spec_sha256: 9904c3abf2f7f617652a23e813a5cba10ca27e4d838ec65e37ba1a449244a260
spec_frozen_sha256: 27a56d1ade4dca705e13ac64101b25738cbf5501ca8ccf46920f72a7cf87fd10
---

# PO-Briefing: fix-3438-wetter-ganzseite

- **Spec:** docs/specs/modules/fix_3438_wetter_ganzseite.md
- **Issue:** #3438
- **Erstellt:** 2026-11-28

## Was gebaut wird

Die Ganzseite des Reiters Wetter wird mit dem Mockup abgeglichen: Chips, Kopf und Knopffarbe passen, Abweichungen sind begründet zugeordnet.

## Definition of Done

Der Bildvergleich von Trip, Orte und einem Ort zeigt keine unzugeordnete Abweichung mehr, und die Änderung ist in Produktion.

## Wie geprüft wird

Automatische Tests, Messung auf Staging und Bildvergleich belegen Chips, Kopf und Knopffarbe; Ziehgriffe und Ein-Ort-Zeile werden nur gemessen, nicht geändert.

## Kritische Anmerkungen

- Knopf bleibt dunkelbraun; stattdessen wird das Mockup angepasst (frühere Entscheidung, Lesbarkeit).
- Region-Stift wandert an die Oberzeile; Regionszeile unter dem Titel entfällt, Bearbeiten bleibt.
- Ziehgriffe und Ein-Ort-Zeile: Spec belegt keine Abweichung, nichts wird geändert.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
