---
spec_file: docs/specs/modules/store_dateimodi_default_acl.md
spec_sha256: 4b6b6bd1f4318f94e704a26eabcd71581411aa7759b0a0c28a5f8e0a468c9ada
spec_frozen_sha256: 8c694041af2deb2d005e1064c038a49754430445084cdd8d3a8084c60bded119
---

# PO-Briefing: fix-2624-store-modi-default-acl

- **Spec:** docs/specs/modules/store_dateimodi_default_acl.md
- **Issue:** #2624
- **Erstellt:** 2026-10-27

## Was gebaut wird

Neu angelegte Nutzerkonten bleiben für die Dienstgruppe beschreibbar, weil Ordner und Dateien künftig gruppenschreibbar entstehen.

## Definition of Done

Ein neu registriertes Staging-Konto ist für den Dienstbenutzer beschreibbar, der Datenrechte-Wächter meldet nichts, und auf Prod öffnet sich kein zusätzlicher Zugriff.

## Wie geprüft wird

Tests prüfen Rechte neu angelegter Dateien und Ordner bei strenger Umask; die echte Wirkung zeigt erst die Staging-Messung.

## Kritische Anmerkungen

- NEU gegenüber Erstfassung (AC-10): auch Python-Zustandsdateien bekommen 0660 statt 0600; zusätzlich zum Ticketumfang.
- Zugriffslisten-Test wird ohne passendes Dateisystem übersprungen; Staging-Abnahme kann „nicht messbar" enden.

## Freigabe-Frage

Soll die Rechte-Korrektur einschließlich der neu aufgenommenen Python-Zustandsdateien umgesetzt werden?
