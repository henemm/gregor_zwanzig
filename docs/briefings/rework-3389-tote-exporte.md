---
spec_file: docs/specs/modules/rework_3389_tote_exporte.md
spec_sha256: c3ff26549731f0a8bd6a2c8a6faf2dfb7ea4bedf72a35bba86c0fb496577e4c6
spec_frozen_sha256: 411d597793bc81766872644299260c953c50029659bbf3df9ff49ddfb6973a8b
---

# PO-Briefing: rework-3389-tote-exporte

- **Spec:** docs/specs/modules/rework_3389_tote_exporte.md
- **Issue:** #3389
- **Erstellt:** 2026-11-26

## Was gebaut wird

Ungenutzte Speicher-Altlogik des Ortsvergleichs wird samt ihrer Tests entfernt; für Nutzer ändert sich nichts Sichtbares.

## Definition of Done

Die 21 toten Funktionen und die zugehörigen Tests sind weg, alle übrigen Prüfungen und der Build laufen grün, die Oberfläche bleibt unverändert.

## Wie geprüft wird

Ein neuer Wächter beweist die Löschung, die verbleibenden Tests prüfen das Laden gespeicherter Werte; echte Browser-Prüfungen sind bewusst nicht Teil davon.

## Kritische Anmerkungen

- Rund 53 Dateien betroffen, weit über den üblichen Umfang; die Spec begründet das als unteilbar.
- Einige Prüfungen wandern vom entfernten Speicherer zum aktuellen; wenige Randfälle haben danach kein Gegenstück mehr, dokumentiert.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
