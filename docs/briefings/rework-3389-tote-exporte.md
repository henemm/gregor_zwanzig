---
spec_file: docs/specs/modules/rework_3389_tote_exporte.md
spec_sha256: 2e4a7d5256b7bb39747ff32fd2a8f31c2be9f35a8282f42ade92a4035aab002f
spec_frozen_sha256: cd87cd7866ab707aed1403f9695f8b23f6e627aba4a6e1501e03de4a5d20052d
---

# PO-Briefing: rework-3389-tote-exporte

- **Spec:** docs/specs/modules/rework_3389_tote_exporte.md
- **Issue:** #3389
- **Erstellt:** 2026-11-26

## Was gebaut wird

Ungenutzte alte Speicherlogik des Ortsvergleichs wird samt ihrer Tests entfernt; für Nutzer ändert sich nichts Sichtbares.

## Definition of Done

Die 21 ungenutzten Funktionen und ihre Tests sind gelöscht, alle verbleibenden Prüfungen und der Build laufen grün, die Oberfläche bleibt unverändert.

## Wie geprüft wird

Ein neuer Wächter belegt die Löschung, die verbleibenden Tests prüfen das Laden gespeicherter Werte; Browser-Prüfungen sind bewusst nicht Teil davon.

## Kritische Anmerkungen

- Rund 53 Dateien betroffen, weit über dem üblichen Umfang; die Spec begründet das als unteilbar.
- Einige Prüfungen wandern zum aktuellen Speicherer; wenige Randfälle des entfernten Speicherers haben danach kein Gegenstück, dokumentiert.

## Freigabe-Frage

Keine – Ampel gruen.

## Ampel

Ampel: gruen
